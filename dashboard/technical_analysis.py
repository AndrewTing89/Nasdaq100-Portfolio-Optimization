"""
Technical Analysis Module for Individual Stock Analysis
Provides detailed technical indicators and AI-powered insights for individual stocks
"""

import pandas as pd
import numpy as np
import yfinance as yf
import pandas_ta as ta
from datetime import datetime, timedelta
import logging
from typing import Dict, Any, List, Optional
import streamlit as st

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StockDataFetcher:
    """Fetches stock data from Yahoo Finance"""
    
    def __init__(self, period: str = "3mo"):
        self.period = period
    
    def get_stock_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Fetch historical stock data"""
        try:
            logger.info(f"Fetching data for {symbol}")
            stock = yf.Ticker(symbol)
            data = stock.history(period=self.period)
            
            if data.empty:
                logger.error(f"No data found for symbol {symbol}")
                return None
            
            return data
        
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {str(e)}")
            return None
    
    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """Fetch stock information"""
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            
            return {
                'symbol': symbol,
                'name': info.get('longName', 'N/A'),
                'sector': info.get('sector', 'N/A'),
                'industry': info.get('industry', 'N/A'),
                'market_cap': info.get('marketCap', 'N/A'),
                'current_price': info.get('currentPrice', info.get('regularMarketPrice', 'N/A')),
                'pe_ratio': info.get('trailingPE', 'N/A'),
                'dividend_yield': info.get('dividendYield', 'N/A'),
                'fifty_two_week_high': info.get('fiftyTwoWeekHigh', 'N/A'),
                'fifty_two_week_low': info.get('fiftyTwoWeekLow', 'N/A'),
                'avg_volume': info.get('averageVolume', 'N/A'),
                'beta': info.get('beta', 'N/A')
            }
        
        except Exception as e:
            logger.error(f"Error fetching info for {symbol}: {str(e)}")
            return {'symbol': symbol, 'name': 'Unknown'}

class TechnicalAnalyzer:
    """Calculates technical indicators for stock analysis"""
    
    def __init__(self, ma_periods=[20, 50], rsi_period=14,
                 macd_fast=12, macd_slow=26, macd_signal=9):
        self.ma_periods = ma_periods
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
    
    def calculate_indicators(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Calculate various technical indicators"""
        try:
            indicators = {}
            
            # Moving Averages
            for period in self.ma_periods:
                ma = ta.sma(data['Close'], length=period)
                indicators[f'MA_{period}'] = ma.iloc[-1] if not ma.empty else None
            
            # RSI
            rsi = ta.rsi(data['Close'], length=self.rsi_period)
            indicators['RSI'] = rsi.iloc[-1] if not rsi.empty else None
            
            # MACD
            macd_data = ta.macd(data['Close'], fast=self.macd_fast,
                              slow=self.macd_slow, signal=self.macd_signal)
            if macd_data is not None and not macd_data.empty:
                indicators['MACD'] = macd_data[f'MACD_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}'].iloc[-1]
                indicators['MACD_Signal'] = macd_data[f'MACDs_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}'].iloc[-1]
                indicators['MACD_Histogram'] = macd_data[f'MACDh_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}'].iloc[-1]
            
            # Bollinger Bands
            bb = ta.bbands(data['Close'], length=20, std=2)
            if bb is not None and not bb.empty:
                indicators['BB_Upper'] = bb['BBU_20_2.0'].iloc[-1] if 'BBU_20_2.0' in bb.columns else None
                indicators['BB_Middle'] = bb['BBM_20_2.0'].iloc[-1] if 'BBM_20_2.0' in bb.columns else None
                indicators['BB_Lower'] = bb['BBL_20_2.0'].iloc[-1] if 'BBL_20_2.0' in bb.columns else None
            
            # Current price and changes
            current_price = data['Close'].iloc[-1]
            prev_price = data['Close'].iloc[-2] if len(data) > 1 else current_price
            price_change = current_price - prev_price
            price_change_pct = (price_change / prev_price) * 100
            
            indicators['Current_Price'] = current_price
            indicators['Price_Change'] = price_change
            indicators['Price_Change_Pct'] = price_change_pct
            
            # Volume analysis
            avg_volume = data['Volume'].rolling(window=20).mean().iloc[-1]
            current_volume = data['Volume'].iloc[-1]
            indicators['Volume_Ratio'] = current_volume / avg_volume if avg_volume > 0 else 1
            
            # Support and Resistance
            indicators['Support'] = data['Low'].rolling(window=20).min().iloc[-1]
            indicators['Resistance'] = data['High'].rolling(window=20).max().iloc[-1]
            
            return indicators
        
        except Exception as e:
            logger.error(f"Error calculating indicators: {str(e)}")
            return {}
    
    def analyze_trend(self, indicators: Dict[str, Any]) -> Dict[str, str]:
        """Analyze trends based on technical indicators"""
        analysis = {
            'overall_trend': 'Neutral',
            'momentum': 'Neutral',
            'volatility': 'Normal',
            'volume_trend': 'Normal',
            'recommendation': 'Hold'
        }
        
        try:
            # Price trend analysis
            current_price = indicators.get('Current_Price', 0)
            ma_20 = indicators.get('MA_20')
            ma_50 = indicators.get('MA_50')
            
            trend_score = 0
            
            if ma_20 and ma_50 and current_price:
                if current_price > ma_20 > ma_50:
                    analysis['overall_trend'] = 'Strong Uptrend'
                    trend_score += 2
                elif current_price > ma_20:
                    analysis['overall_trend'] = 'Uptrend'
                    trend_score += 1
                elif current_price < ma_20 < ma_50:
                    analysis['overall_trend'] = 'Strong Downtrend'
                    trend_score -= 2
                elif current_price < ma_20:
                    analysis['overall_trend'] = 'Downtrend'
                    trend_score -= 1
            
            # RSI analysis
            rsi = indicators.get('RSI')
            if rsi:
                if rsi > 70:
                    analysis['momentum'] = 'Overbought'
                    trend_score -= 1
                elif rsi < 30:
                    analysis['momentum'] = 'Oversold'
                    trend_score += 1
                elif rsi > 60:
                    analysis['momentum'] = 'Strong'
                elif rsi < 40:
                    analysis['momentum'] = 'Weak'
                else:
                    analysis['momentum'] = 'Neutral'
            
            # MACD analysis
            macd = indicators.get('MACD')
            macd_signal = indicators.get('MACD_Signal')
            if macd and macd_signal:
                if macd > macd_signal:
                    trend_score += 1
                else:
                    trend_score -= 1
            
            # Bollinger Bands analysis
            bb_upper = indicators.get('BB_Upper')
            bb_lower = indicators.get('BB_Lower')
            if bb_upper and bb_lower and current_price:
                bb_range = bb_upper - bb_lower
                bb_middle = (bb_upper + bb_lower) / 2
                if bb_range > bb_middle * 0.1:  # High volatility
                    analysis['volatility'] = 'High'
                elif bb_range < bb_middle * 0.05:  # Low volatility
                    analysis['volatility'] = 'Low'
            
            # Volume analysis
            volume_ratio = indicators.get('Volume_Ratio', 1)
            if volume_ratio > 1.5:
                analysis['volume_trend'] = 'High Volume'
            elif volume_ratio < 0.5:
                analysis['volume_trend'] = 'Low Volume'
            
            # Final recommendation based on trend score
            if trend_score >= 3:
                analysis['recommendation'] = 'Strong Buy'
            elif trend_score >= 1:
                analysis['recommendation'] = 'Buy'
            elif trend_score <= -3:
                analysis['recommendation'] = 'Strong Sell'
            elif trend_score <= -1:
                analysis['recommendation'] = 'Sell'
            else:
                analysis['recommendation'] = 'Hold'
            
            return analysis
        
        except Exception as e:
            logger.error(f"Error in trend analysis: {str(e)}")
            return analysis

