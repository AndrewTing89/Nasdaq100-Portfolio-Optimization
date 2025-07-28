#!/bin/bash

# Portfolio Dashboard EC2 Deployment Script
# Run this on your EC2 instance

echo "🚀 Starting Portfolio Dashboard Deployment..."

# Update system
sudo yum update -y
echo "✅ System updated"

# Install Python and required packages
sudo yum install python3 python3-pip git htop -y
echo "✅ Python installed"

# Install Python dependencies
pip3 install --user streamlit pandas plotly boto3 numpy python-dateutil
echo "✅ Python packages installed"

# Create application directory
mkdir -p ~/portfolio-dashboard
cd ~/portfolio-dashboard

# Copy your dashboard file (you'll need to upload this)
echo "📁 Please upload your streamlit_app_comprehensive.py to this directory"
echo "   Use: scp -i your-key.pem streamlit_app_comprehensive.py ec2-user@your-ip:~/portfolio-dashboard/"

# Create systemd service file for auto-restart
sudo tee /etc/systemd/system/portfolio-dashboard.service > /dev/null <<EOF
[Unit]
Description=Portfolio Optimization Dashboard
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/portfolio-dashboard
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
echo ""
echo "🔑 Next steps:"
echo "1. Upload your streamlit app file"
echo "2. Configure AWS credentials"
echo "3. Start the service"
echo ""
echo "Commands to run:"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable portfolio-dashboard"
echo "  sudo systemctl start portfolio-dashboard"
echo "  sudo systemctl status portfolio-dashboard"