# AWS Dependency Analysis Report

## Overview
This document analyzes all AWS dependencies in the portfolio optimization application to facilitate migration to self-hosted Docker deployment.

## Lambda Functions Analysis

### 1. nasdaq_analyzer (Phase 1)
**Purpose**: Scrapes NASDAQ-100 components and calculates undervaluation rates

**AWS Dependencies**:
- `boto3` - AWS SDK for S3 operations
- `S3Handler` class from shared utils
- `LambdaConfig` class for configuration
- Lambda handler function pattern

**S3 Operations**:
- Writes to: `{raw_data_prefix}nasdaq_100_analysis_{timestamp}.csv`
- Writes to: `{processed_data_prefix}nasdaq_100_analysis.csv`
- Writes to: `{results_prefix}phase1/nasdaq_analysis_summary_{timestamp}.json`

**Environment Variables**:
- `MAX_STOCKS` (default: 100)
- `S3_BUCKET_NAME` (from LambdaConfig)

**External APIs**:
- Wikipedia for NASDAQ-100 components list
- yfinance for stock data

### 2. stock_data_fetcher (Phase 2)
**Purpose**: Downloads 5-year historical data and calculates returns/volatility

**AWS Dependencies**:
- `boto3` - AWS SDK for S3 operations
- `S3Handler` class from shared utils
- `LambdaConfig` class for configuration
- Lambda handler function pattern

**S3 Operations**:
- Reads from: `{processed_data_prefix}nasdaq_100_analysis.csv`
- Writes individual stock data: `{stocks_data_prefix}{symbol}.csv`
- Writes to: `{raw_data_prefix}nasdaq_100_with_returns_{timestamp}.csv`
- Writes to: `{processed_data_prefix}nasdaq_100_with_returns.csv`
- Writes to: `{results_prefix}phase2/stock_data_summary_{timestamp}.json`

**Environment Variables**:
- `MAX_STOCKS` (default: all from input)
- `S3_BUCKET_NAME` (from LambdaConfig)

**External APIs**:
- yfinance for historical stock data

### 3. portfolio_optimizer (Phase 3)
**Purpose**: Runs Mean-Variance, Risk Parity, and Black-Litterman optimization

**AWS Dependencies**:
- `boto3` - AWS SDK for S3 operations
- `S3Handler` class from shared utils
- `LambdaConfig` class for configuration
- Lambda handler function pattern

**S3 Operations**:
- Reads from: `{processed_data_prefix}nasdaq_100_with_returns.csv`
- Reads individual stocks: `{stocks_data_prefix}{symbol}.csv`
- Writes to: `{results_prefix}phase3/optimization_results_{model}_{timestamp}.json`
- Writes to: `{results_prefix}phase3/portfolio_weights_{model}_{timestamp}.csv`
- Writes to: `{results_prefix}phase3/optimization_summary_{timestamp}.json`

**Environment Variables**:
- `RISK_FREE_RATE` (default: 0.02)
- `S3_BUCKET_NAME` (from LambdaConfig)

## Shared Utilities (utils.py)
**Components**:
- `S3Handler`: Wrapper for S3 operations (upload_csv, download_csv, upload_json)
- `LambdaConfig`: Configuration management
- `create_lambda_response`: Lambda response formatter
- `parse_lambda_event`: Event parser

## Dashboard Analysis

### streamlit_app_comprehensive.py
**AWS Dependencies**:
- `boto3` client for S3 access
- Direct S3 bucket operations throughout

**S3 Data Access Patterns**:
- Reads optimization results from `results/phase3/`
- Reads stock data from `stock_data/`
- Reads processed data from `processed_data/`
- Monitors CloudWatch logs
- Checks Lambda function statuses

**CloudWatch Integration**:
- Monitors Lambda execution logs
- Displays system health metrics
- Shows pipeline execution history

## S3 Bucket Structure
```
portfolio-optimization-bucket/
├── raw_data/
│   ├── nasdaq_100_analysis_{timestamp}.csv
│   └── nasdaq_100_with_returns_{timestamp}.csv
├── processed_data/
│   ├── nasdaq_100_analysis.csv
│   └── nasdaq_100_with_returns.csv
├── stock_data/
│   └── {SYMBOL}.csv (for each stock)
└── results/
    ├── phase1/
    │   └── nasdaq_analysis_summary_{timestamp}.json
    ├── phase2/
    │   └── stock_data_summary_{timestamp}.json
    └── phase3/
        ├── optimization_results_{model}_{timestamp}.json
        ├── portfolio_weights_{model}_{timestamp}.csv
        └── optimization_summary_{timestamp}.json
```

## Step Functions Orchestration
- Sequential execution: Phase1 → Phase2 → Phase3
- 10-second wait between phases
- Retry logic: 2 attempts with exponential backoff
- EventBridge triggers monthly execution

## Migration Requirements

### Code Changes Needed:
1. **Remove Lambda Handlers**: Convert `lambda_handler(event, context)` to regular Python functions
2. **Replace S3 Operations**: Change S3Handler to LocalFileHandler
3. **Remove AWS SDK**: Replace boto3 with local file I/O
4. **Combine Services**: Merge three Lambda functions into unified pipeline
5. **Local Scheduling**: Replace EventBridge with cron or Python scheduler

### Data Storage Migration:
1. S3 buckets → Local directories under `/data/`
2. Maintain same folder structure locally
3. Implement file cleanup for old data
4. Add local caching layer

### Configuration Changes:
1. Environment variables remain similar
2. Remove AWS-specific configs
3. Add local paths configuration
4. Add Cloudflare Tunnel settings

### Dashboard Modifications:
1. Replace boto3 S3 client with local file access
2. Remove CloudWatch monitoring
3. Add local system monitoring (disk usage, process status)
4. Implement basic authentication
5. Add rate limiting for public access

## Recommended Architecture

### Services:
1. **data-pipeline**: Combined Python service (all 3 Lambda functions)
2. **streamlit-app**: Modified dashboard for local data
3. **scheduler**: Cron-like service for monthly runs
4. **redis** (optional): Caching layer

### Docker Volumes:
- `data-volume`: Persistent storage for all data
- `config-volume`: Configuration files

### Networks:
- Internal network for service communication
- Cloudflare Tunnel for external access to Streamlit only