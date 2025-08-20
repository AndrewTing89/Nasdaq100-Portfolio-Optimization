#!/usr/bin/env python3
"""
Notification service for scheduler
Sends notifications when pipeline runs complete
"""

import requests
import json
import os
from datetime import datetime

def send_notification(status, message, webhook_url=None):
    """Send notification via webhook"""
    if not webhook_url:
        webhook_url = os.environ.get('WEBHOOK_URL')
    
    if not webhook_url:
        print("No webhook URL configured, skipping notification")
        return
    
    payload = {
        "text": f"Portfolio Pipeline {status}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Portfolio Pipeline {status}*\n{message}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Time: {datetime.now().isoformat()}"
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        print(f"Notification sent successfully: {status}")
    except Exception as e:
        print(f"Failed to send notification: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        send_notification(sys.argv[1], sys.argv[2])
    else:
        print("Usage: notification.py <status> <message>")