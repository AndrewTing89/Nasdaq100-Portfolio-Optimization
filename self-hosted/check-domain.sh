#!/bin/bash
# Domain activation checker for onlyapps-studio.com

DOMAIN="onlyapps-studio.com"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "🔍 Checking domain activation status for $DOMAIN"
echo "================================================"

while true; do
    # Check nameservers
    echo -e "\n${YELLOW}Checking nameservers...${NC}"
    NS_CHECK=$(nslookup -type=NS $DOMAIN 2>/dev/null | grep "nameserver")
    
    if echo "$NS_CHECK" | grep -q "cloudflare.com"; then
        echo -e "${GREEN}✓ Cloudflare nameservers detected!${NC}"
        
        # Check if domain resolves
        echo -e "\n${YELLOW}Checking DNS resolution...${NC}"
        IP_CHECK=$(nslookup $DOMAIN 2>/dev/null | grep "Address" | tail -1)
        
        if [[ ! -z "$IP_CHECK" ]]; then
            echo -e "${GREEN}✓ Domain is resolving to: $IP_CHECK${NC}"
            
            # Check SSL certificate
            echo -e "\n${YELLOW}Checking SSL certificate...${NC}"
            SSL_CHECK=$(curl -Is https://$DOMAIN 2>&1 | head -1)
            
            if [[ $SSL_CHECK == *"HTTP"* ]]; then
                echo -e "${GREEN}✓ SSL certificate is working!${NC}"
                echo -e "\n${GREEN}🎉 DOMAIN IS FULLY ACTIVE!${NC}"
                echo -e "${GREEN}Your domain is ready to be configured with the tunnel.${NC}"
                echo -e "\nNext steps:"
                echo "1. Go to Zero Trust → Networks → Tunnels"
                echo "2. Edit your tunnel's public hostname"
                echo "3. Change domain to: $DOMAIN"
                break
            else
                echo -e "${YELLOW}⏳ SSL certificate not ready yet${NC}"
            fi
        else
            echo -e "${YELLOW}⏳ Domain not resolving yet${NC}"
        fi
    else
        echo -e "${RED}⏳ Still using Squarespace nameservers${NC}"
        echo "Current nameservers:"
        echo "$NS_CHECK"
    fi
    
    echo -e "\n${YELLOW}Waiting 30 seconds before next check...${NC}"
    echo "Press Ctrl+C to stop monitoring"
    sleep 30
done