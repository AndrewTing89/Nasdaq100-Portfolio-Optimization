#!/usr/bin/env python3
"""
Simplified Data Pipeline for Portfolio Optimization
Loads data from existing CSV files instead of fetching from APIs
Uses proper optimization algorithms from scipy
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
import json
import sys
from scipy.optimize import minimize

# Set up logging to both file and console
def setup_logging(data_dir: Path):
    """Setup logging to file and console"""
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create log file with today's date
    log_file = log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d')}.log"
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='a'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

class SimplifiedPipeline:
    """Pipeline that loads from existing CSV files with proper optimization"""
    
    def __init__(self, data_dir: str = "/data"):
        self.data_dir = Path(data_dir)
        self.processed_dir = self.data_dir / "processed"
        self.results_dir = self.data_dir / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuration
        self.min_weight_threshold = 0.001
        self.risk_free_rate = 0.02
        
        # Setup logging
        global logger
        logger = setup_logging(self.data_dir)
        
    def run_phase1(self) -> Dict[str, Any]:
        """Phase 1: Load NASDAQ-100 analysis from CSV"""
        logger.info("=" * 50)
        logger.info("PHASE 1: NASDAQ-100 ANALYSIS")
        logger.info("=" * 50)
        
        csv_path = self.processed_dir / "nasdaq_100_analysis.csv"
        
        if not csv_path.exists():
            return {
                "status": "error",
                "error": f"File not found: {csv_path}",
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            df = pd.read_csv(csv_path)
            logger.info(f"Loaded {len(df)} companies from {csv_path}")
            
            return {
                "status": "success",
                "companies_count": len(df),
                "output_file": str(csv_path),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in Phase 1: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def run_phase2(self) -> Dict[str, Any]:
        """Phase 2: Load stock data with returns from CSV"""
        logger.info("=" * 50)
        logger.info("PHASE 2: STOCK DATA WITH RETURNS")
        logger.info("=" * 50)
        
        csv_path = self.processed_dir / "nasdaq_100_with_returns.csv"
        
        if not csv_path.exists():
            return {
                "status": "error",
                "error": f"File not found: {csv_path}",
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            df = pd.read_csv(csv_path)
            logger.info(f"Loaded {len(df)} stocks with returns from {csv_path}")
            
            # Log some statistics
            valid_returns = df['Annual_Return_5Y'].notna().sum()
            valid_volatility = df['Annual_Volatility_5Y'].notna().sum()
            valid_undervalue = df['Undervalue Rate'].notna().sum() if 'Undervalue Rate' in df.columns else 0
            
            logger.info(f"Valid returns: {valid_returns}/{len(df)}")
            logger.info(f"Valid volatility: {valid_volatility}/{len(df)}")
            logger.info(f"Valid undervalue rates: {valid_undervalue}/{len(df)}")
            
            return {
                "status": "success",
                "stocks_count": len(df),
                "valid_returns": int(valid_returns),
                "valid_volatility": int(valid_volatility),
                "valid_undervalue": int(valid_undervalue),
                "output_file": str(csv_path),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in Phase 2: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def portfolio_performance(self, weights: np.ndarray, returns: np.ndarray, cov_matrix: np.ndarray) -> Tuple[float, float, float]:
        """Calculate portfolio performance metrics"""
        portfolio_return = np.dot(weights, returns)
        portfolio_volatility = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_volatility if portfolio_volatility > 0 else 0
        return portfolio_return, portfolio_volatility, sharpe_ratio
    
    def negative_sharpe_ratio(self, weights: np.ndarray, returns: np.ndarray, cov_matrix: np.ndarray) -> float:
        """Negative Sharpe ratio for optimization"""
        _, _, sharpe_ratio = self.portfolio_performance(weights, returns, cov_matrix)
        return -sharpe_ratio
    
    def optimize_mean_variance_portfolio(self, returns: np.ndarray, cov_matrix: np.ndarray) -> Dict[str, Any]:
        """Mean-Variance optimization with both max Sharpe and min volatility"""
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
    
    def run_phase3(self, model_type: str = "all") -> Dict[str, Any]:
        """Phase 3: Portfolio Optimization with all 6 portfolio types"""
        logger.info("=" * 50)
        logger.info("PHASE 3: PORTFOLIO OPTIMIZATION")
        logger.info("=" * 50)
        logger.info(f"Model type: {model_type}")
        
        # Load the data
        csv_path = self.processed_dir / "nasdaq_100_with_returns.csv"
        
        if not csv_path.exists():
            return {
                "status": "error",
                "error": f"File not found: {csv_path}",
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            df = pd.read_csv(csv_path)
            
            # Filter stocks with valid return and volatility data
            df_clean = df.dropna(subset=['Annual_Return_5Y', 'Annual_Volatility_5Y'])
            logger.info(f"Using {len(df_clean)} stocks with complete return/volatility data")
            
            if len(df_clean) < 10:
                return {
                    "status": "error",
                    "error": "Insufficient stocks with valid data for optimization",
                    "timestamp": datetime.now().isoformat()
                }
            
            results = {}
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Mean-Variance Optimization with Historical Returns
            if model_type in ['mv', 'all']:
                logger.info("Running Mean-Variance optimization...")
                
                # Historical returns
                historical_returns = df_clean['Annual_Return_5Y'].values
                volatilities = df_clean['Annual_Volatility_5Y'].values
                
                # Create covariance matrix
                n_stocks = len(df_clean)
                correlation = 0.25
                cov_matrix = np.zeros((n_stocks, n_stocks))
                for i in range(n_stocks):
                    for j in range(n_stocks):
                        if i == j:
                            cov_matrix[i, j] = volatilities[i] ** 2
                        else:
                            cov_matrix[i, j] = correlation * volatilities[i] * volatilities[j]
                
                # Optimize with historical returns
                logger.info("  Optimizing with historical returns...")
                mv_result = self.optimize_mean_variance_portfolio(historical_returns, cov_matrix)
                
                # Save both max Sharpe and min volatility portfolios
                for portfolio_type in ['max_sharpe', 'min_vol']:
                    weights = mv_result[f'{portfolio_type}_weights']
                    
                    result_df = df_clean.copy()
                    result_df['Weight'] = weights
                    
                    # Filter significant holdings
                    significant = result_df[result_df['Weight'] > self.min_weight_threshold].copy()
                    significant = significant.sort_values('Weight', ascending=False)
                    
                    # Save files
                    output_file = self.results_dir / f"mv_historical_{portfolio_type}_significant_{timestamp}.csv"
                    significant.to_csv(output_file, index=False)
                    
                    full_file = self.results_dir / f"mv_historical_{portfolio_type}_portfolio_{timestamp}.csv"
                    result_df.to_csv(full_file, index=False)
                    
                    logger.info(f"    Historical {portfolio_type}: {len(significant)} significant holdings")
                    
                    results[f'mv_historical_{portfolio_type}'] = {
                        'status': 'success',
                        'stocks_selected': len(significant),
                        'total_stocks': len(result_df),
                        'output_file': str(output_file),
                        'full_file': str(full_file),
                        'performance': mv_result[f'{portfolio_type}_performance']
                    }
                
                # Now handle undervalue optimization if data is available
                df_undervalue = df_clean.dropna(subset=['Undervalue Rate'])
                if len(df_undervalue) >= 10:
                    logger.info("  Optimizing with undervalue rates...")
                    
                    # Use only stocks with undervalue data
                    undervalue_returns = df_undervalue['Undervalue Rate'].values
                    undervalue_volatilities = df_undervalue['Annual_Volatility_5Y'].values
                    
                    # Create covariance matrix for undervalue stocks
                    n_undervalue = len(df_undervalue)
                    undervalue_cov = np.zeros((n_undervalue, n_undervalue))
                    for i in range(n_undervalue):
                        for j in range(n_undervalue):
                            if i == j:
                                undervalue_cov[i, j] = undervalue_volatilities[i] ** 2
                            else:
                                undervalue_cov[i, j] = correlation * undervalue_volatilities[i] * undervalue_volatilities[j]
                    
                    # Optimize
                    mv_undervalue_result = self.optimize_mean_variance_portfolio(undervalue_returns, undervalue_cov)
                    
                    # Save portfolios
                    for portfolio_type in ['max_sharpe', 'min_vol']:
                        weights = mv_undervalue_result[f'{portfolio_type}_weights']
                        
                        result_df = df_undervalue.copy()
                        result_df['Weight'] = weights
                        
                        # Filter significant holdings
                        significant = result_df[result_df['Weight'] > self.min_weight_threshold].copy()
                        significant = significant.sort_values('Weight', ascending=False)
                        
                        # Save files
                        output_file = self.results_dir / f"mv_undervalue_{portfolio_type}_significant_{timestamp}.csv"
                        significant.to_csv(output_file, index=False)
                        
                        full_file = self.results_dir / f"mv_undervalue_{portfolio_type}_portfolio_{timestamp}.csv"
                        result_df.to_csv(full_file, index=False)
                        
                        logger.info(f"    Undervalue {portfolio_type}: {len(significant)} significant holdings")
                        
                        results[f'mv_undervalue_{portfolio_type}'] = {
                            'status': 'success',
                            'stocks_selected': len(significant),
                            'total_stocks': len(result_df),
                            'output_file': str(output_file),
                            'full_file': str(full_file),
                            'performance': mv_undervalue_result[f'{portfolio_type}_performance']
                        }
            
            # Risk Parity Optimization
            if model_type in ['rp', 'all']:
                logger.info("Running Risk Parity optimization...")
                
                # For historical data
                volatilities = df_clean['Annual_Volatility_5Y'].values
                n_stocks = len(df_clean)
                correlation = 0.25
                cov_matrix = np.zeros((n_stocks, n_stocks))
                for i in range(n_stocks):
                    for j in range(n_stocks):
                        if i == j:
                            cov_matrix[i, j] = volatilities[i] ** 2
                        else:
                            cov_matrix[i, j] = correlation * volatilities[i] * volatilities[j]
                
                rp_result = self.optimize_risk_parity(cov_matrix)
                
                # Save historical risk parity
                logger.info("  Creating historical risk parity portfolio...")
                weights = rp_result['weights']
                historical_returns = df_clean['Annual_Return_5Y'].values
                
                port_return, port_volatility, sharpe = self.portfolio_performance(
                    weights, historical_returns, cov_matrix
                )
                
                result_df = df_clean.copy()
                result_df['Weight'] = weights
                result_df['Risk_Contribution'] = rp_result['risk_contribution']
                
                significant = result_df[result_df['Weight'] > self.min_weight_threshold].copy()
                significant = significant.sort_values('Weight', ascending=False)
                
                output_file = self.results_dir / f"rp_historical_significant_{timestamp}.csv"
                significant.to_csv(output_file, index=False)
                
                full_file = self.results_dir / f"rp_historical_portfolio_{timestamp}.csv"
                result_df.to_csv(full_file, index=False)
                
                logger.info(f"    Historical: {len(significant)} significant holdings")
                
                results['rp_historical'] = {
                    'status': 'success',
                    'stocks_selected': len(significant),
                    'total_stocks': len(result_df),
                    'output_file': str(output_file),
                    'full_file': str(full_file),
                    'performance': {
                        'return': port_return,
                        'volatility': port_volatility,
                        'sharpe': sharpe
                    }
                }
                
                # Risk parity with undervalue data
                df_undervalue = df_clean.dropna(subset=['Undervalue Rate'])
                if len(df_undervalue) >= 10:
                    logger.info("  Creating undervalue risk parity portfolio...")
                    
                    # For undervalue, use same weights but calculate performance with undervalue returns
                    undervalue_returns = df_undervalue['Undervalue Rate'].values
                    undervalue_volatilities = df_undervalue['Annual_Volatility_5Y'].values
                    
                    # Create covariance matrix for undervalue stocks
                    n_undervalue = len(df_undervalue)
                    undervalue_cov = np.zeros((n_undervalue, n_undervalue))
                    for i in range(n_undervalue):
                        for j in range(n_undervalue):
                            if i == j:
                                undervalue_cov[i, j] = undervalue_volatilities[i] ** 2
                            else:
                                undervalue_cov[i, j] = correlation * undervalue_volatilities[i] * undervalue_volatilities[j]
                    
                    # Optimize risk parity for undervalue stocks
                    rp_undervalue_result = self.optimize_risk_parity(undervalue_cov)
                    weights = rp_undervalue_result['weights']
                    
                    port_return, port_volatility, sharpe = self.portfolio_performance(
                        weights, undervalue_returns, undervalue_cov
                    )
                    
                    result_df = df_undervalue.copy()
                    result_df['Weight'] = weights
                    result_df['Risk_Contribution'] = rp_undervalue_result['risk_contribution']
                    
                    significant = result_df[result_df['Weight'] > self.min_weight_threshold].copy()
                    significant = significant.sort_values('Weight', ascending=False)
                    
                    output_file = self.results_dir / f"rp_undervalue_significant_{timestamp}.csv"
                    significant.to_csv(output_file, index=False)
                    
                    full_file = self.results_dir / f"rp_undervalue_portfolio_{timestamp}.csv"
                    result_df.to_csv(full_file, index=False)
                    
                    logger.info(f"    Undervalue: {len(significant)} significant holdings")
                    
                    results['rp_undervalue'] = {
                        'status': 'success',
                        'stocks_selected': len(significant),
                        'total_stocks': len(result_df),
                        'output_file': str(output_file),
                        'full_file': str(full_file),
                        'performance': {
                            'return': port_return,
                            'volatility': port_volatility,
                            'sharpe': sharpe
                        }
                    }
            
            # Create performance comparison
            if results:
                comparison_data = []
                for model_name, model_result in results.items():
                    if 'performance' in model_result:
                        comparison_data.append({
                            'Model': model_name,
                            'Return': model_result['performance']['return'],
                            'Volatility': model_result['performance']['volatility'],
                            'Sharpe_Ratio': model_result['performance']['sharpe'],
                            'Stocks_Selected': model_result['stocks_selected']
                        })
                
                if comparison_data:
                    comparison_df = pd.DataFrame(comparison_data)
                    comparison_path = self.results_dir / f"portfolio_performance_comparison_{timestamp}.csv"
                    comparison_df.to_csv(comparison_path, index=False)
                    logger.info(f"Saved performance comparison to {comparison_path}")
            
            logger.info("Phase 3 completed successfully")
            
            return {
                "status": "success",
                "models": results,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in Phase 3: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def run_full_pipeline(self) -> Dict[str, Any]:
        """Run all phases sequentially"""
        logger.info("=" * 50)
        logger.info("RUNNING FULL PIPELINE")
        logger.info("=" * 50)
        
        results = {
            "phase1": self.run_phase1(),
            "phase2": self.run_phase2(),
            "phase3": self.run_phase3(model_type="all"),
            "timestamp": datetime.now().isoformat()
        }
        
        # Determine overall status
        all_success = all(
            phase.get("status") == "success" 
            for phase in [results["phase1"], results["phase2"], results["phase3"]]
        )
        
        results["status"] = "success" if all_success else "partial"
        
        logger.info(f"Full pipeline completed with status: {results['status']}")
        
        return results
    
    def health_check(self) -> Dict[str, Any]:
        """Check pipeline health"""
        checks = {
            "data_dir_exists": self.data_dir.exists(),
            "processed_dir_exists": self.processed_dir.exists(),
            "results_dir_exists": self.results_dir.exists(),
            "nasdaq_analysis_exists": (self.processed_dir / "nasdaq_100_analysis.csv").exists(),
            "nasdaq_returns_exists": (self.processed_dir / "nasdaq_100_with_returns.csv").exists()
        }
        
        all_healthy = all(checks.values())
        
        return {
            "status": "healthy" if all_healthy else "unhealthy",
            "checks": checks,
            "timestamp": datetime.now().isoformat()
        }


# CLI interface for testing
if __name__ == "__main__":
    import sys
    
    pipeline = SimplifiedPipeline()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "health":
            result = pipeline.health_check()
        elif command == "phase1":
            result = pipeline.run_phase1()
        elif command == "phase2":
            result = pipeline.run_phase2()
        elif command == "phase3":
            model = sys.argv[2] if len(sys.argv) > 2 else "all"
            result = pipeline.run_phase3(model_type=model)
        elif command == "full":
            result = pipeline.run_full_pipeline()
        else:
            result = {"error": f"Unknown command: {command}"}
    else:
        result = {"error": "No command provided"}
    
    print(json.dumps(result, indent=2))