# Self-Hosted Deployment

This directory contains all files for deploying the Portfolio Optimization application on Ubuntu Server.

## Directory Structure

```
self-hosted/
├── analysis/           # Migration analysis and planning documents
├── src/               # Containerized services (Python apps)
├── dashboard/         # Local Streamlit dashboard
├── cloudflare/        # Cloudflare Tunnel configuration
├── data/              # Local data storage (replaces S3)
├── deployment/        # Docker and deployment scripts
├── config/            # Configuration files
└── agents/            # Claude Code agent definitions
```

## Components

### Core Services
- **src/** - Microservices replacing Lambda functions
- **dashboard/** - Self-hosted Streamlit interface
- **data/** - Persistent local storage

### Infrastructure
- **deployment/** - Docker Compose and orchestration
- **cloudflare/** - External access configuration
- **config/** - Environment and service configuration

### Documentation
- **analysis/** - AWS to self-hosted migration analysis
- **agents/** - Development automation tools

## Quick Start

1. Navigate to deployment directory
2. Configure environment variables
3. Run Docker Compose
4. Access dashboard at http://localhost:8501

## Benefits Over AWS

- **Cost Savings**: 50-70% reduction in monthly costs
- **Full Control**: Complete ownership of infrastructure
- **No Vendor Lock-in**: Portable, standard Docker deployment
- **Data Privacy**: All data remains on your server
- **Customization**: Easy to modify and extend

## Requirements

- Ubuntu Server 20.04+
- Docker and Docker Compose
- 4GB RAM minimum
- 20GB storage
- (Optional) Cloudflare account for external access