#!/bin/bash
# Start Cloudflare Tunnel for Portfolio Dashboard

echo "Starting Cloudflare Tunnel for Portfolio Dashboard..."
echo "This will create a public URL that you can share."
echo ""

# Kill any existing tunnels
pkill cloudflared 2>/dev/null

# Start the tunnel
~/.local/bin/cloudflared tunnel --url http://localhost:8501 2>&1 | tee /tmp/cloudflared.log &

# Wait for URL
echo "Waiting for tunnel to establish..."
sleep 5

# Extract and display the URL
URL=$(grep "https://.*trycloudflare.com" /tmp/cloudflared.log | tail -1 | sed 's/.*https/https/' | sed 's/[[:space:]]*|$//')

if [ ! -z "$URL" ]; then
    echo ""
    echo "=========================================="
    echo "Your Portfolio Dashboard is now accessible at:"
    echo "$URL"
    echo "=========================================="
    echo ""
    echo "Share this URL with anyone you want to give access."
    echo "The tunnel will remain active until you stop it."
    echo ""
    echo "To stop the tunnel, run: pkill cloudflared"
else
    echo "Failed to start tunnel. Check /tmp/cloudflared.log for details."
fi

# Keep script running
echo "Press Ctrl+C to stop the tunnel..."
wait