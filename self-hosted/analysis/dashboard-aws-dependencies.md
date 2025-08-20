# Dashboard AWS Dependencies Analysis

## Overview
The Streamlit dashboard (`dashboard/streamlit_app_comprehensive.py`) is heavily dependent on AWS services. This document provides a comprehensive analysis of all AWS dependencies and a modification plan for local deployment.

## AWS Dependencies Analysis

### 1. boto3 Client Initialization and Usage

#### S3 Client (Line 124, 364, 481, 1782)
- **File:Line:** `124`, `364`, `481`, `1782`
- **Code Pattern:** `boto3.client('s3', region_name='us-west-1')`
- **Usage:** Primary data retrieval mechanism for all dashboard data

#### Lambda Client (Line 340)
- **File:Line:** `340`
- **Code Pattern:** `boto3.client('lambda', region_name='us-west-1')`
- **Usage:** Health check for Lambda functions

#### Step Functions Client (Line 372, 1694)
- **File:Line:** `372`, `1694`
- **Code Pattern:** `boto3.client('stepfunctions', region_name='us-west-1')`
- **Usage:** Pipeline status monitoring and execution history

#### EventBridge Scheduler Client (Line 389)
- **File:Line:** `389`
- **Code Pattern:** `boto3.client('scheduler', region_name='us-west-1')`
- **Usage:** Schedule monitoring for automated pipeline

#### EventBridge Events Client (Line 453)
- **File:Line:** `453`
- **Code Pattern:** `boto3.client('events', region_name='us-west-1')`
- **Usage:** Fallback schedule monitoring

### 2. S3 Data Retrieval Patterns

#### Bucket Configuration
- **File:Line:** `122`, `242`
- **Hardcoded Bucket:** `"portfolio-optimization-jwj"`
- **Region:** `us-west-1`

#### Data Loading Methods

**CSV Files (Lines 127-136):**
```python
def load_csv(_self, key: str) -> Optional[pd.DataFrame]:
    response = _self.s3_client.get_object(Bucket=_self.bucket_name, Key=key)
    csv_string = response['Body'].read().decode('utf-8')
    df = pd.read_csv(io.StringIO(csv_string))
```

**JSON Files (Lines 139-148):**
```python  
def load_json(_self, key: str) -> Optional[Dict]:
    response = _self.s3_client.get_object(Bucket=_self.bucket_name, Key=key)
    json_string = response['Body'].read().decode('utf-8')
    data = json.loads(json_string)
```

**File Listing (Lines 150-160):**
```python
def list_files(self, prefix: str) -> List[str]:
    response = self.s3_client.list_objects_v2(
        Bucket=self.bucket_name,
        Prefix=prefix
    )
    return [obj['Key'] for obj in response.get('Contents', [])]
```

#### Critical Data Paths (Lines 251-327)
- `processed/nasdaq_100_analysis.csv`
- `processed/nasdaq_100_with_returns.csv`
- `results/final/` (portfolio optimization results)
- `results/phase1/` (NASDAQ analysis summaries)
- `results/phase2/` (historical data summaries)
- `data/stocks/` (individual stock data)

### 3. CloudWatch Integrations
- **None Found:** No direct CloudWatch logging or metrics integration

### 4. Authentication/Authorization Mechanisms
- **File:Line:** Implicit throughout boto3 usage
- **Method:** AWS credential chain (IAM roles, environment variables, AWS credentials file)
- **No explicit authentication code** - relies on AWS SDK default credential resolution

### 5. Environment Variables
- **Bucket Name:** Hardcoded as `"portfolio-optimization-jwj"` (Line 242)
- **Region:** Hardcoded as `'us-west-1'` throughout
- **No environment variable usage found**

### 6. Data Refresh and Caching Strategies

#### Streamlit Caching (Lines 126, 138)
```python
@st.cache_data(ttl=300)  # Cache for 5 minutes
```
- **TTL:** 5 minutes for both CSV and JSON loading
- **Cache Strategy:** Function-level caching with Streamlit's built-in mechanism

#### Real-time Health Checks (Line 329)
- AWS service health checks performed on each page load
- No persistent caching for health status

### 7. AWS-Specific Configurations

#### Hardcoded ARN (Line 374)
```python
stateMachineArn='arn:aws:states:us-west-1:901398601400:stateMachine:portfolio-optimization-pipeline'
```

#### Lambda Function Names (Line 341)
```python
function_names = ['nasdaq-analyzer-docker', 'stock-data-fetcher-docker', 'portfolio-optimizer-docker']
```

#### EventBridge Rule Names (Line 454)
```python
rule_names = ['portfolio-monthly-trigger', 'portfolio-daily-trigger', 'portfolio-optimization-trigger']
```

## Line-by-Line AWS Dependency Inventory

