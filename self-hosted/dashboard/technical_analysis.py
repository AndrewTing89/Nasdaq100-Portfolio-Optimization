#!/usr/bin/env python3
"""
Technical Analysis Module for Portfolio Optimization Dashboard
Provides comprehensive technical analysis capabilities for individual stock analysis
"""

import yfinance as yf
import pandas as pd
import numpy as np
import pandas_ta as ta
import requests
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple, Any
import warnings
warnings.filterwarnings('ignore')

# Import FMP client for better financial data
try:
    from fmp_client import FMPClient
    FMP_AVAILABLE = True
except ImportError:
    FMP_AVAILABLE = False
    logging.warning("FMP client not available, using Yahoo Finance only")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DirectYahooFinance:
    """Direct Yahoo Finance API access for better reliability"""
    
    @staticmethod
    def get_quote_table(symbol: str) -> Dict:
        """Get current quote data directly from Yahoo Finance"""
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            result = data['chart']['result'][0]
            meta = result['meta']
            
            return {
                'Previous Close': meta.get('previousClose', 0),
                'Open': meta.get('currentTradingPeriod', {}).get('regular', {}).get('start', 0),
                'Bid': meta.get('bid', 0),
                'Ask': meta.get('ask', 0),
                'Day Range': f"{meta.get('dayLow', 0)} - {meta.get('dayHigh', 0)}",
                '52 Week Range': f"{meta.get('fiftyTwoWeekLow', 0)} - {meta.get('fiftyTwoWeekHigh', 0)}",
                'Volume': meta.get('volume', 0),
                'Avg. Volume': meta.get('averageDailyVolume10Day', 0),
                'Market Cap': meta.get('marketCap', 0),
                'Beta': meta.get('beta', 0),
                'PE Ratio': meta.get('trailingPE', 0),
                'EPS': meta.get('epsTrailingTwelveMonths', 0),
                'Earnings Date': meta.get('earningsTimestamp', ''),
                'Forward Dividend & Yield': f"{meta.get('dividendRate', 0)} ({meta.get('dividendYield', 0)*100:.2f}%)" if meta.get('dividendRate') else 'N/A',
                'Ex-Dividend Date': meta.get('exDividendDate', ''),
                '1y Target Est': meta.get('targetMeanPrice', 0)
            }
        except Exception as e:
            logger.error(f"Error fetching quote data for {symbol}: {e}")
            return {}
    
    @staticmethod
    def get_historical_data(symbol: str, period: str = "1y") -> pd.DataFrame:
        """Get historical price data directly from Yahoo Finance"""
        try:
            # Convert period to start/end dates
            end_date = datetime.now()
            if period == "1mo":
                start_date = end_date - timedelta(days=30)
            elif period == "3mo":
                start_date = end_date - timedelta(days=90)
            elif period == "6mo":
                start_date = end_date - timedelta(days=180)
            elif period == "1y":
                start_date = end_date - timedelta(days=365)
            elif period == "2y":
                start_date = end_date - timedelta(days=730)
            else:
                start_date = end_date - timedelta(days=365)
            
            # Convert to timestamps
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())
            
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            params = {
                'period1': start_timestamp,
                'period2': end_timestamp,
                'interval': '1d',
                'includePrePost': 'false'
            }
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            result = data['chart']['result'][0]
            
            # Extract timestamps and OHLCV data
            timestamps = result['timestamp']
            ohlcv = result['indicators']['quote'][0]
            
            # Create DataFrame
            df = pd.DataFrame({
                'Open': ohlcv['open'],
                'High': ohlcv['high'],
                'Low': ohlcv['low'],
                'Close': ohlcv['close'],
                'Volume': ohlcv['volume']
            })
            
            # Convert timestamps to datetime index
            df.index = pd.to_datetime([datetime.fromtimestamp(ts) for ts in timestamps])
            df.index.name = 'Date'
            
            # Remove any rows with all NaN values
            df = df.dropna(how='all')
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return pd.DataFrame()

