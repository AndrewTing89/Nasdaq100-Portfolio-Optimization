"""
Direct Yahoo Finance API wrapper to bypass yfinance rate limiting issues
Uses query1.finance.yahoo.com which is more reliable
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class DirectYahooFinance:
    """Direct Yahoo Finance API access without yfinance"""
    
    BASE_URL = "https://query1.finance.yahoo.com"
    
    @staticmethod
    def get_stock_data(symbol: str, period: str = "3mo") -> Optional[pd.DataFrame]:
        """
        Fetch stock data directly from Yahoo Finance API
        
        Args:
            symbol: Stock ticker symbol (e.g., 'AAPL')
            period: Time period ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max')
        
        Returns:
            DataFrame with OHLCV data or None if failed
        """
        try:
            # Build URL
            url = f"{DirectYahooFinance.BASE_URL}/v8/finance/chart/{symbol}"
            
            # Convert period to range parameter
            range_map = {
                '1d': '1d', '5d': '5d', '1mo': '1mo', '3mo': '3mo',
                '6mo': '6mo', '1y': '1y', '2y': '2y', '5y': '5y',
                '10y': '10y', 'ytd': 'ytd', 'max': 'max'
            }
            range_param = range_map.get(period, '3mo')
            
            # Parameters
            params = {
                'range': range_param,
                'interval': '1d',  # Daily data
                'includePrePost': 'false',
                'events': 'div,splits'
            }
            
            # Headers to avoid being blocked
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.9',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
            
            logger.info(f"Fetching data for {symbol} from Yahoo Finance API")
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse the response
                result = data['chart']['result'][0]
                
                # Extract data
                timestamps = result['timestamp']
                quotes = result['indicators']['quote'][0]
                
                # Create DataFrame
                df = pd.DataFrame({
                    'Date': pd.to_datetime(timestamps, unit='s'),
                    'Open': quotes.get('open', []),
                    'High': quotes.get('high', []),
                    'Low': quotes.get('low', []),
                    'Close': quotes.get('close', []),
                    'Volume': quotes.get('volume', [])
                })
                
                # Set Date as index
                df.set_index('Date', inplace=True)
                
                # Remove any NaN rows
                df = df.dropna()
                
                logger.info(f"Successfully fetched {len(df)} days of data for {symbol}")
                return df
                
            elif response.status_code == 429:
                logger.error(f"Rate limited by Yahoo Finance for {symbol}")
                return None
            else:
                logger.error(f"Failed to fetch data for {symbol}: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {str(e)}")
            return None
    
    @staticmethod
    def get_stock_info(symbol: str) -> Dict[str, Any]:
        """
        Get comprehensive stock information using multiple endpoints
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Dictionary with stock information
        """
        try:
            # First get basic data from chart endpoint
            url = f"{DirectYahooFinance.BASE_URL}/v8/finance/chart/{symbol}"
            
            params = {
                'range': '1d',
                'interval': '1d'
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            basic_info = {}
            if response.status_code == 200:
                data = response.json()
                result = data['chart']['result'][0]
                meta = result['meta']
                
                # Extract current price from the latest quote
                quotes = result['indicators']['quote'][0]
                current_price = quotes['close'][-1] if quotes.get('close') else None
                
                basic_info = {
                    'symbol': symbol,
                    'name': meta.get('longName', symbol),
                    'currency': meta.get('currency', 'USD'),
                    'exchange': meta.get('exchangeName', 'N/A'),
                    'current_price': current_price,
                    'previous_close': meta.get('previousClose', None),
                    'regular_market_price': meta.get('regularMarketPrice', current_price),
                    'fifty_day_average': meta.get('fiftyDayAverage', None),
                    'two_hundred_day_average': meta.get('twoHundredDayAverage', None),
                    'market_cap': meta.get('marketCap', None),
                    'volume': quotes['volume'][-1] if quotes.get('volume') else None
                }
            
            # Now try to get detailed info from quote endpoint
            quote_url = f"{DirectYahooFinance.BASE_URL}/v10/finance/quoteSummary/{symbol}"
            
            # Request multiple modules for comprehensive data
            modules = [
                'summaryProfile',      # Company description, sector, industry
                'defaultKeyStatistics', # PE ratio, beta, market cap
                'financialData',        # Current price, target prices
                'summaryDetail'         # Previous close, volume, market cap
            ]
            
            params = {
                'modules': ','.join(modules)
            }
            
            try:
                response = requests.get(quote_url, params=params, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    quote_summary = data.get('quoteSummary', {}).get('result', [{}])[0]
                    
                    # Extract detailed information
                    summary_profile = quote_summary.get('summaryProfile', {})
                    key_stats = quote_summary.get('defaultKeyStatistics', {})
                    financial_data = quote_summary.get('financialData', {})
                    summary_detail = quote_summary.get('summaryDetail', {})
                    
                    # Merge with basic info, preferring detailed data where available
                    return {
                        'symbol': symbol,
                        'name': basic_info.get('name', symbol),
                        'sector': summary_profile.get('sector', 'N/A'),
                        'industry': summary_profile.get('industry', 'N/A'),
                        'current_price': financial_data.get('currentPrice', {}).get('raw', basic_info.get('current_price')),
                        'pe_ratio': summary_detail.get('trailingPE', {}).get('raw', 
                                   key_stats.get('trailingEps', {}).get('raw', 'N/A')),
                        'forward_pe': key_stats.get('forwardPE', {}).get('raw', 'N/A'),
                        'beta': summary_detail.get('beta', {}).get('raw', 
                               key_stats.get('beta', {}).get('raw', 'N/A')),
                        'market_cap': summary_detail.get('marketCap', {}).get('raw', basic_info.get('market_cap')),
                        'dividend_yield': summary_detail.get('dividendYield', {}).get('raw', 'N/A'),
                        'fifty_two_week_high': summary_detail.get('fiftyTwoWeekHigh', {}).get('raw', 'N/A'),
                        'fifty_two_week_low': summary_detail.get('fiftyTwoWeekLow', {}).get('raw', 'N/A'),
                        'avg_volume': summary_detail.get('averageVolume', {}).get('raw', 'N/A'),
                        'volume': summary_detail.get('volume', {}).get('raw', basic_info.get('volume')),
                        'previous_close': summary_detail.get('previousClose', {}).get('raw', basic_info.get('previous_close'))
                    }
                else:
                    logger.warning(f"Could not fetch detailed info for {symbol}, using basic info")
                    return basic_info
                    
            except Exception as e:
                logger.warning(f"Error fetching detailed info for {symbol}: {str(e)}, using basic info")
                return basic_info
                
        except Exception as e:
            logger.error(f"Error fetching info for {symbol}: {str(e)}")
            return {'symbol': symbol, 'name': symbol}


# Test the direct API
if __name__ == "__main__":
    # Test fetching data
    print("Testing Direct Yahoo Finance API...")
    
    df = DirectYahooFinance.get_stock_data("AAPL", period="1mo")
    if df is not None and not df.empty:
        print(f"✅ Successfully fetched {len(df)} days of data")
        print(f"Latest close: ${df['Close'].iloc[-1]:.2f}")
        print("\nFirst 5 rows:")
        print(df.head())
    else:
        print("❌ Failed to fetch data")
    
    # Test fetching info
    info = DirectYahooFinance.get_stock_info("AAPL")
    print(f"\n✅ Stock info:")
    for key, value in info.items():
        if value is not None and value != "N/A":
            print(f"  {key}: {value}")