# Portfolio Optimization Docker Deployment

This directory contains a complete Docker-based architecture for the Portfolio Optimization Suite, replacing the original AWS serverless implementation with containerized services.

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Nginx Proxy   │    │   Dashboard     │    │  Data Pipeline  │
│   (Port 80/443) │◄──►│  (Streamlit)    │◄──►│   (Python)      │
│                 │    │   Port 8501     │    │   Port 8080     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐    ┌─────────────────┐
         │              │   Scheduler     │    │     Redis       │
         └──────────────►│    (Cron)       │    │   (Cache)       │
                        │                 │    │   Port 6379     │
                        └─────────────────┘    └─────────────────┘
                                 │
                        ┌─────────────────┐
                        │ Cloudflare      │
                        │ Tunnel          │
                        │ (Optional)      │
                        └─────────────────┘
```

## Services

### 1. Data Pipeline Service
- **Container**: `portfolio-data-pipeline`
- **Purpose**: Unified portfolio optimization pipeline
- **Port**: 8080
- **Features**:
  - NASDAQ-100 component analysis
  - Historical data fetching via yfinance
  - Portfolio optimization (Mean-Variance, Risk Parity, Black-Litterman)
  - REST API for health checks and execution
  - File-based storage replacing S3

### 2. Dashboard Service
- **Container**: `portfolio-dashboard`
- **Purpose**: Streamlit-based visualization dashboard
- **Port**: 8501
- **Features**:
  - Interactive portfolio visualization
  - Real-time data access
  - Performance metrics and charts
  - Export capabilities

### 3. Scheduler Service
- **Container**: `portfolio-scheduler`
- **Purpose**: Automated pipeline execution
- **Features**:
  - Configurable cron scheduling
  - Health monitoring
  - Notification support via webhooks
  - Error handling and retries

### 4. Nginx Reverse Proxy
- **Container**: `portfolio-nginx`
- **Purpose**: Load balancing and SSL termination
- **Ports**: 80, 443
- **Features**:
  - Route dashboard and API traffic
  - SSL/TLS support
  - Security headers
  - Rate limiting

### 5. Redis Cache (Optional)
- **Container**: `portfolio-redis`
- **Purpose**: Caching for performance optimization
- **Port**: 6379

### 6. Cloudflare Tunnel (Optional)
- **Container**: `portfolio-cloudflare-tunnel`
- **Purpose**: Secure external access without port forwarding

## Quick Start

### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB+ RAM available
- 10GB+ disk space

### 1. Clone and Setup
```bash
cd self-hosted
cp .env.example .env
# Edit .env file with your configuration
```

### 2. Deploy
```bash
# Make deployment script executable
chmod +x deploy.sh

# Run complete deployment
./deploy.sh deploy
```

### 3. Access
- **Dashboard**: http://localhost:8501
- **API**: http://localhost:8080
- **Nginx Proxy**: http://localhost:80

## Configuration

### Environment Variables (.env)

#### Core Configuration
```bash
# Data storage
HOST_DATA_DIR=./data
HOST_LOGS_DIR=./logs

# Financial parameters
RISK_FREE_RATE=0.02
MAX_STOCKS=100
HISTORICAL_PERIOD=5y

# Scheduling
CRON_SCHEDULE=0 6 * * *  # Daily at 6 AM UTC
```

#### Security & Access
```bash
# SSL (optional)
SSL_ENABLED=false
SSL_CERT_DIR=./config/ssl

# Cloudflare Tunnel (optional)
CLOUDFLARE_TUNNEL_TOKEN=your-token-here
```

#### Resource Limits
```bash
DATA_PIPELINE_MEMORY_LIMIT=2G
DASHBOARD_MEMORY_LIMIT=1G
NGINX_MEMORY_LIMIT=256M
```

### Port Configuration
- `HTTP_PORT=80` - Main HTTP port
- `HTTPS_PORT=443` - HTTPS port (when SSL enabled)
- Dashboard and API ports are internal

## Deployment Commands

```bash
# Complete deployment
./deploy.sh deploy

# Build images only
./deploy.sh build

# Start services
./deploy.sh start

# Stop services
./deploy.sh stop

# View logs
./deploy.sh logs [service-name]

# Check status
./deploy.sh status

# Clean up everything
./deploy.sh clean
```

## Data Management

### Directory Structure
```
data/
├── raw/              # Raw scraped data with timestamps
├── processed/        # Processed datasets
├── stocks/          # Individual stock data files
├── results/         # Optimization results
└── logs/           # Application logs
```

### Backup Strategy
```bash
# Backup data directory
tar -czf backup-$(date +%Y%m%d).tar.gz data/

# Restore from backup
tar -xzf backup-20241201.tar.gz
```

## Monitoring & Health Checks

### Health Endpoints
```bash
# Overall health
curl http://localhost:80/health

