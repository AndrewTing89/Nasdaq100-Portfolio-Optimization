#!/bin/bash
# ================================================================
# Scheduler Service Entrypoint
# Configures and starts cron daemon for automated pipeline execution
# ================================================================

set -e

# Set timezone if provided
if [ -n "$TZ" ]; then
    echo "Setting timezone to $TZ"
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime
    echo $TZ > /etc/timezone
fi

# Configure cron schedule from environment variable
CRON_SCHEDULE=${CRON_SCHEDULE:-"0 6 * * *"}  # Default: daily at 6 AM
PIPELINE_URL=${PIPELINE_URL:-"http://data-pipeline:8080"}
NOTIFICATION_ENABLED=${NOTIFICATION_ENABLED:-"false"}
WEBHOOK_URL=${WEBHOOK_URL:-""}

echo "Configuring cron schedule: $CRON_SCHEDULE"

# Create crontab from template
cat > /tmp/crontab << EOF
# Portfolio Optimization Pipeline Scheduler
# Auto-generated from environment variables

# Pipeline execution schedule
$CRON_SCHEDULE /app/pipeline_trigger.sh "$PIPELINE_URL" "$NOTIFICATION_ENABLED" "$WEBHOOK_URL" >> /var/log/cron/pipeline.log 2>&1

# Health check every 5 minutes
*/5 * * * * echo "\$(date): Scheduler health check" >> /var/log/cron/health.log

# Log rotation weekly
0 0 * * 0 find /var/log/cron -name "*.log" -size +10M -exec truncate -s 1M {} \;

EOF

# Install crontab
crontab /tmp/crontab

# Create log directory and files
mkdir -p /var/log/cron
touch /var/log/cron/pipeline.log /var/log/cron/health.log

# Set permissions
chmod 644 /var/log/cron/*.log

echo "Cron configuration completed"
echo "Pipeline URL: $PIPELINE_URL"
echo "Schedule: $CRON_SCHEDULE"
echo "Notifications: $NOTIFICATION_ENABLED"

# Show current crontab
echo "Active crontab:"
crontab -l

# Start cron daemon
echo "Starting cron daemon..."
exec "$@"