| Line | Code | AWS Service | Description |
|------|------|-------------|-------------|
| 12 | `import boto3` | All | Core AWS SDK import |
| 124 | `boto3.client('s3', region_name='us-west-1')` | S3 | S3 client initialization |
| 130 | `_self.s3_client.get_object()` | S3 | CSV file retrieval |
| 142 | `_self.s3_client.get_object()` | S3 | JSON file retrieval |
| 153 | `_self.s3_client.list_objects_v2()` | S3 | File listing |
| 171 | `data_loader.list_files("data/stocks/")` | S3 | Stock data discovery |
| 182 | `data_loader.load_csv(stock_file)` | S3 | Individual stock loading |
| 242 | `"portfolio-optimization-jwj"` | S3 | Hardcoded bucket name |
| 251-313 | Multiple S3 data loading calls | S3 | Core data pipeline |
| 340 | `boto3.client('lambda')` | Lambda | Lambda health checks |
| 346 | `lambda_client.get_function()` | Lambda | Function status check |
| 364 | `boto3.client('s3')` | S3 | S3 health check client |
| 365 | `s3_client.head_bucket()` | S3 | Bucket accessibility check |
| 372 | `boto3.client('stepfunctions')` | Step Functions | Pipeline client |
| 373 | `stepfunctions_client.describe_state_machine()` | Step Functions | State machine status |
| 389 | `boto3.client('scheduler')` | EventBridge | Scheduler client |
| 453 | `boto3.client('events')` | EventBridge | Events client fallback |
| 481 | `boto3.client('s3')` | S3 | Data age checking |
| 1694 | `boto3.client('stepfunctions')` | Step Functions | Execution history |
| 1782 | `boto3.client('s3')` | S3 | Historical data loading |

## Modification Plan for Local Deployment

### 1. Data Source Replacement

#### Replace S3DataLoader Class (Lines 119-161)
**Current:**
```python
class S3DataLoader:
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
        self.s3_client = boto3.client('s3', region_name='us-west-1')
```

**Replacement:**
```python
class LocalDataLoader:
    def __init__(self, data_directory: str = "./data"):
        self.data_directory = Path(data_directory)
        
    def load_csv(self, key: str) -> Optional[pd.DataFrame]:
        file_path = self.data_directory / key
        if file_path.exists():
            return pd.read_csv(file_path)
        return None
        
    def load_json(self, key: str) -> Optional[Dict]:
        file_path = self.data_directory / key
        if file_path.exists():
            with open(file_path, 'r') as f:
                return json.load(f)
        return None
        
    def list_files(self, prefix: str) -> List[str]:
        prefix_path = self.data_directory / prefix
        if prefix_path.exists():
            return [str(p.relative_to(self.data_directory)) 
                   for p in prefix_path.rglob("*") if p.is_file()]
        return []
```

### 2. Environment Variable Changes

#### Add Environment Configuration (New)
```python
import os
from pathlib import Path

# Configuration
DATA_DIRECTORY = os.getenv('DATA_DIRECTORY', './data')
CACHE_TTL = int(os.getenv('CACHE_TTL', '300'))  # 5 minutes default
```

#### Update Session State Initialization (Line 239-244)
**Current:**
```python
if 'bucket_name' not in st.session_state:
    st.session_state.bucket_name = "portfolio-optimization-jwj"
if 'data_loader' not in st.session_state:
    st.session_state.data_loader = S3DataLoader(st.session_state.bucket_name)
```

**Replacement:**
```python
if 'data_directory' not in st.session_state:
    st.session_state.data_directory = DATA_DIRECTORY
if 'data_loader' not in st.session_state:
    st.session_state.data_loader = LocalDataLoader(st.session_state.data_directory)
```

### 3. Health Check Replacement

#### Remove AWS Health Checks (Lines 329-475)
Replace `check_aws_service_health()` with:
```python
def check_local_system_health() -> Dict[str, Dict[str, str]]:
    services = {
        'data_files': {'status': 'Unknown', 'detail': 'Checking...'},
        'cache': {'status': 'Unknown', 'detail': 'Checking...'},
        'compute': {'status': 'Unknown', 'detail': 'Checking...'}
    }
    
    # Check data directory accessibility
    try:
        data_path = Path(DATA_DIRECTORY)
        if data_path.exists():
            file_count = len(list(data_path.rglob("*")))
            services['data_files'] = {'status': 'Healthy', 'detail': f'{file_count} files available'}
        else:
            services['data_files'] = {'status': 'Error', 'detail': 'Data directory not found'}
    except Exception:
        services['data_files'] = {'status': 'Error', 'detail': 'Access denied'}
    
    # Check memory usage
    import psutil
    memory = psutil.virtual_memory()
    if memory.percent < 80:
        services['compute'] = {'status': 'Healthy', 'detail': f'{memory.percent:.1f}% memory used'}
    else:
        services['compute'] = {'status': 'Partial', 'detail': f'{memory.percent:.1f}% memory used'}
    
    return services
```

