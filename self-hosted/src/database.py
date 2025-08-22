#!/usr/bin/env python3
"""
Database module for portfolio optimization pipeline
Handles all PostgreSQL operations with checkpoint/resume support
"""

import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from psycopg2.pool import SimpleConnectionPool
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from contextlib import contextmanager


class DatabaseManager:
    """Manages PostgreSQL database operations for the portfolio pipeline"""
    
    def __init__(self, connection_string: str = None):
        """Initialize database connection pool"""
        self.connection_string = connection_string or os.environ.get(
            'DATABASE_URL',
            'postgresql://portfolio_user:secure_password@postgres:5432/portfolio_optimization'
        )
        
        # Create connection pool
        self.pool = SimpleConnectionPool(
            1, 5,  # min 1, max 5 connections
            self.connection_string
        )
        
        logging.info("Database connection pool initialized")
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool"""
        conn = self.pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            self.pool.putconn(conn)
    
    def close(self):
        """Close all connections in the pool"""
        if self.pool:
            self.pool.closeall()
    
    # ============= Pipeline Run Management =============
    
    def create_pipeline_run(self, run_type: str = 'full') -> int:
        """Create a new pipeline run and return its ID"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO pipeline_runs (
                        run_type, status, phase, started_at
                    ) VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, (run_type, 'running', 'phase1_nasdaq', datetime.now()))
                run_id = cur.fetchone()[0]
                logging.info(f"Created pipeline run ID: {run_id}")
                return run_id
    
    def update_pipeline_status(self, run_id: int, status: str, phase: str = None, 
                              error_message: str = None, stocks_processed: int = None):
        """Update pipeline run status"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                update_fields = ["status = %s", "updated_at = %s"]
                params = [status, datetime.now()]
                
                if phase:
                    update_fields.append("phase = %s")
                    params.append(phase)
                
                if error_message:
                    update_fields.append("error_message = %s")
                    params.append(error_message)
                
                if stocks_processed is not None:
                    update_fields.append("stocks_processed = %s")
                    params.append(stocks_processed)
                
                if status == 'completed':
                    update_fields.append("completed_at = %s")
                    params.append(datetime.now())
                
                params.append(run_id)
                query = f"UPDATE pipeline_runs SET {', '.join(update_fields)} WHERE id = %s"
                cur.execute(query, params)
    
    def get_last_successful_run(self) -> Optional[Dict]:
        """Get the last successful pipeline run"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM pipeline_runs 
                    WHERE status = 'completed' 
                    ORDER BY completed_at DESC 
                    LIMIT 1
                """)
                return cur.fetchone()
    
    # ============= Stock Data Management =============
    
    def upsert_stocks(self, stocks_df: pd.DataFrame, run_id: int):
        """Insert or update stock information"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Prepare data for insertion
                stocks_data = []
                for _, row in stocks_df.iterrows():
                    stocks_data.append((
                        row.get('symbol'),
                        row.get('name', row.get('companyName')),
                        row.get('sector'),
                        row.get('subSector', row.get('industry')),
                        row.get('marketCap'),
                        True,  # is_active
                        datetime.now(),
                        datetime.now()
                    ))
                
                # Upsert stocks
                execute_values(cur, """
                    INSERT INTO stocks (symbol, company_name, sector, industry, 
                                      market_cap, is_active, created_at, updated_at)
                    VALUES %s
                    ON CONFLICT (symbol) 
                    DO UPDATE SET 
                        company_name = EXCLUDED.company_name,
                        sector = EXCLUDED.sector,
                        industry = EXCLUDED.industry,
                        market_cap = EXCLUDED.market_cap,
                        is_active = EXCLUDED.is_active,
                        updated_at = EXCLUDED.updated_at
                """, stocks_data)
                
                logging.info(f"Upserted {len(stocks_data)} stocks for run {run_id}")
    
    def insert_stock_metrics(self, symbol: str, metrics: Dict, run_id: int):
        """Insert stock metrics for a given symbol"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Get stock ID
                cur.execute("SELECT id FROM stocks WHERE symbol = %s", (symbol,))
                result = cur.fetchone()
                if not result:
                    logging.warning(f"Stock {symbol} not found in database")
                    return
                
                stock_id = result[0]
                
                # Insert metrics
                cur.execute("""
                    INSERT INTO stock_metrics (
                        stock_id, pipeline_run_id, current_price, target_price,
                        analyst_count, pe_ratio, peg_ratio, dividend_yield,
                        price_to_book, beta, annual_return_5y, annual_volatility_5y,
                        sharpe_ratio, max_drawdown, undervaluation_rate, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    stock_id, run_id,
                    metrics.get('current_price'),
                    metrics.get('target_price'),
                    metrics.get('analyst_count', 0),
                    metrics.get('pe_ratio'),
                    metrics.get('peg_ratio'),
                    metrics.get('dividend_yield'),
                    metrics.get('price_to_book'),
                    metrics.get('beta'),
                    metrics.get('annual_return'),
                    metrics.get('volatility'),
                    metrics.get('sharpe_ratio'),
                    metrics.get('max_drawdown'),
                    metrics.get('undervaluation_rate'),
                    datetime.now()
                ))
    
    def insert_stock_prices(self, symbol: str, prices_df: pd.DataFrame, run_id: int):
        """Insert historical stock prices"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Get stock ID
                cur.execute("SELECT id FROM stocks WHERE symbol = %s", (symbol,))
                result = cur.fetchone()
                if not result:
                    return
                
                stock_id = result[0]
                
                # Prepare batch insert data
                price_data = []
                for _, row in prices_df.iterrows():
                    price_data.append((
                        stock_id,
                        row['date'],
                        row.get('open'),
                        row.get('high'),
                        row.get('low'),
                        row.get('close'),
                        row.get('adjClose', row.get('close')),
                        row.get('volume'),
                        datetime.now()
                    ))
                
                # Batch insert (only insert recent data to save space)
                # Keep last 252 trading days (1 year)
                recent_data = price_data[-252:] if len(price_data) > 252 else price_data
                
                execute_values(cur, """
                    INSERT INTO stock_prices (
                        stock_id, date, open_price, high_price, low_price, close_price, 
                        adjusted_close, volume, created_at
                    ) VALUES %s
                    ON CONFLICT (stock_id, date) DO NOTHING
                """, recent_data)
    
    # ============= Portfolio Model Management =============
    
    def upsert_portfolio_model(self, model_name: str, model_type: str, 
                               optimization_method: str, params: Dict) -> int:
        """Insert or get portfolio model ID"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Check if model exists
                cur.execute("""
                    SELECT id FROM portfolio_models 
                    WHERE model_name = %s AND model_type = %s 
                    AND optimization_method = %s
                """, (model_name, model_type, optimization_method))
                
                result = cur.fetchone()
                if result:
                    return result[0]
                
                # Insert new model
                cur.execute("""
                    INSERT INTO portfolio_models (
                        model_name, model_type, optimization_method,
                        description, risk_free_rate, risk_aversion, tau,
                        min_weight_threshold, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    model_name, model_type, optimization_method,
                    params.get('description', ''),
                    params.get('risk_free_rate', 0.02),
                    params.get('risk_aversion', 2.5),
                    params.get('tau', 0.025),
                    params.get('min_weight_threshold', 0.001),
                    datetime.now()
                ))
                
                return cur.fetchone()[0]
    
    def insert_portfolio_performance(self, model_id: int, run_id: int, 
                                    performance: Dict):
        """Insert portfolio performance metrics"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO portfolio_performance (
                        portfolio_model_id, pipeline_run_id, total_return,
                        volatility, sharpe_ratio, max_drawdown, value_at_risk_95,
                        stocks_selected, concentration_ratio, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (portfolio_model_id, pipeline_run_id) 
                    DO UPDATE SET
                        total_return = EXCLUDED.total_return,
                        volatility = EXCLUDED.volatility,
                        sharpe_ratio = EXCLUDED.sharpe_ratio,
                        max_drawdown = EXCLUDED.max_drawdown,
                        updated_at = EXCLUDED.created_at
                """, (
                    model_id, run_id,
                    performance.get('total_return'),
                    performance.get('volatility'),
                    performance.get('sharpe_ratio'),
                    performance.get('max_drawdown'),
                    performance.get('value_at_risk_95'),
                    performance.get('stocks_selected'),
                    performance.get('concentration_ratio'),
                    datetime.now()
                ))
    
    def insert_portfolio_composition(self, model_id: int, run_id: int, 
                                    allocations: pd.DataFrame):
        """Insert portfolio allocations"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Prepare allocation data
                composition_data = []
                for _, row in allocations.iterrows():
                    # Get stock ID
                    cur.execute("SELECT id FROM stocks WHERE symbol = %s", 
                              (row['Symbol'],))
                    result = cur.fetchone()
                    if result:
                        composition_data.append((
                            model_id,
                            result[0],  # stock_id
                            run_id,
                            row['Weight'],
                            row.get('Expected_Return'),
                            row.get('Risk_Contribution'),
                            datetime.now()
                        ))
                
                # Batch insert allocations
                if composition_data:
                    execute_values(cur, """
                        INSERT INTO portfolio_compositions (
                            portfolio_model_id, stock_id, pipeline_run_id,
                            weight, expected_return, risk_contribution, created_at
                        ) VALUES %s
                    """, composition_data)
    
    # ============= Data Retrieval for Dashboard =============
    
    def get_latest_portfolios(self) -> pd.DataFrame:
        """Get latest portfolio performance for all models"""
        with self.get_connection() as conn:
            query = """
                SELECT 
                    pm.model_name,
                    pm.model_type,
                    pm.optimization_method,
                    pp.total_return,
                    pp.volatility,
                    pp.sharpe_ratio,
                    pp.max_drawdown,
                    pp.stocks_selected,
                    pp.created_at
                FROM portfolio_performance pp
                JOIN portfolio_models pm ON pp.portfolio_model_id = pm.id
                WHERE pp.pipeline_run_id = (
                    SELECT id FROM pipeline_runs 
                    WHERE status = 'completed' 
                    ORDER BY completed_at DESC 
                    LIMIT 1
                )
                ORDER BY pp.sharpe_ratio DESC
            """
            return pd.read_sql(query, conn)
    
    def get_portfolio_allocations(self, model_name: str) -> pd.DataFrame:
        """Get portfolio allocations for a specific model"""
        with self.get_connection() as conn:
            query = """
                SELECT 
                    s.symbol,
                    s.company_name,
                    pc.weight,
                    pc.expected_return,
                    pc.risk_contribution,
                    sm.current_price,
                    sm.target_price,
                    sm.analyst_count
                FROM portfolio_compositions pc
                JOIN stocks s ON pc.stock_id = s.id
                JOIN portfolio_models pm ON pc.portfolio_model_id = pm.id
                LEFT JOIN stock_metrics sm ON s.id = sm.stock_id
                WHERE pm.model_name = %s
                AND pc.pipeline_run_id = (
                    SELECT id FROM pipeline_runs 
                    WHERE status = 'completed' 
                    ORDER BY completed_at DESC 
                    LIMIT 1
                )
                AND pc.weight > 0.001
                ORDER BY pc.weight DESC
            """
            return pd.read_sql(query, conn, params=(model_name,))
    
    def get_historical_performance(self, days: int = 30) -> pd.DataFrame:
        """Get historical performance for all models over time"""
        with self.get_connection() as conn:
            query = """
                SELECT 
                    pm.model_name,
                    DATE(pp.created_at) as date,
                    pp.sharpe_ratio,
                    pp.total_return,
                    pp.volatility
                FROM portfolio_performance pp
                JOIN portfolio_models pm ON pp.portfolio_model_id = pm.id
                JOIN pipeline_runs pr ON pp.pipeline_run_id = pr.id
                WHERE pr.status = 'completed'
                AND pp.created_at >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY pp.created_at, pm.model_name
            """
            return pd.read_sql(query, conn, params=(days,))
    
    def get_checkpoint_info(self, run_id: int) -> Optional[Dict]:
        """Get checkpoint information for resuming a pipeline run"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT phase, last_processed_stock, stocks_processed
                    FROM pipeline_runs
                    WHERE id = %s
                """, (run_id,))
                return cur.fetchone()


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize database manager
    db = DatabaseManager()
    
    # Create a pipeline run
    run_id = db.create_pipeline_run('test')
    print(f"Created pipeline run: {run_id}")
    
    # Update status
    db.update_pipeline_status(run_id, 'running', 'phase1_nasdaq')
    
    # Get latest portfolios
    portfolios = db.get_latest_portfolios()
    print(f"Found {len(portfolios)} portfolio models")
    
    # Clean up
    db.close()