class StockDataFetcher:
    """Enhanced stock data fetcher with multiple sources and error handling"""
    
    def __init__(self):
        self.direct_yahoo = DirectYahooFinance()
        self.fmp_client = FMPClient() if FMP_AVAILABLE else None
    
    def get_stock_data(self, symbol: str, period: str = "1y") -> pd.DataFrame:
        """
        Fetch historical stock data with fallback mechanisms
        
        Args:
            symbol: Stock ticker symbol
            period: Time period (1mo, 3mo, 6mo, 1y, 2y)
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            # Try direct Yahoo Finance first
            logger.info(f"Fetching data for {symbol} using direct Yahoo Finance...")
            data = self.direct_yahoo.get_historical_data(symbol, period)
            
            if not data.empty:
                logger.info(f"Successfully fetched {len(data)} days of data for {symbol}")
                return data
            
            # Fallback to yfinance
            logger.warning(f"Direct Yahoo failed for {symbol}, trying yfinance...")
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period)
            
            if not data.empty:
                logger.info(f"Successfully fetched {len(data)} days of data for {symbol} via yfinance")
                return data
            
            logger.error(f"All methods failed to fetch data for {symbol}")
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"Error fetching stock data for {symbol}: {e}")
            return pd.DataFrame()
    
    def get_stock_info(self, symbol: str) -> Dict:
        """
        Get current stock information and quote data
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Dictionary with stock information
        """
        result = {}
        
        try:
            # Primary: Use FMP for comprehensive financial data
            if self.fmp_client:
                logger.info(f"Fetching {symbol} data from FMP...")
                
                # Get quote data
                quote_data = self.fmp_client.get_quote(symbol)
                if quote_data:
                    result.update({
                        'Previous Close': quote_data.get('previousClose', 0),
                        'Open': quote_data.get('open', 0),
                        'Volume': quote_data.get('volume', 0),
                        'Avg. Volume': quote_data.get('avgVolume', 0),
                        'Market Cap': quote_data.get('marketCap', 0),
                        'PE Ratio': quote_data.get('pe', 0),
                        'EPS': quote_data.get('eps', 0),
                        'Day Range': f"{quote_data.get('dayLow', 0)} - {quote_data.get('dayHigh', 0)}",
                        '52 Week Range': f"{quote_data.get('yearLow', 0)} - {quote_data.get('yearHigh', 0)}",
                    })
                
                # Get company profile for beta and other details
                profile_data = self.fmp_client.get_company_profile(symbol)
                if profile_data:
                    result.update({
                        'Beta': profile_data.get('beta', 0),
                        'Company Name': profile_data.get('companyName', symbol),
                        'Sector': profile_data.get('sector', 'N/A'),
                        'Industry': profile_data.get('industry', 'N/A'),
                    })
                
                # Get key metrics for additional ratios
                metrics_data = self.fmp_client.get_key_metrics(symbol)
                if metrics_data:
                    result.update({
                        'PEG Ratio': metrics_data.get('pegRatio', 0),
                        'Price to Book': metrics_data.get('priceToBookRatio', 0),
                        'Dividend Yield': metrics_data.get('dividendYield', 0),
                    })
                
                if result:
                    logger.info(f"Successfully fetched comprehensive data for {symbol} from FMP")
                    return result
            
            # Fallback 1: Try Yahoo Finance chart API for basic data
            logger.warning(f"FMP failed or unavailable for {symbol}, trying Yahoo Finance...")
            yahoo_data = self.direct_yahoo.get_quote_table(symbol)
            
            if yahoo_data and any(v != 0 for v in yahoo_data.values() if isinstance(v, (int, float))):
                logger.info(f"Got basic data for {symbol} from Yahoo Finance")
                return yahoo_data
            
            # Fallback 2: Try yfinance (with error handling for rate limits)
            logger.warning(f"Yahoo direct failed for {symbol}, trying yfinance (may hit rate limits)...")
            ticker = yf.Ticker(symbol)
            
            # Try to get basic info without triggering rate limits
            try:
                info_data = ticker.info
                if info_data:
                    return {
                        'Previous Close': info_data.get('previousClose', 0),
                        'Open': info_data.get('open', 0),
                        'Bid': info_data.get('bid', 0),
                        'Ask': info_data.get('ask', 0),
                        'Day Range': f"{info_data.get('dayLow', 0)} - {info_data.get('dayHigh', 0)}",
                        '52 Week Range': f"{info_data.get('fiftyTwoWeekLow', 0)} - {info_data.get('fiftyTwoWeekHigh', 0)}",
                        'Volume': info_data.get('volume', 0),
                        'Avg. Volume': info_data.get('averageVolume', 0),
                        'Market Cap': info_data.get('marketCap', 0),
                        'Beta': info_data.get('beta', 0),
                        'PE Ratio': info_data.get('trailingPE', 0),
                        'EPS': info_data.get('trailingEps', 0),
                        'Earnings Date': info_data.get('earningsDate', ''),
                        'Forward Dividend & Yield': f"{info_data.get('dividendRate', 0)} ({info_data.get('dividendYield', 0)*100:.2f}%)" if info_data.get('dividendRate') else 'N/A',
                        'Ex-Dividend Date': info_data.get('exDividendDate', ''),
                        '1y Target Est': info_data.get('targetMeanPrice', 0)
                    }
            except Exception as yf_error:
                if "429" in str(yf_error) or "Too Many Requests" in str(yf_error):
                    logger.warning(f"Rate limited by Yahoo Finance for {symbol}")
                else:
                    logger.error(f"yfinance error for {symbol}: {yf_error}")
            
            # If all sources fail, return minimal data structure
            logger.error(f"All data sources failed for {symbol}")
            return {
                'Previous Close': 0,
                'Open': 0,
                'Volume': 0,
                'Market Cap': 0,
                'PE Ratio': 0,
                'Beta': 0,
                'Day Range': 'N/A',
                '52 Week Range': 'N/A'
            }
            
        except Exception as e:
            logger.error(f"Error fetching stock info for {symbol}: {e}")
            return {}

class TechnicalAnalyzer:
    """Advanced technical analysis with comprehensive indicators"""
    
    def __init__(self):
        self.data_fetcher = StockDataFetcher()
    
    def calculate_indicators(self, data: pd.DataFrame, 
                           rsi_period: int = 14,
                           macd_fast: int = 12,
                           macd_slow: int = 26,
                           macd_signal: int = 9,
                           bb_period: int = 20,
                           bb_std: float = 2.0) -> pd.DataFrame:
        """
        Calculate comprehensive technical indicators
        
        Args:
            data: OHLCV DataFrame
            rsi_period: RSI calculation period
            macd_fast: MACD fast EMA period
            macd_slow: MACD slow EMA period
            macd_signal: MACD signal line period
            bb_period: Bollinger Bands period
            bb_std: Bollinger Bands standard deviation
            
        Returns:
            DataFrame with technical indicators
        """
        try:
            if data.empty:
                return pd.DataFrame()
            
            df = data.copy()
            
            # Moving Averages
            df['SMA_20'] = ta.sma(df['Close'], length=20)
            df['SMA_50'] = ta.sma(df['Close'], length=50)
            df['EMA_12'] = ta.ema(df['Close'], length=12)
            df['EMA_26'] = ta.ema(df['Close'], length=26)
            
            # RSI
            df['RSI'] = ta.rsi(df['Close'], length=rsi_period)
            
            # MACD
            macd_data = ta.macd(df['Close'], fast=macd_fast, slow=macd_slow, signal=macd_signal)
            if macd_data is not None:
                df['MACD'] = macd_data[f'MACD_{macd_fast}_{macd_slow}_{macd_signal}']
                df['MACD_Signal'] = macd_data[f'MACDs_{macd_fast}_{macd_slow}_{macd_signal}']
                df['MACD_Histogram'] = macd_data[f'MACDh_{macd_fast}_{macd_slow}_{macd_signal}']
            
            # Bollinger Bands
            bb_data = ta.bbands(df['Close'], length=bb_period, std=bb_std)
            if bb_data is not None:
                df['BB_Upper'] = bb_data[f'BBU_{bb_period}_{bb_std}']
                df['BB_Middle'] = bb_data[f'BBM_{bb_period}_{bb_std}']
                df['BB_Lower'] = bb_data[f'BBL_{bb_period}_{bb_std}']
                df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Middle']
                df['BB_Position'] = (df['Close'] - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'])
            
            # Volume indicators
            df['Volume_SMA'] = ta.sma(df['Volume'], length=20)
            df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA']
            
            # Price change indicators
            df['Price_Change'] = df['Close'].pct_change()
            df['Price_Change_5d'] = df['Close'].pct_change(5)
            df['Price_Change_20d'] = df['Close'].pct_change(20)
            
            # Volatility
            df['Volatility_20d'] = df['Price_Change'].rolling(20).std() * np.sqrt(252)
            
            # Support and Resistance levels
            df['Resistance'] = df['High'].rolling(20).max()
            df['Support'] = df['Low'].rolling(20).min()
            
            # Average True Range (ATR)
            df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
            
            # Stochastic Oscillator
            stoch_data = ta.stoch(df['High'], df['Low'], df['Close'])
            if stoch_data is not None:
                df['Stoch_K'] = stoch_data['STOCHk_14_3_3']
                df['Stoch_D'] = stoch_data['STOCHd_14_3_3']
            
            return df
            
        except Exception as e:
            logger.error(f"Error calculating technical indicators: {e}")
            return data
    
    def analyze_trend(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze trend and provide trading recommendation
        
        Args:
            data: DataFrame with technical indicators
            
        Returns:
            Dictionary with trend analysis and recommendation
        """
        try:
            if data.empty or len(data) < 50:
                return {
                    'trend': 'Insufficient Data',
                    'strength': 0,
                    'recommendation': 'Hold',
                    'confidence': 0,
                    'signals': []
                }
            
            latest = data.iloc[-1]
            prev = data.iloc[-2] if len(data) > 1 else latest
            
            signals = []
            bullish_signals = 0
            bearish_signals = 0
            
            # Price vs Moving Averages
            if latest['Close'] > latest['SMA_20']:
                signals.append("Price above 20-day SMA (Bullish)")
                bullish_signals += 1
            else:
                signals.append("Price below 20-day SMA (Bearish)")
                bearish_signals += 1
            
            if latest['Close'] > latest['SMA_50']:
                signals.append("Price above 50-day SMA (Bullish)")
                bullish_signals += 1
            else:
                signals.append("Price below 50-day SMA (Bearish)")
                bearish_signals += 1
            
            # RSI Analysis
            if latest['RSI'] > 70:
                signals.append(f"RSI overbought ({latest['RSI']:.1f}) (Bearish)")
                bearish_signals += 1
            elif latest['RSI'] < 30:
                signals.append(f"RSI oversold ({latest['RSI']:.1f}) (Bullish)")
                bullish_signals += 1
            elif latest['RSI'] > 50:
                signals.append(f"RSI bullish ({latest['RSI']:.1f}) (Bullish)")
                bullish_signals += 0.5
            else:
                signals.append(f"RSI bearish ({latest['RSI']:.1f}) (Bearish)")
                bearish_signals += 0.5
            
            # MACD Analysis
            if 'MACD' in data.columns and 'MACD_Signal' in data.columns:
                if latest['MACD'] > latest['MACD_Signal']:
                    signals.append("MACD above signal line (Bullish)")
                    bullish_signals += 1
                else:
                    signals.append("MACD below signal line (Bearish)")
                    bearish_signals += 1
                
                # MACD crossover
                if (latest['MACD'] > latest['MACD_Signal'] and 
                    prev['MACD'] <= prev['MACD_Signal']):
                    signals.append("MACD bullish crossover (Strong Bullish)")
                    bullish_signals += 2
                elif (latest['MACD'] < latest['MACD_Signal'] and 
                      prev['MACD'] >= prev['MACD_Signal']):
                    signals.append("MACD bearish crossover (Strong Bearish)")
                    bearish_signals += 2
            
            # Bollinger Bands Analysis
            if 'BB_Position' in data.columns:
                bb_pos = latest['BB_Position']
                if bb_pos > 0.8:
                    signals.append("Near upper Bollinger Band (Bearish)")
                    bearish_signals += 1
                elif bb_pos < 0.2:
                    signals.append("Near lower Bollinger Band (Bullish)")
                    bullish_signals += 1
            
            # Volume Analysis
            if latest['Volume_Ratio'] > 1.5:
                signals.append("High volume activity (Significant)")
                
            # Determine overall trend
            total_signals = bullish_signals + bearish_signals
            if total_signals == 0:
                net_bullish = 0
            else:
                net_bullish = (bullish_signals - bearish_signals) / total_signals
            
            # Trend classification
            if net_bullish > 0.3:
                trend = 'Bullish'
                recommendation = 'Buy'
            elif net_bullish < -0.3:
                trend = 'Bearish'
                recommendation = 'Sell'
            else:
                trend = 'Neutral'
                recommendation = 'Hold'
            
            # Confidence based on signal strength
            confidence = min(abs(net_bullish) * 100, 95)
            
            # Strength calculation
            strength = abs(net_bullish) * 100
            
            return {
                'trend': trend,
                'strength': strength,
                'recommendation': recommendation,
                'confidence': confidence,
                'signals': signals,
                'bullish_signals': bullish_signals,
                'bearish_signals': bearish_signals,
                'net_score': net_bullish
            }
            
        except Exception as e:
            logger.error(f"Error analyzing trend: {e}")
            return {
                'trend': 'Error',
                'strength': 0,
                'recommendation': 'Hold',
                'confidence': 0,
                'signals': [f"Analysis error: {e}"]
            }