# Individual services
curl http://localhost:8080/health          # Pipeline
curl http://localhost:8501/_stcore/health  # Dashboard
```

### Log Monitoring
```bash
# View real-time logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f data-pipeline

# Pipeline logs via API
curl http://localhost:8080/logs?lines=100
```

### Resource Monitoring
```bash
# Check resource usage
docker stats

# Service status
./deploy.sh status
```

## API Usage

### Execute Pipeline
```bash
# Full pipeline execution
curl -X POST http://localhost:8080/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "full", "model_type": "all", "return_type": "both"}'

# Individual phases
curl -X POST http://localhost:8080/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "phase1"}'  # NASDAQ analysis only
```

### Check Execution Status
```bash
curl http://localhost:8080/status
```

### Access Data Files
```bash
# Get results
curl http://localhost:8080/data/results/recommended_portfolio_latest.csv

# Get analysis summary
curl http://localhost:8080/data/results/pipeline_summary_latest.json
```

## Advanced Configuration

### SSL/HTTPS Setup
1. Obtain SSL certificates
2. Place in `./config/ssl/` directory
3. Update `.env`:
   ```bash
   SSL_ENABLED=true
   SSL_CERT_PATH=/etc/nginx/ssl/cert.pem
   SSL_KEY_PATH=/etc/nginx/ssl/key.pem
   ```
4. Restart services: `./deploy.sh restart`

### Cloudflare Tunnel
1. Create tunnel at https://one.dash.cloudflare.com/
2. Get tunnel token
3. Update `.env`:
   ```bash
   CLOUDFLARE_TUNNEL_TOKEN=your-token-here
   ```
4. Deploy with Cloudflare profile:
   ```bash
   docker-compose --profile cloudflare up -d
   ```

### Custom Scheduling
```bash
# Daily at 2 AM
CRON_SCHEDULE=0 2 * * *

# Weekly on Monday at 6 AM
CRON_SCHEDULE=0 6 * * 1

# Monthly on 1st day at 6 AM
CRON_SCHEDULE=0 6 1 * *
```

### Notification Setup
```bash
# Enable notifications
NOTIFICATION_ENABLED=true
WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK

# Or Discord webhook
WEBHOOK_URL=https://discord.com/api/webhooks/YOUR/DISCORD/WEBHOOK
```

## Troubleshooting

### Common Issues

#### Services Not Starting
```bash
# Check Docker daemon
docker info

# Check logs
./deploy.sh logs

# Rebuild images
./deploy.sh build
```

#### Permission Issues
```bash
# Fix data directory permissions
sudo chown -R $(id -u):$(id -g) data/
chmod -R 755 data/
```

#### Memory Issues
```bash
# Check available memory
free -h

# Reduce resource limits in .env
DATA_PIPELINE_MEMORY_LIMIT=1G
DASHBOARD_MEMORY_LIMIT=512M
```

#### Network Issues
```bash
# Check Docker networks
docker network ls

# Recreate network
docker-compose down
docker-compose up -d
```

### Performance Tuning

#### For High-Frequency Trading
```bash
# Reduce request delays
REQUEST_DELAY=0.5

# Increase parallel processing
MAX_WORKERS=10
```

#### For Large Datasets
```bash
# Increase memory limits
DATA_PIPELINE_MEMORY_LIMIT=4G

# Enable Redis caching
REDIS_ENABLED=true
```

## Security Best Practices

1. **Network Security**
   - Use internal Docker networks
   - Limit exposed ports
   - Enable SSL/TLS

2. **Access Control**
   - Implement basic authentication
   - Use Cloudflare Access for external access
   - Regular security updates

3. **Data Protection**
   - Regular backups
   - Encrypt sensitive data
   - Monitor access logs

## Migration from AWS

### Data Migration
1. Export S3 data to local storage
2. Update file paths in configuration
3. Test data access in new environment

### Schedule Migration
1. Disable AWS EventBridge rules
2. Configure new cron schedule
3. Monitor execution logs

### Dashboard Migration
1. Update data source configurations
2. Test dashboard functionality
3. Update any hardcoded AWS references

## Production Deployment

### Recommended Setup
- Dedicated server with 8GB+ RAM
- SSD storage for data directory
- Regular automated backups
- Monitoring and alerting
- SSL certificates from Let's Encrypt
- Cloudflare for CDN and security

### Scaling Considerations
- Use external PostgreSQL for larger datasets
- Implement Redis cluster for caching
- Load balance across multiple instances
- Use object storage for long-term data retention

## Support

For issues and questions:
1. Check logs: `./deploy.sh logs`
2. Verify configuration: `./deploy.sh status`
3. Review environment variables in `.env`
4. Check Docker resources: `docker system df`

## License

This Docker deployment configuration is part of the Portfolio Optimization project.