#\!/bin/bash
# Quick DNS check for onlyapps-studio.com
echo "Checking DNS status for onlyapps-studio.com..."
echo "=========================================="
echo ""
echo "1. Checking nameservers:"
dig +short NS onlyapps-studio.com
echo ""
echo "2. Checking if pointing to Cloudflare:"
dig NS onlyapps-studio.com | grep cloudflare
echo ""
echo "3. Checking A records:"
dig +short A onlyapps-studio.com
echo ""
echo "Run ./self-hosted/check-domain.sh for continuous monitoring"
