-- Portfolio Optimization Database Schema
-- Tracks historical pipeline runs and portfolio performance

-- Create schema if not exists
CREATE SCHEMA IF NOT EXISTS portfolio;

-- Set default search path
SET search_path TO portfolio, public;

-- ==================== PIPELINE RUNS ====================
-- Track each execution of the portfolio optimization pipeline
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    run_type VARCHAR(50) NOT NULL, -- 'manual', 'scheduled', 'api_triggered'
    status VARCHAR(20) NOT NULL DEFAULT 'running', -- 'running', 'completed', 'failed', 'partial'
    
    -- Configuration used for this run
    config JSONB NOT NULL DEFAULT '{}',
    fmp_api_calls INTEGER DEFAULT 0,
    data_source VARCHAR(20) DEFAULT 'fmp', -- 'fmp', 'csv', 'mixed'
    
    -- Execution metadata
    start_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP WITH TIME ZONE,
    execution_time_seconds NUMERIC(10,2),
    error_message TEXT,
    
    -- Phase completion tracking
    phase1_completed BOOLEAN DEFAULT FALSE,
    phase2_completed BOOLEAN DEFAULT FALSE,
    phase3_completed BOOLEAN DEFAULT FALSE,
    
    -- Data statistics
    total_stocks_analyzed INTEGER,
    stocks_selected INTEGER,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==================== PORTFOLIO RESULTS ====================
