#!/usr/bin/env python3
"""
Database-Only Portfolio Optimization Pipeline
All data is stored in PostgreSQL - NO CSV files
"""

import os
import sys
import logging
import time
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from psycopg2.pool import SimpleConnectionPool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseOnlyPipeline:
    """Complete pipeline that only uses PostgreSQL database"""
    
    def __init__(self):
        """Initialize database connection"""
        self.db_url = os.environ.get(
            'DATABASE_URL',
            'postgresql://portfolio_user:secure_password@postgres:5432/portfolio_optimization'
        )
        
        # Create connection pool
        self.pool = SimpleConnectionPool(1, 5, self.db_url)
        self.run_id = None
        
        # Import pipeline components
        try:
            from fmp_client import FMPClient
            self.fmp = FMPClient()
        except:
            logger.warning("FMP client not available, using mock data")
            self.fmp = None
            
    def get_connection(self):
        """Get database connection from pool"""
        return self.pool.getconn()
    
    def return_connection(self, conn):
        """Return connection to pool"""
        self.pool.putconn(conn)
        
    def run_complete_pipeline(self, max_stocks: int = 100) -> Dict:
        """Run complete pipeline with database storage only"""
        conn = None
        try:
            conn = self.get_connection()
            
            # Create pipeline run
            self.run_id = self._create_pipeline_run(conn)
            logger.info(f"Started pipeline run {self.run_id}")
            
            # Phase 1: Get NASDAQ-100 stocks
            logger.info("PHASE 1: Fetching NASDAQ-100 constituents")
            stocks_count = self._phase1_nasdaq_stocks(conn, max_stocks)
            self._update_pipeline_phase(conn, 'phase1_nasdaq', stocks_count)
            conn.commit()  # Commit after phase 1
            
            # Phase 2: Fetch stock metrics and historical data
            logger.info("PHASE 2: Fetching stock metrics and historical data")
            metrics_count = self._phase2_stock_metrics(conn, max_stocks)
            self._update_pipeline_phase(conn, 'phase2_metrics', metrics_count)
            conn.commit()  # Commit after phase 2
            
            # Phase 3: Portfolio optimization
            logger.info("PHASE 3: Running portfolio optimization")
            portfolio_count = self._phase3_optimization(conn)
            self._update_pipeline_phase(conn, 'phase3_optimization', portfolio_count)
            
            # Mark pipeline as complete
            self._complete_pipeline_run(conn)
            
            conn.commit()
            logger.info(f"Pipeline run {self.run_id} completed successfully")
            
            return {
                'status': 'success',
                'run_id': self.run_id,
                'stocks_processed': stocks_count,
                'metrics_generated': metrics_count,
                'portfolios_created': portfolio_count
            }
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            if conn:
                conn.rollback()
                self._fail_pipeline_run(conn, str(e))
            return {
                'status': 'error',
                'run_id': self.run_id,
                'error': str(e)
            }
        finally:
            if conn:
                self.return_connection(conn)
    
    def _create_pipeline_run(self, conn) -> int:
        """Create new pipeline run record"""
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO pipeline_runs (
                    run_type, status, phase, started_at
                ) VALUES ('full', 'running', 'starting', NOW())
                RETURNING id
            """)
            run_id = cur.fetchone()[0]
            conn.commit()
            return run_id
    
    def _update_pipeline_phase(self, conn, phase: str, items_processed: int):
        """Update pipeline run phase"""
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE pipeline_runs 
                SET phase = %s, 
                    stocks_processed = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (phase, items_processed, self.run_id))
            conn.commit()
    
    def _complete_pipeline_run(self, conn):
        """Mark pipeline run as completed"""
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE pipeline_runs 
                SET status = 'completed',
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
            """, (self.run_id,))
            conn.commit()
    
    def _fail_pipeline_run(self, conn, error_msg: str):
        """Mark pipeline run as failed"""
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE pipeline_runs 
                    SET status = 'failed',
                        error_message = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (error_msg, self.run_id))
                conn.commit()
        except:
            pass
    
    def _phase1_nasdaq_stocks(self, conn, max_stocks: int) -> int:
        """Phase 1: Get NASDAQ-100 stocks and store in database"""
        
        if self.fmp:
            # Get from FMP API
            logger.info("Fetching NASDAQ-100 from FMP API")
            df = self.fmp.get_nasdaq100_constituents()
            if df is None or df.empty:
                # Fallback to hardcoded list
                df = self._get_hardcoded_nasdaq100()
        else:
            # Use hardcoded list
            df = self._get_hardcoded_nasdaq100()
        
        # Limit to max_stocks
        df = df.head(max_stocks)
        
        # Store in database
        with conn.cursor() as cur:
            for _, row in df.iterrows():
                cur.execute("""
                    INSERT INTO stocks (symbol, company_name, sector, industry, is_active)
                    VALUES (%s, %s, %s, %s, true)
                    ON CONFLICT (symbol) DO UPDATE
                    SET company_name = EXCLUDED.company_name,
                        sector = COALESCE(EXCLUDED.sector, stocks.sector),
                        industry = COALESCE(EXCLUDED.industry, stocks.industry),
                        is_active = true,
                        updated_at = NOW()
                """, (
                    row.get('symbol', row.get('Symbol')),
                    row.get('name', row.get('companyName', row.get('symbol'))),
                    row.get('sector', 'Technology'),
                    row.get('industry', 'Technology')
                ))
        
        conn.commit()
        logger.info(f"Stored {len(df)} stocks in database")
        return len(df)
    
    def _phase2_stock_metrics(self, conn, max_stocks: int) -> int:
        """Phase 2: Fetch and store stock metrics"""
        
        # Get active stocks
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, symbol FROM stocks 
                WHERE is_active = true 
                ORDER BY symbol 
                LIMIT %s
            """, (max_stocks,))
            stocks = cur.fetchall()
        
        metrics_count = 0
        
        for stock in stocks:
            try:
                if self.fmp:
                    # Get real data from FMP
                    analysis = self.fmp.get_stock_analysis(stock['symbol'])
                    quote = self.fmp.get_quote(stock['symbol'])
                    historical = self.fmp.get_historical_prices(stock['symbol'], days=252*5)
                    
                    # Calculate metrics
                    if historical is not None and not historical.empty:
                        returns = self.fmp.calculate_returns_metrics(historical)
                    else:
                        returns = {'annual_return': 0, 'volatility': 0.2, 'sharpe_ratio': 0}
                    
                    # Get analyst estimates
                    estimates = self.fmp.get_analyst_estimates(stock['symbol'])
                    
                    # Prepare metrics
                    metrics = {
                        'current_price': quote.get('price', 100) if quote else 100,
                        'target_price': estimates.get('targetMeanPrice', 110) if estimates else 110,
                        'analyst_count': estimates.get('numberOfAnalystOpinions', 1) if estimates else 1,
                        'annual_return': returns.get('annual_return', 0.1),
                        'volatility': returns.get('volatility', 0.2),
                        'sharpe_ratio': returns.get('sharpe_ratio', 0.5),
                        'pe_ratio': analysis.get('pe_ratio', 20) if analysis else 20,
                        'market_cap': analysis.get('market_cap', 1000000000) if analysis else 1000000000,
                        'beta': analysis.get('beta', 1.0) if analysis else 1.0
                    }
                else:
                    # Generate mock data for testing
                    metrics = self._generate_mock_metrics(stock['symbol'])
                
                # Calculate undervaluation rate
                if metrics['current_price'] > 0:
                    metrics['undervaluation_rate'] = (
                        (metrics['target_price'] - metrics['current_price']) / 
                        metrics['current_price']
                    )
                else:
                    metrics['undervaluation_rate'] = 0
                
                # Store in database - delete old data for today first
                with conn.cursor() as cur:
                    # Delete existing metrics for this stock today
                    cur.execute("""
                        DELETE FROM stock_metrics 
                        WHERE stock_id = %s AND date = CURRENT_DATE
                    """, (stock['id'],))
                    
                    # Insert new metrics
                    cur.execute("""
                        INSERT INTO stock_metrics (
                            stock_id, pipeline_run_id, date,
                            previous_close, target_estimate_1y, undervalue_rate,
                            annual_return_5y, annual_volatility_5y,
                            pe_ratio, market_cap, beta
                        ) VALUES (%s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        stock['id'], self.run_id,
                        metrics['current_price'],
                        metrics['target_price'],
                        metrics['undervaluation_rate'],
                        metrics['annual_return'],
                        metrics['volatility'],
                        metrics['pe_ratio'],
                        metrics['market_cap'],
                        metrics['beta']
                    ))
                
                metrics_count += 1
                
                if metrics_count % 10 == 0:
                    logger.info(f"Processed {metrics_count}/{len(stocks)} stocks")
                    conn.commit()
                    
            except Exception as e:
                logger.error(f"Error processing {stock['symbol']}: {e}")
                continue
        
        conn.commit()
        logger.info(f"Stored metrics for {metrics_count} stocks")
        return metrics_count
    
    def _phase3_optimization(self, conn) -> int:
        """Phase 3: Run portfolio optimization"""
        
        # Get stock data for optimization - use most recent data
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    s.id, s.symbol, s.company_name,
                    sm.previous_close as price,
                    sm.annual_return_5y as expected_return,
                    sm.annual_volatility_5y as volatility,
                    sm.undervalue_rate,
                    sm.beta
                FROM stocks s
                JOIN stock_metrics sm ON s.id = sm.stock_id
                WHERE sm.date = CURRENT_DATE
                AND sm.annual_return_5y IS NOT NULL
                AND sm.annual_volatility_5y IS NOT NULL
                AND sm.annual_volatility_5y > 0
                ORDER BY s.symbol
            """)
            stocks_data = cur.fetchall()
        
        if not stocks_data:
            logger.warning("No stock data available for optimization")
            return 0
        
        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame(stocks_data)
        
        # Convert Decimal types to float
        for col in ['price', 'expected_return', 'volatility', 'undervalue_rate', 'beta']:
            df[col] = df[col].astype(float)
        
        # Prepare data for optimization
        returns = df['expected_return'].values
        volatilities = df['volatility'].values
        
        portfolio_count = 0
        
        # 1. Mean-Variance Optimization (Max Sharpe)
        try:
            weights_mv = self._optimize_mean_variance(returns, volatilities)
            portfolio_count += self._save_portfolio(
                conn, df, weights_mv, 'Mean-Variance', 'max_sharpe'
            )
        except Exception as e:
            logger.error(f"Mean-Variance optimization failed: {e}")
        
        # 2. Risk Parity
        try:
            weights_rp = self._optimize_risk_parity(volatilities)
            portfolio_count += self._save_portfolio(
                conn, df, weights_rp, 'Risk Parity', 'equal_risk'
            )
        except Exception as e:
            logger.error(f"Risk Parity optimization failed: {e}")
        
        # 3. Equal Weight (Benchmark)
        try:
            weights_eq = np.ones(len(df)) / len(df)
            portfolio_count += self._save_portfolio(
                conn, df, weights_eq, 'Equal Weight', 'equal_weight'
            )
        except Exception as e:
            logger.error(f"Equal Weight portfolio failed: {e}")
        
        # 4. Undervalue-Weighted Portfolio
        try:
            undervalue_scores = df['undervalue_rate'].fillna(0).values
            undervalue_scores = np.maximum(undervalue_scores, 0)  # Only positive undervaluation
            if undervalue_scores.sum() > 0:
                weights_uv = undervalue_scores / undervalue_scores.sum()
            else:
                weights_uv = np.ones(len(df)) / len(df)
            portfolio_count += self._save_portfolio(
                conn, df, weights_uv, 'Undervalue Focus', 'undervalue_weighted'
            )
        except Exception as e:
            logger.error(f"Undervalue portfolio failed: {e}")
        
        conn.commit()
        logger.info(f"Created {portfolio_count} portfolio models")
        return portfolio_count
    
    def _optimize_mean_variance(self, returns, volatilities, risk_free_rate=0.02):
        """Simple Mean-Variance optimization for max Sharpe ratio"""
        n = len(returns)
        
        # Create covariance matrix (simplified - diagonal with volatilities)
        cov_matrix = np.diag(volatilities ** 2)
        
        # Use equal weights as starting point
        weights = np.ones(n) / n
        
        # Simple optimization: allocate more to higher Sharpe ratio stocks
        sharpe_ratios = (returns - risk_free_rate) / volatilities
        sharpe_ratios = np.nan_to_num(sharpe_ratios, 0)
        
        # Normalize to get weights
        if sharpe_ratios.max() > sharpe_ratios.min():
            weights = (sharpe_ratios - sharpe_ratios.min()) / (sharpe_ratios.max() - sharpe_ratios.min())
            weights = weights / weights.sum()
        
        return weights
    
    def _optimize_risk_parity(self, volatilities):
        """Risk Parity optimization - equal risk contribution"""
        # Inverse volatility weighting
        inv_vol = 1 / volatilities
        weights = inv_vol / inv_vol.sum()
        return weights
    
    def _save_portfolio(self, conn, stocks_df, weights, model_name, optimization_method):
        """Save portfolio to database"""
        
        # Filter stocks with significant weights
        min_weight = 0.001
        significant_mask = weights > min_weight
        
        if not significant_mask.any():
            return 0
        
        # Calculate portfolio metrics
        returns = stocks_df['expected_return'].values
        volatilities = stocks_df['volatility'].values
        
        portfolio_return = np.sum(weights * returns)
        portfolio_vol = np.sqrt(np.sum((weights * volatilities) ** 2))
        sharpe_ratio = (portfolio_return - 0.02) / portfolio_vol if portfolio_vol > 0 else 0
        
        # Insert or get portfolio model
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO portfolio_models (
                    model_name, model_type, optimization_method,
                    description, risk_free_rate
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (model_name, model_type, optimization_method) 
                DO UPDATE SET updated_at = NOW()
                RETURNING id
            """, (
                model_name, 'optimization', optimization_method,
                f'{model_name} portfolio using {optimization_method}',
                0.02
            ))
            model_id = cur.fetchone()[0]
            
            # Insert portfolio performance
            cur.execute("""
                INSERT INTO portfolio_performance (
                    portfolio_model_id, pipeline_run_id,
                    total_return, volatility, sharpe_ratio,
                    stocks_selected, concentration_ratio
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (portfolio_model_id, pipeline_run_id) DO UPDATE
                SET total_return = EXCLUDED.total_return,
                    volatility = EXCLUDED.volatility,
                    sharpe_ratio = EXCLUDED.sharpe_ratio,
                    stocks_selected = EXCLUDED.stocks_selected,
                    concentration_ratio = EXCLUDED.concentration_ratio,
                    updated_at = NOW()
            """, (
                model_id, self.run_id,
                portfolio_return, portfolio_vol, sharpe_ratio,
                int(significant_mask.sum()),
                float(weights[significant_mask][:10].sum())  # Top 10 concentration
            ))
            
            # Insert portfolio composition
            for i, (_, stock) in enumerate(stocks_df.iterrows()):
                if weights[i] > min_weight:
                    cur.execute("""
                        INSERT INTO portfolio_compositions (
                            portfolio_model_id, stock_id, pipeline_run_id,
                            weight, expected_return, risk_contribution
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (
                        model_id, stock['id'], self.run_id,
                        float(weights[i]),
                        float(stock['expected_return']),
                        float(weights[i] * stock['volatility'] / portfolio_vol) if portfolio_vol > 0 else 0
                    ))
        
        return 1
    
    def _generate_mock_metrics(self, symbol: str) -> Dict:
        """Generate mock metrics for testing"""
        np.random.seed(hash(symbol) % 10000)
        base_price = np.random.uniform(50, 500)
        
        return {
            'current_price': base_price,
            'target_price': base_price * np.random.uniform(0.9, 1.3),
            'analyst_count': np.random.randint(5, 30),
            'annual_return': np.random.uniform(-0.1, 0.4),
            'volatility': np.random.uniform(0.15, 0.45),
            'sharpe_ratio': np.random.uniform(-0.5, 2.0),
            'pe_ratio': np.random.uniform(10, 40),
            'market_cap': np.random.uniform(1e9, 1e12),
            'beta': np.random.uniform(0.5, 2.0)
        }
    
    def _get_hardcoded_nasdaq100(self) -> pd.DataFrame:
        """Get hardcoded NASDAQ-100 list for testing"""
        nasdaq_100 = [
            ('AAPL', 'Apple Inc.', 'Technology', 'Consumer Electronics'),
            ('MSFT', 'Microsoft Corporation', 'Technology', 'Software'),
            ('GOOGL', 'Alphabet Inc. Class A', 'Technology', 'Internet'),
            ('AMZN', 'Amazon.com Inc.', 'Consumer Cyclical', 'E-Commerce'),
            ('NVDA', 'NVIDIA Corporation', 'Technology', 'Semiconductors'),
            ('META', 'Meta Platforms Inc.', 'Technology', 'Social Media'),
            ('TSLA', 'Tesla Inc.', 'Consumer Cyclical', 'Automobiles'),
            ('AVGO', 'Broadcom Inc.', 'Technology', 'Semiconductors'),
            ('ORCL', 'Oracle Corporation', 'Technology', 'Software'),
            ('COST', 'Costco Wholesale', 'Consumer Defensive', 'Retail'),
            ('ADBE', 'Adobe Inc.', 'Technology', 'Software'),
            ('CRM', 'Salesforce Inc.', 'Technology', 'Software'),
            ('NFLX', 'Netflix Inc.', 'Communication', 'Entertainment'),
            ('AMD', 'Advanced Micro Devices', 'Technology', 'Semiconductors'),
            ('PEP', 'PepsiCo Inc.', 'Consumer Defensive', 'Beverages'),
            ('CSCO', 'Cisco Systems', 'Technology', 'Networking'),
            ('TMUS', 'T-Mobile US', 'Communication', 'Telecom'),
            ('INTC', 'Intel Corporation', 'Technology', 'Semiconductors'),
            ('INTU', 'Intuit Inc.', 'Technology', 'Software'),
            ('QCOM', 'Qualcomm Inc.', 'Technology', 'Semiconductors'),
        ]
        
        return pd.DataFrame(nasdaq_100, columns=['symbol', 'companyName', 'sector', 'industry'])


def main():
    """Main entry point"""
    pipeline = DatabaseOnlyPipeline()
    
    # Get max_stocks from environment or use default
    max_stocks = int(os.environ.get('MAX_STOCKS', 20))
    
    logger.info(f"Starting database-only pipeline with {max_stocks} stocks")
    result = pipeline.run_complete_pipeline(max_stocks=max_stocks)
    
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'success' else 1


if __name__ == '__main__':
    sys.exit(main())