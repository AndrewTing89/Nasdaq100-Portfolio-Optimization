# Lambda Functions AWS Dependency Analysis

## Overview

This document provides a comprehensive analysis of the three Lambda functions in the portfolio optimization system, documenting all AWS dependencies, data flow patterns, and migration considerations for containerization.

**Functions Analyzed:**
- `src/nasdaq_analyzer/app.py` - NASDAQ-100 data scraping and undervaluation analysis
- `src/stock_data_fetcher/app.py` - Historical stock data retrieval and metrics calculation  
- `src/portfolio_optimizer/app.py` - Portfolio optimization using multiple models

---

## 1. NASDAQ Analyzer Function Analysis

### Function Signature
```python
def lambda_handler(event, context):
```

### AWS Dependencies

#### Boto3/AWS Service Clients
- **S3 Client**: Accessed through shared `S3Handler` utility class
  - Used for uploading CSV files and JSON summaries
  - Boto3 version: `>=1.28.17`

#### S3 Operations
**Bucket Access Pattern:**
- Bucket name retrieved from `LambdaConfig` (likely environment variable)
- **Write Operations:**
  - `{raw_data_prefix}nasdaq_100_analysis_{timestamp}.csv` - Raw analysis results
  - `{processed_data_prefix}nasdaq_100_analysis.csv` - Latest processed results
  - `{results_prefix}phase1/nasdaq_analysis_summary_{timestamp}.json` - Summary statistics

**Data Patterns:**
- Timestamped raw data for historical tracking
- Latest processed data for downstream consumption
- JSON summaries for reporting and monitoring

#### Environment Variables
- `MAX_STOCKS` - Controls number of stocks to process (default: 100)
- Bucket configuration accessed through `LambdaConfig`
- S3 path prefixes for data organization

#### External Dependencies (Non-AWS)
- **yfinance**: Stock data retrieval
- **requests/BeautifulSoup**: Wikipedia scraping for NASDAQ-100 components
- **pandas**: Data processing
- **numpy**: Numerical operations

#### Shared Utilities Dependencies
```python
sys.path.append('/opt/shared')
from utils import S3Handler, LambdaConfig, create_lambda_response, parse_lambda_event
```

### IAM Permissions Required
- `s3:PutObject` - Upload analysis results and summaries
- `s3:PutObjectAcl` - Set object permissions (if needed)
- Lambda execution role permissions
- CloudWatch Logs permissions for logging

### Data Output
- **Primary Output**: Stock undervaluation analysis with target prices
- **Summary Statistics**: Mean/median undervaluation rates, categorized stocks
- **Data Flow**: Feeds into `stock_data_fetcher` function

---

## 2. Stock Data Fetcher Function Analysis

### Function Signature  
```python
def lambda_handler(event, context):
```

### AWS Dependencies

#### Boto3/AWS Service Clients
- **S3 Client**: Accessed through shared `S3Handler` utility class
  - Read operations from NASDAQ analyzer output
  - Write operations for processed stock data

#### S3 Operations
**Read Operations:**
- Input stock list (configurable via event or default path)
- Default: `{processed_data_prefix}nasdaq_100_analysis.csv`

**Write Operations:**
- `{stocks_data_prefix}{symbol}.csv` - Individual stock historical data files
- `{raw_data_prefix}nasdaq_100_with_returns_{timestamp}.csv` - Raw results with metrics
- `{processed_data_prefix}nasdaq_100_with_returns.csv` - Latest processed results
- `{results_prefix}phase2/stock_metrics_summary_{timestamp}.json` - Processing summary

**Data Patterns:**
- Individual stock files for granular access by portfolio optimizer
- Batch processing with configurable limits
- Comprehensive error tracking and failed stock reporting

#### Environment Variables
- `MAX_STOCKS` - Controls processing limits (default: all available)
- S3 configuration through `LambdaConfig`

#### Event Processing
- Supports multiple trigger types:
  - Manual execution with specified input file
  - S3-triggered execution using uploaded file
  - Scheduled execution using default processed data

#### External Dependencies (Non-AWS)
- **yfinance**: Historical stock data download (5-year period)
- **pandas/numpy**: Data processing and metric calculations
- **scipy**: Not directly used but available

### IAM Permissions Required
- `s3:GetObject` - Read input stock lists
- `s3:PutObject` - Upload individual stock files and results
- Lambda execution role permissions
- CloudWatch Logs permissions