def get_news_sentiment(symbol: str) -> List[Dict[str, Any]]:
    """Fetch recent news and sentiment for a stock"""
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news
        
        if not news:
            return []
        
        news_data = []
        for article in news[:5]:  # Get top 5 news articles
            news_data.append({
                'title': article.get('title', 'No title'),
                'publisher': article.get('publisher', 'Unknown'),
                'link': article.get('link', ''),
                'published': datetime.fromtimestamp(article.get('providerPublishTime', 0)).strftime('%Y-%m-%d %H:%M'),
                'sentiment': analyze_news_sentiment(article.get('title', ''))
            })
        
        return news_data
    
    except Exception as e:
        logger.error(f"Error fetching news for {symbol}: {str(e)}")
        return []

def analyze_news_sentiment(text: str) -> str:
    """Simple sentiment analysis based on keywords"""
    text_lower = text.lower()
    
    positive_words = ['beats', 'exceeds', 'strong', 'growth', 'gains', 'up', 'rise',
                     'positive', 'buy', 'upgrade', 'bullish', 'outperform', 'success',
                     'record', 'high', 'surge', 'rally', 'boom']
    negative_words = ['falls', 'drops', 'weak', 'decline', 'down', 'loss', 'negative',
                     'sell', 'downgrade', 'bearish', 'underperform', 'concern', 'risk',
                     'low', 'plunge', 'crash', 'warning', 'cut']
    
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)
    
    if positive_count > negative_count:
        return "Positive"
    elif negative_count > positive_count:
        return "Negative"
    else:
        return "Neutral"