def get_news_sentiment(symbol: str, limit: int = 5) -> List[Dict]:
    """
    Fetch recent news for a stock (simplified version)
    
    Args:
        symbol: Stock ticker symbol
        limit: Number of news articles to fetch
        
    Returns:
        List of news articles with sentiment
    """
    try:
        # This is a placeholder implementation
        # In a real implementation, you would integrate with news APIs
        # like Alpha Vantage, NewsAPI, or scrape financial news sites
        
        fake_news = [
            {
                'title': f'{symbol} reports strong quarterly earnings',
                'summary': f'{symbol} exceeded analyst expectations in the latest quarter.',
                'sentiment': 'Positive',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'source': 'Financial News'
            },
            {
                'title': f'Analysts upgrade {symbol} price target',
                'summary': f'Several analysts have raised their price targets for {symbol}.',
                'sentiment': 'Positive',
                'date': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
                'source': 'Market Watch'
            }
        ]
        
        return fake_news[:limit]
        
    except Exception as e:
        logger.error(f"Error fetching news for {symbol}: {e}")
        return []

def analyze_news_sentiment(news_articles: List[Dict]) -> Dict[str, Any]:
    """
    Analyze sentiment of news articles
    
    Args:
        news_articles: List of news articles
        
    Returns:
        Dictionary with sentiment analysis
    """
    try:
        if not news_articles:
            return {
                'overall_sentiment': 'Neutral',
                'positive_count': 0,
                'negative_count': 0,
                'neutral_count': 0,
                'sentiment_score': 0
            }
        
        positive_keywords = ['strong', 'growth', 'upgrade', 'beat', 'exceed', 'positive', 'bullish', 'rally']
        negative_keywords = ['weak', 'decline', 'downgrade', 'miss', 'concern', 'negative', 'bearish', 'fall']
        
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        
        for article in news_articles:
            text = (article.get('title', '') + ' ' + article.get('summary', '')).lower()
            
            positive_score = sum(1 for keyword in positive_keywords if keyword in text)
            negative_score = sum(1 for keyword in negative_keywords if keyword in text)
            
            if positive_score > negative_score:
                positive_count += 1
            elif negative_score > positive_score:
                negative_count += 1
            else:
                neutral_count += 1
        
        total_articles = len(news_articles)
        sentiment_score = (positive_count - negative_count) / total_articles if total_articles > 0 else 0
        
        if sentiment_score > 0.2:
            overall_sentiment = 'Positive'
        elif sentiment_score < -0.2:
            overall_sentiment = 'Negative'
        else:
            overall_sentiment = 'Neutral'
        
        return {
            'overall_sentiment': overall_sentiment,
            'positive_count': positive_count,
            'negative_count': negative_count,
            'neutral_count': neutral_count,
            'sentiment_score': sentiment_score
        }
        
    except Exception as e:
        logger.error(f"Error analyzing news sentiment: {e}")
        return {
            'overall_sentiment': 'Neutral',
            'positive_count': 0,
            'negative_count': 0,
            'neutral_count': 0,
            'sentiment_score': 0
        }