### Data Processing
- **Metrics Calculated**: Annual return and volatility (5-year historical)
- **Data Validation**: Minimum 252 trading days required
- **Error Handling**: Comprehensive tracking of failed downloads
- **Output Format**: Enhanced stock list with financial metrics

---

## 3. Portfolio Optimizer Function Analysis

### Function Signature
```python
def lambda_handler(event, context):
```

### AWS Dependencies

#### Boto3/AWS Service Clients
- **S3 Client**: Most complex S3 usage pattern of the three functions
  - Reads processed stock data and individual stock files
  - Writes multiple portfolio optimization results

#### S3 Operations
**Read Operations:**
- Main input: `{processed_data_prefix}nasdaq_100_with_returns.csv`
- Individual stock data: `{stocks_data_prefix}{symbol}.csv` (for covariance matrix calculation)

**Write Operations (Extensive):**
**Mean-Variance Results:**
- `{results_prefix}final/mv_{return_type}_{portfolio_type}_portfolio_{timestamp}.csv`
- `{results_prefix}final/mv_{return_type}_{portfolio_type}_significant_{timestamp}.csv`

**Risk Parity Results:**
- `{results_prefix}final/rp_{return_type}_portfolio_{timestamp}.csv`  
- `{results_prefix}final/rp_{return_type}_significant_{timestamp}.csv`

**Black-Litterman Results:**
- `{results_prefix}final/bl_{return_type}_portfolio_{timestamp}.csv`
- `{results_prefix}final/bl_{return_type}_significant_{timestamp}.csv`

**Summary Results:**
- `{results_prefix}final/portfolio_performance_comparison_{timestamp}.csv`
- `{results_prefix}final/recommended_portfolio_{timestamp}.csv`
- `{results_prefix}final/recommended_portfolio_significant_{timestamp}.csv`

#### Configuration Parameters
- `min_weight_threshold` - Filter for significant holdings
- `risk_free_rate` - Used in Sharpe ratio calculations
- Model selection: `model_type` ('mv', 'rp', 'bl', 'all')
- Return type: `return_type` ('historical', 'undervalue', 'both')

#### Advanced Portfolio Models
- **Mean-Variance Optimization**: Maximum Sharpe ratio and minimum volatility portfolios
- **Risk Parity**: Equal risk contribution optimization
- **Black-Litterman**: Bayesian approach with investor views
- **Ensemble Approach**: Averaged weights across models

### IAM Permissions Required
- `s3:GetObject` - Read stock data and individual stock files
- `s3:PutObject` - Upload portfolio results and comparisons
- Lambda execution role permissions
- CloudWatch Logs permissions

### Data Processing Complexity
- **Covariance Matrix Calculation**: Downloads and processes individual stock files
- **Multiple Optimization Models**: Parallel execution of different strategies
- **Performance Comparison**: Cross-model analysis and recommendations
- **Significant Holdings Filtering**: Focused results for practical implementation

---

## Inter-Service Communication Patterns

### Step Functions Orchestration
Based on `step-functions-simple.json`:

```
Phase 1: nasdaq-analyzer-docker
    ↓ (10 second wait)
Phase 2: stock-data-fetcher-docker  
    ↓ (10 second wait)
Phase 3: portfolio-optimizer-docker
```

### Data Flow Dependencies

1. **NASDAQ Analyzer → Stock Data Fetcher**
   - Input: `processed/nasdaq_100_analysis.csv`
   - Contains: Company names, symbols, undervaluation rates

2. **Stock Data Fetcher → Portfolio Optimizer**
   - Input: `processed/nasdaq_100_with_returns.csv`
   - Individual files: `stocks/{symbol}.csv`
   - Contains: Historical returns, volatility metrics

3. **Portfolio Optimizer Output**
   - Multiple portfolio configurations
   - Performance comparisons
   - Recommended allocations

### S3 Data Organization Structure
```
bucket/
├── raw/                          # Timestamped raw data
├── processed/                    # Latest processed data  
├── stocks/                       # Individual stock files
└── results/
    ├── phase1/                   # NASDAQ analysis summaries
    ├── phase2/                   # Stock metrics summaries
    └── final/                    # Portfolio optimization results
```

---

## Migration Challenges for Containerization

### 1. Shared Utilities Dependency
**Challenge**: All functions depend on shared utilities at `/opt/shared/utils`
- `S3Handler` class
- `LambdaConfig` class  
- `create_lambda_response` function
- `parse_lambda_event` function

