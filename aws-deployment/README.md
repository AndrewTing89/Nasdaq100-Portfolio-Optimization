# AWS Deployment Files

This directory contains all AWS-specific deployment files for the Portfolio Optimization application.

## Structure

- **src/** - Lambda functions (nasdaq_analyzer, stock_data_fetcher, portfolio_optimizer)
- **dashboard/** - EC2 deployment scripts and AWS-connected Streamlit app
- **step-functions/** - Step Functions state machine definitions
- **TECHNICAL_CHALLENGES_AWS.md** - AWS-specific technical challenges and solutions

## Components

### Lambda Functions
- nasdaq_analyzer - Analyzes NASDAQ-100 constituents
- stock_data_fetcher - Fetches historical stock data
- portfolio_optimizer - Runs optimization algorithms

### Dashboard
- streamlit_app_aws.py - AWS-integrated dashboard
- deploy_ec2.sh - EC2 deployment script
- security_setup.sh - AWS security configuration
- requirements_ec2.txt - EC2 Python dependencies

### Orchestration
- step-functions-simple.json - Step Functions workflow definition

## Usage

This directory is maintained for reference and potential AWS deployment needs. For self-hosted deployment, use the ../self-hosted directory instead.