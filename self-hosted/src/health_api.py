#!/usr/bin/env python3
"""
Health API Server for Data Pipeline Service
Provides HTTP endpoints for health checks and pipeline execution
"""

import json
import logging
import threading
import time
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from flask import Flask, request, jsonify
import sys
import os

# Add current directory to path for imports
sys.path.append(os.path.dirname(__file__))

from pipeline_wrapper import PipelineWrapper
from data_cleanup import DataCleanupManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global pipeline instance
pipeline = None
pipeline_lock = threading.Lock()
execution_status = {
    "running": False,
    "last_run": None,
    "last_status": None,
    "last_duration": None
}

app = Flask(__name__)

def initialize_pipeline():
    """Initialize the global pipeline instance"""
    global pipeline
    try:
        pipeline = PipelineWrapper()
        logger.info("Pipeline initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize pipeline: {e}")
        raise

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        if pipeline is None:
            return jsonify({
                "status": "unhealthy",
                "error": "Pipeline not initialized",
                "timestamp": datetime.now().isoformat()
            }), 503
        
        health_result = pipeline.health_check()
        status_code = 200 if health_result["status"] == "healthy" else 503
        return jsonify(health_result), status_code
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 503

@app.route('/status', methods=['GET'])
def pipeline_status():
    """Get current pipeline execution status"""
    return jsonify({
        "execution_status": execution_status,
        "timestamp": datetime.now().isoformat()
    })

def execute_pipeline_async(parameters: Dict[str, Any]):
    """Execute pipeline in background thread"""
    global execution_status
    
    try:
        with pipeline_lock:
            execution_status["running"] = True
            execution_status["last_run"] = datetime.now().isoformat()
        
        start_time = time.time()
        
        # Execute based on command
        command = parameters.get("command", "full")
        
        if command == "health":
            result = pipeline.health_check()
        elif command == "phase1":
            result = pipeline.run_phase1()
        elif command == "phase2":
            result = pipeline.run_phase2()
        elif command == "phase3":
            model_type = parameters.get("model_type", "all")
            result = pipeline.run_phase3(model_type=model_type)
        elif command == "full":
            result = pipeline.run_full_pipeline()
        else:
            result = {"status": "error", "error": f"Unknown command: {command}"}
        
        end_time = time.time()
        duration = end_time - start_time
        
        with pipeline_lock:
            execution_status["running"] = False
            execution_status["last_status"] = result.get("status", "unknown")
            execution_status["last_duration"] = duration
        
        logger.info(f"Pipeline execution completed: {result.get('status', 'unknown')} in {duration:.2f}s")
        
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        with pipeline_lock:
            execution_status["running"] = False
            execution_status["last_status"] = "error"
            execution_status["last_duration"] = time.time() - start_time

