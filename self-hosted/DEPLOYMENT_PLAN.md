# Ubuntu Server Self-Hosted Deployment Plan

## Overview
Converting AWS-based NASDAQ-100 Portfolio Optimization app to self-hosted Docker deployment with Cloudflare Tunnel for secure public access.

## Architecture Goals
- Complete removal of AWS dependencies (Lambda, S3, Step Functions, EventBridge)
- Docker-based microservices architecture
- Local file storage replacing S3
- Cloudflare Tunnel for secure public access without exposing home network
- Automated scheduling using cron/scheduler service

## Phase 1: Analysis & Research (Subagents Wave 1)
### Agent 1: AWS Lambda Analyzer
**Task**: Analyze all Lambda functions and document AWS dependencies
- [ ] Analyze `src/nasdaq_analyzer/app.py`
- [ ] Analyze `src/stock_data_fetcher/app.py`
- [ ] Analyze `src/portfolio_optimizer/app.py`
- [ ] Document all AWS SDK usage (boto3, S3, Lambda handlers)
- [ ] Identify shared utilities and dependencies
- [ ] Map data flow between Lambda functions
- [ ] Document S3 bucket structure and usage patterns

### Agent 2: Dashboard Analyzer
**Task**: Review Streamlit dashboard for AWS dependencies
- [ ] Analyze `dashboard/streamlit_app_comprehensive.py`
- [ ] Identify all boto3/S3 calls
- [ ] Document data retrieval patterns
- [ ] List CloudWatch integration points
- [ ] Map UI components to data sources
- [ ] Identify authentication/security mechanisms

### Agent 3: Architecture Designer
**Task**: Design Docker architecture and deployment strategy
- [ ] Design docker-compose.yml structure
- [ ] Plan service communication (networks, volumes)
- [ ] Design local data storage structure to replace S3
- [ ] Plan scheduling mechanism (cron vs scheduler service)
- [ ] Design Cloudflare Tunnel integration
- [ ] Plan security measures (rate limiting, auth)

## Phase 2: Implementation (Subagents Wave 2)
### Agent 4: Python Service Converter
**Task**: Convert Lambda functions to standalone services
- [ ] Create `self-hosted/src/data_pipeline.py` (unified service)
- [ ] Remove Lambda handlers, convert to regular Python functions
- [ ] Replace S3 operations with local file I/O
- [ ] Implement local scheduling logic
- [ ] Create data models and interfaces
- [ ] Add proper logging for local deployment

### Agent 5: Docker Configuration Creator
**Task**: Create all Docker-related files
- [ ] Create `self-hosted/docker-compose.yml`
- [ ] Create `self-hosted/Dockerfile.dataservice`
- [ ] Create `self-hosted/Dockerfile.dashboard`
- [ ] Set up volume mappings for persistent data
- [ ] Configure service networks
- [ ] Add health checks and restart policies

### Agent 6: Dashboard Adapter
**Task**: Modify Streamlit for local deployment
- [ ] Create `self-hosted/dashboard/app.py`
- [ ] Replace S3 calls with local file access
- [ ] Remove CloudWatch monitoring
- [ ] Add local system monitoring
- [ ] Implement basic authentication
- [ ] Add rate limiting logic

## Phase 3: Infrastructure (Subagents Wave 3)
### Agent 7: Cloudflare Tunnel Setup
**Task**: Configure Cloudflare Tunnel for secure access
- [ ] Create `self-hosted/cloudflare/tunnel-config.yml`
- [ ] Create `self-hosted/cloudflare/setup-tunnel.sh`
- [ ] Document tunnel setup process
- [ ] Configure access policies
- [ ] Set up SSL/TLS termination
- [ ] Add DDoS protection rules

### Agent 8: Deployment Automation
**Task**: Create deployment and maintenance scripts
- [ ] Create `self-hosted/deployment/install.sh`
- [ ] Create `self-hosted/deployment/update.sh`
- [ ] Create `self-hosted/deployment/backup.sh`
- [ ] Create `self-hosted/deployment/monitor.sh`
- [ ] Add systemd service files
- [ ] Create data cleanup scripts

