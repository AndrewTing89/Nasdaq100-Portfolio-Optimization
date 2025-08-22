#!/bin/bash

# Run the database-only pipeline to populate PostgreSQL
echo "Running database-only pipeline to populate PostgreSQL..."
echo "This will store ALL data in the database (no CSV files)"

# Set the number of stocks to process (default 20 for testing, use 100 for full)
MAX_STOCKS=${1:-20}

echo "Processing $MAX_STOCKS stocks..."

# Execute the db_only_pipeline.py inside the container
docker exec -e MAX_STOCKS=$MAX_STOCKS portfolio-data-pipeline python /app/db_only_pipeline.py

echo "Database pipeline completed!"

# Check results
echo ""
echo "=== Database Contents ==="
docker exec portfolio-postgres psql -U portfolio_user -d portfolio_optimization -c "
SELECT 'Pipeline Runs:' as table_name, COUNT(*) as count FROM pipeline_runs
UNION ALL
SELECT 'Stocks:', COUNT(*) FROM stocks
UNION ALL  
SELECT 'Stock Metrics:', COUNT(*) FROM stock_metrics
UNION ALL
SELECT 'Portfolio Performance:', COUNT(*) FROM portfolio_performance
UNION ALL
SELECT 'Portfolio Compositions:', COUNT(*) FROM portfolio_compositions;
"

echo ""
echo "=== Latest Portfolio Performance ==="
docker exec portfolio-postgres psql -U portfolio_user -d portfolio_optimization -c "
SELECT 
    pm.model_name,
    pm.optimization_method,
    pp.total_return,
    pp.volatility,
    pp.sharpe_ratio,
    pp.stocks_selected
FROM portfolio_performance pp
JOIN portfolio_models pm ON pp.portfolio_model_id = pm.id
WHERE pp.pipeline_run_id = (
    SELECT id FROM pipeline_runs 
    ORDER BY started_at DESC 
    LIMIT 1
)
ORDER BY pp.sharpe_ratio DESC;
"