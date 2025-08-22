#!/usr/bin/env python3
"""
Financial Modeling Prep (FMP) API Client
Replaces yfinance for more reliable data fetching
"""

import requests
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime, timedelta
import time
import os

class FMPClient:
    """Client for Financial Modeling Prep API"""
    
    def __init__(self, api_key: str = None):
        """
        Initialize FMP client
        
        Args:
            api_key: FMP API key (or set FMP_API_KEY environment variable)
        """
        self.api_key = api_key or os.environ.get('FMP_API_KEY', 'USIa8HA0z2NCAdBwL1ZEHnpMaxe73DF8')
        self.base_url = "https://financialmodelingprep.com/api/v3"
        self.session = requests.Session()
        self.rate_limit_delay = 1.0  # 1 second between requests to avoid rate limits
        
    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Any]:
        """Make API request with error handling"""
        if params is None:
            params = {}
        params['apikey'] = self.api_key
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            # Rate limiting
            time.sleep(self.rate_limit_delay)
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for API errors
            if isinstance(data, dict) and 'Error Message' in data:
                logging.error(f"FMP API error: {data['Error Message']}")
                return None
                
            return data
            
        except requests.exceptions.RequestException as e:
            logging.error(f"FMP request failed for {endpoint}: {e}")
            return None
    
    def get_nasdaq100_constituents(self) -> pd.DataFrame:
        """Get NASDAQ-100 constituent list"""
        # FMP endpoint for NASDAQ-100 constituents
        endpoint = "index/constituents"
        params = {"symbol": "^NDX"}  # NASDAQ-100 index
        
        data = self._make_request(endpoint, params)
        
        if not data:
            # Fallback to S&P 500 if NASDAQ-100 not available
            logging.warning("NASDAQ-100 constituents not available, using tech stocks from S&P 500")
            params = {"symbol": "^GSPC"}
            data = self._make_request(endpoint, params)
        
        if data:
            df = pd.DataFrame(data)
            # Filter for tech/growth stocks if using S&P 500
            if 'sector' in df.columns:
                tech_sectors = ['Technology', 'Communication Services', 'Consumer Discretionary']
                df = df[df['sector'].isin(tech_sectors)].head(100)
            return df
        
        # Ultimate fallback - hardcoded top NASDAQ stocks
        logging.warning("Using hardcoded NASDAQ-100 list")
        nasdaq_100 = [
            "AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "GOOG", "TSLA", "AVGO", "PEP",
            "COST", "ADBE", "CSCO", "CMCSA", "NFLX", "TMUS", "TXN", "INTC", "AMD", "QCOM",
            "HON", "INTU", "AMGN", "AMAT", "SBUX", "ISRG", "BKNG", "ADP", "MDLZ", "ADI"
        ]
        return pd.DataFrame({"symbol": nasdaq_100[:30]})
    
    def get_quote(self, symbol: str) -> Optional[Dict]:
        """Get real-time quote for a symbol"""
        endpoint = f"quote/{symbol}"
        data = self._make_request(endpoint)
        
        if data and len(data) > 0:
            return data[0]
        return None
    
    def get_company_profile(self, symbol: str) -> Optional[Dict]:
        """Get company profile including sector, industry, description"""
        endpoint = f"profile/{symbol}"
        data = self._make_request(endpoint)
        
        if data and len(data) > 0:
            return data[0]
        return None
    
    def get_key_metrics(self, symbol: str) -> Optional[Dict]:
        """Get key financial metrics including P/E ratio, market cap, etc."""
        endpoint = f"key-metrics/{symbol}"
        params = {"limit": 1}
        data = self._make_request(endpoint, params)
        
        if data and len(data) > 0:
            return data[0]
        return None
    
    def get_financial_ratios(self, symbol: str) -> Optional[Dict]:
        """Get financial ratios for valuation analysis"""
        endpoint = f"ratios/{symbol}"
        params = {"limit": 1}
        data = self._make_request(endpoint, params)
        
        if data and len(data) > 0:
            return data[0]
        return None
    
    def get_historical_prices(self, symbol: str, days: int = 365*5) -> Optional[pd.DataFrame]:
        """
        Get historical price data
        
        Args:
            symbol: Stock ticker
            days: Number of days of history (default 5 years)
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        endpoint = f"historical-price-full/{symbol}"
        params = {
            "from": start_date.strftime("%Y-%m-%d"),
            "to": end_date.strftime("%Y-%m-%d")
        }
        
        data = self._make_request(endpoint, params)
        
        if data and 'historical' in data:
            df = pd.DataFrame(data['historical'])
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            return df
            
        return None
    
    def calculate_returns_metrics(self, df: pd.DataFrame) -> Dict:
        """Calculate return metrics from price data"""
        if df is None or df.empty:
            return {
                'annual_return': np.nan,
                'volatility': np.nan,
                'sharpe_ratio': np.nan,
                'max_drawdown': np.nan
            }
        
        # Calculate daily returns
        df['returns'] = df['close'].pct_change()
        
        # Annual return (geometric mean)
        total_return = (df['close'].iloc[-1] / df['close'].iloc[0]) - 1
        years = len(df) / 252  # Trading days
        annual_return = (1 + total_return) ** (1/years) - 1 if years > 0 else 0
        
        # Volatility (annualized)
        volatility = df['returns'].std() * np.sqrt(252)
        
        # Sharpe ratio (assuming 2% risk-free rate)
        risk_free_rate = 0.02
        sharpe_ratio = (annual_return - risk_free_rate) / volatility if volatility > 0 else 0
        
        # Maximum drawdown
        cumulative = (1 + df['returns']).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()
        
        return {
            'annual_return': annual_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown
        }
    
    def get_stock_analysis(self, symbol: str) -> Dict:
        """
        Get comprehensive stock analysis
        
        Returns dict with all relevant data for the stock
        """
        result = {
            'symbol': symbol,
            'company_name': '',
            'price': np.nan,
            'market_cap': np.nan,
            'pe_ratio': np.nan,
            'peg_ratio': np.nan,
            'price_to_book': np.nan,
            'dividend_yield': np.nan,
            'sector': '',
            'industry': '',
            'beta': np.nan,
            'undervalued': False,
            'undervalue_score': 0.0
        }
        
        # Get quote data
        quote = self.get_quote(symbol)
        if quote:
            result['price'] = quote.get('price', np.nan)
            result['market_cap'] = quote.get('marketCap', np.nan)
            result['pe_ratio'] = quote.get('pe', np.nan)
            
        # Get company profile
        profile = self.get_company_profile(symbol)
        if profile:
            result['company_name'] = profile.get('companyName', '')
            result['sector'] = profile.get('sector', '')
            result['industry'] = profile.get('industry', '')
            result['beta'] = profile.get('beta', np.nan)
            
        # Get key metrics
        metrics = self.get_key_metrics(symbol)
        if metrics:
            result['peg_ratio'] = metrics.get('pegRatio', np.nan)
            result['price_to_book'] = metrics.get('priceToBookRatio', np.nan)
            result['dividend_yield'] = metrics.get('dividendYield', np.nan)
            
        # Calculate undervaluation score
        result['undervalue_score'] = self._calculate_undervalue_score(result)
        result['undervalued'] = result['undervalue_score'] > 0.5
        
        # Get historical data for return metrics
        historical = self.get_historical_prices(symbol, days=365*5)
        if historical is not None:
            returns = self.calculate_returns_metrics(historical)
            result.update(returns)
        
        return result
    
    def get_analyst_estimates(self, symbol: str) -> Optional[Dict]:
        """Get analyst price targets and estimates using v4 API for better data"""
        # Try v4 consensus endpoint first (has aggregated data)
        v4_base = "https://financialmodelingprep.com/api/v4"
        consensus_url = f"{v4_base}/price-target-consensus?symbol={symbol}&apikey={self.api_key}"
        
        consensus_data = None
        analyst_count = 0
        
        try:
            response = self.session.get(consensus_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    consensus_data = data[0]
        except Exception as e:
            logging.warning(f"V4 consensus API failed for {symbol}: {e}")
        
        # Get individual analyst reports for count
        target_url = f"{v4_base}/price-target?symbol={symbol}&apikey={self.api_key}"
        try:
            response = self.session.get(target_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    analyst_count = len(data)
        except Exception as e:
            logging.warning(f"V4 price-target API failed for {symbol}: {e}")
        
        # If we have v4 data, use it
        if consensus_data:
            result = {
                'targetMeanPrice': consensus_data.get('targetConsensus'),
                'targetHighPrice': consensus_data.get('targetHigh'),
                'targetLowPrice': consensus_data.get('targetLow'),
                'targetMedianPrice': consensus_data.get('targetMedian'),
                'numberOfAnalystOpinions': analyst_count if analyst_count > 0 else 1,
                'targetDispersion': (consensus_data.get('targetHigh', 0) - consensus_data.get('targetLow', 0)) / consensus_data.get('targetConsensus', 1) if consensus_data.get('targetConsensus') else 0
            }
            # Filter out None values
            return {k: v for k, v in result.items() if v is not None}
        
        # Fallback to v3 endpoint
        endpoint = f"analyst-price-target/{symbol}"
        data = self._make_request(endpoint)
        
        if data and len(data) > 0:
            # Aggregate analyst data
            targets = [d.get('priceTarget', 0) for d in data if d.get('priceTarget')]
            if targets:
                return {
                    'targetMeanPrice': np.mean(targets),
                    'targetHighPrice': max(targets),
                    'targetLowPrice': min(targets),
                    'numberOfAnalystOpinions': len(targets)
                }
        
        # Final fallback to DCF valuation
        dcf_endpoint = f"discounted-cash-flow/{symbol}"
        dcf_data = self._make_request(dcf_endpoint)
        if dcf_data and len(dcf_data) > 0:
            return {
                'targetMeanPrice': dcf_data[0].get('dcf'),
                'numberOfAnalystOpinions': 1
            }
        
        return {}
    
    def get_historical_data(self, symbol: str, period: str = "5y") -> Optional[pd.DataFrame]:
        """
        Get historical price data (alias for compatibility)
        
        Args:
            symbol: Stock ticker  
            period: Time period (ignored, always returns 5 years)
        """
        return self.get_historical_prices(symbol, days=365*5)
    
    def _calculate_undervalue_score(self, data: Dict) -> float:
        """
        Calculate undervaluation score based on multiple metrics
        
        Returns score between 0 and 1 (higher = more undervalued)
        """
        score = 0.0
        factors = 0
        
        # P/E ratio (lower is better, < 20 is good)
        if not np.isnan(data.get('pe_ratio', np.nan)):
            pe = data['pe_ratio']
            if pe > 0:
                if pe < 15:
                    score += 1.0
                elif pe < 20:
                    score += 0.7
                elif pe < 25:
                    score += 0.4
                factors += 1
        
        # PEG ratio (< 1 is undervalued)
        if not np.isnan(data.get('peg_ratio', np.nan)):
            peg = data['peg_ratio']
            if peg > 0:
                if peg < 1:
                    score += 1.0
                elif peg < 1.5:
                    score += 0.5
                factors += 1
        
        # Price to Book (< 3 is reasonable for tech)
        if not np.isnan(data.get('price_to_book', np.nan)):
            pb = data['price_to_book']
            if pb > 0:
                if pb < 2:
                    score += 1.0
                elif pb < 3:
                    score += 0.6
                elif pb < 5:
                    score += 0.3
                factors += 1
        
        # Calculate final score
        if factors > 0:
            return score / factors
        return 0.0


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize client
    client = FMPClient()
    
    # Test getting NASDAQ-100 constituents
    print("Getting NASDAQ-100 constituents...")
    constituents = client.get_nasdaq100_constituents()
    print(f"Found {len(constituents)} stocks")
    
    # Test getting data for a stock
    print("\nGetting data for AAPL...")
    analysis = client.get_stock_analysis("AAPL")
    for key, value in analysis.items():
        print(f"  {key}: {value}")