### Agent 9: Documentation
**Task**: Create comprehensive documentation
- [ ] Create `self-hosted/README.md`
- [ ] Create `self-hosted/SETUP_GUIDE.md`
- [ ] Create `self-hosted/cloudflare/TUNNEL_SETUP.md`
- [ ] Document environment variables
- [ ] Create troubleshooting guide
- [ ] Add architecture diagrams

## File Structure (Target)
```
self-hosted/
├── docker-compose.yml
├── .env.example
├── src/
│   ├── data_pipeline.py      # Unified service replacing Lambdas
│   ├── scheduler.py           # Cron replacement
│   ├── models.py             # Data models
│   └── config.py             # Configuration
├── dashboard/
│   ├── app.py                # Modified Streamlit
│   ├── requirements.txt
│   └── Dockerfile
├── data/                     # Local data storage (replaces S3)
│   ├── nasdaq_components/
│   ├── stock_data/
│   ├── optimization_results/
│   └── cache/
├── cloudflare/
│   ├── tunnel-config.yml
│   ├── setup-tunnel.sh
│   └── README.md
├── deployment/
│   ├── install.sh
│   ├── update.sh
│   ├── backup.sh
│   └── monitor.sh
├── config/
│   ├── nginx.conf           # Optional
│   └── redis.conf           # Optional
└── docs/
    ├── README.md
    ├── SETUP_GUIDE.md
    └── TROUBLESHOOTING.md
```

## Key Conversions Required

### AWS Lambda → Local Python Service
```python
# FROM (Lambda):
def lambda_handler(event, context):
    # Lambda logic
    return {"statusCode": 200, "body": json.dumps(result)}

# TO (Local):
def process_data():
    # Same logic
    return result
```

### S3 → Local Filesystem
```python
# FROM (S3):
s3.put_object(Bucket='bucket', Key='path/file.json', Body=data)

# TO (Local):
with open('/data/path/file.json', 'w') as f:
    json.dump(data, f)
```

### Step Functions → Python Scheduler
```python
# FROM (Step Functions):
# Complex state machine

# TO (Scheduler):
schedule.every().month.do(run_pipeline)
```

## Environment Variables
```bash
# Data Processing
MAX_STOCKS=100
RISK_FREE_RATE=0.02
UPDATE_FREQUENCY=monthly

# Cloudflare
TUNNEL_TOKEN=<from cloudflare>
TUNNEL_NAME=portfolio-optimizer

# Security
RATE_LIMIT=100/hour
MAX_CONCURRENT_USERS=10

# Paths
DATA_DIR=/data
CACHE_DIR=/data/cache
```

## Success Criteria
1. All Lambda functions converted to local services
2. Docker containers running successfully
3. Data persistence working with local storage
4. Streamlit dashboard accessible via Cloudflare Tunnel
5. Automated monthly updates functioning
6. No AWS dependencies remaining
7. Secure public access without exposing home IP

## Testing Checklist
- [ ] Docker containers build successfully
- [ ] Services communicate properly
- [ ] Data fetching works (yfinance API)
- [ ] Portfolio optimization calculations correct
- [ ] Dashboard displays data correctly
- [ ] Cloudflare Tunnel connects
- [ ] Public access works securely
- [ ] Scheduled updates trigger properly
- [ ] Data persistence across restarts
- [ ] Resource usage acceptable

## Next Steps After Each Phase
1. After Phase 1: Review analysis results, adjust implementation plan
2. After Phase 2: Test local functionality before adding public access
3. After Phase 3: Full system test, security audit, go live

## Recovery Points
If conversation gets compacted or restarted:
1. Check this file for current phase
2. Review completed tasks (marked with ✓)
3. Check `self-hosted/` directory for created files
4. Continue from last incomplete task