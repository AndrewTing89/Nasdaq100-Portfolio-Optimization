"""
Lambda function for portfolio optimization using Mean-Variance, Risk Parity, and Black-Litterman models.
This function reads processed stock data from S3 and runs portfolio optimization algorithms.
"""

import json
import sys
import os
import pandas as pd
import numpy as np
# matplotlib removed for Lambda compatibility
from scipy.optimize import minimize
from datetime import datetime
from typing import Dict, Any, List, Tuple
# io and base64 removed with matplotlib

# Add shared utilities to path
sys.path.append('/opt/shared')
from utils import S3Handler, LambdaConfig, create_lambda_response, parse_lambda_event


class PortfolioOptimizer:
    """Portfolio optimization class with multiple models"""
    
    def __init__(self, config: LambdaConfig):
        self.config = config
        self.risk_free_rate = config.risk_free_rate
    
    def calculate_covariance_matrix(self, stock_symbols: List[str], s3_handler: S3Handler) -> Tuple[np.ndarray, List[str]]:
        """Calculate covariance matrix from individual stock data files in S3"""
        daily_returns = {}
        
        # Read daily returns for each stock from S3
        for symbol in stock_symbols:
            try:
                stock_key = f"{self.config.stocks_data_prefix}{symbol}.csv"
                stock_data = s3_handler.download_csv(stock_key)
                
                if stock_data is None:
                    print(f"Could not download data for {symbol}, skipping...")
                    continue
                
                # Ensure Date column is datetime
                stock_data['Date'] = pd.to_datetime(stock_data['Date'])
                stock_data.set_index('Date', inplace=True)
                stock_data.sort_index(inplace=True)
                
                # Calculate daily returns
                returns = stock_data['Close'].pct_change().dropna()
                daily_returns[symbol] = returns
                
            except Exception as e:
                print(f"Error processing {symbol}: {e}")
        
        # Create DataFrame with all returns
        returns_df = pd.DataFrame(daily_returns)
        
        # Calculate annualized covariance matrix
        cov_matrix = returns_df.cov() * 252
        
        return cov_matrix.values, list(daily_returns.keys())
    
    def portfolio_performance(self, weights: np.ndarray, returns: np.ndarray, cov_matrix: np.ndarray) -> Tuple[float, float, float]:
        """Calculate portfolio performance metrics"""
        portfolio_return = np.sum(returns * weights)
        portfolio_volatility = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_volatility
        return portfolio_return, portfolio_volatility, sharpe_ratio
    
    def negative_sharpe_ratio(self, weights: np.ndarray, returns: np.ndarray, cov_matrix: np.ndarray) -> float:
        """Calculate negative Sharpe ratio for minimization"""
        _, _, sharpe_ratio = self.portfolio_performance(weights, returns, cov_matrix)
        return -sharpe_ratio
    
    def optimize_mean_variance_portfolio(self, returns: np.ndarray, cov_matrix: np.ndarray) -> Dict[str, Any]:
        """Mean-Variance optimization"""
        num_assets = len(returns)
        initial_weights = np.ones(num_assets) / num_assets
        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
        bounds = tuple((0, 1) for _ in range(num_assets))
        
        # Maximize Sharpe ratio
        max_sharpe_result = minimize(
            self.negative_sharpe_ratio,
            initial_weights,
            args=(returns, cov_matrix),
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        # Minimize volatility
        def min_volatility_objective(weights):
            return self.portfolio_performance(weights, returns, cov_matrix)[1]
        
        min_volatility_result = minimize(
            min_volatility_objective,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        # Calculate performance metrics
        max_sharpe_return, max_sharpe_volatility, max_sharpe_sharpe = self.portfolio_performance(
            max_sharpe_result['x'], returns, cov_matrix
        )
        
        min_vol_return, min_vol_volatility, min_vol_sharpe = self.portfolio_performance(
            min_volatility_result['x'], returns, cov_matrix
        )
        
        return {
            'max_sharpe_weights': max_sharpe_result['x'],
            'min_vol_weights': min_volatility_result['x'],
            'max_sharpe_performance': {
                'return': max_sharpe_return,
                'volatility': max_sharpe_volatility,
                'sharpe': max_sharpe_sharpe
            },
            'min_vol_performance': {
                'return': min_vol_return,
                'volatility': min_vol_volatility,
                'sharpe': min_vol_sharpe
            }
        }
    
    def calculate_risk_contribution(self, weights: np.ndarray, cov_matrix: np.ndarray) -> np.ndarray:
        """Calculate risk contribution for each asset"""
        portfolio_volatility = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        marginal_contrib = np.dot(cov_matrix, weights)
        risk_contrib = np.multiply(marginal_contrib, weights) / portfolio_volatility
        return risk_contrib
    
    def risk_budget_objective(self, weights: np.ndarray, cov_matrix: np.ndarray, target_risk_contribution: np.ndarray) -> float:
        """Objective function for risk parity optimization"""
        risk_contrib = self.calculate_risk_contribution(weights, cov_matrix)
        risk_diff = np.sum(np.square(risk_contrib - target_risk_contribution))
        return risk_diff
    
    def optimize_risk_parity(self, cov_matrix: np.ndarray) -> Dict[str, Any]:
        """Risk Parity optimization"""
        n = cov_matrix.shape[0]
        risk_budget = np.ones(n) / n
        initial_weights = np.ones(n) / n
        
        constraints = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}]
        bounds = tuple((0, 1) for _ in range(n))
        
        target_risk_contribution = risk_budget * np.sqrt(np.dot(initial_weights.T, np.dot(cov_matrix, initial_weights)))
        
        result = minimize(
            self.risk_budget_objective,
            initial_weights,
            args=(cov_matrix, target_risk_contribution),
            method='SLSQP',
            constraints=constraints,
            bounds=bounds,
            options={'ftol': 1e-12, 'maxiter': 1000}
        )
        
        weights = result['x']
        portfolio_volatility = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        risk_contribution = self.calculate_risk_contribution(weights, cov_matrix)
        
        return {
            'weights': weights,
            'volatility': portfolio_volatility,
            'risk_contribution': risk_contribution,
            'success': result['success']
        }
    
    def black_litterman(self, market_weights: np.ndarray, cov_matrix: np.ndarray, 
                       P: np.ndarray, Q: np.ndarray, Omega: np.ndarray, 
                       risk_aversion: float = 2.5, tau: float = 0.025) -> np.ndarray:
        """Black-Litterman model implementation"""
        # Calculate implied returns
        implied_returns = risk_aversion * np.dot(cov_matrix, market_weights)
        
        # Apply Black-Litterman formula
        precision_prior = np.linalg.inv(tau * cov_matrix)
        precision_views = np.dot(P.T, np.dot(np.linalg.inv(Omega), P))
        precision_posterior = precision_prior + precision_views
        
        mean_prior = np.dot(precision_prior, implied_returns)
        mean_views = np.dot(P.T, np.dot(np.linalg.inv(Omega), Q))
        
        posterior_returns = np.dot(np.linalg.inv(precision_posterior), mean_prior + mean_views)
        
        return posterior_returns
    
    def form_views(self, stocks_data: pd.DataFrame, cov_matrix: np.ndarray, view_type: str = 'both') -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Form investment views for Black-Litterman"""
        n_assets = len(stocks_data)
        n_views = 2 if view_type != 'both' else 3
        
        P = np.zeros((n_views, n_assets))
        Q = np.zeros(n_views)
        
        # Calculate median values for classification
        median_return = stocks_data['Annual_Return_5Y'].median()
        median_volatility = stocks_data['Annual_Volatility_5Y'].median()
        
        # AI-driven growth companies
        ai_companies = ['NVDA', 'MSFT', 'GOOGL', 'GOOG', 'META', 'AMZN', 'AVGO', 'AMD']
        
        view_index = 0
        
        # View 1: High return stocks will outperform
        if view_type in ['historical', 'both']:
            high_return_indices = stocks_data[stocks_data['Annual_Return_5Y'] > median_return].index
            for idx in high_return_indices:
                P[view_index, idx] = 1.0
            
            if P[view_index].sum() > 0:
                P[view_index] = P[view_index] / P[view_index].sum()
            
            Q[view_index] = stocks_data.loc[high_return_indices, 'Annual_Return_5Y'].mean() + 0.02
            view_index += 1
        
        # View 2: Undervalued stocks will outperform
        if view_type in ['undervalue', 'both'] and 'Undervalue Rate' in stocks_data.columns:
            undervalued_indices = stocks_data[
                (stocks_data['Undervalue Rate'].notnull()) & 
                (stocks_data['Undervalue Rate'] > 0)
            ].index
            
            for idx in undervalued_indices:
                P[view_index, idx] = 1.0
            
            if P[view_index].sum() > 0:
                P[view_index] = P[view_index] / P[view_index].sum()
                Q[view_index] = stocks_data.loc[undervalued_indices, 'Undervalue Rate'].mean()
            else:
                Q[view_index] = 0.10
            
            view_index += 1
        
        # View 3: AI-driven companies will outperform (always included if view_type is 'both')
        if view_type == 'both':
            ai_indices = stocks_data[stocks_data['Symbol'].isin(ai_companies)].index
            for idx in ai_indices:
                P[view_index, idx] = 1.0
            
            if P[view_index].sum() > 0:
                P[view_index] = P[view_index] / P[view_index].sum()
            
            Q[view_index] = 0.20  # 20% expected return for AI-driven stocks
        
        # Create uncertainty matrix
        Omega = np.zeros((n_views, n_views))
        for i in range(n_views):
            portfolio_var = np.dot(P[i], np.dot(cov_matrix, P[i].T))
            Omega[i, i] = portfolio_var * 0.3
        
        return P, Q, Omega
    
    def optimize_bl_portfolio(self, expected_returns: np.ndarray, cov_matrix: np.ndarray, risk_aversion: float = 2.5) -> np.ndarray:
        """Optimize portfolio based on Black-Litterman expected returns"""
        n_assets = len(expected_returns)
        
        def objective(weights):
            portfolio_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
            portfolio_return = np.dot(weights.T, expected_returns)
            return portfolio_variance - (1/risk_aversion) * portfolio_return
        
        initial_weights = np.ones(n_assets) / n_assets
        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
        bounds = tuple((0, 1) for _ in range(n_assets))
        
        result = minimize(objective, initial_weights, method='SLSQP', bounds=bounds, constraints=constraints)
        return result['x']


def run_portfolio_optimization(config: LambdaConfig, s3_handler: S3Handler, input_file_key: str, 
                             model_type: str = 'all', return_type: str = 'both') -> Dict[str, Any]:
    """Main portfolio optimization function"""
    
    # Download processed stock data
    print(f"Downloading stock data from {input_file_key}")
    stocks_data = s3_handler.download_csv(input_file_key)
    
    if stocks_data is None:
        raise Exception(f"Could not download stock data from {input_file_key}")
    
    # Validate required columns
    required_columns = ['Symbol', 'Annual_Return_5Y', 'Annual_Volatility_5Y']
    if not all(col in stocks_data.columns for col in required_columns):
        missing = [col for col in required_columns if col not in stocks_data.columns]
        raise Exception(f"Missing required columns: {', '.join(missing)}")
    
    # Filter out stocks with missing data
    valid_data = stocks_data.dropna(subset=['Annual_Return_5Y', 'Annual_Volatility_5Y']).copy()
    
    has_undervalue = 'Undervalue Rate' in valid_data.columns
    if return_type in ['undervalue', 'both'] and has_undervalue:
        valid_data = valid_data.dropna(subset=['Undervalue Rate'])
    
    print(f"Processing {len(valid_data)} stocks with valid data")
    
    if len(valid_data) < 2:
        raise Exception("Not enough stocks with valid data for portfolio optimization")
    
    # Initialize optimizer
    optimizer = PortfolioOptimizer(config)
    
    # Calculate covariance matrix
    print("Calculating covariance matrix from S3 stock data...")
    stock_symbols = valid_data['Symbol'].tolist()
    cov_matrix, available_symbols = optimizer.calculate_covariance_matrix(stock_symbols, s3_handler)
    
    # Filter to stocks with covariance data
    filtered_data = valid_data[valid_data['Symbol'].isin(available_symbols)].copy()
    filtered_data = filtered_data.reset_index(drop=True)
    
    print(f"Running optimization with {len(filtered_data)} stocks")
    
    # Prepare results
    results = {}
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Mean-Variance optimization
    if model_type in ['mv', 'all']:
        print("Running Mean-Variance optimization...")
        
        for ret_type in (['historical', 'undervalue'] if return_type == 'both' else [return_type]):
            if ret_type == 'undervalue' and not has_undervalue:
                continue
                
            returns = (filtered_data['Annual_Return_5Y'].values if ret_type == 'historical' 
                      else filtered_data['Undervalue Rate'].values)
            
            mv_result = optimizer.optimize_mean_variance_portfolio(returns, cov_matrix)
            
            # Save results
            for portfolio_type in ['max_sharpe', 'min_vol']:
                weights = mv_result[f'{portfolio_type}_weights']
                
                result_df = filtered_data.copy()
                result_df['Weight'] = weights
                
                # Upload to S3
                key = f"{config.results_prefix}final/mv_{ret_type}_{portfolio_type}_portfolio_{timestamp}.csv"
                s3_handler.upload_csv(result_df, key)
                
                # Store significant holdings
                significant = result_df[result_df['Weight'] > config.min_weight_threshold].sort_values('Weight', ascending=False)
                sig_key = f"{config.results_prefix}final/mv_{ret_type}_{portfolio_type}_significant_{timestamp}.csv"
                s3_handler.upload_csv(significant, sig_key)
                
                results[f'mv_{ret_type}_{portfolio_type}'] = {
                    'weights': weights.tolist(),
                    'performance': mv_result[f'{portfolio_type}_performance'],
                    'full_results_key': key,
                    'significant_holdings_key': sig_key
                }
    
    # Risk Parity optimization
    if model_type in ['rp', 'all']:
        print("Running Risk Parity optimization...")
        
        for ret_type in (['historical', 'undervalue'] if return_type == 'both' else [return_type]):
            if ret_type == 'undervalue' and not has_undervalue:
                continue
                
            returns = (filtered_data['Annual_Return_5Y'].values if ret_type == 'historical' 
                      else filtered_data['Undervalue Rate'].values)
            
            rp_result = optimizer.optimize_risk_parity(cov_matrix)
            
            # Calculate performance
            port_return, port_volatility, sharpe = optimizer.portfolio_performance(
                rp_result['weights'], returns, cov_matrix
            )
            
            result_df = filtered_data.copy()
            result_df['Weight'] = rp_result['weights']
            result_df['Risk_Contribution'] = rp_result['risk_contribution']
            
            # Upload to S3
            key = f"{config.results_prefix}final/rp_{ret_type}_portfolio_{timestamp}.csv"
            s3_handler.upload_csv(result_df, key)
            
            # Store significant holdings
            significant = result_df[result_df['Weight'] > config.min_weight_threshold].sort_values('Weight', ascending=False)
            sig_key = f"{config.results_prefix}final/rp_{ret_type}_significant_{timestamp}.csv"
            s3_handler.upload_csv(significant, sig_key)
            
            results[f'rp_{ret_type}'] = {
                'weights': rp_result['weights'].tolist(),
                'performance': {
                    'return': port_return,
                    'volatility': port_volatility,
                    'sharpe': sharpe
                },
                'full_results_key': key,
                'significant_holdings_key': sig_key,
                'optimization_success': rp_result['success']
            }
    
    # Black-Litterman optimization
    if model_type in ['bl', 'all']:
        print("Running Black-Litterman optimization...")
        
        # Use MV max sharpe weights as market equilibrium
        historical_returns = filtered_data['Annual_Return_5Y'].values
        mv_result = optimizer.optimize_mean_variance_portfolio(historical_returns, cov_matrix)
        market_weights = mv_result['max_sharpe_weights']
        
        for ret_type in (['historical', 'undervalue', 'both'] if return_type == 'both' else [return_type]):
            if ret_type == 'undervalue' and not has_undervalue:
                continue
                
            P, Q, Omega = optimizer.form_views(filtered_data, cov_matrix, ret_type)
            bl_returns = optimizer.black_litterman(market_weights, cov_matrix, P, Q, Omega)
            bl_weights = optimizer.optimize_bl_portfolio(bl_returns, cov_matrix)
            
            # Calculate performance
            port_return, port_volatility, sharpe = optimizer.portfolio_performance(
                bl_weights, bl_returns, cov_matrix
            )
            
            result_df = filtered_data.copy()
            result_df['Weight'] = bl_weights
            result_df['BL_Expected_Return'] = bl_returns
            
            # Upload to S3
            key = f"{config.results_prefix}final/bl_{ret_type}_portfolio_{timestamp}.csv"
            s3_handler.upload_csv(result_df, key)
            
            # Store significant holdings
            significant = result_df[result_df['Weight'] > config.min_weight_threshold].sort_values('Weight', ascending=False)
            sig_key = f"{config.results_prefix}final/bl_{ret_type}_significant_{timestamp}.csv"
            s3_handler.upload_csv(significant, sig_key)
            
            results[f'bl_{ret_type}'] = {
                'weights': bl_weights.tolist(),
                'performance': {
                    'return': port_return,
                    'volatility': port_volatility,
                    'sharpe': sharpe
                },
                'full_results_key': key,
                'significant_holdings_key': sig_key
            }
    
    # Create comparison summary
    performance_comparison = []
    for model_name, model_result in results.items():
        performance_comparison.append({
            'Model': model_name,
            'Return': model_result['performance']['return'],
            'Volatility': model_result['performance']['volatility'],
            'Sharpe_Ratio': model_result['performance']['sharpe']
        })
    
    comparison_df = pd.DataFrame(performance_comparison)
    comparison_key = f"{config.results_prefix}final/portfolio_performance_comparison_{timestamp}.csv"
    s3_handler.upload_csv(comparison_df, comparison_key)
    
    # Create recommended portfolio (average of all models)
    if len(results) > 1:
        avg_weights = np.zeros(len(filtered_data))
        for model_result in results.values():
            avg_weights += np.array(model_result['weights'])
        avg_weights /= len(results)
        
        recommended_df = filtered_data.copy()
        recommended_df['Weight'] = avg_weights
        
        recommended_key = f"{config.results_prefix}final/recommended_portfolio_{timestamp}.csv"
        s3_handler.upload_csv(recommended_df, recommended_key)
        
        # Significant holdings
        significant_rec = recommended_df[recommended_df['Weight'] > config.min_weight_threshold].sort_values('Weight', ascending=False)
        significant_rec_key = f"{config.results_prefix}final/recommended_portfolio_significant_{timestamp}.csv"
        s3_handler.upload_csv(significant_rec, significant_rec_key)
        
        results['recommended'] = {
            'weights': avg_weights.tolist(),
            'full_results_key': recommended_key,
            'significant_holdings_key': significant_rec_key
        }
    
    return {
        'models_run': list(results.keys()),
        'total_stocks_analyzed': len(filtered_data),
        'comparison_results_key': comparison_key,
        'results': results,
        'timestamp': timestamp
    }


def lambda_handler(event, context):
    """AWS Lambda handler function"""
    try:
        # Parse event
        parsed_event = parse_lambda_event(event)
        print(f"Received event: {json.dumps(parsed_event, indent=2)}")
        
        # Initialize configuration and S3 handler
        config = LambdaConfig()
        s3_handler = S3Handler(config.bucket_name)
        
        # Determine input file
        input_file_key = None
        model_type = parsed_event.get('model_type', 'all')
        return_type = parsed_event.get('return_type', 'both')
        
        if 'input_file' in parsed_event:
            input_file_key = parsed_event['input_file']
        elif parsed_event.get('trigger_type') == 's3':
            input_file_key = parsed_event['key']
        else:
            # Default: use the latest processed stock data
            input_file_key = f"{config.processed_data_prefix}nasdaq_100_with_returns.csv"
        
        print(f"Using input file: {input_file_key}")
        print(f"Model type: {model_type}, Return type: {return_type}")
        
        # Run optimization
        result = run_portfolio_optimization(config, s3_handler, input_file_key, model_type, return_type)
        
        print(f"Portfolio optimization completed successfully")
        
        return create_lambda_response(200, {
            "message": "Portfolio optimization completed successfully", 
            "result": result
        })
        
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return create_lambda_response(500, {
            "message": "Error during portfolio optimization",
            "error": str(e)
        })


# For local testing
if __name__ == "__main__":
    # Mock event for testing
    test_event = {
        "trigger_type": "manual",
        "input_file": "processed/nasdaq_100_with_returns.csv",
        "model_type": "all",
        "return_type": "both"
    }
    result = lambda_handler(test_event, None)
    print(f"Test result: {result}")