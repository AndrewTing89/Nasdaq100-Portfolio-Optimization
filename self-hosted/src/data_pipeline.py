"""
Complete Production-Ready Portfolio Optimization Data Pipeline
Unified service combining all three Lambda functions for local/Docker execution

This service combines:
- NASDAQ-100 web scraping and analysis
- 5-year historical data fetching via yfinance
- Portfolio optimization (Mean-Variance, Risk Parity, Black-Litterman)

Removes all AWS dependencies and provides local file operations.
"""

import json
import os
import sys
import logging
import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import fcntl
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import pandas as pd
import numpy as np
# import yfinance as yf  # Replaced with FMP
from fmp_client import FMPClient
import requests
from bs4 import BeautifulSoup
from scipy.optimize import minimize


# ================ CONFIGURATION ================

@dataclass
class Config:
    """Configuration management for the data pipeline"""
    
    # File paths
    data_dir: Path = Path("/data")
    raw_data_dir: Path = Path("/data/raw")
    processed_data_dir: Path = Path("/data/processed")  
    stocks_data_dir: Path = Path("/data/stocks")
    results_dir: Path = Path("/data/results")
    
    # Financial parameters
    risk_free_rate: float = 0.02  # 2% risk-free rate
    min_weight_threshold: float = 0.01  # 1% minimum weight for significant holdings
    max_stocks: int = 100  # Maximum stocks to process
    
    # Optimization parameters
    risk_aversion: float = 2.5
    tau: float = 0.025
    
    # Data fetching parameters
    historical_period: str = "5y"
    request_delay: float = 1.0  # Delay between API requests
    max_retries: int = 3
    
    def __post_init__(self):
        """Create directories if they don't exist"""
        for directory in [self.data_dir, self.raw_data_dir, self.processed_data_dir, 
                         self.stocks_data_dir, self.results_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def from_env(cls) -> 'Config':
        """Create configuration from environment variables"""
        return cls(
            data_dir=Path(os.getenv('DATA_DIR', '/data')),
            risk_free_rate=float(os.getenv('RISK_FREE_RATE', '0.02')),
            min_weight_threshold=float(os.getenv('MIN_WEIGHT_THRESHOLD', '0.01')),
            max_stocks=int(os.getenv('MAX_STOCKS', '100')),
            risk_aversion=float(os.getenv('RISK_AVERSION', '2.5')),
            tau=float(os.getenv('TAU', '0.025')),
            historical_period=os.getenv('HISTORICAL_PERIOD', '5y'),
            request_delay=float(os.getenv('REQUEST_DELAY', '1.0')),
            max_retries=int(os.getenv('MAX_RETRIES', '3'))
        )


# ================ LOCAL FILE HANDLER ================

class LocalFileHandler:
    """
    Local file operations to replace S3Handler
    Handles CSV and JSON files with concurrent access protection
    """
    
    def __init__(self, config: Config):
        self.config = config
        self._file_locks = {}
        self._lock_mutex = threading.Lock()
    
    def _get_file_lock(self, file_path: Path) -> threading.Lock:
        """Get or create a file-specific lock for thread safety"""
        with self._lock_mutex:
            if str(file_path) not in self._file_locks:
                self._file_locks[str(file_path)] = threading.Lock()
            return self._file_locks[str(file_path)]
    
    def read_csv(self, file_path: Path) -> Optional[pd.DataFrame]:
        """Read CSV file with file locking"""
        try:
            if not file_path.exists():
                logging.warning(f"File does not exist: {file_path}")
                return None
            
            lock = self._get_file_lock(file_path)
            with lock:
                with open(file_path, 'r') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock for reading
                    df = pd.read_csv(file_path)
                    return df
                    
        except Exception as e:
            logging.error(f"Error reading CSV from {file_path}: {e}")
            return None
    
    def write_csv(self, df: pd.DataFrame, file_path: Path) -> bool:
        """Write CSV file with file locking"""
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            lock = self._get_file_lock(file_path)
            with lock:
                with open(file_path, 'w') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock for writing
                    df.to_csv(file_path, index=False)
            
            logging.info(f"Successfully wrote CSV to {file_path}")
            return True
            
        except Exception as e:
            logging.error(f"Error writing CSV to {file_path}: {e}")
            return False
    
    def read_json(self, file_path: Path) -> Optional[Dict]:
        """Read JSON file with file locking"""
        try:
            if not file_path.exists():
                logging.warning(f"File does not exist: {file_path}")
                return None
            
            lock = self._get_file_lock(file_path)
            with lock:
                with open(file_path, 'r') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock for reading
                    data = json.load(f)
                    return data
                    
        except Exception as e:
            logging.error(f"Error reading JSON from {file_path}: {e}")
            return None
    
    def write_json(self, data: Dict, file_path: Path) -> bool:
        """Write JSON file with file locking"""
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            lock = self._get_file_lock(file_path)
            with lock:
                with open(file_path, 'w') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock for writing
                    json.dump(data, f, indent=2, default=str)
            
            logging.info(f"Successfully wrote JSON to {file_path}")
            return True
            
        except Exception as e:
            logging.error(f"Error writing JSON to {file_path}: {e}")
            return False


# ================ NASDAQ ANALYZER ================

class NasdaqAnalyzer:
    """NASDAQ-100 components scraping and undervaluation analysis"""
    
    def __init__(self, config: Config, file_handler: LocalFileHandler):
        self.config = config
        self.file_handler = file_handler
    
    def get_nasdaq_components(self) -> List[Tuple[str, str]]:
        """Scrape NASDAQ-100 components from Wikipedia"""
        url = "https://en.wikipedia.org/wiki/Nasdaq-100"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            tables = soup.find_all('table', {'class': 'wikitable'})
            logging.info(f"Found {len(tables)} wikitables")
            
            for i, table in enumerate(tables):
                headers = [th.get_text(strip=True) for th in table.find_all('th')]
                
                if any(term in ' '.join(headers).lower() for term in ['ticker', 'symbol', 'company']):
                    company_idx = -1
                    symbol_idx = -1
                    
                    for idx, header in enumerate(headers):
                        header_lower = header.lower()
                        if 'company' in header_lower or 'name' in header_lower:
                            company_idx = idx
                        if 'symbol' in header_lower or 'ticker' in header_lower:
                            symbol_idx = idx
                    
                    if company_idx >= 0 and symbol_idx >= 0:
                        components = []
                        rows = table.find_all('tr')
                        data_rows = [row for row in rows if row.find('td')]
                        
                        for row in data_rows:
                            cells = row.find_all('td')
                            if len(cells) > max(company_idx, symbol_idx):
                                company_cell = cells[company_idx]
                                company_link = company_cell.find('a')
                                company = company_link.get_text(strip=True) if company_link else company_cell.get_text(strip=True)
                                
                                symbol_cell = cells[symbol_idx]
                                symbol_link = symbol_cell.find('a')
                                symbol = symbol_link.get_text(strip=True) if symbol_link else symbol_cell.get_text(strip=True)
                                
                                company = company.replace('\n', ' ').strip()
                                symbol = symbol.replace('\n', ' ').strip()
                                
                                if company and symbol:
                                    components.append((company, symbol))
                        
                        logging.info(f"Extracted {len(components)} components")
                        if len(components) >= 50:
                            return components
            
            # Fallback components for testing
            logging.warning("Using fallback component list")
            fallback_components = [
                ("Apple Inc.", "AAPL"), ("Microsoft Corporation", "MSFT"), ("Amazon.com Inc.", "AMZN"),
                ("NVIDIA Corporation", "NVDA"), ("Alphabet Inc. Class A", "GOOGL"), ("Meta Platforms Inc.", "META"),
                ("Tesla, Inc.", "TSLA"), ("Broadcom Inc.", "AVGO"), ("PepsiCo, Inc.", "PEP"),
                ("Costco Wholesale Corporation", "COST"), ("Advanced Micro Devices, Inc.", "AMD"),
                ("Netflix Inc.", "NFLX"), ("Adobe Inc.", "ADBE"), ("Cisco Systems, Inc.", "CSCO")
            ]
            return fallback_components
            
        except Exception as e:
            logging.error(f"Error scraping NASDAQ components: {e}")
            return []
    
    def get_stock_data(self, ticker: str) -> Tuple[Optional[float], Optional[float]]:
        """Get current price and target price for a stock using yfinance"""
        try:
            logging.debug(f"Fetching data for {ticker} using FMP API...")
            
            # Initialize FMP client
            fmp_client = FMPClient()
            quote = fmp_client.get_quote(ticker)
            estimates = fmp_client.get_analyst_estimates(ticker)
            
            # Combine quote and estimates data
            info = {}
            if quote:
                info.update(quote)
            if estimates:
                info.update(estimates)
            
            # Get previous close price
            prev_close = info.get('previousClose') or info.get('regularMarketPreviousClose')
            
            # Get analyst target price
            target_est = info.get('targetMeanPrice')
            
            if prev_close is not None:
                prev_close = float(prev_close)
            if target_est is not None:
                target_est = float(target_est)
            
            logging.debug(f"Data for {ticker} - Previous Close: {prev_close}, Target: {target_est}")
            return prev_close, target_est
            
        except Exception as e:
            logging.error(f"Error retrieving data for {ticker}: {e}")
            return None, None
    
    def calculate_undervalue_rate(self, target_est: Optional[float], prev_close: Optional[float]) -> Optional[float]:
        """Calculate undervaluation rate"""
        if target_est is not None and prev_close is not None and prev_close != 0:
            return (target_est / prev_close) - 1
        return None
    
    def analyze_nasdaq_components(self) -> Dict[str, Any]:
        """Main analysis function for NASDAQ-100 components"""
        logging.info("Starting NASDAQ-100 component analysis...")
        
        components = self.get_nasdaq_components()
        if not components:
            raise Exception("No components retrieved")
        
        logging.info(f"Successfully retrieved {len(components)} components")
        
        # Limit the number of stocks to process
        test_components = components[:self.config.max_stocks]
        logging.info(f"Processing first {len(test_components)} components")
        
        results = []
        for i, (company, symbol) in enumerate(test_components):
            logging.info(f"Processing {i+1}/{len(test_components)}: {company} ({symbol})...")
            
            for attempt in range(self.config.max_retries):
                prev_close, target_est = self.get_stock_data(symbol)
                if prev_close is not None or attempt == self.config.max_retries - 1:
                    break
                time.sleep(self.config.request_delay)
            
            undervalue_rate = self.calculate_undervalue_rate(target_est, prev_close)
            
            results.append({
                "Company": company,
                "Symbol": symbol,
                "Previous Close": prev_close,
                "1y Target Est": target_est,
                "Undervalue Rate": undervalue_rate
            })
            
            # Rate limiting
            if i < len(test_components) - 1:
                time.sleep(self.config.request_delay)
        
        # Create results DataFrame
        df_results = pd.DataFrame(results)
        
        # Save results to files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Raw results with timestamp
        raw_path = self.config.raw_data_dir / f"nasdaq_100_analysis_{timestamp}.csv"
        self.file_handler.write_csv(df_results, raw_path)
        
        # Processed results (latest)
        processed_path = self.config.processed_data_dir / "nasdaq_100_analysis.csv"
        self.file_handler.write_csv(df_results, processed_path)
        
        # Generate summary statistics
        summary = {
            "total_stocks": len(df_results),
            "timestamp": timestamp
        }
        
        if "Undervalue Rate" in df_results.columns:
            valid_df = df_results.dropna(subset=["Undervalue Rate"])
            if not valid_df.empty:
                summary.update({
                    "stocks_with_target_price": len(valid_df),
                    "mean_undervalue_rate": float(valid_df["Undervalue Rate"].mean()),
                    "median_undervalue_rate": float(valid_df["Undervalue Rate"].median()),
                    "high_potential_stocks": int(valid_df[valid_df["Undervalue Rate"] > 0.2].shape[0]),
                    "moderate_potential_stocks": int(valid_df[(valid_df["Undervalue Rate"] <= 0.2) & (valid_df["Undervalue Rate"] > 0)].shape[0]),
                    "overvalued_stocks": int(valid_df[valid_df["Undervalue Rate"] <= 0].shape[0])
                })
        
        # Save summary
        summary_path = self.config.results_dir / f"phase1_nasdaq_analysis_summary_{timestamp}.json"
        self.file_handler.write_json(summary, summary_path)
        
        logging.info(f"NASDAQ analysis completed successfully. Processed {len(results)} stocks.")
        
        return {
            "processed_stocks": len(results),
            "raw_data_path": str(raw_path),
            "processed_data_path": str(processed_path),
            "summary_path": str(summary_path),
            "summary": summary
        }


# ================ STOCK DATA FETCHER ================

class StockDataFetcher:
    """Historical stock data fetching and metrics calculation"""
    
    def __init__(self, config: Config, file_handler: LocalFileHandler):
        self.config = config
        self.file_handler = file_handler
    
    def download_stock_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Download historical stock data using FMP API"""
        try:
            # Initialize FMP client
            fmp_client = FMPClient()
            
            # Get historical data
            data = fmp_client.get_historical_data(symbol)
            
            if data is None or data.empty:
                logging.warning(f"No data found for {symbol}")
                return None
            
            # FMP returns data with date as index or column
            if 'Date' not in data.columns and 'date' not in data.columns:
                data.reset_index(inplace=True)
            
            # Rename columns to match expected format
            column_mapping = {
                'date': 'Date',
                'open': 'Open', 
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            }
            data.rename(columns=column_mapping, inplace=True)
            
            # Ensure we have required columns
            required_columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            if not all(col in data.columns for col in required_columns):
                available_cols = list(data.columns)
                logging.warning(f"Missing required columns for {symbol}. Available: {available_cols}")
                return None
            
            # Sort by date ascending (FMP returns descending)
            data['Date'] = pd.to_datetime(data['Date'])
            data.sort_values('Date', inplace=True)
            data.reset_index(drop=True, inplace=True)
            
            return data[required_columns]
            
        except Exception as e:
            logging.error(f"Error downloading data for {symbol}: {e}")
            return None
    
    def calculate_metrics(self, stock_data: pd.DataFrame) -> Dict[str, Any]:
        """Calculate annual return and volatility from stock data"""
        try:
            # Calculate daily returns
            stock_data['Daily_Return'] = stock_data['Close'].pct_change()
            returns = stock_data['Daily_Return'].dropna()
            
            if len(returns) < 252:  # Need at least one year of data
                return {"error": f"Insufficient data: only {len(returns)} trading days"}
            
            # Calculate annualized return and volatility
            annual_return = returns.mean() * 252
            annual_volatility = returns.std() * np.sqrt(252)
            
            return {
                "Annual_Return_5Y": float(annual_return),
                "Annual_Volatility_5Y": float(annual_volatility),
                "data_points": len(returns)
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def process_stock_list(self, stock_list_path: Optional[Path] = None) -> Dict[str, Any]:
        """Process stock list and download/calculate metrics for each stock"""
        
        # Determine input file path
        if stock_list_path is None:
            stock_list_path = self.config.processed_data_dir / "nasdaq_100_analysis.csv"
        
        logging.info(f"Loading stock list from {stock_list_path}")
        stock_df = self.file_handler.read_csv(stock_list_path)
        
        if stock_df is None:
            raise Exception(f"Could not load stock list from {stock_list_path}")
        
        if 'Symbol' not in stock_df.columns:
            raise Exception("Stock list must contain 'Symbol' column")
        
        # Prepare new columns for metrics
        if "Annual_Return_5Y" not in stock_df.columns:
            stock_df["Annual_Return_5Y"] = np.nan
        if "Annual_Volatility_5Y" not in stock_df.columns:
            stock_df["Annual_Volatility_5Y"] = np.nan
        
        # Limit stocks to process
        stock_df_subset = stock_df.head(self.config.max_stocks)
        logging.info(f"Processing {len(stock_df_subset)} stocks...")
        
        processed_count = 0
        failed_stocks = []
        individual_stock_data = {}
        
        # Use ThreadPoolExecutor for concurrent downloads
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all download tasks
            future_to_symbol = {
                executor.submit(self.download_stock_data, row['Symbol']): (i, row['Symbol'])
                for i, row in stock_df_subset.iterrows()
            }
            
            for future in future_to_symbol:
                i, symbol = future_to_symbol[future]
                
                try:
                    stock_data = future.result(timeout=60)  # 60 second timeout
                    
                    if stock_data is None:
                        logging.warning(f"Failed to download data for {symbol}")
                        failed_stocks.append(symbol)
                        continue
                    
                    # Calculate metrics
                    metrics = self.calculate_metrics(stock_data)
                    
                    if "error" in metrics:
                        logging.warning(f"Calculation failed for {symbol}: {metrics['error']}")
                        failed_stocks.append(symbol)
                        continue
                    
                    # Update the main dataframe
                    stock_df.loc[i, "Annual_Return_5Y"] = metrics["Annual_Return_5Y"]
                    stock_df.loc[i, "Annual_Volatility_5Y"] = metrics["Annual_Volatility_5Y"]
                    
                    # Store individual stock data
                    individual_stock_data[symbol] = stock_data
                    
                    logging.info(f"Success for {symbol}: Return={metrics['Annual_Return_5Y']:.4f}, Volatility={metrics['Annual_Volatility_5Y']:.4f}")
                    processed_count += 1
                    
                except Exception as e:
                    logging.error(f"Error processing {symbol}: {e}")
                    failed_stocks.append(symbol)
        
        # Save individual stock data files
        logging.info("Saving individual stock data files...")
        for symbol, data in individual_stock_data.items():
            stock_path = self.config.stocks_data_dir / f"{symbol}.csv"
            self.file_handler.write_csv(data, stock_path)
        
        # Save updated stock list with metrics
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Raw results with timestamp
        raw_path = self.config.raw_data_dir / f"nasdaq_100_with_returns_{timestamp}.csv"
        self.file_handler.write_csv(stock_df, raw_path)
        
        # Processed results (latest)
        processed_path = self.config.processed_data_dir / "nasdaq_100_with_returns.csv"
        self.file_handler.write_csv(stock_df, processed_path)
        
        # Create summary statistics
        stocks_with_data = stock_df[stock_df["Annual_Return_5Y"].notnull()]
        
        summary = {
            "total_stocks": len(stock_df),
            "successfully_processed": processed_count,
            "failed_stocks": len(failed_stocks),
            "failed_stock_list": failed_stocks,
            "timestamp": timestamp
        }
        
        if len(stocks_with_data) > 0:
            summary.update({
                "mean_annual_return": float(stocks_with_data["Annual_Return_5Y"].mean()),
                "median_annual_return": float(stocks_with_data["Annual_Return_5Y"].median()),
                "mean_annual_volatility": float(stocks_with_data["Annual_Volatility_5Y"].mean()),
                "median_annual_volatility": float(stocks_with_data["Annual_Volatility_5Y"].median()),
                "top_performers": stocks_with_data.nlargest(10, "Annual_Return_5Y")[["Symbol", "Annual_Return_5Y"]].to_dict('records'),
                "most_volatile": stocks_with_data.nlargest(10, "Annual_Volatility_5Y")[["Symbol", "Annual_Volatility_5Y"]].to_dict('records')
            })
        
        # Save summary
        summary_path = self.config.results_dir / f"phase2_stock_metrics_summary_{timestamp}.json"
        self.file_handler.write_json(summary, summary_path)
        
        logging.info(f"Stock data processing completed. Processed {processed_count} stocks.")
        
        return {
            "processed_stocks": processed_count,
            "failed_stocks": len(failed_stocks),
            "raw_data_path": str(raw_path),
            "processed_data_path": str(processed_path),
            "summary_path": str(summary_path),
            "individual_files_uploaded": len(individual_stock_data),
            "summary": summary
        }


# ================ PORTFOLIO OPTIMIZER ================

class PortfolioOptimizer:
    """Portfolio optimization with multiple models"""
    
    def __init__(self, config: Config, file_handler: LocalFileHandler):
        self.config = config
        self.file_handler = file_handler
    
    def calculate_covariance_matrix(self, stock_symbols: List[str]) -> Tuple[np.ndarray, List[str]]:
        """Calculate covariance matrix from individual stock data files"""
        daily_returns = {}
        
        # Read daily returns for each stock
        for symbol in stock_symbols:
            try:
                stock_path = self.config.stocks_data_dir / f"{symbol}.csv"
                stock_data = self.file_handler.read_csv(stock_path)
                
                if stock_data is None:
                    logging.warning(f"Could not load data for {symbol}, skipping...")
                    continue
                
                # Ensure Date column is datetime
                stock_data['Date'] = pd.to_datetime(stock_data['Date'])
                stock_data.set_index('Date', inplace=True)
                stock_data.sort_index(inplace=True)
                
                # Calculate daily returns
                returns = stock_data['Close'].pct_change().dropna()
                daily_returns[symbol] = returns
                
            except Exception as e:
                logging.error(f"Error processing {symbol}: {e}")
        
        # Create DataFrame with all returns
        returns_df = pd.DataFrame(daily_returns)
        
        # Calculate annualized covariance matrix
        cov_matrix = returns_df.cov() * 252
        
        return cov_matrix.values, list(daily_returns.keys())
    
    def portfolio_performance(self, weights: np.ndarray, returns: np.ndarray, cov_matrix: np.ndarray) -> Tuple[float, float, float]:
        """Calculate portfolio performance metrics"""
        portfolio_return = np.sum(returns * weights)
        portfolio_volatility = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        sharpe_ratio = (portfolio_return - self.config.risk_free_rate) / portfolio_volatility
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
                       P: np.ndarray, Q: np.ndarray, Omega: np.ndarray) -> np.ndarray:
        """Black-Litterman model implementation"""
        # Calculate implied returns
        implied_returns = self.config.risk_aversion * np.dot(cov_matrix, market_weights)
        
        # Apply Black-Litterman formula
        precision_prior = np.linalg.inv(self.config.tau * cov_matrix)
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
        
        # View 3: AI-driven companies will outperform
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
    
    def optimize_bl_portfolio(self, expected_returns: np.ndarray, cov_matrix: np.ndarray) -> np.ndarray:
        """Optimize portfolio based on Black-Litterman expected returns"""
        n_assets = len(expected_returns)
        
        def objective(weights):
            portfolio_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
            portfolio_return = np.dot(weights.T, expected_returns)
            return portfolio_variance - (1/self.config.risk_aversion) * portfolio_return
        
        initial_weights = np.ones(n_assets) / n_assets
        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
        bounds = tuple((0, 1) for _ in range(n_assets))
        
        result = minimize(objective, initial_weights, method='SLSQP', bounds=bounds, constraints=constraints)
        return result['x']
    
    def run_portfolio_optimization(self, input_file_path: Optional[Path] = None, 
                                  model_type: str = 'all', return_type: str = 'both') -> Dict[str, Any]:
        """Main portfolio optimization function"""
        
        # Determine input file path
        if input_file_path is None:
            input_file_path = self.config.processed_data_dir / "nasdaq_100_with_returns.csv"
        
        logging.info(f"Loading stock data from {input_file_path}")
        stocks_data = self.file_handler.read_csv(input_file_path)
        
        if stocks_data is None:
            raise Exception(f"Could not load stock data from {input_file_path}")
        
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
        
        logging.info(f"Processing {len(valid_data)} stocks with valid data")
        
        if len(valid_data) < 2:
            raise Exception("Not enough stocks with valid data for portfolio optimization")
        
        # Calculate covariance matrix
        logging.info("Calculating covariance matrix from stock data...")
        stock_symbols = valid_data['Symbol'].tolist()
        cov_matrix, available_symbols = self.calculate_covariance_matrix(stock_symbols)
        
        # Filter to stocks with covariance data
        filtered_data = valid_data[valid_data['Symbol'].isin(available_symbols)].copy()
        filtered_data = filtered_data.reset_index(drop=True)
        
        logging.info(f"Running optimization with {len(filtered_data)} stocks")
        
        # Prepare results
        results = {}
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Mean-Variance optimization
        if model_type in ['mv', 'all']:
            logging.info("Running Mean-Variance optimization...")
            
            for ret_type in (['historical', 'undervalue'] if return_type == 'both' else [return_type]):
                if ret_type == 'undervalue' and not has_undervalue:
                    continue
                    
                returns = (filtered_data['Annual_Return_5Y'].values if ret_type == 'historical' 
                          else filtered_data['Undervalue Rate'].values)
                
                mv_result = self.optimize_mean_variance_portfolio(returns, cov_matrix)
                
                # Save results
                for portfolio_type in ['max_sharpe', 'min_vol']:
                    weights = mv_result[f'{portfolio_type}_weights']
                    
                    result_df = filtered_data.copy()
                    result_df['Weight'] = weights
                    
                    # Save full results
                    results_path = self.config.results_dir / f"mv_{ret_type}_{portfolio_type}_portfolio_{timestamp}.csv"
                    self.file_handler.write_csv(result_df, results_path)
                    
                    # Save significant holdings
                    significant = result_df[result_df['Weight'] > self.config.min_weight_threshold].sort_values('Weight', ascending=False)
                    significant_path = self.config.results_dir / f"mv_{ret_type}_{portfolio_type}_significant_{timestamp}.csv"
                    self.file_handler.write_csv(significant, significant_path)
                    
                    results[f'mv_{ret_type}_{portfolio_type}'] = {
                        'weights': weights.tolist(),
                        'performance': mv_result[f'{portfolio_type}_performance'],
                        'full_results_path': str(results_path),
                        'significant_holdings_path': str(significant_path)
                    }
        
        # Risk Parity optimization
        if model_type in ['rp', 'all']:
            logging.info("Running Risk Parity optimization...")
            
            for ret_type in (['historical', 'undervalue'] if return_type == 'both' else [return_type]):
                if ret_type == 'undervalue' and not has_undervalue:
                    continue
                    
                returns = (filtered_data['Annual_Return_5Y'].values if ret_type == 'historical' 
                          else filtered_data['Undervalue Rate'].values)
                
                rp_result = self.optimize_risk_parity(cov_matrix)
                
                # Calculate performance
                port_return, port_volatility, sharpe = self.portfolio_performance(
                    rp_result['weights'], returns, cov_matrix
                )
                
                result_df = filtered_data.copy()
                result_df['Weight'] = rp_result['weights']
                result_df['Risk_Contribution'] = rp_result['risk_contribution']
                
                # Save full results
                results_path = self.config.results_dir / f"rp_{ret_type}_portfolio_{timestamp}.csv"
                self.file_handler.write_csv(result_df, results_path)
                
                # Save significant holdings
                significant = result_df[result_df['Weight'] > self.config.min_weight_threshold].sort_values('Weight', ascending=False)
                significant_path = self.config.results_dir / f"rp_{ret_type}_significant_{timestamp}.csv"
                self.file_handler.write_csv(significant, significant_path)
                
                results[f'rp_{ret_type}'] = {
                    'weights': rp_result['weights'].tolist(),
                    'performance': {
                        'return': port_return,
                        'volatility': port_volatility,
                        'sharpe': sharpe
                    },
                    'full_results_path': str(results_path),
                    'significant_holdings_path': str(significant_path),
                    'optimization_success': rp_result['success']
                }
        
        # Black-Litterman optimization
        if model_type in ['bl', 'all']:
            logging.info("Running Black-Litterman optimization...")
            
            # Use MV max sharpe weights as market equilibrium
            historical_returns = filtered_data['Annual_Return_5Y'].values
            mv_result = self.optimize_mean_variance_portfolio(historical_returns, cov_matrix)
            market_weights = mv_result['max_sharpe_weights']
            
            for ret_type in (['historical', 'undervalue', 'both'] if return_type == 'both' else [return_type]):
                if ret_type == 'undervalue' and not has_undervalue:
                    continue
                    
                P, Q, Omega = self.form_views(filtered_data, cov_matrix, ret_type)
                bl_returns = self.black_litterman(market_weights, cov_matrix, P, Q, Omega)
                bl_weights = self.optimize_bl_portfolio(bl_returns, cov_matrix)
                
                # Calculate performance
                port_return, port_volatility, sharpe = self.portfolio_performance(
                    bl_weights, bl_returns, cov_matrix
                )
                
                result_df = filtered_data.copy()
                result_df['Weight'] = bl_weights
                result_df['BL_Expected_Return'] = bl_returns
                
                # Save full results
                results_path = self.config.results_dir / f"bl_{ret_type}_portfolio_{timestamp}.csv"
                self.file_handler.write_csv(result_df, results_path)
                
                # Save significant holdings
                significant = result_df[result_df['Weight'] > self.config.min_weight_threshold].sort_values('Weight', ascending=False)
                significant_path = self.config.results_dir / f"bl_{ret_type}_significant_{timestamp}.csv"
                self.file_handler.write_csv(significant, significant_path)
                
                results[f'bl_{ret_type}'] = {
                    'weights': bl_weights.tolist(),
                    'performance': {
                        'return': port_return,
                        'volatility': port_volatility,
                        'sharpe': sharpe
                    },
                    'full_results_path': str(results_path),
                    'significant_holdings_path': str(significant_path)
                }
        
        # Create performance comparison
        performance_comparison = []
        for model_name, model_result in results.items():
            performance_comparison.append({
                'Model': model_name,
                'Return': model_result['performance']['return'],
                'Volatility': model_result['performance']['volatility'],
                'Sharpe_Ratio': model_result['performance']['sharpe']
            })
        
        comparison_df = pd.DataFrame(performance_comparison)
        comparison_path = self.config.results_dir / f"portfolio_performance_comparison_{timestamp}.csv"
        self.file_handler.write_csv(comparison_df, comparison_path)
        
        # Create recommended portfolio (average of all models)
        if len(results) > 1:
            avg_weights = np.zeros(len(filtered_data))
            for model_result in results.values():
                avg_weights += np.array(model_result['weights'])
            avg_weights /= len(results)
            
            recommended_df = filtered_data.copy()
            recommended_df['Weight'] = avg_weights
            
            recommended_path = self.config.results_dir / f"recommended_portfolio_{timestamp}.csv"
            self.file_handler.write_csv(recommended_df, recommended_path)
            
            # Significant holdings
            significant_rec = recommended_df[recommended_df['Weight'] > self.config.min_weight_threshold].sort_values('Weight', ascending=False)
            significant_rec_path = self.config.results_dir / f"recommended_portfolio_significant_{timestamp}.csv"
            self.file_handler.write_csv(significant_rec, significant_rec_path)
            
            results['recommended'] = {
                'weights': avg_weights.tolist(),
                'full_results_path': str(recommended_path),
                'significant_holdings_path': str(significant_rec_path)
            }
        
        logging.info(f"Portfolio optimization completed successfully")
        
        return {
            'models_run': list(results.keys()),
            'total_stocks_analyzed': len(filtered_data),
            'comparison_results_path': str(comparison_path),
            'results': results,
            'timestamp': timestamp
        }


# ================ MAIN DATA PIPELINE ================

class DataPipeline:
    """Main data pipeline orchestrating all components"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.from_env()
        self.file_handler = LocalFileHandler(self.config)
        self.nasdaq_analyzer = NasdaqAnalyzer(self.config, self.file_handler)
        self.stock_fetcher = StockDataFetcher(self.config, self.file_handler)
        self.portfolio_optimizer = PortfolioOptimizer(self.config, self.file_handler)
        
        # Setup logging
        self.setup_logging()
    
    def setup_logging(self):
        """Setup comprehensive logging"""
        log_dir = self.config.data_dir / "logs"
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Reduce yfinance logging verbosity
        logging.getLogger('yfinance').setLevel(logging.WARNING)
    
    def health_check(self) -> Dict[str, Any]:
        """Health check endpoint"""
        try:
            # Check directories
            directories_ok = all(d.exists() for d in [
                self.config.data_dir, self.config.raw_data_dir,
                self.config.processed_data_dir, self.config.stocks_data_dir,
                self.config.results_dir
            ])
            
            # Check internet connectivity
            try:
                response = requests.get("https://httpbin.org/ip", timeout=10)
                internet_ok = response.status_code == 200
            except:
                internet_ok = False
            
            return {
                "status": "healthy" if directories_ok and internet_ok else "degraded",
                "directories_ok": directories_ok,
                "internet_ok": internet_ok,
                "timestamp": datetime.now().isoformat(),
                "config": {
                    "data_dir": str(self.config.data_dir),
                    "max_stocks": self.config.max_stocks,
                    "risk_free_rate": self.config.risk_free_rate
                }
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def run_phase1_nasdaq_analysis(self) -> Dict[str, Any]:
        """Phase 1: NASDAQ-100 component analysis"""
        logging.info("=" * 50)
        logging.info("STARTING PHASE 1: NASDAQ-100 ANALYSIS")
        logging.info("=" * 50)
        
        try:
            result = self.nasdaq_analyzer.analyze_nasdaq_components()
            logging.info(f"Phase 1 completed successfully: {result['processed_stocks']} stocks processed")
            return {"status": "success", "phase": 1, "result": result}
        except Exception as e:
            logging.error(f"Phase 1 failed: {e}")
            return {"status": "error", "phase": 1, "error": str(e)}
    
    def run_phase2_stock_data_fetching(self, input_file: Optional[str] = None) -> Dict[str, Any]:
        """Phase 2: Historical stock data fetching"""
        logging.info("=" * 50)
        logging.info("STARTING PHASE 2: STOCK DATA FETCHING")
        logging.info("=" * 50)
        
        try:
            input_path = Path(input_file) if input_file else None
            result = self.stock_fetcher.process_stock_list(input_path)
            logging.info(f"Phase 2 completed successfully: {result['processed_stocks']} stocks processed")
            return {"status": "success", "phase": 2, "result": result}
        except Exception as e:
            logging.error(f"Phase 2 failed: {e}")
            return {"status": "error", "phase": 2, "error": str(e)}
    
    def run_phase3_portfolio_optimization(self, input_file: Optional[str] = None, 
                                         model_type: str = 'all', return_type: str = 'both') -> Dict[str, Any]:
        """Phase 3: Portfolio optimization"""
        logging.info("=" * 50)
        logging.info("STARTING PHASE 3: PORTFOLIO OPTIMIZATION")
        logging.info("=" * 50)
        
        try:
            input_path = Path(input_file) if input_file else None
            result = self.portfolio_optimizer.run_portfolio_optimization(input_path, model_type, return_type)
            logging.info(f"Phase 3 completed successfully: {len(result['models_run'])} models executed")
            return {"status": "success", "phase": 3, "result": result}
        except Exception as e:
            logging.error(f"Phase 3 failed: {e}")
            return {"status": "error", "phase": 3, "error": str(e)}
    
    def run_full_pipeline(self, model_type: str = 'all', return_type: str = 'both') -> Dict[str, Any]:
        """Run the complete data pipeline"""
        logging.info("=" * 60)
        logging.info("STARTING COMPLETE PORTFOLIO OPTIMIZATION PIPELINE")
        logging.info("=" * 60)
        
        pipeline_start = datetime.now()
        results = {"pipeline_start": pipeline_start.isoformat()}
        
        try:
            # Phase 1: NASDAQ Analysis
            phase1_result = self.run_phase1_nasdaq_analysis()
            results["phase1"] = phase1_result
            
            if phase1_result["status"] != "success":
                raise Exception(f"Phase 1 failed: {phase1_result.get('error')}")
            
            # Phase 2: Stock Data Fetching
            phase2_result = self.run_phase2_stock_data_fetching()
            results["phase2"] = phase2_result
            
            if phase2_result["status"] != "success":
                raise Exception(f"Phase 2 failed: {phase2_result.get('error')}")
            
            # Phase 3: Portfolio Optimization
            phase3_result = self.run_phase3_portfolio_optimization(
                model_type=model_type, return_type=return_type
            )
            results["phase3"] = phase3_result
            
            if phase3_result["status"] != "success":
                raise Exception(f"Phase 3 failed: {phase3_result.get('error')}")
            
            pipeline_end = datetime.now()
            pipeline_duration = (pipeline_end - pipeline_start).total_seconds()
            
            results.update({
                "status": "success",
                "pipeline_end": pipeline_end.isoformat(),
                "duration_seconds": pipeline_duration,
                "summary": {
                    "stocks_analyzed": phase1_result["result"]["processed_stocks"],
                    "stocks_with_data": phase2_result["result"]["processed_stocks"],
                    "optimization_models": len(phase3_result["result"]["models_run"]),
                    "final_portfolios": phase3_result["result"]["models_run"]
                }
            })
            
            # Save pipeline summary
            summary_path = self.config.results_dir / f"pipeline_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            self.file_handler.write_json(results, summary_path)
            results["summary_path"] = str(summary_path)
            
            logging.info("=" * 60)
            logging.info("PIPELINE COMPLETED SUCCESSFULLY!")
            logging.info(f"Duration: {pipeline_duration:.2f} seconds")
            logging.info(f"Summary saved to: {summary_path}")
            logging.info("=" * 60)
            
            return results
            
        except Exception as e:
            pipeline_end = datetime.now()
            pipeline_duration = (pipeline_end - pipeline_start).total_seconds()
            
            results.update({
                "status": "error",
                "pipeline_end": pipeline_end.isoformat(),
                "duration_seconds": pipeline_duration,
                "error": str(e)
            })
            
            logging.error("=" * 60)
            logging.error("PIPELINE FAILED!")
            logging.error(f"Error: {e}")
            logging.error(f"Duration before failure: {pipeline_duration:.2f} seconds")
            logging.error("=" * 60)
            
            return results


# ================ CLI INTERFACE ================

def main():
    """Command-line interface for the data pipeline"""
    parser = argparse.ArgumentParser(description='Portfolio Optimization Data Pipeline')
    
    # Command selection
    parser.add_argument('command', choices=['health', 'phase1', 'phase2', 'phase3', 'full'],
                       help='Command to execute')
    
    # Optional parameters
    parser.add_argument('--input-file', type=str, help='Input file path for phases 2 and 3')
    parser.add_argument('--model-type', choices=['mv', 'rp', 'bl', 'all'], default='all',
                       help='Optimization model type (default: all)')
    parser.add_argument('--return-type', choices=['historical', 'undervalue', 'both'], default='both',
                       help='Return type for optimization (default: both)')
    parser.add_argument('--config-file', type=str, help='Configuration file path')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], default='INFO',
                       help='Logging level (default: INFO)')
    
    args = parser.parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    try:
        # Initialize pipeline
        config = Config.from_env()
        pipeline = DataPipeline(config)
        
        # Execute command
        if args.command == 'health':
            result = pipeline.health_check()
            
        elif args.command == 'phase1':
            result = pipeline.run_phase1_nasdaq_analysis()
            
        elif args.command == 'phase2':
            result = pipeline.run_phase2_stock_data_fetching(args.input_file)
            
        elif args.command == 'phase3':
            result = pipeline.run_phase3_portfolio_optimization(
                args.input_file, args.model_type, args.return_type
            )
            
        elif args.command == 'full':
            result = pipeline.run_full_pipeline(args.model_type, args.return_type)
        
        # Output result
        print(json.dumps(result, indent=2, default=str))
        
        # Exit with appropriate code
        exit_code = 0 if result.get('status') in ['success', 'healthy'] else 1
        sys.exit(exit_code)
        
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        print(json.dumps({"status": "error", "error": str(e)}, indent=2))
        sys.exit(1)