def generate_ai_insights(symbol: str, technical_analysis: Dict, news_sentiment: Dict, stock_info: Dict) -> List[str]:
    """
    Generate AI-powered insights based on technical analysis and news sentiment
    
    Args:
        symbol: Stock ticker symbol
        technical_analysis: Technical analysis results
        news_sentiment: News sentiment analysis
        stock_info: Stock information
        
    Returns:
        List of AI-generated insights
    """
    try:
        insights = []
        
        # Technical Analysis Insights
        trend = technical_analysis.get('trend', 'Neutral')
        strength = technical_analysis.get('strength', 0)
        confidence = technical_analysis.get('confidence', 0)
        
        if trend == 'Bullish' and strength > 60:
            insights.append(f"🚀 Strong bullish momentum detected for {symbol} with {confidence:.0f}% confidence. "
                          f"Multiple technical indicators are aligning positively.")
        elif trend == 'Bearish' and strength > 60:
            insights.append(f"⚠️ Strong bearish pressure on {symbol} with {confidence:.0f}% confidence. "
                          f"Consider risk management strategies.")
        else:
            insights.append(f"📊 {symbol} is showing {trend.lower()} trends with moderate strength. "
                          f"Wait for clearer signals before major position changes.")
        
        # News Sentiment Insights
        news_sentiment_score = news_sentiment.get('sentiment_score', 0)
        overall_sentiment = news_sentiment.get('overall_sentiment', 'Neutral')
        
        if overall_sentiment == 'Positive' and news_sentiment_score > 0.3:
            insights.append(f"📰 Recent news sentiment for {symbol} is strongly positive, "
                          f"which could provide fundamental support for price movement.")
        elif overall_sentiment == 'Negative' and news_sentiment_score < -0.3:
            insights.append(f"📰 Negative news sentiment around {symbol} could create headwinds. "
                          f"Monitor for any fundamental changes.")
        
        # Volume and Volatility Insights
        if stock_info.get('Volume', 0) > stock_info.get('Avg. Volume', 0) * 1.5:
            insights.append(f"📈 {symbol} is experiencing unusually high trading volume, "
                          f"indicating increased investor interest and potential price volatility.")
        
        # Valuation Insights
        pe_ratio = stock_info.get('PE Ratio', 0)
        if pe_ratio and pe_ratio > 0:
            if pe_ratio < 15:
                insights.append(f"💰 {symbol} appears relatively undervalued with a P/E ratio of {pe_ratio:.1f}, "
                              f"which could present a good entry opportunity.")
            elif pe_ratio > 30:
                insights.append(f"⚡ {symbol} is trading at a high P/E ratio of {pe_ratio:.1f}, "
                              f"suggesting premium valuation. Ensure growth justifies the price.")
        
        # Risk Assessment
        beta = stock_info.get('Beta', 0)
        if beta and beta > 0:
            if beta > 1.5:
                insights.append(f"⚡ {symbol} has high beta ({beta:.2f}), making it more volatile than the market. "
                              f"Suitable for risk-tolerant investors.")
            elif beta < 0.8:
                insights.append(f"🛡️ {symbol} has low beta ({beta:.2f}), offering more stability than the broader market.")
        
        # Recommendation Synthesis
        if (trend == 'Bullish' and overall_sentiment == 'Positive' and 
            confidence > 70):
            insights.append(f"✅ Multiple factors align positively for {symbol}: strong technical trends, "
                          f"positive news sentiment, and high confidence signals suggest favorable conditions.")
        elif (trend == 'Bearish' and overall_sentiment == 'Negative' and 
              confidence > 70):
            insights.append(f"❌ Caution advised for {symbol}: bearish technical signals combined with "
                          f"negative sentiment create unfavorable risk/reward conditions.")
        
        # Default insight if no specific conditions are met
        if not insights:
            insights.append(f"📊 {symbol} shows mixed signals across technical and fundamental indicators. "
                          f"Consider your investment timeline and risk tolerance before making decisions.")
        
        return insights[:5]  # Limit to 5 insights
        
    except Exception as e:
        logger.error(f"Error generating AI insights: {e}")
        return [f"Unable to generate insights for {symbol} due to data limitations."]

