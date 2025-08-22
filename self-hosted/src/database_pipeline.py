#!/usr/bin/env python3
"""
Database-enabled Portfolio Optimization Pipeline
Wraps existing pipeline functionality and writes to PostgreSQL instead of CSV files
"""

import os
import sys
import logging
import time
from datetime import datetime
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple

# Import our modules
from data_pipeline import DataPipeline, Config, NasdaqAnalyzer, StockDataFetcher, PortfolioOptimizer
from database import DatabaseManager
from fmp_client import FMPClient


class DatabasePipeline:
    """Database-enabled pipeline with checkpoint/resume support"""
    
    def __init__(self, config: Config = None):
        """Initialize database-enabled pipeline"""
        self.config = config or Config()
        self.db = DatabaseManager()
        self.fmp = FMPClient()
        self.run_id = None
        
        # We'll use FMP client directly instead of old components
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def run_full_pipeline(self, resume_run_id: Optional[int] = None) -> Dict:
        """Run complete pipeline with database storage"""
        try:
            # Create or resume pipeline run
            if resume_run_id:
                self.run_id = resume_run_id
                checkpoint = self.db.get_checkpoint_info(self.run_id)
                logging.info(f"Resuming pipeline run {self.run_id} from phase {checkpoint.get('phase')}")
            else:
                self.run_id = self.db.create_pipeline_run('full')
                checkpoint = None
            
            # Phase 1: Get NASDAQ-100 constituents from FMP
            if not checkpoint or checkpoint['phase'] == 'phase1_nasdaq':
                self._run_phase1_nasdaq()
            
            # Phase 2: Fetch stock data from FMP
            if not checkpoint or checkpoint['phase'] in ['phase1_nasdaq', 'phase2_stock_data']:
                self._run_phase2_stock_data(checkpoint)
            
            # Phase 3: Portfolio optimization
            if not checkpoint or checkpoint['phase'] in ['phase1_nasdaq', 'phase2_stock_data', 'phase3_optimization']:
                self._run_phase3_optimization()
            
            # Mark pipeline as complete
            self.db.update_pipeline_status(self.run_id, 'completed')
            
            return {
                'status': 'success',
                'run_id': self.run_id,
                'message': 'Pipeline completed successfully'
            }
            
        except Exception as e:
            logging.error(f"Pipeline failed: {e}")
            if self.run_id:
                self.db.update_pipeline_status(
                    self.run_id, 'failed', 
                    error_message=str(e)
                )
            return {
                'status': 'error',
                'run_id': self.run_id,
                'error': str(e)
            }
    
    def _run_phase1_nasdaq(self):
        """Phase 1: Get NASDAQ-100 constituents from FMP"""
        logging.info("Phase 1: Fetching NASDAQ-100 constituents from FMP")
        self.db.update_pipeline_status(self.run_id, 'running', 'phase1_nasdaq')
        
        # Get constituents from FMP
        constituents_df = self.fmp.get_nasdaq100_constituents()
        
        if constituents_df is None or constituents_df.empty:
            raise Exception("Failed to fetch NASDAQ-100 constituents")
        
        logging.info(f"Fetched {len(constituents_df)} NASDAQ-100 constituents")
        
        # Store in database
        self.db.upsert_stocks(constituents_df, self.run_id)
        
        # Log API usage
        stats = self.fmp.get_api_usage_stats()
        logging.info(f"API usage after Phase 1: {stats['calls_last_minute']} calls, {stats['calls_remaining']} remaining")
    
    def _run_phase2_stock_data(self, checkpoint: Optional[Dict] = None):
        """Phase 2: Fetch stock data from FMP with checkpointing"""
        logging.info("Phase 2: Fetching stock data from FMP")
        self.db.update_pipeline_status(self.run_id, 'running', 'phase2_stock_data')
        
        # Get stock list from database
        with self.db.get_connection() as conn:
            stocks_df = pd.read_sql(
                "SELECT symbol, company_name FROM stocks WHERE is_active = true",
                conn
            )
        
        total_stocks = len(stocks_df)
        start_idx = 0
        
        # Resume from checkpoint if available
        if checkpoint and checkpoint.get('last_processed_stock'):
            last_symbol = checkpoint['last_processed_stock']
            start_idx = stocks_df[stocks_df['symbol'] == last_symbol].index[0] + 1
            logging.info(f"Resuming from stock {start_idx}/{total_stocks}")
        
        # Process stocks in batches to allow checkpointing
        batch_size = 25
        
        for batch_start in range(start_idx, total_stocks, batch_size):
            batch_end = min(batch_start + batch_size, total_stocks)
            batch_stocks = stocks_df.iloc[batch_start:batch_end]
            
            logging.info(f"Processing batch {batch_start}-{batch_end} of {total_stocks} stocks")
            
            for idx, row in batch_stocks.iterrows():
                symbol = row['symbol']
                
                try:
                    # Fetch data from FMP
                    logging.info(f"Fetching data for {symbol} ({idx+1}/{total_stocks})")
                    
                    # Get quote and analyst estimates
                    quote = self.fmp.get_quote(symbol)
                    estimates = self.fmp.get_analyst_estimates(symbol)
                    
                    # Get historical prices (5 years)
                    historical_prices = self.fmp.get_historical_prices(symbol)
                    
                    # Calculate metrics
                    metrics = {}
                    if quote:
                        metrics['current_price'] = quote.get('price')
                        metrics['pe_ratio'] = quote.get('pe')
                        metrics['market_cap'] = quote.get('marketCap')
                    
                    if estimates:
                        metrics['target_price'] = estimates.get('targetMeanPrice')
                        metrics['analyst_count'] = estimates.get('numberOfAnalystOpinions', 0)
                        
                        # Calculate undervaluation rate
                        if metrics.get('current_price') and metrics.get('target_price'):
                            metrics['undervaluation_rate'] = (
                                (metrics['target_price'] - metrics['current_price']) / 
                                metrics['current_price']
                            )
                    
                    if historical_prices is not None and not historical_prices.empty:
                        # Calculate return metrics
                        returns_metrics = self.fmp.calculate_returns_metrics(historical_prices)
                        metrics.update({
                            'annual_return': returns_metrics['annual_return'],
                            'volatility': returns_metrics['volatility'],
                            'sharpe_ratio': returns_metrics['sharpe_ratio'],
                            'max_drawdown': returns_metrics['max_drawdown']
                        })
                        
                        # Store historical prices (only last year to save space)
                        self.db.insert_stock_prices(symbol, historical_prices, self.run_id)
                    
                    # Store metrics in database
                    if metrics:
                        self.db.insert_stock_metrics(symbol, metrics, self.run_id)
                    
                except Exception as e:
                    logging.error(f"Error processing {symbol}: {e}")
                    continue
            
            # Update checkpoint after each batch
            self.db.update_pipeline_status(
                self.run_id, 'running', 'phase2_stock_data',
                stocks_processed=batch_end,
                last_processed_stock=batch_stocks.iloc[-1]['symbol']
            )
            
            # Check API usage and wait if needed
            stats = self.fmp.get_api_usage_stats()
            logging.info(f"API usage: {stats['calls_last_minute']} calls, {stats['calls_remaining']} remaining")
            
            # If we're close to the limit, pause
            if stats['calls_remaining'] < 50:
                wait_time = 30
                logging.info(f"Approaching rate limit, waiting {wait_time} seconds...")
                time.sleep(wait_time)
    
    def _run_phase3_optimization(self):
        """Phase 3: Run portfolio optimization models"""
        logging.info("Phase 3: Running portfolio optimization")
        self.db.update_pipeline_status(self.run_id, 'running', 'phase3_optimization')
        
        # Load stock data from database
        with self.db.get_connection() as conn:
            stock_data_query = """
                SELECT 
                    s.symbol,
                    s.company_name,
                    sm.current_price,
                    sm.target_price,
                    sm.analyst_count,
                    sm.annual_return_5y,
                    sm.annual_volatility_5y,
                    sm.undervaluation_rate
                FROM stocks s
                JOIN stock_metrics sm ON s.id = sm.stock_id
                WHERE sm.pipeline_run_id = %s
                AND sm.annual_return_5y IS NOT NULL
                AND sm.annual_volatility_5y IS NOT NULL
            """
            stock_df = pd.read_sql(stock_data_query, conn, params=(self.run_id,))
        
        if stock_df.empty:
            raise Exception("No stock data available for optimization")
        
        logging.info(f"Loaded {len(stock_df)} stocks for optimization")
        
        # Prepare data for optimizer
        stock_df.columns = [
            'Symbol', 'Company', 'Previous Close', '1y Target Est', 
            'Analyst_Count', 'Annual_Return_5Y', 'Annual_Volatility_5Y', 
            'Undervalue Rate'
        ]
        
        # Define optimization models
        models = [
            ('mv_historical_max_sharpe', 'Mean-Variance', 'max_sharpe', 'historical'),
            ('mv_historical_min_vol', 'Mean-Variance', 'min_volatility', 'historical'),
            ('mv_undervalue_max_sharpe', 'Mean-Variance', 'max_sharpe', 'undervalue'),
            ('mv_undervalue_min_vol', 'Mean-Variance', 'min_volatility', 'undervalue'),
            ('rp_historical', 'Risk Parity', 'equal_risk', 'historical'),
            ('rp_undervalue', 'Risk Parity', 'equal_risk', 'undervalue'),
            ('bl_historical', 'Black-Litterman', 'bayesian', 'historical'),
            ('bl_undervalue', 'Black-Litterman', 'bayesian', 'undervalue')
        ]
        
        # Run each model
        for model_name, model_type, opt_method, returns_type in models:
            try:
                logging.info(f"Running {model_name} optimization")
                
                # Get or create model ID
                model_id = self.db.upsert_portfolio_model(
                    model_name, model_type, opt_method,
                    {
                        'description': f'{model_type} optimization using {returns_type} returns',
                        'risk_free_rate': self.config.risk_free_rate,
                        'min_weight_threshold': self.config.min_weight_threshold
                    }
                )
                
                # Run optimization (using existing optimizer logic)
                if model_type == 'Mean-Variance':
                    weights = self._optimize_mean_variance(
                        stock_df, opt_method, returns_type
                    )
                elif model_type == 'Risk Parity':
                    weights = self._optimize_risk_parity(
                        stock_df, returns_type
                    )
                elif model_type == 'Black-Litterman':
                    weights = self._optimize_black_litterman(
                        stock_df, returns_type
                    )
                else:
                    continue
                
                if weights is None:
                    logging.warning(f"Optimization failed for {model_name}")
                    continue
                
                # Create allocation dataframe
                allocation_df = pd.DataFrame({
                    'Symbol': stock_df['Symbol'],
                    'Weight': weights,
                    'Expected_Return': stock_df['Annual_Return_5Y'] if returns_type == 'historical' 
                                     else stock_df['Undervalue Rate']
                })
                
                # Filter significant holdings
                allocation_df = allocation_df[allocation_df['Weight'] > self.config.min_weight_threshold]
                
                # Calculate performance metrics
                portfolio_return = (allocation_df['Weight'] * allocation_df['Expected_Return']).sum()
                portfolio_volatility = np.sqrt(
                    (allocation_df['Weight']**2 * stock_df.set_index('Symbol').loc[allocation_df['Symbol']]['Annual_Volatility_5Y']**2).sum()
                )
                sharpe_ratio = (portfolio_return - self.config.risk_free_rate) / portfolio_volatility if portfolio_volatility > 0 else 0
                
                performance = {
                    'total_return': portfolio_return,
                    'volatility': portfolio_volatility,
                    'sharpe_ratio': sharpe_ratio,
                    'stocks_selected': len(allocation_df),
                    'concentration_ratio': allocation_df['Weight'].head(10).sum()
                }
                
                # Store in database
                self.db.insert_portfolio_performance(model_id, self.run_id, performance)
                self.db.insert_portfolio_composition(model_id, self.run_id, allocation_df)
                
                logging.info(f"Completed {model_name}: Sharpe={sharpe_ratio:.2f}, Stocks={len(allocation_df)}")
                
            except Exception as e:
                logging.error(f"Error in {model_name}: {e}")
                continue
    
    def _optimize_mean_variance(self, stock_df: pd.DataFrame, method: str, returns_type: str) -> Optional[np.ndarray]:
        """Run mean-variance optimization"""
        # Use existing optimizer logic
        try:
            if returns_type == 'historical':
                returns = stock_df['Annual_Return_5Y'].values
            else:
                returns = stock_df['Undervalue Rate'].values
            
            volatilities = stock_df['Annual_Volatility_5Y'].values
            
            # Simple covariance approximation (diagonal)
            cov_matrix = np.diag(volatilities ** 2)
            
            n_assets = len(stock_df)
            
            if method == 'max_sharpe':
                # Maximum Sharpe ratio
                from scipy.optimize import minimize
                
                def neg_sharpe(weights):
                    port_return = np.dot(weights, returns)
                    port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
                    return -(port_return - self.config.risk_free_rate) / port_vol
                
                constraints = [
                    {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
                ]
                bounds = tuple((0, 1) for _ in range(n_assets))
                initial_guess = np.array([1/n_assets] * n_assets)
                
                result = minimize(neg_sharpe, initial_guess, method='SLSQP',
                                bounds=bounds, constraints=constraints)
                
                return result.x if result.success else None
                
            elif method == 'min_volatility':
                # Minimum volatility
                from scipy.optimize import minimize
                
                def portfolio_vol(weights):
                    return np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
                
                constraints = [
                    {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
                ]
                bounds = tuple((0, 1) for _ in range(n_assets))
                initial_guess = np.array([1/n_assets] * n_assets)
                
                result = minimize(portfolio_vol, initial_guess, method='SLSQP',
                                bounds=bounds, constraints=constraints)
                
                return result.x if result.success else None
                
        except Exception as e:
            logging.error(f"Mean-variance optimization failed: {e}")
            return None
    
    def _optimize_risk_parity(self, stock_df: pd.DataFrame, returns_type: str) -> Optional[np.ndarray]:
        """Run risk parity optimization"""
        try:
            volatilities = stock_df['Annual_Volatility_5Y'].values
            
            # Inverse volatility weighting (simplified risk parity)
            inv_vols = 1 / volatilities
            weights = inv_vols / inv_vols.sum()
            
            return weights
            
        except Exception as e:
            logging.error(f"Risk parity optimization failed: {e}")
            return None
    
    def _optimize_black_litterman(self, stock_df: pd.DataFrame, returns_type: str) -> Optional[np.ndarray]:
        """Run Black-Litterman optimization"""
        try:
            # Market cap weights (equal weight as proxy)
            n_assets = len(stock_df)
            market_weights = np.array([1/n_assets] * n_assets)
            
            # Covariance matrix
            volatilities = stock_df['Annual_Volatility_5Y'].values
            cov_matrix = np.diag(volatilities ** 2)
            
            # Views
            if returns_type == 'undervalue':
                Q = stock_df['Undervalue Rate'].values
                # Confidence based on analyst count
                analyst_counts = stock_df['Analyst_Count'].fillna(1).values
                confidence = np.minimum(analyst_counts / 30, 1.0) * 0.8
            else:
                Q = stock_df['Annual_Return_5Y'].values
                confidence = np.ones(n_assets) * 0.5
            
            # P matrix (identity - each view is about one asset)
            P = np.eye(n_assets)
            
            # Omega (uncertainty of views)
            omega_diag = (1 - confidence) * 0.1
            Omega = np.diag(omega_diag)
            
            # Black-Litterman formula
            tau = 0.025
            
            # Add regularization to prevent singular matrix
            epsilon = 1e-8
            cov_matrix_reg = cov_matrix + epsilon * np.eye(n_assets)
            
            # Calculate posterior expected returns
            term1 = np.linalg.inv(tau * cov_matrix_reg)
            term2 = P.T @ np.linalg.inv(Omega) @ P
            term3 = np.linalg.inv(tau * cov_matrix_reg) @ (market_weights * 0.1)  # Prior
            term4 = P.T @ np.linalg.inv(Omega) @ Q
            
            posterior_returns = np.linalg.inv(term1 + term2) @ (term3 + term4)
            
            # Optimize with posterior returns (max Sharpe)
            from scipy.optimize import minimize
            
            def neg_sharpe(weights):
                port_return = np.dot(weights, posterior_returns)
                port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix_reg, weights)))
                return -(port_return - self.config.risk_free_rate) / port_vol
            
            constraints = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}]
            bounds = tuple((0, 1) for _ in range(n_assets))
            initial_guess = market_weights
            
            result = minimize(neg_sharpe, initial_guess, method='SLSQP',
                            bounds=bounds, constraints=constraints)
            
            return result.x if result.success else None
            
        except Exception as e:
            logging.error(f"Black-Litterman optimization failed: {e}")
            return None


# Main execution
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Database-enabled Portfolio Pipeline')
    parser.add_argument('--resume', type=int, help='Resume from run ID')
    parser.add_argument('--test', action='store_true', help='Run test mode')
    args = parser.parse_args()
    
    # Initialize pipeline
    pipeline = DatabasePipeline()
    
    if args.test:
        # Test mode - just check connections
        print("Testing database connection...")
        portfolios = pipeline.db.get_latest_portfolios()
        print(f"Found {len(portfolios)} portfolio models in database")
        
        print("\nTesting FMP API...")
        stats = pipeline.fmp.get_api_usage_stats()
        print(f"API stats: {stats}")
        
    else:
        # Run pipeline
        result = pipeline.run_full_pipeline(resume_run_id=args.resume)
        print(f"Pipeline result: {result}")
    
    # Clean up
    pipeline.db.close()