def generate_ai_insights(indicators: Dict[str, Any], trend_analysis: Dict[str, str], 
                         stock_info: Dict[str, Any]) -> str:
    """Generate AI-like insights based on technical analysis"""
    insights = []
    
    # Price action insight
    price_change = indicators.get('Price_Change_Pct', 0)
    if abs(price_change) > 2:
        if price_change > 0:
            insights.append(f"📈 Strong positive momentum with {price_change:.2f}% gain today")
        else:
            insights.append(f"📉 Significant decline of {price_change:.2f}% requires caution")
    
    # Trend insight
    trend = trend_analysis.get('overall_trend', 'Neutral')
    if 'Strong' in trend:
        insights.append(f"💪 {trend} confirmed by moving average alignment")
    elif trend != 'Neutral':
        insights.append(f"📊 Currently in {trend.lower()} phase")
    
    # RSI insight
    momentum = trend_analysis.get('momentum', 'Neutral')
    if momentum == 'Overbought':
        insights.append("⚠️ RSI indicates overbought conditions - potential pullback risk")
    elif momentum == 'Oversold':
        insights.append("🎯 RSI shows oversold conditions - possible buying opportunity")
    
    # Volume insight
    volume_trend = trend_analysis.get('volume_trend', 'Normal')
    if volume_trend == 'High Volume':
        insights.append("📊 High volume confirms price movement strength")
    elif volume_trend == 'Low Volume':
        insights.append("⚡ Low volume suggests weak conviction in current move")
    
    # Support/Resistance insight
    current_price = indicators.get('Current_Price', 0)
    support = indicators.get('Support', 0)
    resistance = indicators.get('Resistance', 0)
    
    if current_price and support and resistance:
        price_position = (current_price - support) / (resistance - support) if resistance != support else 0.5
        if price_position > 0.8:
            insights.append(f"🎯 Price approaching resistance at ${resistance:.2f}")
        elif price_position < 0.2:
            insights.append(f"🛡️ Price near support level at ${support:.2f}")
    
    # Final recommendation
    recommendation = trend_analysis.get('recommendation', 'Hold')
    rec_emoji = {
        'Strong Buy': '🚀',
        'Buy': '👍',
        'Hold': '⏸️',
        'Sell': '👎',
        'Strong Sell': '🔴'
    }.get(recommendation, '❓')
    
    insights.append(f"{rec_emoji} **Recommendation: {recommendation}**")
    
    return '\n\n'.join(insights)

def calculate_risk_metrics(data: pd.DataFrame) -> Dict[str, float]:
    """Calculate risk metrics for the stock"""
    try:
        returns = data['Close'].pct_change().dropna()
        
        metrics = {
            'volatility': returns.std() * np.sqrt(252) * 100,  # Annualized volatility
            'sharpe_ratio': (returns.mean() * 252) / (returns.std() * np.sqrt(252)) if returns.std() > 0 else 0,
            'max_drawdown': ((data['Close'] / data['Close'].cummax() - 1).min()) * 100,
            'var_95': np.percentile(returns, 5) * 100,  # 95% VaR
            'avg_daily_return': returns.mean() * 100,
            'winning_days_pct': (returns > 0).mean() * 100
        }
        
        return metrics
    
    except Exception as e:
        logger.error(f"Error calculating risk metrics: {str(e)}")
        return {}