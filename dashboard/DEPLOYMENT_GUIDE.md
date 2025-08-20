# 📚 Deployment Guide: Technical Analysis Feature

## Option A: Test Locally First (Recommended)

### Step 1: Test on your local machine
```bash
cd "/Users/ndting/Desktop/Portfolio Optimization Project/AWS Deployment/dashboard"
chmod +x test_local.sh
./test_local.sh
```

Open http://localhost:8501 in your browser and test:
- Navigate to the new "📊 Technical Analysis" page
- Try analyzing a stock (e.g., AAPL)
- Verify the charts and indicators work

### Step 2: If local test passes, deploy to AWS

## Option B: Direct AWS Deployment

### Method 1: Quick Update (If EC2 is already running)

1. **SSH into your EC2 instance:**
```bash
ssh -i your-key.pem ec2-user@your-ec2-ip
```

2. **Navigate to the dashboard directory:**
```bash
cd ~/portfolio-dashboard
```

3. **Pull the latest changes:**
```bash
# If you have git setup on EC2:
git fetch origin
git checkout feature/technical-analysis-page
git pull

# OR manually copy the files:
exit  # Exit SSH first
scp -i your-key.pem technical_analysis.py ec2-user@your-ec2-ip:~/portfolio-dashboard/dashboard/
scp -i your-key.pem streamlit_app_comprehensive.py ec2-user@your-ec2-ip:~/portfolio-dashboard/dashboard/
scp -i your-key.pem requirements.txt ec2-user@your-ec2-ip:~/portfolio-dashboard/dashboard/
```

4. **Install new dependencies:**
```bash
ssh -i your-key.pem ec2-user@your-ec2-ip
pip3 install --user yfinance pandas-ta
```

5. **Restart the service:**
```bash
sudo systemctl restart portfolio-dashboard
sudo systemctl status portfolio-dashboard
```

### Method 2: Full Re-deployment

1. **SSH into EC2:**
```bash
ssh -i your-key.pem ec2-user@your-ec2-ip
```

2. **Run the updated deployment script:**
```bash
# First, upload the new deployment script
exit  # Exit SSH
scp -i your-key.pem deploy_ec2_updated.sh ec2-user@your-ec2-ip:~/

# SSH back in and run it
ssh -i your-key.pem ec2-user@your-ec2-ip
chmod +x deploy_ec2_updated.sh
./deploy_ec2_updated.sh
```

## 🔍 Verification Steps

After deployment, verify everything works:

1. **Check service status:**
```bash
sudo systemctl status portfolio-dashboard
```

2. **Check logs for errors:**
```bash
sudo journalctl -u portfolio-dashboard -n 50
```

3. **Test in browser:**
- Go to: http://your-ec2-ip:8501
- Navigate to "📊 Technical Analysis" page
- Try analyzing a stock

## 🔧 Troubleshooting

### If the page doesn't load:
```bash
# Check if the service is running
sudo systemctl status portfolio-dashboard

# Check for import errors
sudo journalctl -u portfolio-dashboard | grep -i error

# Manually test
cd ~/portfolio-dashboard/dashboard
/home/ec2-user/.local/bin/streamlit run streamlit_app_comprehensive.py
```

### If Yahoo Finance doesn't work:
- This might be due to rate limiting
- Try again after a few minutes
- Consider implementing caching for production

### If dependencies fail to install:
```bash
# Try installing with sudo
sudo pip3 install yfinance pandas-ta

# Or use --break-system-packages flag
pip3 install --user --break-system-packages yfinance pandas-ta
```

## 🚀 Production Considerations

1. **Security Group**: Ensure port 8501 is open in your EC2 security group
2. **Elastic IP**: Use an Elastic IP for consistent access
3. **Domain Name**: Consider setting up a domain name with Route 53
4. **HTTPS**: Set up an Application Load Balancer with SSL certificate
5. **Caching**: Implement Redis or similar for caching stock data
6. **Rate Limiting**: Add rate limiting for Yahoo Finance API calls

## 📝 Notes

- The technical analysis page will work independently of your S3 data
- Yahoo Finance has unofficial rate limits - be mindful of this in production
- Consider adding error handling for when Yahoo Finance is unavailable
- You might want to merge to main branch after testing on feature branch