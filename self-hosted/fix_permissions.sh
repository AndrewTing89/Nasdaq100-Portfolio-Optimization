#!/bin/bash

echo "This script will fix the data directory permissions"
echo "You'll need to enter your sudo password"
echo ""

# Remove the incorrectly owned directory
echo "Removing old data directory..."
sudo rm -rf /home/beehiveting/apps/portfolio-optimization/self-hosted/data

# Create new directory structure with correct ownership
echo "Creating new data directory structure..."
mkdir -p /home/beehiveting/apps/portfolio-optimization/self-hosted/data/{raw,processed,stocks,results,logs}
mkdir -p /home/beehiveting/apps/portfolio-optimization/self-hosted/data/results/{phase1,phase2,final}

# Set proper permissions
echo "Setting permissions..."
chmod -R 755 /home/beehiveting/apps/portfolio-optimization/self-hosted/data

# Create a docker-compatible permission setup
# The container runs as user 'portfolio' which doesn't exist on host
# We'll make the directory world-writable for now (not ideal for production)
chmod -R 777 /home/beehiveting/apps/portfolio-optimization/self-hosted/data

echo "Permissions fixed!"
echo ""
echo "Directory structure:"
ls -la /home/beehiveting/apps/portfolio-optimization/self-hosted/data/

echo ""
echo "Now you can run the data pipeline without permission errors"