# ================ SCHEDULER SUPPORT ================

class PipelineScheduler:
    """Scheduler for automated pipeline execution"""
    
    def __init__(self, config: Config):
        self.config = config
        self.pipeline = DataPipeline(config)
    
    def schedule_daily(self, hour: int = 6, minute: int = 0):
        """Schedule daily pipeline execution (placeholder for cron integration)"""
        # This would integrate with system cron or container scheduler
        schedule_time = f"{hour:02d}:{minute:02d}"
        logging.info(f"Pipeline would be scheduled for daily execution at {schedule_time}")
        
        # Example cron entry:
        cron_command = f"{minute} {hour} * * * /usr/local/bin/python /app/data_pipeline.py full >> /data/logs/cron.log 2>&1"
        
        return {
            "schedule": "daily",
            "time": schedule_time,
            "cron_command": cron_command
        }
    
    def run_scheduled(self):
        """Execute pipeline as scheduled task"""
        logging.info("Executing scheduled pipeline run...")
        result = self.pipeline.run_full_pipeline()
        
        # Log execution result
        status = "SUCCESS" if result.get('status') == 'success' else "FAILED"
        logging.info(f"Scheduled execution {status}")
        
        return result


# ================ MODULE ENTRY POINTS ================

if __name__ == "__main__":
    main()