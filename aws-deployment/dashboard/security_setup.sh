#!/bin/bash

# Security hardening for EC2 instance
echo "🔒 Configuring security..."

# Update all packages
sudo yum update -y

# Install fail2ban to prevent brute force attacks
sudo yum install fail2ban -y
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Configure firewall (only allow SSH and Streamlit)
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8501 -j ACCEPT
sudo iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
sudo iptables -A INPUT -j DROP

# Save iptables rules
sudo service iptables save

# Set up automatic security updates
echo "0 2 * * * root yum update -y --security" | sudo tee -a /etc/crontab

# Create non-root user for additional security (optional)
# sudo adduser dashboarduser
# sudo usermod -aG wheel dashboarduser

echo "✅ Basic security configured"
echo "🔑 Remember to:"
echo "  - Keep your SSH key secure"
echo "  - Regular security updates"
echo "  - Monitor CloudWatch logs"