@app.route('/execute', methods=['POST'])
def execute_pipeline():
    """Execute pipeline with parameters"""
    try:
        # Check if pipeline is already running
        if execution_status["running"]:
            return jsonify({
                "status": "rejected",
                "error": "Pipeline is already running",
                "current_execution": execution_status,
                "timestamp": datetime.now().isoformat()
            }), 409
        
        # Parse request parameters
        parameters = request.get_json() or {}
        command = parameters.get("command", "full")
        
        logger.info(f"Received execution request: {command}")
        
        # For synchronous execution (immediate response)
        if parameters.get("async", True) is False:
            with pipeline_lock:
                execution_status["running"] = True
                execution_status["last_run"] = datetime.now().isoformat()
            
            try:
                start_time = time.time()
                
                if command == "health":
                    result = pipeline.health_check()
                elif command == "phase1":
                    result = pipeline.run_phase1()
                elif command == "phase2":
                    result = pipeline.run_phase2()
                elif command == "phase3":
                    model_type = parameters.get("model_type", "all")
                    result = pipeline.run_phase3(model_type=model_type)
                elif command == "full":
                    result = pipeline.run_full_pipeline()
                else:
                    result = {"status": "error", "error": f"Unknown command: {command}"}
                
                end_time = time.time()
                duration = end_time - start_time
                
                with pipeline_lock:
                    execution_status["running"] = False
                    execution_status["last_status"] = result.get("status", "unknown")
                    execution_status["last_duration"] = duration
                
                return jsonify(result)
                
            except Exception as e:
                logger.error(f"Synchronous execution failed: {e}")
                with pipeline_lock:
                    execution_status["running"] = False
                    execution_status["last_status"] = "error"
                
                return jsonify({
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }), 500
        
        # For asynchronous execution (start in background)
        else:
            thread = threading.Thread(target=execute_pipeline_async, args=(parameters,))
            thread.daemon = True
            thread.start()
            
            return jsonify({
                "status": "accepted",
                "message": "Pipeline execution started",
                "command": command,
                "parameters": parameters,
                "timestamp": datetime.now().isoformat()
            }), 202
    
    except Exception as e:
        logger.error(f"Execute endpoint failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/data/<path:filepath>', methods=['GET'])
def serve_data_file(filepath):
    """Serve data files (read-only access)"""
    try:
        if pipeline is None:
            return jsonify({"error": "Pipeline not initialized"}), 503
        
        # Construct safe file path
        data_dir = pipeline.data_dir
        file_path = data_dir / filepath
        
        # Security check - ensure path is within data directory
        try:
            file_path.resolve().relative_to(data_dir.resolve())
        except ValueError:
            return jsonify({"error": "Access denied"}), 403
        
        if not file_path.exists():
            return jsonify({"error": "File not found"}), 404
        
        if file_path.suffix.lower() == '.json':
            with open(file_path, 'r') as f:
                data = json.load(f)
            return jsonify(data)
        else:
            # For CSV and other files, return raw content
            with open(file_path, 'r') as f:
                content = f.read()
            return content, 200, {'Content-Type': 'text/plain'}
    
    except Exception as e:
        logger.error(f"Data file serving failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/logs', methods=['GET'])
def get_logs():
    """Get recent log entries"""
    try:
        if pipeline is None:
            return jsonify({"error": "Pipeline not initialized"}), 503
        
        log_dir = pipeline.data_dir / "logs"
        today_log = log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d')}.log"
        
        if not today_log.exists():
            return jsonify({"logs": [], "message": "No logs for today"})
        
        # Read last N lines
        lines_to_read = request.args.get('lines', 100, type=int)
        lines_to_read = min(lines_to_read, 1000)  # Limit to 1000 lines max
        
        with open(today_log, 'r') as f:
            lines = f.readlines()
        
        recent_lines = lines[-lines_to_read:] if len(lines) > lines_to_read else lines
        
        return jsonify({
            "logs": [line.strip() for line in recent_lines],
            "total_lines": len(lines),
            "returned_lines": len(recent_lines),
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"Log retrieval failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/cleanup', methods=['POST'])
def run_cleanup():
    """Run data cleanup to remove old files"""
    try:
        cleanup_manager = DataCleanupManager(
            data_dir=pipeline.data_dir if hasattr(pipeline, 'data_dir') else "/data",
            keep_recent=10
        )
        
        # Get current stats
        initial_stats = cleanup_manager.get_storage_stats()
        
        # Run cleanup
        result = cleanup_manager.run_cleanup()
        
        return jsonify({
            "status": "success",
            "initial_stats": initial_stats,
            "files_deleted": result['files_deleted'],
            "logs_deleted": result['logs_deleted'],
            "space_freed_mb": result['space_freed_mb'],
            "final_stats": result['final_stats'],
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/data-info', methods=['GET'])
def get_data_info():
    """Get data freshness and storage information"""
    try:
        data_dir = Path(pipeline.data_dir if hasattr(pipeline, 'data_dir') else "/data")
        
        # Get last optimization time from results
        results_dir = data_dir / "results"
        latest_result = None
        if results_dir.exists():
            csv_files = sorted(results_dir.glob("portfolio_performance_comparison_*.csv"))
            if csv_files:
                latest_file = csv_files[-1]
                # Extract timestamp from filename
                import re
                match = re.search(r'(\d{8}_\d{6})', latest_file.name)
                if match:
                    timestamp_str = match.group(1)
                    latest_result = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S').isoformat()
        
        # Get storage stats
        cleanup_manager = DataCleanupManager(data_dir=str(data_dir))
        storage_stats = cleanup_manager.get_storage_stats()
        
        # Check if using live API data
        use_api = os.environ.get('USE_API_PIPELINE', 'false').lower() == 'true'
        
        return jsonify({
            "last_optimization": latest_result,
            "data_mode": "live" if use_api else "csv",
            "stocks_analyzed": 100,  # NASDAQ-100
            "storage": storage_stats,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get data info: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/execution-history', methods=['GET'])
def get_execution_history():
    """Get pipeline execution history"""
    try:
        # Read recent log entries to build execution history
        log_dir = Path(pipeline.data_dir if hasattr(pipeline, 'data_dir') else "/data") / "logs"
        history = []
        
        if log_dir.exists():
            today_log = log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d')}.log"
            if today_log.exists():
                with open(today_log, 'r') as f:
                    lines = f.readlines()[-100:]  # Last 100 lines
                    
                for line in lines:
                    if "Pipeline execution completed" in line or "Phase 3 completed successfully" in line:
                        # Parse execution info from log line
                        parts = line.split(" - ")
                        if len(parts) >= 2:
                            timestamp = parts[0]
                            status = "success" if "success" in line.lower() else "error"
                            
                            # Extract duration if present
                            duration = 0
                            if "in " in line and "s" in line:
                                try:
                                    duration_match = re.search(r'in ([\d.]+)s', line)
                                    if duration_match:
                                        duration = float(duration_match.group(1))
                                except:
                                    pass
                            
                            history.append({
                                "timestamp": timestamp,
                                "status": status,
                                "duration": duration,
                                "stocks_processed": 100
                            })
        
        # Add current execution if running
        if execution_status.get("running"):
            history.insert(0, {
                "timestamp": execution_status.get("last_run"),
                "status": "running",
                "duration": 0,
                "stocks_processed": 0
            })
        
        return jsonify({
            "history": history[:10],  # Return last 10 executions
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Failed to get execution history: {e}")
        return jsonify({
            "error": str(e),
            "history": [],
            "timestamp": datetime.now().isoformat()
        }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    try:
        # Initialize pipeline
        logger.info("Starting Portfolio Optimization Health API Server")
        initialize_pipeline()
        
        # Start Flask app
        port = int(os.environ.get('PORT', 8080))
        debug = os.environ.get('DEBUG', 'false').lower() == 'true'
        
        logger.info(f"Server starting on port {port}")
        app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        exit(1)