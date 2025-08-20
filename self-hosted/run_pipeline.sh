#!/bin/bash

# Create temporary data directory with proper permissions
mkdir -p /tmp/pipeline-data/{raw,processed,stocks,results,logs}

# Run the pipeline with temporary data directory
docker run --rm \
  -v /tmp/pipeline-data:/data \
  -e MAX_STOCKS=10 \
  self-hosted_data-pipeline:latest \
  python data_pipeline.py phase1

echo "Phase 1 complete. Checking output..."
ls -la /tmp/pipeline-data/processed/

# If successful, copy to actual data directory
if [ -f /tmp/pipeline-data/processed/nasdaq_100_analysis.csv ]; then
  echo "Copying results to actual data directory..."
  cp -r /tmp/pipeline-data/* /home/beehiveting/apps/portfolio-optimization/self-hosted/data/
  echo "Data pipeline phase 1 complete!"
else
  echo "Pipeline failed to generate expected files"
fi