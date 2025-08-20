#!/bin/bash
# ================================================================
# Pipeline Trigger Script
# Executes portfolio optimization pipeline via API call
# ================================================================

set -e

# Configuration from arguments
PIPELINE_URL=$1
NOTIFICATION_ENABLED=$2
WEBHOOK_URL=$3

# Default values
PIPELINE_URL=${PIPELINE_URL:-"http://data-pipeline:8080"}
NOTIFICATION_ENABLED=${NOTIFICATION_ENABLED:-"false"}
TIMEOUT=${TIMEOUT:-"1800"}  # 30 minutes timeout

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Send notification function
send_notification() {
    local status=$1
    local message=$2
    
    if [ "$NOTIFICATION_ENABLED" = "true" ] && [ -n "$WEBHOOK_URL" ]; then
        log "Sending notification: $status"
        
        local payload=$(cat <<EOF
{
    "text": "Portfolio Optimization Pipeline",
    "attachments": [
        {
            "color": $([ "$status" = "SUCCESS" ] && echo '"good"' || echo '"danger"'),
            "fields": [
                {
                    "title": "Status",
                    "value": "$status",
                    "short": true
                },
                {
                    "title": "Timestamp",
                    "value": "$(date '+%Y-%m-%d %H:%M:%S UTC')",
                    "short": true
                },
                {
                    "title": "Message",
                    "value": "$message",
                    "short": false
                }
            ]
        }
    ]
}
EOF
        )
        
        curl -X POST -H 'Content-type: application/json' \
             --data "$payload" \
             "$WEBHOOK_URL" \
             --max-time 30 \
             --silent \
             --show-error || log "Failed to send notification"
    fi
}

# Main execution
main() {
    log "Starting scheduled portfolio optimization pipeline"
    log "Pipeline URL: $PIPELINE_URL"
    log "Timeout: ${TIMEOUT}s"
    
    # Health check first
    log "Performing health check..."
    if ! curl -f -s --max-time 10 "$PIPELINE_URL/health" > /dev/null; then
        local error_msg="Pipeline service is not healthy"
        log "ERROR: $error_msg"
        send_notification "FAILED" "$error_msg"
        exit 1
    fi
    
    log "Health check passed, starting pipeline execution"
    
    # Start pipeline execution
    local start_time=$(date +%s)
    local temp_file=$(mktemp)
    
    # Execute pipeline with timeout
    if curl -X POST \
            -H "Content-Type: application/json" \
            -d '{"command": "full", "model_type": "all", "return_type": "both"}' \
            --max-time "$TIMEOUT" \
            --silent \
            --show-error \
            --output "$temp_file" \
            "$PIPELINE_URL/execute"; then
        
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        # Parse response
        local status=$(cat "$temp_file" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null || echo "unknown")
        
        if [ "$status" = "success" ]; then
            local success_msg="Pipeline completed successfully in ${duration}s"
            log "SUCCESS: $success_msg"
            send_notification "SUCCESS" "$success_msg"
            
            # Log some results
            if command -v jq >/dev/null 2>&1; then
                log "Pipeline Results:"
                cat "$temp_file" | jq '.summary' || true
            fi
        else
            local error_msg="Pipeline execution failed with status: $status"
            log "ERROR: $error_msg"
            send_notification "FAILED" "$error_msg"
            
            # Log error details if available
            log "Error details:"
            cat "$temp_file" || true
            exit 1
        fi
    else
        local error_msg="Failed to execute pipeline API call"
        log "ERROR: $error_msg"
        send_notification "FAILED" "$error_msg"
        
        # Show response if available
        if [ -f "$temp_file" ]; then
            log "API Response:"
            cat "$temp_file" || true
        fi
        exit 1
    fi
    
    # Cleanup
    rm -f "$temp_file"
    
    log "Scheduled pipeline execution completed successfully"
}

# Execute main function
main "$@"