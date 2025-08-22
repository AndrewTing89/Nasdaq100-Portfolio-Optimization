# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Portfolio optimization system that analyzes NASDAQ-100 stocks using quantitative strategies to determine if active optimization can outperform the vanilla index on a risk-adjusted basis. Live demo: http://52.53.227.136:8501

## Architecture

### Dual Deployment Options:
1. **AWS Cloud-Native**: Lambda functions + S3 + Step Functions + EventBridge + EC2
2. **Self-Hosted Docker**: PostgreSQL + Redis + Nginx + Docker Compose

### Three-Phase Data Pipeline:
1. **Phase 1** (`src/nasdaq_analyzer/`): Scrapes NASDAQ-100 components, fetches prices and analyst targets
2. **Phase 2** (`src/stock_data_fetcher/`): Downloads 5-year historical data, calculates returns/volatility
3. **Phase 3** (`src/portfolio_optimizer/`): Implements Mean-Variance, Risk Parity, and Black-Litterman models

## Key Commands

### Self-Hosted Docker Deployment
```bash
# Full deployment
cd self-hosted
./deploy.sh

# Specific operations
./deploy.sh build    # Build Docker images
./deploy.sh start    # Start all services
./deploy.sh stop     # Stop all services
./deploy.sh status   # Check service status
./deploy.sh logs     # View service logs

# Run pipeline manually
./run_pipeline.sh
```

### AWS Deployment
```bash
# Build Lambda container
cd src/nasdaq_analyzer
docker build --platform linux/amd64 -t nasdaq-analyzer .

# Deploy Step Functions
aws stepfunctions create-state-machine \
  --name portfolio-optimization-pipeline \
  --definition file://aws-deployment/step-functions/step-functions-simple.json \
  --role-arn arn:aws:iam::YOUR-ACCOUNT:role/StepFunctionsRole
```

### Dashboard
```bash
# Run Streamlit dashboard locally
cd dashboard
streamlit run streamlit_app_comprehensive.py

# Self-hosted dashboard
cd self-hosted/dashboard
streamlit run app.py
```

### Testing Individual Components
```bash
# Test each phase independently
cd src/nasdaq_analyzer && python app.py
cd src/stock_data_fetcher && python app.py
cd src/portfolio_optimizer && python app.py
```

## Code Structure

### Key Directories:
- `src/`: AWS Lambda function code for each pipeline phase
- `aws-deployment/`: AWS-specific deployment configurations
- `self-hosted/`: Docker-based deployment with all services
- `dashboard/`: Streamlit visualization dashboard

### Important Files:
- `src/*/app.py`: Main logic for each pipeline phase
- `self-hosted/docker-compose.yml`: Production Docker configuration
- `self-hosted/src/pipeline.py`: Unified pipeline orchestrator
- `dashboard/streamlit_app_comprehensive.py`: Main dashboard interface

## Environment Configuration

### Required Environment Variables:
```bash
# Financial Data
FMP_API_KEY=USIa8HA0z2NCAdBwL1ZEHnpMaxe73DF8

# AWS (if using cloud deployment)
S3_BUCKET_NAME=your-portfolio-bucket
AWS_DEFAULT_REGION=us-west-1

# Portfolio Optimization Parameters
RISK_FREE_RATE=0.02
MAX_STOCKS=100
MIN_WEIGHT_THRESHOLD=0.01
RISK_AVERSION=2.5
TAU=0.025
```

## Data Flow

1. **Input**: NASDAQ-100 stock tickers scraped from Wikipedia
2. **Processing**: 
   - Current prices and analyst targets (Phase 1)
   - 5-year historical data via yfinance (Phase 2)
   - Portfolio optimization with three models (Phase 3)
3. **Output**: Optimized portfolio allocations stored in S3 or PostgreSQL
4. **Visualization**: Interactive Streamlit dashboard with risk-return analysis

## Portfolio Optimization Models

- **Mean-Variance (Markowitz)**: Maximizes Sharpe ratio for optimal risk-adjusted returns
- **Risk Parity**: Allocates equal risk contribution across all assets
- **Black-Litterman**: Bayesian approach incorporating market equilibrium and investor views

## Service Endpoints

- Dashboard: `http://localhost:8501`
- API: `http://localhost:8080`
- Nginx Proxy: `http://localhost:80`

## Development Tips

- Pipeline execution takes 20-30 minutes for all 100 stocks
- Use `./run_pipeline.sh` for testing the complete pipeline locally
- Check logs with `docker-compose logs -f [service_name]` for debugging
- The dashboard automatically refreshes data from the latest pipeline run
- For production, ensure proper API keys and AWS credentials are configured