#!/bin/bash

# Updated Portfolio Dashboard EC2 Deployment Script with Technical Analysis
# Run this on your EC2 instance

echo "🚀 Starting Portfolio Dashboard Deployment (with Technical Analysis)..."

# Update system
sudo yum update -y
echo "✅ System updated"

# Install Python and required packages
sudo yum install python3 python3-pip git htop -y
echo "✅ Python installed"

# Install Python dependencies (including new ones for technical analysis)
pip3 install --user streamlit pandas plotly boto3 numpy python-dateutil yfinance pandas-ta
echo "✅ Python packages installed (including technical analysis libraries)"

# Create application directory
mkdir -p ~/portfolio-dashboard
cd ~/portfolio-dashboard

# Pull latest code from GitHub (if using git)
echo "📥 Pulling latest code from GitHub..."
if [ -d ".git" ]; then
    git pull origin feature/technical-analysis-page
else
    echo "   First time setup - clone your repository:"
    echo "   git clone -b feature/technical-analysis-page https://github.com/AndrewTing89/Nasdaq100-Portfolio-Optimization.git ."
fi

# Create systemd service file for auto-restart
sudo tee /etc/systemd/system/portfolio-dashboard.service > /dev/null <<EOF
[Unit]
Description=Portfolio Optimization Dashboard with Technical Analysis
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/portfolio-dashboard/dashboard
Environment=PATH=/home/ec2-user/.local/bin
ExecStart=/home/ec2-user/.local/bin/streamlit run streamlit_app_comprehensive.py --server.port=8501 --server.address=0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Set environment variables
echo "export S3_BUCKET_NAME=portfolio-optimization-jwj" >> ~/.bashrc
echo "export AWS_DEFAULT_REGION=us-west-1" >> ~/.bashrc
source ~/.bashrc

echo "✅ Service file created"

# Restart the service with new code
echo "🔄 Restarting dashboard service..."
sudo systemctl daemon-reload
sudo systemctl restart portfolio-dashboard
sudo systemctl enable portfolio-dashboard

# Check status
sleep 3
sudo systemctl status portfolio-dashboard --no-pager

echo ""
echo "✅ Deployment complete!"
echo "📱 Your dashboard should be accessible at: http://your-ec2-ip:8501"
echo ""
echo "🔧 Useful commands:"
echo "  View logs: sudo journalctl -u portfolio-dashboard -f"
echo "  Restart: sudo systemctl restart portfolio-dashboard"
echo "  Stop: sudo systemctl stop portfolio-dashboard"
echo "  Status: sudo systemctl status portfolio-dashboard"