### 4. Data Age Calculation (Lines 477-523)
Replace S3-based data age with local file modification times:
```python
def get_data_age(data_loader, prefix: str) -> str:
    try:
        prefix_path = Path(data_loader.data_directory) / prefix
        if not prefix_path.exists():
            return "No data found"
        
        # Find most recent file
        files = list(prefix_path.rglob("*"))
        if not files:
            return "No data found"
            
        latest_file = max(files, key=lambda x: x.stat().st_mtime)
        last_modified = datetime.fromtimestamp(latest_file.stat().st_mtime)
        
        # Calculate time difference (same logic as before)
        time_diff = datetime.now() - last_modified
        # ... rest of time formatting logic remains the same
        
    except Exception:
        return "Unknown"
```

### 5. Historical Tracking Modifications (Lines 1688-1861)

#### Remove Step Functions Integration (Lines 1693-1774)
Replace with local execution log:
```python
def get_local_execution_history():
    log_file = Path(DATA_DIRECTORY) / "execution_log.json"
    if log_file.exists():
        with open(log_file, 'r') as f:
            return json.load(f)
    return []
    
def log_execution(phase: str, status: str, duration: float = None):
    log_file = Path(DATA_DIRECTORY) / "execution_log.json"
    history = get_local_execution_history()
    history.append({
        'Date': datetime.now().isoformat(),
        'Phase': phase,
        'Status': status,
        'Duration_Minutes': duration
    })
    with open(log_file, 'w') as f:
        json.dump(history[-50:], f)  # Keep last 50 entries
```

#### Replace S3 Historical Data Loading (Lines 1781-1845)
```python
def get_historical_performance_data(data_loader):
    results_path = Path(data_loader.data_directory) / "results" / "final"
    comparison_files = list(results_path.glob("*performance_comparison*.csv"))
    
    historical_data = []
    for file in sorted(comparison_files)[-10:]:  # Last 10 files
        try:
            timestamp = datetime.fromtimestamp(file.stat().st_mtime)
            df = pd.read_csv(file)
            df['Date'] = timestamp
            historical_data.append(df)
        except Exception:
            continue
            
    return historical_data
```

### 6. Alternative Approaches for Each AWS Service

#### S3 Storage → Local File System
- **Current:** Centralized S3 bucket with structured paths
- **Alternative:** Local directory structure mirroring S3 paths
- **Benefits:** No network latency, offline capability
- **Trade-offs:** No automatic backup, manual file management

#### Lambda Functions → Local Scripts
- **Current:** Serverless functions for data processing
- **Alternative:** Python scripts with cron scheduling
- **Benefits:** No cold starts, easier debugging
- **Trade-offs:** Requires server maintenance

#### Step Functions → Local Orchestration
- **Current:** AWS Step Functions for pipeline orchestration  
- **Alternative:** Python workflow manager (Airflow, Prefect, or simple scripts)
- **Benefits:** Full control, easier customization
- **Trade-offs:** More complex setup

#### EventBridge → Cron Jobs
- **Current:** EventBridge Scheduler for automation
- **Alternative:** System cron jobs or Python APScheduler
- **Benefits:** Simpler configuration
- **Trade-offs:** Less sophisticated scheduling options

### 7. Required File Structure for Local Deployment

```
data/
├── raw/                          # Raw scraped data
├── processed/                    # Processed analysis files
│   ├── nasdaq_100_analysis.csv
│   └── nasdaq_100_with_returns.csv
├── results/                      # Analysis results
│   ├── phase1/                   # NASDAQ analysis
│   ├── phase2/                   # Historical data
│   └── final/                    # Portfolio optimization
└── stocks/                       # Individual stock data
    ├── AAPL.csv
    ├── MSFT.csv
    └── ...
```

## Implementation Priority

### Phase 1: Core Data Loading (High Priority)
1. Replace S3DataLoader with LocalDataLoader
2. Update session state initialization
3. Test basic data loading functionality

### Phase 2: Health Monitoring (Medium Priority)
1. Implement local system health checks
2. Replace AWS service monitoring
3. Update system status page

### Phase 3: Historical Tracking (Low Priority)
1. Implement local execution logging
2. Replace Step Functions integration
3. Update historical performance tracking

## Migration Checklist

- [ ] Install required dependencies: `psutil`, `pathlib`
- [ ] Create local data directory structure
- [ ] Implement LocalDataLoader class
- [ ] Update configuration and session state
- [ ] Replace AWS health checks
- [ ] Implement local execution logging
- [ ] Test all dashboard pages
- [ ] Create data migration scripts from S3 to local
- [ ] Set up automated local pipeline execution
- [ ] Update documentation

## Estimated Effort
- **Development Time:** 2-3 days
- **Testing Time:** 1 day
- **Data Migration:** 0.5 day
- **Total:** ~4 days

This analysis provides a complete roadmap for converting the AWS-dependent dashboard to a self-hosted local version while maintaining all functionality.