def calculate_risk_metrics(data: pd.DataFrame, risk_free_rate: float = 0.02) -> Dict[str, float]:
    """
    Calculate comprehensive risk metrics
    
    Args:
        data: OHLCV DataFrame
        risk_free_rate: Annual risk-free rate (default 2%)
        
    Returns:
        Dictionary with risk metrics
    """
    try:
        if data.empty or len(data) < 30:
            return {
                'volatility': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'var_95': 0,
                'var_99': 0,
                'calmar_ratio': 0,
                'sortino_ratio': 0
            }
        
        # Calculate returns
        returns = data['Close'].pct_change().dropna()
        
        # Annualized volatility
        volatility = returns.std() * np.sqrt(252)
        
        # Annualized return
        total_return = (data['Close'].iloc[-1] / data['Close'].iloc[0]) - 1
        periods = len(data) / 252
        annualized_return = (1 + total_return) ** (1 / periods) - 1 if periods > 0 else 0
        
        # Sharpe Ratio
        excess_return = annualized_return - risk_free_rate
        sharpe_ratio = excess_return / volatility if volatility > 0 else 0
        
        # Maximum Drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # Value at Risk (VaR)
        var_95 = np.percentile(returns, 5)
        var_99 = np.percentile(returns, 1)
        
        # Calmar Ratio (annual return / max drawdown)
        calmar_ratio = abs(annualized_return / max_drawdown) if max_drawdown != 0 else 0
        
        # Sortino Ratio (excess return / downside deviation)
        downside_returns = returns[returns < 0]
        downside_deviation = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0
        sortino_ratio = excess_return / downside_deviation if downside_deviation > 0 else 0
        
        return {
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'var_95': var_95,
            'var_99': var_99,
            'calmar_ratio': calmar_ratio,
            'sortino_ratio': sortino_ratio,
            'annualized_return': annualized_return
        }
        
    except Exception as e:
        logger.error(f"Error calculating risk metrics: {e}")
        return {
            'volatility': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
            'var_95': 0,
            'var_99': 0,
            'calmar_ratio': 0,
            'sortino_ratio': 0,
            'annualized_return': 0
        }