-- Store optimization results for each model in each run
CREATE TABLE IF NOT EXISTS portfolio_results (
    result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    model_type VARCHAR(50) NOT NULL, -- 'mv_historical_max_sharpe', 'mv_historical_min_vol', etc.
    
    -- Performance metrics
    expected_return NUMERIC(10,6) NOT NULL,
    volatility NUMERIC(10,6) NOT NULL,
    sharpe_ratio NUMERIC(10,6) NOT NULL,
    sortino_ratio NUMERIC(10,6),
    max_drawdown NUMERIC(10,6),
    calmar_ratio NUMERIC(10,6),
    
    -- Risk metrics
    var_95 NUMERIC(10,6), -- Value at Risk (95% confidence)
    cvar_95 NUMERIC(10,6), -- Conditional Value at Risk
    beta NUMERIC(10,6),
    
    -- Portfolio composition
    num_stocks INTEGER NOT NULL,
    concentration_top5 NUMERIC(10,6), -- Weight of top 5 holdings
    concentration_top10 NUMERIC(10,6), -- Weight of top 10 holdings
    effective_diversification NUMERIC(10,6),
    
    -- Additional metrics
    turnover_rate NUMERIC(10,6),
    rebalancing_frequency VARCHAR(20),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==================== STOCK ALLOCATIONS ====================
-- Track individual stock allocations for each portfolio
CREATE TABLE IF NOT EXISTS stock_allocations (
    allocation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    result_id UUID NOT NULL REFERENCES portfolio_results(result_id) ON DELETE CASCADE,
    run_id UUID NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    
    ticker VARCHAR(10) NOT NULL,
    company_name VARCHAR(255),
    sector VARCHAR(100),
    
    -- Allocation details
    weight NUMERIC(10,8) NOT NULL,
    dollar_allocation NUMERIC(15,2),
    shares_to_buy INTEGER,
    
    -- Stock metrics at time of selection
    current_price NUMERIC(12,4),
    market_cap NUMERIC(20,2),
    pe_ratio NUMERIC(10,2),
    dividend_yield NUMERIC(10,6),
    
    -- Performance metrics
    expected_return NUMERIC(10,6),
    volatility NUMERIC(10,6),
    correlation_to_portfolio NUMERIC(10,6),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==================== MARKET DATA SNAPSHOT ====================
-- Store market conditions at time of each run
CREATE TABLE IF NOT EXISTS market_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    
    -- Market indices
    sp500_level NUMERIC(12,2),
    nasdaq_level NUMERIC(12,2),
    vix_level NUMERIC(10,2),
    
    -- Interest rates
    risk_free_rate NUMERIC(10,6),
    ten_year_yield NUMERIC(10,6),
    
    -- Market statistics
    market_volatility NUMERIC(10,6),
    market_return_ytd NUMERIC(10,6),
    market_pe_ratio NUMERIC(10,2),
    
    -- Breadth indicators
    advance_decline_ratio NUMERIC(10,4),
    new_highs INTEGER,
    new_lows INTEGER,
    
    snapshot_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==================== PERFORMANCE TRACKING ====================
-- Track actual performance vs predictions over time
CREATE TABLE IF NOT EXISTS performance_tracking (
    tracking_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    result_id UUID NOT NULL REFERENCES portfolio_results(result_id) ON DELETE CASCADE,
    run_id UUID NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    
    tracking_date DATE NOT NULL,
    days_since_creation INTEGER,
    
    -- Predicted vs Actual
    predicted_return NUMERIC(10,6),
    actual_return NUMERIC(10,6),
    return_difference NUMERIC(10,6),
    
    predicted_volatility NUMERIC(10,6),
    actual_volatility NUMERIC(10,6),
    volatility_difference NUMERIC(10,6),
    
    -- Cumulative performance
    cumulative_return NUMERIC(10,6),
    cumulative_benchmark_return NUMERIC(10,6),
    excess_return NUMERIC(10,6),
    
    -- Risk metrics
    current_drawdown NUMERIC(10,6),
    tracking_error NUMERIC(10,6),
    information_ratio NUMERIC(10,6),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(result_id, tracking_date)
);

-- ==================== REBALANCING HISTORY ====================
-- Track portfolio rebalancing events
CREATE TABLE IF NOT EXISTS rebalancing_history (
    rebalance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_run_id UUID NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    new_run_id UUID NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    
    rebalance_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    rebalance_reason VARCHAR(100), -- 'scheduled', 'threshold_breach', 'manual'
    
    -- Changes summary
    stocks_added INTEGER,
    stocks_removed INTEGER,
    total_turnover NUMERIC(10,6),
    transaction_cost_estimate NUMERIC(12,2),
    
    -- Performance since last rebalance
    performance_since_last NUMERIC(10,6),
    volatility_since_last NUMERIC(10,6),
    sharpe_since_last NUMERIC(10,6),
    
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==================== INDEXES ====================
-- Create indexes for better query performance
CREATE INDEX idx_pipeline_runs_timestamp ON pipeline_runs(run_timestamp DESC);
CREATE INDEX idx_pipeline_runs_status ON pipeline_runs(status);
CREATE INDEX idx_portfolio_results_run_id ON portfolio_results(run_id);
CREATE INDEX idx_portfolio_results_model_type ON portfolio_results(model_type);
CREATE INDEX idx_stock_allocations_run_id ON stock_allocations(run_id);
CREATE INDEX idx_stock_allocations_ticker ON stock_allocations(ticker);
CREATE INDEX idx_performance_tracking_date ON performance_tracking(tracking_date);
CREATE INDEX idx_performance_tracking_result_id ON performance_tracking(result_id);

-- ==================== VIEWS ====================
-- Create useful views for analysis

-- Latest portfolio for each model type
CREATE OR REPLACE VIEW latest_portfolios AS
SELECT DISTINCT ON (pr.model_type)
    pr.*,
    pl.run_timestamp,
    pl.status
FROM portfolio_results pr
JOIN pipeline_runs pl ON pr.run_id = pl.run_id
WHERE pl.status = 'completed'
ORDER BY pr.model_type, pl.run_timestamp DESC;

-- Portfolio performance summary
CREATE OR REPLACE VIEW portfolio_performance_summary AS
SELECT 
    pr.run_id,
    pl.run_timestamp,
    pr.model_type,
    pr.expected_return,
    pr.volatility,
    pr.sharpe_ratio,
    pr.num_stocks,
    COUNT(DISTINCT pt.tracking_date) as tracking_days,
    AVG(pt.actual_return) as avg_actual_return,
    AVG(pt.return_difference) as avg_prediction_error
FROM portfolio_results pr
JOIN pipeline_runs pl ON pr.run_id = pl.run_id
LEFT JOIN performance_tracking pt ON pr.result_id = pt.result_id
GROUP BY pr.run_id, pl.run_timestamp, pr.model_type, pr.expected_return, 
         pr.volatility, pr.sharpe_ratio, pr.num_stocks;

-- Stock allocation frequency
CREATE OR REPLACE VIEW stock_selection_frequency AS
SELECT 
    ticker,
    company_name,
    COUNT(DISTINCT run_id) as selection_count,
    AVG(weight) as avg_weight,
    MAX(weight) as max_weight,
    MIN(weight) as min_weight,
    AVG(expected_return) as avg_expected_return
FROM stock_allocations
GROUP BY ticker, company_name
ORDER BY selection_count DESC;

-- ==================== FUNCTIONS ====================

-- Function to calculate portfolio tracking error
CREATE OR REPLACE FUNCTION calculate_tracking_error(
    p_result_id UUID,
    p_days INTEGER DEFAULT 30
) RETURNS NUMERIC AS $$
DECLARE
    v_tracking_error NUMERIC;
BEGIN
    SELECT STDDEV(return_difference) INTO v_tracking_error
    FROM performance_tracking
    WHERE result_id = p_result_id
    AND tracking_date >= CURRENT_DATE - p_days;
    
    RETURN COALESCE(v_tracking_error, 0);
END;
$$ LANGUAGE plpgsql;

-- Function to get best performing portfolio over a period
CREATE OR REPLACE FUNCTION get_best_portfolio(
    p_start_date DATE,
    p_end_date DATE DEFAULT CURRENT_DATE
) RETURNS TABLE (
    model_type VARCHAR,
    total_return NUMERIC,
    volatility NUMERIC,
    sharpe_ratio NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        pr.model_type,
        MAX(pt.cumulative_return) as total_return,
        AVG(pt.actual_volatility) as volatility,
        CASE 
            WHEN AVG(pt.actual_volatility) > 0 
            THEN (MAX(pt.cumulative_return) - 0.02) / AVG(pt.actual_volatility)
            ELSE 0 
        END as sharpe_ratio
    FROM portfolio_results pr
    JOIN performance_tracking pt ON pr.result_id = pt.result_id
    WHERE pt.tracking_date BETWEEN p_start_date AND p_end_date
    GROUP BY pr.model_type
    ORDER BY sharpe_ratio DESC;
END;
$$ LANGUAGE plpgsql;

-- ==================== TRIGGERS ====================

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_pipeline_runs_updated_at 
    BEFORE UPDATE ON pipeline_runs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Calculate execution time on pipeline completion
CREATE OR REPLACE FUNCTION calculate_execution_time()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'completed' AND OLD.status != 'completed' THEN
        NEW.end_time = CURRENT_TIMESTAMP;
        NEW.execution_time_seconds = EXTRACT(EPOCH FROM (NEW.end_time - NEW.start_time));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER calculate_pipeline_execution_time
    BEFORE UPDATE ON pipeline_runs
    FOR EACH ROW
    EXECUTE FUNCTION calculate_execution_time();

-- ==================== INITIAL DATA ====================
-- Insert a test run to verify schema
INSERT INTO pipeline_runs (run_type, status, config)
VALUES ('manual', 'completed', '{"test": true}')
ON CONFLICT DO NOTHING;

-- Grant permissions
GRANT ALL ON SCHEMA portfolio TO portfolio_user;
GRANT ALL ON ALL TABLES IN SCHEMA portfolio TO portfolio_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA portfolio TO portfolio_user;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA portfolio TO portfolio_user;