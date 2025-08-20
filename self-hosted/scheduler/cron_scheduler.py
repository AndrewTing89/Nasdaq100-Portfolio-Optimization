#!/usr/bin/env python3
"""
Python-based Cron Scheduler
Alternative to system cron for more flexible scheduling
"""

import time
import logging
import schedule
import requests
import json
from datetime import datetime
from typing import Optional
import os
import signal
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/cron/python_scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PipelineScheduler:
    """Python-based scheduler for portfolio optimization pipeline"""
    
    def __init__(self):
        self.pipeline_url = os.getenv('PIPELINE_URL', 'http://data-pipeline:8080')
        self.notification_enabled = os.getenv('NOTIFICATION_ENABLED', 'false').lower() == 'true'
        self.webhook_url = os.getenv('WEBHOOK_URL', '')
        self.schedule_pattern = os.getenv('CRON_SCHEDULE', '0 6 * * *')
        self.running = True
        
        # Parse cron schedule to Python schedule format
        self.setup_schedule()
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def parse_cron_schedule(self, cron_pattern: str) -> dict:
        """Parse cron pattern and return schedule parameters"""
        parts = cron_pattern.split()
        if len(parts) != 5:
            raise ValueError("Invalid cron pattern. Expected 5 parts: minute hour day month day_of_week")
        
        minute, hour, day, month, day_of_week = parts
        
        return {
            'minute': minute,
            'hour': hour,
            'day': day,
            'month': month,
            'day_of_week': day_of_week
        }
    
    def setup_schedule(self):
        """Setup schedule based on cron pattern"""
        try:
            schedule_params = self.parse_cron_schedule(self.schedule_pattern)
            minute = schedule_params['minute']
            hour = schedule_params['hour']
            day_of_week = schedule_params['day_of_week']
            
            # Convert to schedule format
            time_str = f"{hour.zfill(2)}:{minute.zfill(2)}"
            
            if day_of_week != '*':
                # Weekly schedule
                days = {
                    '0': 'sunday', '1': 'monday', '2': 'tuesday', '3': 'wednesday',
                    '4': 'thursday', '5': 'friday', '6': 'saturday'
                }
                day_name = days.get(day_of_week, 'monday')
                schedule.every().week.at(time_str).tag('pipeline')
                logger.info(f"Scheduled weekly execution on {day_name} at {time_str}")
            else:
                # Daily schedule
                schedule.every().day.at(time_str).do(self.execute_pipeline).tag('pipeline')
                logger.info(f"Scheduled daily execution at {time_str}")
                
        except Exception as e:
            logger.error(f"Failed to setup schedule: {e}")
            # Fallback to daily at 6 AM
            schedule.every().day.at("06:00").do(self.execute_pipeline).tag('pipeline')
            logger.info("Using fallback schedule: daily at 06:00")
    
    def send_notification(self, status: str, message: str):
        """Send notification via webhook"""
        if not self.notification_enabled or not self.webhook_url:
            return
        
        try:
            payload = {
                "text": "Portfolio Optimization Pipeline",
                "attachments": [{
                    "color": "good" if status == "SUCCESS" else "danger",
                    "fields": [
                        {"title": "Status", "value": status, "short": True},
                        {"title": "Timestamp", "value": datetime.now().isoformat(), "short": True},
                        {"title": "Message", "value": message, "short": False}
                    ]
                }]
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            logger.info("Notification sent successfully")
            
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
    
    def check_pipeline_health(self) -> bool:
        """Check if pipeline service is healthy"""
        try:
            response = requests.get(f"{self.pipeline_url}/health", timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def execute_pipeline(self):
        """Execute the portfolio optimization pipeline"""
        logger.info("Starting scheduled pipeline execution")
        
        try:
            # Health check first
            if not self.check_pipeline_health():
                error_msg = "Pipeline service is not healthy"
                logger.error(error_msg)
                self.send_notification("FAILED", error_msg)
                return
            
            # Execute pipeline
            start_time = time.time()
            
            payload = {
                "command": "full",
                "model_type": "all",
                "return_type": "both",
                "async": False  # Synchronous execution
            }
            
            response = requests.post(
                f"{self.pipeline_url}/execute",
                json=payload,
                timeout=1800  # 30 minutes timeout
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            if response.status_code == 200:
                result = response.json()
                status = result.get('status', 'unknown')
                
                if status == 'success':
                    success_msg = f"Pipeline completed successfully in {duration:.2f}s"
                    logger.info(success_msg)
                    self.send_notification("SUCCESS", success_msg)
                    
                    # Log summary if available
                    if 'summary' in result:
                        logger.info(f"Pipeline summary: {json.dumps(result['summary'], indent=2)}")
                else:
                    error_msg = f"Pipeline execution failed with status: {status}"
                    logger.error(error_msg)
                    self.send_notification("FAILED", error_msg)
            else:
                error_msg = f"Pipeline API call failed with status: {response.status_code}"
                logger.error(error_msg)
                logger.error(f"Response: {response.text}")
                self.send_notification("FAILED", error_msg)
                
        except Exception as e:
            error_msg = f"Pipeline execution failed: {str(e)}"
            logger.error(error_msg)
            self.send_notification("FAILED", error_msg)
    
    def run(self):
        """Main scheduler loop"""
        logger.info("Python scheduler started")
        logger.info(f"Pipeline URL: {self.pipeline_url}")
        logger.info(f"Schedule: {self.schedule_pattern}")
        logger.info(f"Notifications: {self.notification_enabled}")
        
        # Show scheduled jobs
        logger.info("Scheduled jobs:")
        for job in schedule.jobs:
            logger.info(f"  - {job}")
        
        try:
            while self.running:
                schedule.run_pending()
                time.sleep(30)  # Check every 30 seconds
                
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            logger.info("Scheduler stopped")

def main():
    """Main entry point"""
    try:
        scheduler = PipelineScheduler()
        scheduler.run()
    except Exception as e:
        logger.error(f"Scheduler failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()