**Solution Requirements:**
- Extract shared utilities to a common module
- Package utilities with each container OR
- Create a shared base image with utilities

### 2. AWS Lambda-Specific Patterns

**Event Processing**: Lambda-specific event parsing
```python
parsed_event = parse_lambda_event(event)
```

**Response Format**: Lambda-specific response structure
```python
return create_lambda_response(200, {...})
```

**Migration Impact**: Requires adaptation for container-based execution

### 3. Environment Configuration

**Current Pattern**: Lambda environment variables through `LambdaConfig`
**Required Environment Variables:**
- `MAX_STOCKS` - Processing limits
- S3 bucket name and path configurations
- Risk-free rate for financial calculations

**Container Requirements:**
- Environment variable injection
- Configuration management system
- Secrets management for AWS credentials

### 4. S3 Access Patterns

**Challenge**: Heavy S3 dependency for data persistence and inter-service communication
**Requirements:**
- AWS credentials management in containers
- S3 endpoint configuration for different environments
- Network connectivity to AWS services

### 5. External API Dependencies

**Rate Limiting Concerns:**
- Wikipedia scraping in NASDAQ analyzer
- Yahoo Finance API calls in stock data fetcher
- Built-in delays and error handling present

**Container Considerations:**
- Network policies for external API access
- Rate limiting and retry mechanisms
- Potential need for API proxies or caching

### 6. Memory and Processing Requirements

**Resource Usage Patterns:**
- **NASDAQ Analyzer**: Light processing, web scraping
- **Stock Data Fetcher**: Moderate processing, 5-year historical data
- **Portfolio Optimizer**: Heavy computation, matrix operations

**Container Sizing Requirements:**
- CPU: Moderate to high for optimization algorithms
- Memory: Variable based on stock count and historical data
- Storage: Temporary storage for CSV processing

---

## Migration Recommendations

### 1. Immediate Actions
1. **Extract Shared Utilities**: Create standalone module for shared functions
2. **Environment Configuration**: Implement container-friendly config management
3. **Event Abstraction**: Create abstraction layer for different trigger types

### 2. Architecture Adaptations
1. **Replace Lambda Handler**: Implement HTTP/message-based endpoints
2. **Add Health Checks**: Container readiness and liveness probes  
3. **Implement Graceful Shutdown**: Handle container termination signals

### 3. Data Persistence Strategy
1. **S3 Compatibility**: Maintain S3 for data storage and inter-service communication
2. **Alternative Storage**: Consider additional storage options for local development
3. **Data Validation**: Enhanced error handling for network-dependent operations

### 4. Orchestration Migration
1. **Step Functions Alternative**: Container orchestration (Kubernetes Jobs, etc.)
2. **Event-Driven Architecture**: Message queue system for service communication
3. **Scheduling**: Cron-based or event-based triggering

### 5. Monitoring and Observability
1. **Structured Logging**: Replace CloudWatch-specific logging
2. **Metrics Collection**: Application metrics for container environments
3. **Distributed Tracing**: Track requests across containerized services

---

## Required Environment Variables Summary

### All Functions
- `AWS_REGION` - AWS region configuration
- `S3_BUCKET_NAME` - Primary storage bucket
- `AWS_ACCESS_KEY_ID` - AWS credentials (if not using IAM roles)
- `AWS_SECRET_ACCESS_KEY` - AWS credentials (if not using IAM roles)

### Function-Specific
- `MAX_STOCKS` - Processing limits (default varies by function)
- `RISK_FREE_RATE` - Portfolio optimization parameter
- `MIN_WEIGHT_THRESHOLD` - Significant holdings filter

### S3 Path Configurations
- `RAW_DATA_PREFIX` - Raw data storage path
- `PROCESSED_DATA_PREFIX` - Processed data storage path  
- `STOCKS_DATA_PREFIX` - Individual stock files path
- `RESULTS_PREFIX` - Results storage path

---

## Conclusion

The Lambda functions demonstrate a sophisticated financial analysis pipeline with heavy AWS integration. Migration to containerized environments requires careful attention to:

1. **Shared utility extraction and management**
2. **Event processing abstraction**  
3. **S3-centric data flow preservation**
4. **External API rate limiting and error handling**
5. **Resource requirements for complex financial calculations**

The modular design and clear data flow patterns make containerization feasible, but the deep AWS integration requires thoughtful abstraction to maintain functionality while gaining deployment flexibility.