# Example usage and testing
if __name__ == "__main__":
    # Test the technical analysis functionality
    print("Testing Technical Analysis Module...")
    
    fetcher = StockDataFetcher()
    analyzer = TechnicalAnalyzer()
    
    # Test with AAPL
    symbol = "AAPL"
    print(f"\nFetching data for {symbol}...")
    
    # Get stock data
    stock_data = fetcher.get_stock_data(symbol, "6mo")
    if not stock_data.empty:
        print(f"Fetched {len(stock_data)} days of data")
        
        # Calculate indicators
        technical_data = analyzer.calculate_indicators(stock_data)
        print(f"Calculated technical indicators")
        
        # Analyze trend
        trend_analysis = analyzer.analyze_trend(technical_data)
        print(f"Trend Analysis: {trend_analysis['trend']} ({trend_analysis['confidence']:.1f}% confidence)")
        print(f"Recommendation: {trend_analysis['recommendation']}")
        
        # Get stock info
        stock_info = fetcher.get_stock_info(symbol)
        print(f"Current Price: ${stock_info.get('Previous Close', 'N/A')}")
        
        # Calculate risk metrics
        risk_metrics = calculate_risk_metrics(stock_data)
        print(f"Volatility: {risk_metrics['volatility']:.2%}")
        print(f"Sharpe Ratio: {risk_metrics['sharpe_ratio']:.2f}")
        
    else:
        print("Failed to fetch stock data")