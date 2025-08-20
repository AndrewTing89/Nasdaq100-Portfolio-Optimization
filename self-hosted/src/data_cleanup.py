#!/usr/bin/env python3
"""
Data Cleanup Utility - Automatically removes old result files to prevent unlimited growth
Keeps only the most recent N runs for each portfolio type
"""

import os
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataCleanupManager:
    """Manages cleanup of old portfolio result files"""
    
    def __init__(self, data_dir: str = "/data", keep_recent: int = 10):
        """
        Initialize cleanup manager
        
        Args:
            data_dir: Base data directory
            keep_recent: Number of recent runs to keep for each portfolio type
        """
        self.data_dir = Path(data_dir)
        self.results_dir = self.data_dir / "results"
        self.keep_recent = keep_recent
        
        # Pattern to extract timestamp from filename
        self.timestamp_pattern = re.compile(r'(\d{8}_\d{6})\.csv$')
        
        # Portfolio type patterns
        self.portfolio_patterns = [
            'mv_historical_max_sharpe',
            'mv_historical_min_vol',
            'mv_undervalue_max_sharpe',
            'mv_undervalue_min_vol',
            'rp_historical',
            'rp_undervalue',
            'equal_portfolio',
            'portfolio_performance_comparison'
        ]
    
    def get_files_by_type(self, portfolio_type: str) -> List[Path]:
        """Get all files for a specific portfolio type, sorted by timestamp"""
        files = []
        
        for file_path in self.results_dir.glob(f"{portfolio_type}*.csv"):
            match = self.timestamp_pattern.search(file_path.name)
            if match:
                timestamp_str = match.group(1)
                try:
                    timestamp = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                    files.append((file_path, timestamp))
                except ValueError:
                    logger.warning(f"Could not parse timestamp from {file_path.name}")
        
        # Sort by timestamp, newest first
        files.sort(key=lambda x: x[1], reverse=True)
        return [f[0] for f in files]
    
    def cleanup_portfolio_type(self, portfolio_type: str) -> int:
        """
        Clean up old files for a specific portfolio type
        
        Returns:
            Number of files deleted
        """
        files = self.get_files_by_type(portfolio_type)
        deleted_count = 0
        
        if len(files) > self.keep_recent:
            files_to_delete = files[self.keep_recent:]
            
            for file_path in files_to_delete:
                try:
                    file_size = file_path.stat().st_size / 1024  # Size in KB
                    file_path.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted: {file_path.name} ({file_size:.1f} KB)")
                except Exception as e:
                    logger.error(f"Failed to delete {file_path.name}: {e}")
        
        return deleted_count
    
    def cleanup_old_logs(self, days_to_keep: int = 30):
        """Clean up old log files"""
        logs_dir = self.data_dir / "logs"
        if not logs_dir.exists():
            return 0
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        deleted_count = 0
        
        for log_file in logs_dir.glob("pipeline_*.log"):
            # Extract date from filename (pipeline_YYYYMMDD.log)
            match = re.match(r'pipeline_(\d{8})\.log', log_file.name)
            if match:
                try:
                    file_date = datetime.strptime(match.group(1), '%Y%m%d')
                    if file_date < cutoff_date:
                        log_file.unlink()
                        deleted_count += 1
                        logger.info(f"Deleted old log: {log_file.name}")
                except (ValueError, OSError) as e:
                    logger.error(f"Failed to process log file {log_file.name}: {e}")
        
        return deleted_count
    
    def get_storage_stats(self) -> Dict:
        """Get storage statistics for data directories"""
        stats = {
            'results_count': 0,
            'results_size_mb': 0,
            'logs_count': 0,
            'logs_size_mb': 0,
            'total_size_mb': 0
        }
        
        # Count and size results files
        if self.results_dir.exists():
            result_files = list(self.results_dir.glob("*.csv"))
            stats['results_count'] = len(result_files)
            stats['results_size_mb'] = sum(f.stat().st_size for f in result_files) / (1024 * 1024)
        
        # Count and size log files
        logs_dir = self.data_dir / "logs"
        if logs_dir.exists():
            log_files = list(logs_dir.glob("*.log"))
            stats['logs_count'] = len(log_files)
            stats['logs_size_mb'] = sum(f.stat().st_size for f in log_files) / (1024 * 1024)
        
        stats['total_size_mb'] = stats['results_size_mb'] + stats['logs_size_mb']
        
        return stats
    
    def run_cleanup(self):
        """Run complete cleanup process"""
        logger.info("=" * 50)
        logger.info("Starting Data Cleanup Process")
        logger.info("=" * 50)
        
        # Get initial stats
        initial_stats = self.get_storage_stats()
        logger.info(f"Initial storage: {initial_stats['results_count']} results files, "
                   f"{initial_stats['results_size_mb']:.1f} MB")
        
        # Clean up each portfolio type
        total_deleted = 0
        for portfolio_type in self.portfolio_patterns:
            deleted = self.cleanup_portfolio_type(portfolio_type)
            if deleted > 0:
                logger.info(f"  {portfolio_type}: deleted {deleted} old files")
            total_deleted += deleted
        
        # Clean up old logs
        logs_deleted = self.cleanup_old_logs()
        if logs_deleted > 0:
            logger.info(f"Deleted {logs_deleted} old log files")
        
        # Get final stats
        final_stats = self.get_storage_stats()
        space_freed = initial_stats['total_size_mb'] - final_stats['total_size_mb']
        
        logger.info("=" * 50)
        logger.info(f"Cleanup Complete: {total_deleted} files deleted")
        logger.info(f"Space freed: {space_freed:.1f} MB")
        logger.info(f"Final storage: {final_stats['results_count']} results files, "
                   f"{final_stats['results_size_mb']:.1f} MB")
        
        return {
            'files_deleted': total_deleted,
            'logs_deleted': logs_deleted,
            'space_freed_mb': space_freed,
            'final_stats': final_stats
        }
    
    def should_run_cleanup(self) -> bool:
        """Check if cleanup should run based on storage usage"""
        stats = self.get_storage_stats()
        
        # Run cleanup if:
        # - More than 100 result files
        # - Results directory > 500 MB
        # - Total storage > 1 GB
        
        return (stats['results_count'] > 100 or 
                stats['results_size_mb'] > 500 or
                stats['total_size_mb'] > 1024)


# CLI interface for manual execution
if __name__ == "__main__":
    import sys
    
    # Parse arguments
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "/data"
    keep_recent = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    
    # Initialize and run cleanup
    cleanup_manager = DataCleanupManager(data_dir, keep_recent)
    
    # Show current stats
    stats = cleanup_manager.get_storage_stats()
    print(f"\nCurrent Storage Statistics:")
    print(f"  Results: {stats['results_count']} files, {stats['results_size_mb']:.1f} MB")
    print(f"  Logs: {stats['logs_count']} files, {stats['logs_size_mb']:.1f} MB")
    print(f"  Total: {stats['total_size_mb']:.1f} MB")
    
    # Run cleanup
    if cleanup_manager.should_run_cleanup() or '--force' in sys.argv:
        print(f"\nRunning cleanup (keeping {keep_recent} recent files per type)...")
        result = cleanup_manager.run_cleanup()
        print(f"\nCleanup complete!")
        print(f"  Files deleted: {result['files_deleted']}")
        print(f"  Logs deleted: {result['logs_deleted']}")
        print(f"  Space freed: {result['space_freed_mb']:.1f} MB")
    else:
        print("\nNo cleanup needed at this time.")
        print("Use --force to run cleanup anyway.")