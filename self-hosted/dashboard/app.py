"""
Local Portfolio Optimization Dashboard
A multi-page Streamlit dashboard for visualizing portfolio optimization results using local files
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
import psutil
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
import requests
import time
import hashlib

# Import technical analysis module
try:
    from technical_analysis import (
        StockDataFetcher, 
        TechnicalAnalyzer, 
        get_news_sentiment, 
        analyze_news_sentiment,
        generate_ai_insights, 
        calculate_risk_metrics
    )
    TECHNICAL_ANALYSIS_AVAILABLE = True
except ImportError as e:
    st.warning("Technical analysis module not available. Some features may be limited.")
    TECHNICAL_ANALYSIS_AVAILABLE = False

# Page configuration
st.set_page_config(
    page_title="Portfolio Optimization Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 5px solid #1f77b4;
        margin-bottom: 1rem;
        color: #2d2d2d !important;
    }
    .metric-card small {
        color: #2d2d2d !important;
    }
    .metric-card h4 {
        color: #2d2d2d !important;
    }
    .metric-card p {
        color: #2d2d2d !important;
    }
    .positive {
        color: #00cc44 !important;
        font-weight: bold;
    }
    .negative {
        color: #ff4444 !important;
        font-weight: bold;
    }
    .neutral {
        color: #666666 !important;
    }
    .warning-card {
        background-color: #fff4e6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 5px solid #ff9800;
        margin-bottom: 1rem;
        color: #2d2d2d !important;
    }
    .success-card {
        background-color: #e8f5e8;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 5px solid #4caf50;
        margin-bottom: 1rem;
        color: #2d2d2d !important;
    }
    .login-form {
        max-width: 400px;
        margin: 0 auto;
        padding: 2rem;
        border-radius: 1rem;
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
    }
</style>
""", unsafe_allow_html=True)


class LocalDataLoader:
    """Handle local data loading and caching"""
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.data_dir = self.base_path
        self.results_dir = self.base_path / "results"
        
    @st.cache_data(ttl=300)  # Cache for 5 minutes
    def load_csv(_self, relative_path: str) -> Optional[pd.DataFrame]:
        """Load CSV file from local filesystem with caching"""
        try:
            file_path = _self.base_path / relative_path
            if file_path.exists():
                df = pd.read_csv(file_path)
                return df
            else:
                st.warning(f"File not found: {relative_path}")
                return None
        except Exception as e:
            st.error(f"Error loading {relative_path}: {str(e)}")
            return None
    
    @st.cache_data(ttl=300)  # Cache for 5 minutes
    def load_json(_self, relative_path: str) -> Optional[Dict]:
        """Load JSON file from local filesystem with caching"""
        try:
            file_path = _self.base_path / relative_path
            if file_path.exists():
                with open(file_path, 'r') as f:
                    data = json.load(f)
                return data
            else:
                st.warning(f"File not found: {relative_path}")
                return None
        except Exception as e:
            st.error(f"Error loading {relative_path}: {str(e)}")
            return None
    
    def list_files(self, relative_path: str) -> List[str]:
        """List files in local directory"""
        try:
            dir_path = self.base_path / relative_path
            if dir_path.exists() and dir_path.is_dir():
                files = []
                for file_path in dir_path.rglob("*"):
                    if file_path.is_file():
                        # Return relative path from base_path
                        rel_path = file_path.relative_to(self.base_path)
                        files.append(str(rel_path))
                return files
            else:
                return []
        except Exception as e:
            st.error(f"Error listing files in {relative_path}: {str(e)}")
            return []
    
    def get_file_timestamp(self, relative_path: str) -> Optional[datetime]:
        """Get the last modified timestamp of a file"""
        try:
            file_path = self.base_path / relative_path
            if file_path.exists():
                return datetime.fromtimestamp(file_path.stat().st_mtime)
            return None
        except Exception as e:
            return None
    
    def get_directory_size(self, relative_path: str) -> int:
        """Get total size of directory in bytes"""
        try:
            dir_path = self.base_path / relative_path
            if dir_path.exists():
                return sum(f.stat().st_size for f in dir_path.rglob('*') if f.is_file())
            return 0
        except Exception as e:
            return 0


def authenticate_user():
    """Simple authentication system"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.markdown('<div class="main-header">🔐 Portfolio Dashboard Login</div>', unsafe_allow_html=True)
        
        with st.container():
            st.markdown('<div class="login-form">', unsafe_allow_html=True)
            st.markdown("### Please login to continue")
            
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("Login", use_container_width=True):
                    # Check credentials from environment variables
                    expected_username = os.getenv("DASHBOARD_USERNAME", "admin")
                    expected_password = os.getenv("DASHBOARD_PASSWORD", "password")
                    
                    if username == expected_username and password == expected_password:
                        st.session_state.authenticated = True
                        st.session_state.username = username
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.info("""
            **Default credentials (change via environment variables):**
            - Username: admin
            - Password: password
            
            Set `DASHBOARD_USERNAME` and `DASHBOARD_PASSWORD` environment variables for custom credentials.
            """)
        
        return False
    
    return True


def get_system_health():
    """Check system health (local services)"""
    health_status = {
        'disk_usage': {'status': 'Unknown', 'detail': 'Checking...'},
        'memory_usage': {'status': 'Unknown', 'detail': 'Checking...'},
        'data_directory': {'status': 'Unknown', 'detail': 'Checking...'},
        'api_service': {'status': 'Unknown', 'detail': 'Checking...'}
    }
    
    try:
        # Check disk usage
        disk_usage = psutil.disk_usage('/')
        used_percent = (disk_usage.used / disk_usage.total) * 100
        
        if used_percent < 80:
            health_status['disk_usage'] = {'status': 'Healthy', 'detail': f'{used_percent:.1f}% used'}
        elif used_percent < 90:
            health_status['disk_usage'] = {'status': 'Warning', 'detail': f'{used_percent:.1f}% used'}
        else:
            health_status['disk_usage'] = {'status': 'Critical', 'detail': f'{used_percent:.1f}% used'}
    except Exception as e:
        health_status['disk_usage'] = {'status': 'Error', 'detail': 'Cannot read disk usage'}
    
    try:
        # Check memory usage
        memory = psutil.virtual_memory()
        if memory.percent < 80:
            health_status['memory_usage'] = {'status': 'Healthy', 'detail': f'{memory.percent:.1f}% used'}
        elif memory.percent < 90:
            health_status['memory_usage'] = {'status': 'Warning', 'detail': f'{memory.percent:.1f}% used'}
        else:
            health_status['memory_usage'] = {'status': 'Critical', 'detail': f'{memory.percent:.1f}% used'}
    except Exception as e:
        health_status['memory_usage'] = {'status': 'Error', 'detail': 'Cannot read memory usage'}
    
    try:
        # Check data directory
        data_loader = st.session_state.data_loader
        if data_loader.data_dir.exists():
            file_count = len(data_loader.list_files("data"))
            health_status['data_directory'] = {'status': 'Healthy', 'detail': f'{file_count} files available'}
        else:
            health_status['data_directory'] = {'status': 'Error', 'detail': 'Data directory not found'}
    except Exception as e:
        health_status['data_directory'] = {'status': 'Error', 'detail': 'Cannot access data directory'}
    
    try:
        # Check pipeline API service (data-pipeline container)
        try:
            # Use correct API endpoints
            api_host = "portfolio-data-pipeline:8080" if os.path.exists("/.dockerenv") else "localhost:8081"
            response = requests.get(f"http://{api_host}/health", timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                status = health_data.get('status', 'unknown')
                if status == 'healthy':
                    health_status['api_service'] = {'status': 'Healthy', 'detail': 'Pipeline API service running'}
                else:
                    health_status['api_service'] = {'status': 'Warning', 'detail': f'Pipeline API status: {status}'}
            else:
                health_status['api_service'] = {'status': 'Warning', 'detail': f'API returned {response.status_code}'}
        except requests.exceptions.ConnectionError:
            health_status['api_service'] = {'status': 'Offline', 'detail': 'Pipeline API service not running'}
        except requests.exceptions.Timeout:
            health_status['api_service'] = {'status': 'Warning', 'detail': 'Pipeline API service timeout'}
    except Exception as e:
        health_status['api_service'] = {'status': 'Error', 'detail': 'Cannot check API service'}
    
    return health_status


def get_execution_history():
    """Get pipeline execution history from logs"""
    try:
        api_host = "portfolio-data-pipeline:8080" if os.path.exists("/.dockerenv") else "localhost:8081"
        response = requests.get(f"http://{api_host}/logs?lines=50", timeout=5)
        if response.status_code == 200:
            log_data = response.json()
            logs = log_data.get("logs", [])
            
            # Parse logs to extract execution history
            history = []
            for log_line in logs:
                if "Pipeline execution completed" in log_line:
                    parts = log_line.split(" - ")
                    if len(parts) >= 3:
                        timestamp = parts[0] if len(parts) > 0 else "Unknown"
                        message = parts[-1] if len(parts) > 0 else ""
                        
                        # Extract status and duration from message
                        status = "unknown"
                        duration = 0
                        if "success" in message.lower():
                            status = "success"
                        elif "error" in message.lower() or "failed" in message.lower():
                            status = "error"
                        
                        # Extract duration if present
                        if "in " in message and "s" in message:
                            try:
                                duration_part = message.split("in ")[1].split("s")[0]
                                duration = float(duration_part)
                            except:
                                duration = 0
                        
                        history.append({
                            'timestamp': timestamp,
                            'status': status, 
                            'duration': duration,
                            'stocks_processed': 0  # Not available from logs
                        })
            
            # Return most recent first
            return list(reversed(history))
    except Exception as e:
        print(f"Failed to get execution history: {e}")
        pass
    return []


def get_time_ago(timestamp_str):
    """Convert timestamp to human-readable time ago"""
    try:
        from datetime import datetime, timedelta
        
        # Parse various timestamp formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y%m%d_%H%M%S", 
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f"
        ]
        
        timestamp = None
        for fmt in formats:
            try:
                timestamp = datetime.strptime(timestamp_str, fmt)
                break
            except:
                continue
        
        if not timestamp:
            return "Unknown"
            
        now = datetime.now()
        diff = now - timestamp
        
        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours}h ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes}m ago"
        else:
            return "Just now"
            
    except Exception:
        return "Unknown"


def get_data_freshness():
    """Get data freshness indicators from status endpoint"""
    try:
        api_host = "portfolio-data-pipeline:8080" if os.path.exists("/.dockerenv") else "localhost:8081"
        response = requests.get(f"http://{api_host}/status", timeout=5)
        if response.status_code == 200:
            status_data = response.json()
            execution_status = status_data.get("execution_status", {})
            
            return {
                'last_optimization': execution_status.get('last_run'),
                'stocks_analyzed': 0,  # Not available from current API
                'pipeline_status': execution_status.get('last_status')
            }
    except Exception as e:
        print(f"Failed to get data freshness: {e}")
        pass
    return {}


def trigger_full_pipeline():
    """Trigger full pipeline with real-time status updates"""
    try:
        # Use container name when running in Docker, localhost for development
        api_host = "portfolio-data-pipeline:8080" if os.path.exists("/.dockerenv") else "localhost:8081"
        
        # Start async execution
        execute_endpoint = f"http://{api_host}/execute"
        status_endpoint = f"http://{api_host}/status"
        
        payload = {
            "command": "full",
            "async": True,  # Start in background
            "model_type": "all"
        }
        
        # Start the pipeline
        st.info("🚀 Starting full portfolio optimization pipeline...")
        response = requests.post(execute_endpoint, json=payload, timeout=10)
        
        if response.status_code != 202:  # 202 = Accepted for async
            st.error(f"❌ Failed to start pipeline: {response.text}")
            return False
            
        st.success("✅ Pipeline started successfully!")
        
        # Create a progress container
        progress_container = st.empty()
        status_container = st.empty()
        
        # Monitor progress
        import time
        max_wait_time = 1800  # 30 minutes
        start_time = time.time()
        last_status = None
        
        while time.time() - start_time < max_wait_time:
            try:
                # Check status
                status_response = requests.get(status_endpoint, timeout=5)
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    execution_status = status_data.get("execution_status", {})
                    
                    is_running = execution_status.get("running", False)
                    current_status = execution_status.get("last_status")
                    duration = execution_status.get("last_duration")
                    
                    if is_running:
                        # Still running - show progress
                        progress_container.info("⏳ Pipeline is running... Please wait.")
                        status_container.info(f"🔄 Status: Processing data (Running for {int(time.time() - start_time)} seconds)")
                    else:
                        # Completed
                        if current_status == "success":
                            progress_container.success("🎉 Pipeline completed successfully!")
                            status_container.success(f"✅ Duration: {duration:.1f} seconds" if duration else "✅ Execution completed")
                            
                            # Show completion summary
                            st.info("📊 **Pipeline Summary:**")
                            st.info("• ✅ Phase 1: NASDAQ-100 analysis completed")  
                            st.info("• ✅ Phase 2: Historical data collection completed")
                            st.info("• ✅ Phase 3: Portfolio optimization completed")
                            st.info("🔄 **Refresh the Executive Summary page to see updated results!**")
                            return True
                        elif current_status == "error":
                            progress_container.error("❌ Pipeline failed")
                            status_container.error("Check system logs for details")
                            return False
                        else:
                            # Unknown status, keep waiting
                            progress_container.info("⏳ Pipeline status unclear, continuing to monitor...")
                            
                # Wait before next check
                time.sleep(3)
                
            except Exception as e:
                status_container.warning(f"⚠️ Status check error: {e}")
                time.sleep(5)
        
        # Timeout
        progress_container.warning("⏰ Pipeline monitoring timed out")
        status_container.info("The pipeline may still be running in the background. Check the Executive Summary page later.")
        return False
                
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to pipeline API service.")
        return False
    except Exception as e:
        st.error(f"❌ Unexpected error: {str(e)}")
        return False


def calculate_benchmark_metrics(portfolio_data: Dict, nasdaq_data: pd.DataFrame) -> Dict:
    """Calculate benchmark comparison metrics"""
    try:
        data_loader = st.session_state.data_loader
        
        # Calculate NASDAQ-100 index performance using market cap weighting
        nasdaq_symbols = nasdaq_data['Symbol'].tolist() if nasdaq_data is not None else []
        
        # Load individual stock data to calculate index performance
        stock_files = data_loader.list_files("data/stocks/")
        
        # Calculate equal-weighted NASDAQ-100 return (simplified benchmark)
        total_return = 0
        valid_stocks = 0
        
        for symbol in nasdaq_symbols[:50]:  # Use subset for performance
            stock_file = f"data/stocks/{symbol}.csv"
            if stock_file in stock_files:
                stock_data = data_loader.load_csv(stock_file)
                if stock_data is not None and len(stock_data) > 0:
                    # Calculate 5-year annualized return
                    if 'Adj Close' in stock_data.columns and len(stock_data) > 250:
                        start_price = stock_data['Adj Close'].iloc[0]
                        end_price = stock_data['Adj Close'].iloc[-1]
                        years = len(stock_data) / 252  # Trading days per year
                        annual_return = ((end_price / start_price) ** (1/years)) - 1
                        total_return += annual_return
                        valid_stocks += 1
        
        if valid_stocks > 0:
            benchmark_return = total_return / valid_stocks
            benchmark_volatility = 0.15  # Approximate NASDAQ-100 volatility
            benchmark_sharpe = benchmark_return / benchmark_volatility
        else:
            benchmark_return = 0.12  # Fallback to approximate NASDAQ-100 return
            benchmark_volatility = 0.15
            benchmark_sharpe = 0.8
        
        # Calculate portfolio metrics vs benchmark
        comparison_data = portfolio_data.get('comparison', pd.DataFrame())
        benchmark_metrics = {
            'benchmark_return': benchmark_return,
            'benchmark_volatility': benchmark_volatility,
            'benchmark_sharpe': benchmark_sharpe,
            'portfolio_comparisons': []
        }
        
        if not comparison_data.empty:
            for _, row in comparison_data.iterrows():
                alpha = row['Return'] - benchmark_return
                beta = row['Volatility'] / benchmark_volatility  # Simplified beta calculation
                tracking_error = abs(row['Volatility'] - benchmark_volatility)
                
                benchmark_metrics['portfolio_comparisons'].append({
                    'Model': row['Model'],
                    'Return': row['Return'],
                    'Volatility': row['Volatility'],
                    'Sharpe_Ratio': row['Sharpe_Ratio'],
                    'Alpha': alpha,
                    'Beta': beta,
                    'Tracking_Error': tracking_error,
                    'Information_Ratio': alpha / tracking_error if tracking_error > 0 else 0
                })
        
        return benchmark_metrics
        
    except Exception as e:
        st.error(f"Error calculating benchmark metrics: {str(e)}")
        return {
            'benchmark_return': 0.12,
            'benchmark_volatility': 0.15,
            'benchmark_sharpe': 0.8,
            'portfolio_comparisons': []
        }


def initialize_session_state():
    """Initialize session state variables"""
    if 'base_path' not in st.session_state:
        st.session_state.base_path = "/data"  # Default Docker mount point
    if 'data_loader' not in st.session_state:
        st.session_state.data_loader = LocalDataLoader(st.session_state.base_path)


def load_latest_data():
    """Load the latest data from all phases"""
    data_loader = st.session_state.data_loader
    
    # Load latest processed data
    nasdaq_data = data_loader.load_csv("processed/nasdaq_100_analysis.csv")
    stock_data = data_loader.load_csv("processed/nasdaq_100_with_returns.csv")
    
    # Load portfolio optimization results from results/
    results_files = data_loader.list_files("results/")
    portfolio_data = {}
    comparison_data = []
    
    if results_files:
        # Define portfolio patterns to match your local structure
        # Updated with short descriptions for dropdown
        portfolio_patterns = {
            'mv_historical_max_sharpe_significant': 'MV Historical Max Sharpe - Best Risk-Adjusted Returns',
            'mv_historical_min_vol_significant': 'MV Historical Min Vol - Smoothest Ride',
            'mv_undervalue_max_sharpe_significant': 'MV Undervalue Max Sharpe - Best Analyst Picks',
            'mv_undervalue_min_vol_significant': 'MV Undervalue Min Vol - Safe Bets',
            'rp_historical_significant': 'Risk Parity Historical - Equal Risk Distribution',
            'rp_undervalue_significant': 'Risk Parity Undervalue - Balanced Future Potential'
        }
        
        for pattern, display_name in portfolio_patterns.items():
            matching_files = [f for f in results_files if pattern in f and f.endswith('.csv')]
            if matching_files:
                # Get latest file for this pattern
                latest_file = sorted(matching_files)[-1]
                df = data_loader.load_csv(latest_file)
                if df is not None and len(df) > 0:
                    portfolio_data[display_name] = df
                    
                    # Calculate portfolio metrics for comparison
                    if 'Annual_Return_5Y' in df.columns and 'Annual_Volatility_5Y' in df.columns and 'Weight' in df.columns:
                        portfolio_return = (df['Weight'] * df['Annual_Return_5Y']).sum()
                        # Simplified portfolio volatility calculation
                        portfolio_volatility = np.sqrt((df['Weight']**2 * df['Annual_Volatility_5Y']**2).sum())
                        sharpe_ratio = (portfolio_return - 0.02) / portfolio_volatility if portfolio_volatility > 0 else 0
                        
                        comparison_data.append({
                            'Model': display_name,
                            'Return': portfolio_return,
                            'Volatility': portfolio_volatility,
                            'Sharpe_Ratio': sharpe_ratio
                        })
        
        # Create comparison dataframe if we have data
        if comparison_data:
            portfolio_data['comparison'] = pd.DataFrame(comparison_data)
    
    if not portfolio_data:
        portfolio_data = None
    
    # Find latest summaries (JSON files)
    summary_files = [f for f in results_files if f.endswith('.json')]
    
    phase1_summary = None
    phase2_summary = None
    phase3_summary = None
    
    # Look for specific summary files
    for file in summary_files:
        if 'nasdaq_analysis_summary' in file:
            summary = data_loader.load_json(file)
            if summary:
                phase1_summary = summary
        elif 'stock_metrics_summary' in file:
            summary = data_loader.load_json(file)
            if summary:
                phase2_summary = summary
        elif 'portfolio_optimization' in file:
            summary = data_loader.load_json(file)
            if summary:
                phase3_summary = summary
    
    # Calculate benchmark metrics if we have the required data
    benchmark_metrics = None
    if nasdaq_data is not None and portfolio_data is not None:
        benchmark_metrics = calculate_benchmark_metrics(portfolio_data, nasdaq_data)
    
    return {
        'nasdaq_data': nasdaq_data,
        'stock_data': stock_data,
        'portfolio_data': portfolio_data,
        'phase1_summary': phase1_summary,
        'phase2_summary': phase2_summary,
        'phase3_summary': phase3_summary,
        'benchmark_metrics': benchmark_metrics
    }


def get_data_age(data_loader, relative_path: str) -> str:
    """Get the age of the most recent data in the specified directory"""
    try:
        files = data_loader.list_files(relative_path)
        if not files:
            return "No data found"
        
        # Find the most recent file
        latest_time = None
        for file in files:
            file_time = data_loader.get_file_timestamp(file)
            if file_time and (latest_time is None or file_time > latest_time):
                latest_time = file_time
        
        if latest_time is None:
            return "Unknown"
        
        # Calculate time difference
        now = datetime.now()
        time_diff = now - latest_time
        
        # Format the time difference
        if time_diff.days > 0:
            if time_diff.days == 1:
                return "1 day ago"
            else:
                return f"{time_diff.days} days ago"
        elif time_diff.seconds > 3600:
            hours = time_diff.seconds // 3600
            if hours == 1:
                return "1 hour ago"
            else:
                return f"{hours} hours ago"
        elif time_diff.seconds > 60:
            minutes = time_diff.seconds // 60
            if minutes == 1:
                return "1 minute ago"
            else:
                return f"{minutes} minutes ago"
        else:
            return "Just now"
            
    except Exception as e:
        return "Unknown"


def render_executive_summary(data):
    """Render the Executive Summary page"""
    st.markdown('<h1 class="main-header">📊 Executive Summary</h1>', unsafe_allow_html=True)
    
    # Data freshness banner
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        if data['phase1_summary']:
            last_analysis = data['phase1_summary'].get('timestamp', 'Unknown')
            st.info(f"🕐 **Data Last Updated:** {last_analysis}")
        else:
            st.warning("⚠️ **No analysis data available** - Run the pipeline first")
    
    with col2:
        if data['stock_data'] is not None:
            stock_count = len(data['stock_data'])
            st.metric("📊 Stocks", stock_count)
    
    with col3:
        if data['portfolio_data']:
            model_count = len([k for k in data['portfolio_data'].keys() if k != 'comparison'])
            st.metric("🎯 Models", model_count)
            
    with col4:
        freshness = get_data_freshness()
        if freshness.get('last_optimization'):
            hours_ago = get_time_ago(freshness['last_optimization'])
            st.metric("⏰ Last Run", hours_ago)
    
    # Page guidance
    st.markdown("""
    <div class="success-card">
        <h4>💡 What can I learn on this page?</h4>
        <ul>
            <li><strong>Quick Overview:</strong> See your portfolio's overall performance at a glance</li>
            <li><strong>Top Opportunities:</strong> Identify the most undervalued stocks from your analysis</li>
            <li><strong>Model Comparison:</strong> Compare how different optimization strategies perform</li>
            <li><strong>System Health:</strong> Check when your data was last updated and pipeline status</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # Data freshness indicator
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    
    with col1:
        if data['phase1_summary']:
            last_update = data['phase1_summary'].get('timestamp', 'Unknown')
            st.info(f"🕐 Last Updated: {last_update}")
    
    with col2:
        if data['nasdaq_data'] is not None:
            total_stocks = len(data['nasdaq_data'])
            st.success(f"📈 {total_stocks} Stocks Analyzed")
    
    with col3:
        if data['portfolio_data']:
            models_count = len([k for k in data['portfolio_data'].keys() if k != 'comparison'])
            st.success(f"🎯 {models_count} Portfolio Models")
    
    with col4:
        if data['stock_data'] is not None:
            stocks_with_returns = len(data['stock_data'][data['stock_data']['Annual_Return_5Y'].notna()])
            st.success(f"📊 {stocks_with_returns} Historical Records")
    
    # Portfolio Performance Summary
    if data['portfolio_data'] and 'comparison' in data['portfolio_data']:
        st.subheader("🏆 Portfolio Performance Summary")
        
        comparison_df = data['portfolio_data']['comparison']
        
        # Create metrics for best performers
        if not comparison_df.empty:
            best_return = comparison_df.loc[comparison_df['Return'].idxmax()]
            best_sharpe = comparison_df.loc[comparison_df['Sharpe_Ratio'].idxmax()]
            lowest_vol = comparison_df.loc[comparison_df['Volatility'].idxmin()]
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown(f"""
                <div class="metric-card">
                    <h4>🚀 Highest Return</h4>
                    <p><strong>Model:</strong> {best_return['Model']}</p>
                    <p><strong>Expected Return:</strong> <span class="positive">{best_return['Return']:.2%}</span></p>
                    <p><strong>Sharpe Ratio:</strong> <span class="neutral">{best_return['Sharpe_Ratio']:.2f}</span></p>
                    <p><strong>Volatility:</strong> <span class="neutral">{best_return['Volatility']:.2%}</span></p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="metric-card">
                    <h4>⚡ Best Risk-Adjusted</h4>
                    <p><strong>Model:</strong> {best_sharpe['Model']}</p>
                    <p><strong>Expected Return:</strong> <span class="neutral">{best_sharpe['Return']:.2%}</span></p>
                    <p><strong>Sharpe Ratio:</strong> <span class="positive">{best_sharpe['Sharpe_Ratio']:.2f}</span></p>
                    <p><strong>Volatility:</strong> <span class="neutral">{best_sharpe['Volatility']:.2%}</span></p>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                st.markdown(f"""
                <div class="metric-card">
                    <h4>🛡️ Lowest Risk</h4>
                    <p><strong>Model:</strong> {lowest_vol['Model']}</p>
                    <p><strong>Expected Return:</strong> <span class="neutral">{lowest_vol['Return']:.2%}</span></p>
                    <p><strong>Sharpe Ratio:</strong> <span class="neutral">{lowest_vol['Sharpe_Ratio']:.2f}</span></p>
                    <p><strong>Volatility:</strong> <span class="positive">{lowest_vol['Volatility']:.2%}</span></p>
                </div>
                """, unsafe_allow_html=True)
    
    # Benchmark Performance Summary
    if data.get('benchmark_metrics'):
        benchmark_data = data['benchmark_metrics']
        
        st.subheader("📈 Performance vs NASDAQ-100")
        st.info("💡 **Benchmark Comparison:** Alpha shows how much extra return your portfolio generates vs the market. Sharpe Ratio measures return per unit of risk - higher is better!")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📊 NASDAQ-100 Return", f"{benchmark_data['benchmark_return']:.2%}")
        with col2:
            st.metric("📊 NASDAQ-100 Volatility", f"{benchmark_data['benchmark_volatility']:.2%}")  
        with col3:
            st.metric("📊 NASDAQ-100 Sharpe", f"{benchmark_data['benchmark_sharpe']:.2f}")
        
        # Show best performing portfolio vs benchmark
        if benchmark_data['portfolio_comparisons']:
            best_alpha = max(benchmark_data['portfolio_comparisons'], key=lambda x: x['Alpha'])
            
            col1, col2 = st.columns(2)
            with col1:
                alpha_color = "positive" if best_alpha['Alpha'] > 0 else "negative"
                st.markdown(f"""
                <div class="metric-card">
                    <h4>🏆 Best Alpha (Excess Return)</h4>
                    <p><strong>Model:</strong> {best_alpha['Model']}</p>
                    <p><strong>Alpha:</strong> <span class="{alpha_color}">{best_alpha['Alpha']:.2%}</span></p>
                    <p><small>{'Outperforming' if best_alpha['Alpha'] > 0 else 'Underperforming'} NASDAQ-100</small></p>
                </div>
                """, unsafe_allow_html=True)
    
    # Top Stock Recommendations
    if data['nasdaq_data'] is not None:
        st.subheader("🔍 Top Stock Recommendations")
        
        # Filter and sort by undervalue rate
        recommendations = data['nasdaq_data'][data['nasdaq_data']['Undervalue Rate'].notna()].copy()
        if not recommendations.empty:
            top_undervalued = recommendations.nlargest(10, 'Undervalue Rate')
            
            # Display as styled table
            display_cols = ['Company', 'Symbol', 'Previous Close', '1y Target Est', 'Undervalue Rate']
            formatted_df = top_undervalued[display_cols].copy()
            formatted_df['Previous Close'] = formatted_df['Previous Close'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "N/A")
            formatted_df['1y Target Est'] = formatted_df['1y Target Est'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "N/A")
            formatted_df['Undervalue Rate'] = formatted_df['Undervalue Rate'].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "N/A")
            
            st.dataframe(formatted_df, use_container_width=True)
        else:
            st.warning("No undervaluation data available")
    
    # Recent Pipeline Activity
    st.subheader("📋 Recent Pipeline Activity")
    
    activity_data = []
    if data['phase1_summary']:
        activity_data.append({
            'Phase': 'Phase 1 - NASDAQ-100 Analysis',
            'Status': '✅ Completed',
            'Timestamp': data['phase1_summary'].get('timestamp', 'Unknown'),
            'Details': f"{data['phase1_summary'].get('total_stocks', 0)} stocks processed"
        })
    
    if data['phase2_summary']:
        activity_data.append({
            'Phase': 'Phase 2 - Historical Data',
            'Status': '✅ Completed',
            'Timestamp': data['phase2_summary'].get('timestamp', 'Unknown'),
            'Details': f"{data['phase2_summary'].get('successfully_processed', 0)} stocks processed"
        })
    
    if data['phase3_summary']:
        activity_data.append({
            'Phase': 'Phase 3 - Portfolio Optimization',
            'Status': '✅ Completed',
            'Timestamp': data['phase3_summary'].get('timestamp', 'Unknown'),
            'Details': f"Portfolio optimization completed"
        })
    
    if activity_data:
        activity_df = pd.DataFrame(activity_data)
        st.dataframe(activity_df, use_container_width=True)


def render_stock_analysis(data):
    """Render the Stock Analysis page"""
    st.markdown('<h1 class="main-header">📊 NASDAQ-100 Analysis</h1>', unsafe_allow_html=True)
    
    # Page guidance
    st.markdown("""
    <div class="success-card">
        <h4>🔍 What can I discover on this page?</h4>
        <ul>
            <li><strong>Find Opportunities:</strong> Discover which NASDAQ-100 stocks have the highest undervaluation potential</li>
            <li><strong>Risk Assessment:</strong> See how returns relate to volatility for informed investment decisions</li>
            <li><strong>Market Patterns:</strong> Understand the distribution of undervalued vs overvalued NASDAQ-100 companies</li>
            <li><strong>Deep Dive:</strong> Use filters to focus on NASDAQ-100 stocks that match your criteria</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    if data['nasdaq_data'] is None:
        st.error("No NASDAQ-100 analysis data available. Please run the analysis pipeline first.")
        
        # Add manual refresh button
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🔄 Refresh Data", use_container_width=True):
                st.rerun()
        
        return
    
    # Combine NASDAQ and stock return data if available
    combined_data = data['nasdaq_data'].copy()
    if data['stock_data'] is not None:
        # Merge on Symbol
        combined_data = combined_data.merge(
            data['stock_data'][['Symbol', 'Annual_Return_5Y', 'Annual_Volatility_5Y']], 
            on='Symbol', 
            how='left'
        )
    
    # Summary statistics
    col1, col2, col3, col4 = st.columns(4)
    
    valid_data = combined_data[combined_data['Undervalue Rate'].notna()]
    
    with col1:
        st.metric("Total Stocks", len(combined_data))
    
    with col2:
        undervalued_count = len(valid_data[valid_data['Undervalue Rate'] > 0])
        st.metric("Undervalued Stocks", undervalued_count)
    
    with col3:
        if not valid_data.empty:
            avg_undervalue = valid_data['Undervalue Rate'].mean()
            st.metric("Avg Undervalue Rate", f"{avg_undervalue:.2%}")
    
    with col4:
        high_potential = len(valid_data[valid_data['Undervalue Rate'] > 0.2])
        st.metric("High Potential (>20%)", high_potential)
    
    # Visualization tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Distribution", "🔝 Top Stocks", "💹 Risk-Return", "📈 Performance"])
    
    with tab1:
        st.subheader("Undervalue Rate Distribution")
        st.info("💡 **What am I looking at?** This shows how many stocks fall into different undervaluation ranges. A right-skewed distribution means more undervalued opportunities!")
        
        if not valid_data.empty:
            fig = px.histogram(
                valid_data,
                x='Undervalue Rate',
                nbins=30,
                title="Distribution of Undervaluation Rates",
                labels={'Undervalue Rate': 'Undervalue Rate (%)', 'count': 'Number of Stocks'}
            )
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.subheader("Top 20 Most Undervalued Stocks")
        st.info("💡 **What am I looking at?** These are your best opportunities! Higher bars = more undervalued = potentially better deals. Hover over bars for details.")
        
        top_20 = valid_data.nlargest(20, 'Undervalue Rate')
        if not top_20.empty:
            fig = px.bar(
                top_20,
                x='Symbol',
                y='Undervalue Rate',
                hover_data=['Company', 'Previous Close', '1y Target Est'],
                title="Top 20 Most Undervalued Stocks",
                labels={'Undervalue Rate': 'Undervalue Rate (%)', 'Symbol': 'Stock Symbol'}
            )
            fig.update_layout(height=500, xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        st.subheader("Risk-Return Analysis")
        st.info("💡 **What am I looking at?** Top-right = high return, high risk. Top-left = high return, low risk (rare gems!). Color shows undervaluation level.")
        
        if 'Annual_Return_5Y' in combined_data.columns and 'Annual_Volatility_5Y' in combined_data.columns:
            risk_return_data = combined_data[
                (combined_data['Annual_Return_5Y'].notna()) & 
                (combined_data['Annual_Volatility_5Y'].notna()) &
                (combined_data['Undervalue Rate'].notna())
            ]
            
            if not risk_return_data.empty:
                fig = px.scatter(
                    risk_return_data,
                    x='Annual_Volatility_5Y',
                    y='Annual_Return_5Y',
                    color='Undervalue Rate',
                    size='Previous Close',
                    hover_data=['Symbol', 'Company'],
                    title="Risk vs Return (Colored by Undervalue Rate)",
                    labels={
                        'Annual_Volatility_5Y': 'Annual Volatility (%)', 
                        'Annual_Return_5Y': 'Annual Return (%)',
                        'Undervalue Rate': 'Undervalue Rate (%)'
                    },
                    color_continuous_scale='RdYlGn'
                )
                fig.update_layout(height=500)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Historical return data not available. Run the complete pipeline to see risk-return analysis.")
    
    with tab4:
        st.subheader("Performance Categories")
        st.info("💡 **What am I looking at?** This shows your stock universe breakdown. More green (High Potential) = more opportunities in your analysis.")
        
        if not valid_data.empty:
            # Categorize stocks
            categories = []
            for _, row in valid_data.iterrows():
                rate = row['Undervalue Rate']
                if rate > 0.2:
                    categories.append('High Potential (>20%)')
                elif rate > 0:
                    categories.append('Moderate Potential (0-20%)')
                else:
                    categories.append('Overvalued (<0%)')
            
            category_counts = pd.Series(categories).value_counts()
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig = px.pie(
                    values=category_counts.values,
                    names=category_counts.index,
                    title="Stock Performance Categories",
                    color_discrete_map={
                        'High Potential (>20%)': '#00cc44',
                        'Moderate Potential (0-20%)': '#ffaa00', 
                        'Overvalued (<0%)': '#ff4444'
                    }
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("### Category Breakdown")
                for category, count in category_counts.items():
                    percentage = count / len(valid_data) * 100
                    st.markdown(f"**{category}**")
                    st.markdown(f"{count} stocks ({percentage:.1f}%)")
                    st.markdown("---")
    
    # Detailed stock table
    st.subheader("📋 Detailed NASDAQ-100 Analysis")
    
    # Interactive filters with guidance
    st.markdown("""
    <div class="warning-card">
        <h4>🎛️ How to use these filters:</h4>
        <ul>
            <li><strong>Minimum Undervalue Rate:</strong> Drag slider to focus on stocks with higher undervaluation (higher = more undervalued)</li>
            <li><strong>Show top N stocks:</strong> Choose how many results to display (start with 20 for manageable list)</li>
            <li><strong>Sort by:</strong> Pick what's most important to you (Undervalue Rate = best deals, Previous Close = stock price)</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        min_undervalue = st.slider(
            "Minimum Undervalue Rate", 
            -0.5, 1.0, 0.0, 0.05,
            help="Higher values show only more undervalued stocks. 0.0 = show all stocks, 0.2 = show only stocks with 20%+ upside potential"
        )
    with col2:
        show_count = st.selectbox(
            "Show top N stocks", 
            [10, 20, 50, 100], 
            index=1,
            help="Number of stocks to display in the table below. Start with 20 for a manageable list."
        )
    with col3:
        sort_by = st.selectbox(
            "Sort by", 
            ['Undervalue Rate', 'Previous Close', '1y Target Est', 'Annual_Return_5Y'],
            help="Choose what to prioritize: Undervalue Rate = best deals, Previous Close = stock price, Annual_Return_5Y = historical performance"
        )
    
    # Filter and display data
    filtered_data = valid_data[valid_data['Undervalue Rate'] >= min_undervalue]
    
    if sort_by in filtered_data.columns:
        top_filtered = filtered_data.nlargest(show_count, sort_by)
    else:
        top_filtered = filtered_data.head(show_count)
    
    if not top_filtered.empty:
        display_cols = ['Company', 'Symbol', 'Previous Close', '1y Target Est', 'Undervalue Rate']
        if 'Annual_Return_5Y' in top_filtered.columns:
            display_cols.append('Annual_Return_5Y')
        if 'Annual_Volatility_5Y' in top_filtered.columns:
            display_cols.append('Annual_Volatility_5Y')
        
        formatted_table = top_filtered[display_cols].copy()
        formatted_table['Previous Close'] = formatted_table['Previous Close'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "N/A")
        formatted_table['1y Target Est'] = formatted_table['1y Target Est'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "N/A")
        formatted_table['Undervalue Rate'] = formatted_table['Undervalue Rate'].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "N/A")
        
        if 'Annual_Return_5Y' in formatted_table.columns:
            formatted_table['Annual_Return_5Y'] = formatted_table['Annual_Return_5Y'].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "N/A")
        if 'Annual_Volatility_5Y' in formatted_table.columns:
            formatted_table['Annual_Volatility_5Y'] = formatted_table['Annual_Volatility_5Y'].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "N/A")
        
        st.dataframe(formatted_table, use_container_width=True)


def render_portfolio_optimization(data):
    """Render the Portfolio Optimization page"""
    st.markdown('<h1 class="main-header">🎯 Portfolio Optimization</h1>', unsafe_allow_html=True)
    
    # Data freshness indicator
    if data['phase3_summary']:
        optimization_time = data['phase3_summary'].get('timestamp', 'Unknown')
        st.info(f"🕐 **Portfolio models optimized:** {optimization_time}")
    
    # Page guidance
    st.markdown("""
    <div class="success-card">
        <h4>🎯 What You'll Find Here</h4>
        <ul>
            <li><strong>Performance Table:</strong> Shows which strategy might make the most money and which is safest - like comparing financial advisors</li>
            <li><strong>Risk vs Return Chart:</strong> Visual map showing high-reward vs low-risk strategies (bigger circles = better performance)</li>
            <li><strong>Stock Allocations:</strong> Exact percentages of each stock to buy (like a shopping list for your broker)</li>
            <li><strong>Download Portfolio:</strong> Get CSV files you can upload directly to your brokerage account</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    if not data or 'comparison' not in data:
        st.warning("No portfolio optimization results available. Run the optimization pipeline first.")
        
        # Add manual refresh button
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🔄 Refresh Data", use_container_width=True):
                st.rerun()
        
        return
    
    comparison_df = data['comparison']
    
    # Model Performance Comparison
    st.subheader("📊 Model Performance Comparison")
    st.info("💡 **How to read this:** Look for high Return % (more money), low Volatility % (less risky), and high Sharpe Ratio (best bang for your buck). A Sharpe ratio above 1.0 is considered good.")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        # Performance metrics table
        metrics_display = comparison_df.copy()
        metrics_display['Return'] = metrics_display['Return'].apply(lambda x: f"{x:.2%}")
        metrics_display['Volatility'] = metrics_display['Volatility'].apply(lambda x: f"{x:.2%}")
        metrics_display['Sharpe_Ratio'] = metrics_display['Sharpe_Ratio'].apply(lambda x: f"{x:.2f}")
        
        st.dataframe(metrics_display, use_container_width=True)
    
    with col2:
        # Best performing model highlights
        best_return = comparison_df.loc[comparison_df['Return'].idxmax()]
        best_sharpe = comparison_df.loc[comparison_df['Sharpe_Ratio'].idxmax()]
        lowest_vol = comparison_df.loc[comparison_df['Volatility'].idxmin()]
        
        st.metric("🚀 Highest Return", f"{best_return['Return']:.2%}", best_return['Model'])
        st.metric("⚡ Best Sharpe Ratio", f"{best_sharpe['Sharpe_Ratio']:.2f}", best_sharpe['Model'])
        st.metric("🛡️ Lowest Risk", f"{lowest_vol['Volatility']:.2%}", lowest_vol['Model'])
    
    # Risk-Return Scatter Plot
    st.subheader("🎯 Risk-Return Analysis")
    st.info("💡 **How to read this chart:** Each dot is a different investment strategy. The best strategies are in the top-left corner (high return, low risk). Bigger, darker circles have better Sharpe ratios. Click and drag to zoom in!")
    
    fig_scatter = go.Figure()
    fig_scatter.add_trace(go.Scatter(
        x=comparison_df['Volatility'],
        y=comparison_df['Return'],
        mode='markers+text',
        text=comparison_df['Model'],
        textposition="top center",
        marker=dict(
            size=comparison_df['Sharpe_Ratio'] * 20,
            color=comparison_df['Sharpe_Ratio'],
            colorscale='Viridis',
            showscale=True,
            colorbar=dict(title="Sharpe Ratio")
        ),
        hovertemplate="<b>%{text}</b><br>Return: %{y:.2%}<br>Volatility: %{x:.2%}<br>Sharpe: %{marker.color:.2f}<extra></extra>"
    ))
    
    fig_scatter.update_layout(
        title="Portfolio Models: Risk vs Return Profile",
        xaxis_title="Volatility (Risk)",
        yaxis_title="Expected Return",
        height=500
    )
    st.plotly_chart(fig_scatter, use_container_width=True)
    
    # Benchmark Comparison
    if 'benchmark_metrics' in st.session_state and st.session_state.get('data', {}).get('benchmark_metrics'):
        benchmark_data = st.session_state.data['benchmark_metrics']
        
        st.subheader("📈 Benchmark Comparison")
        st.info("💡 **Portfolio vs NASDAQ-100:** See how your optimized portfolios perform against the market index. Alpha shows excess return, Beta shows risk relative to market.")
        
        # Create benchmark comparison table
        if benchmark_data['portfolio_comparisons']:
            bench_df = pd.DataFrame(benchmark_data['portfolio_comparisons'])
            
            # Display benchmark metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📊 NASDAQ-100 Return", f"{benchmark_data['benchmark_return']:.2%}")
            with col2:
                st.metric("📊 NASDAQ-100 Volatility", f"{benchmark_data['benchmark_volatility']:.2%}")
            with col3:
                st.metric("📊 NASDAQ-100 Sharpe", f"{benchmark_data['benchmark_sharpe']:.2f}")
            
            # Enhanced comparison table with benchmark metrics
            display_df = bench_df.copy()
            display_df['Return'] = display_df['Return'].apply(lambda x: f"{x:.2%}")
            display_df['Volatility'] = display_df['Volatility'].apply(lambda x: f"{x:.2%}")
            display_df['Sharpe_Ratio'] = display_df['Sharpe_Ratio'].apply(lambda x: f"{x:.2f}")
            display_df['Alpha'] = display_df['Alpha'].apply(lambda x: f"{x:.2%}")
            display_df['Beta'] = display_df['Beta'].apply(lambda x: f"{x:.2f}")
            display_df['Tracking_Error'] = display_df['Tracking_Error'].apply(lambda x: f"{x:.2%}")
            display_df['Information_Ratio'] = display_df['Information_Ratio'].apply(lambda x: f"{x:.2f}")
            
            # Rename columns for display
            display_df = display_df.rename(columns={
                'Sharpe_Ratio': 'Sharpe Ratio',
                'Tracking_Error': 'Tracking Error',
                'Information_Ratio': 'Info Ratio'
            })
            
            st.dataframe(display_df, use_container_width=True)
            
            # Alpha visualization
            fig_alpha = go.Figure()
            fig_alpha.add_trace(go.Bar(
                x=bench_df['Model'],
                y=bench_df['Alpha'],
                marker_color=['green' if x > 0 else 'red' for x in bench_df['Alpha']],
                text=[f"{x:.2%}" for x in bench_df['Alpha']],
                textposition='auto'
            ))
            
            fig_alpha.update_layout(
                title="Alpha vs NASDAQ-100 (Excess Return)",
                xaxis_title="Portfolio Model",
                yaxis_title="Alpha",
                height=400,
                showlegend=False
            )
            
            # Add benchmark line at 0
            fig_alpha.add_hline(y=0, line_dash="dash", line_color="blue", 
                              annotation_text="NASDAQ-100 Benchmark")
            
            st.plotly_chart(fig_alpha, use_container_width=True)
    
    # Portfolio Allocations
    st.subheader("🥧 Portfolio Allocations")
    st.info("💡 **How to use this:** Pick your favorite strategy from the dropdown, see exactly what percentage of each stock to buy, then download the CSV file to upload to your broker (like Fidelity, Schwab, etc.)")
    
    # Model selector
    available_portfolios = [k for k in data.keys() if k not in ['comparison'] and isinstance(data[k], pd.DataFrame)]
    if available_portfolios:
        selected_portfolio = st.selectbox(
            "Select Portfolio to Analyze:",
            available_portfolios,
            help="Choose a portfolio model to view detailed allocations"
        )
        
        if selected_portfolio in data:
            portfolio_df = data[selected_portfolio]
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Top 10 holdings pie chart
                top_holdings = portfolio_df.nlargest(10, 'Weight')
                fig_pie = px.pie(
                    top_holdings,
                    values='Weight',
                    names='Symbol',
                    title=f"Top 10 Holdings - {selected_portfolio.replace('_', ' ').title()}"
                )
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_pie, use_container_width=True)
                
                # Add detailed description box
                portfolio_descriptions = {
                    'MV Historical Max Sharpe - Best Risk-Adjusted Returns': {
                        'title': '📈 Best Bang for Your Buck - Based on Past Performance',
                        'description': 'This strategy finds stocks that historically gave the highest returns relative to their risk. Like choosing players with the best batting average considering their consistency.',
                        'details': '• Typically selects 10-15 top performers\n• Balances high returns with manageable risk\n• Best for: Investors seeking maximum efficiency from historical data'
                    },
                    'MV Historical Min Vol - Smoothest Ride': {
                        'title': '🛡️ Smooth Sailing - The Steady & Stable Portfolio',
                        'description': 'Focuses on stocks with the least price swings based on historical data. Like choosing the calmest route even if it takes a bit longer.',
                        'details': '• Usually picks 20-30 stable stocks\n• Minimizes portfolio ups and downs\n• Best for: Conservative investors who prefer stability'
                    },
                    'MV Undervalue Max Sharpe - Best Analyst Picks': {
                        'title': '💎 Hidden Gems - Best Potential Based on Analyst Predictions',
                        'description': 'Uses analyst price targets to find stocks with the best upside potential relative to risk. Like betting on underdog teams that experts think will surprise everyone.',
                        'details': '• Selects 10-15 stocks analysts believe are most underpriced\n• Combines growth potential with risk management\n• Best for: Investors who trust analyst forecasts'
                    },
                    'MV Undervalue Min Vol - Safe Bets': {
                        'title': '🎯 Safe Bets - Stable Stocks with Room to Grow',
                        'description': 'Combines analyst optimism with preference for stability. Like choosing reliable companies that experts also think are undervalued.',
                        'details': '• Picks 20-30 stocks offering steady growth potential\n• Minimizes wild price swings\n• Best for: Cautious investors seeking modest growth'
                    },
                    'Risk Parity Historical - Equal Risk Distribution': {
                        'title': '⚖️ Equal Opportunity - Everyone Gets a Fair Share of Risk',
                        'description': 'Gives each stock an allocation so they all contribute equally to portfolio risk. Like a potluck where everyone brings a dish of similar size.',
                        'details': '• Includes all stocks (typically 100+)\n• Weights them to balance risk contribution\n• Best for: Maximum diversification based on past volatility'
                    },
                    'Risk Parity Undervalue - Balanced Future Potential': {
                        'title': '🔮 Balanced Potential - Equal Risk with Analyst Insights',
                        'description': 'Same equal-risk approach but evaluates performance using analyst predictions. Like giving everyone equal playing time but measuring success by future potential.',
                        'details': '• All stocks included (typically 100+)\n• Weighted for equal risk, scored on predicted growth\n• Best for: Diversified exposure to analyst-favored stocks'
                    }
                }
                
                # Display description for selected portfolio
                if selected_portfolio in portfolio_descriptions:
                    desc_info = portfolio_descriptions[selected_portfolio]
                    with st.expander("📚 **About This Strategy**", expanded=True):
                        st.markdown(f"### {desc_info['title']}")
                        st.markdown(desc_info['description'])
                        st.markdown(desc_info['details'])
            
            with col2:
                # Portfolio statistics
                total_weight = portfolio_df['Weight'].sum()
                num_holdings = len(portfolio_df[portfolio_df['Weight'] > 0.001])
                max_weight = portfolio_df['Weight'].max()
                
                st.metric("Total Allocation", f"{total_weight:.1%}")
                st.metric("Number of Holdings", f"{num_holdings}")
                st.metric("Largest Position", f"{max_weight:.1%}")
                
                # Download button
                csv = portfolio_df.to_csv(index=False)
                st.download_button(
                    "📥 Download Portfolio",
                    csv,
                    f"{selected_portfolio}_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv",
                    use_container_width=True
                )


def render_historical_tracking(data):
    """Render the Historical Tracking page"""
    st.markdown('<h1 class="main-header">📈 Historical Tracking</h1>', unsafe_allow_html=True)
    
    data_loader = st.session_state.data_loader
    
    # Page guidance
    st.markdown("""
    <div class="success-card">
        <h4>📈 What You'll Find Here</h4>
        <ul>
            <li><strong>System Reliability:</strong> See if your automated system runs successfully each month (green = good, red = needs attention)</li>
            <li><strong>Strategy Evolution:</strong> Watch how different investment strategies perform as market conditions change over months</li>
            <li><strong>Timing Insights:</strong> Identify the best times to rebalance your portfolio based on historical patterns</li>
            <li><strong>Data Freshness:</strong> Know how recent your investment recommendations are - like checking your car's maintenance history</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # Pipeline Execution History
    st.subheader("🔄 Pipeline Execution History")
    st.caption("Track pipeline reliability and performance over time from local execution logs.")
    
    # Get historical results from local files
    results_files = data_loader.list_files("results/")
    
    if results_files:
        execution_data = []
        for file in results_files:
            file_timestamp = data_loader.get_file_timestamp(file)
            if file_timestamp:
                execution_data.append({
                    'Date': file_timestamp,
                    'File': file,
                    'Type': 'Portfolio Result' if file.endswith('.csv') else 'Summary Report',
                    'Status': 'Completed'
                })
        
        if execution_data:
            execution_history = pd.DataFrame(execution_data)
            execution_history = execution_history.sort_values('Date', ascending=False)
            
            # Metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                total_executions = len(execution_history)
                st.metric("Total Executions", total_executions)
            with col2:
                if not execution_history.empty:
                    last_run = execution_history['Date'].max().strftime('%Y-%m-%d %H:%M')
                    st.metric("Last Execution", last_run)
            with col3:
                recent_files = len(execution_history[execution_history['Date'] > datetime.now() - timedelta(days=7)])
                st.metric("Recent Files (7 days)", recent_files)
            
            # Recent executions table
            st.subheader("📋 Recent Files")
            recent_executions = execution_history.head(20).copy()
            recent_executions['Date'] = recent_executions['Date'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            st.dataframe(
                recent_executions[['Date', 'Type', 'File']],
                use_container_width=True
            )
        else:
            st.info("No execution history found yet.")
    else:
        st.info("No results files found. Run the pipeline first to see execution history.")
    
    # Model performance over time
    st.subheader("📊 Model Performance Trends")
    st.caption("Historical model performance based on local results files over time.")
    
    # Look for comparison files
    comparison_files = [f for f in results_files if 'comparison' in f.lower() or 'performance' in f.lower()]
    
    if comparison_files:
        historical_data = []
        for file in sorted(comparison_files)[-10:]:  # Last 10 files
            try:
                file_timestamp = data_loader.get_file_timestamp(file)
                if file_timestamp:
                    df = data_loader.load_csv(file)
                    if df is not None and 'Model' in df.columns:
                        df['Date'] = file_timestamp
                        historical_data.append(df)
            except Exception:
                continue
        
        if historical_data:
            # Combine all historical data
            combined_df = pd.concat(historical_data, ignore_index=True)
            
            # Performance trend chart
            if 'Return' in combined_df.columns:
                fig_trend = px.line(
                    combined_df,
                    x='Date',
                    y='Return',
                    color='Model',
                    title="Model Return Trends Over Time"
                )
                st.plotly_chart(fig_trend, use_container_width=True)
            
            # Show data table
            st.subheader("📋 Historical Performance Data")
            if 'Return' in combined_df.columns:
                pivot_df = combined_df.pivot_table(
                    index='Date', 
                    columns='Model', 
                    values='Return', 
                    aggfunc='first'
                ).round(4)
                st.dataframe(pivot_df, use_container_width=True)
        else:
            st.info("No historical performance comparison files found.")
    else:
        st.info("No historical model performance data available yet. Performance comparison files will be created as you run the pipeline over time.")
    
    # Data freshness
    st.subheader("📅 Data Freshness")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("**Stock Data:** Updated when pipeline runs")
        st.info("**Portfolio Analysis:** Refreshed on manual execution")
    
    with col2:
        # Get real data ages from local files
        stock_data_age = get_data_age(data_loader, "data")
        portfolio_age = get_data_age(data_loader, "results")
        
        st.metric("Stock Data Age", stock_data_age)
        st.metric("Portfolio Results Age", portfolio_age)


def render_system_status(data):
    """Render the System Status page"""
    st.markdown('<h1 class="main-header">⚙️ System Status</h1>', unsafe_allow_html=True)
    
    # Page guidance
    st.markdown("""
    <div class="success-card">
        <h4>⚙️ What You'll Find Here</h4>
        <ul>
            <li><strong>Check System Health:</strong> Monitor local system resources and data availability</li>
            <li><strong>View Data Status:</strong> Check when your data was last updated and file counts</li>
            <li><strong>Manual Controls:</strong> Trigger analysis runs and refresh data</li>
            <li><strong>Container Health:</strong> Monitor Docker container performance and resource usage</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # System Health Overview
    st.subheader("🏥 System Health")
    
    # Get local system health
    with st.spinner("Checking system health..."):
        health_status = get_system_health()
    
    col1, col2, col3, col4 = st.columns(4)
    
    def get_status_color(status):
        if status == 'Healthy':
            return 'positive'
        elif status in ['Warning', 'Partial']:
            return 'neutral'
        else:
            return 'negative'
    
    def get_status_icon(status):
        if status == 'Healthy':
            return '● Online'
        elif status in ['Warning', 'Partial']:
            return '◐ Warning'
        elif status == 'Offline':
            return '○ Offline'
        else:
            return '● Error'
    
    with col1:
        disk_status = health_status['disk_usage']
        st.markdown(f"""
        <div class="metric-card">
            <h4>Disk Usage</h4>
            <div class="{get_status_color(disk_status['status'])}">{get_status_icon(disk_status['status'])}</div>
            <small>{disk_status['detail']}</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        memory_status = health_status['memory_usage']
        st.markdown(f"""
        <div class="metric-card">
            <h4>Memory Usage</h4>
            <div class="{get_status_color(memory_status['status'])}">{get_status_icon(memory_status['status'])}</div>
            <small>{memory_status['detail']}</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        data_status = health_status['data_directory']
        st.markdown(f"""
        <div class="metric-card">
            <h4>Data Directory</h4>
            <div class="{get_status_color(data_status['status'])}">{get_status_icon(data_status['status'])}</div>
            <small>{data_status['detail']}</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        api_status = health_status['api_service']
        st.markdown(f"""
        <div class="metric-card">
            <h4>API Service</h4>
            <div class="{get_status_color(api_status['status'])}">{get_status_icon(api_status['status'])}</div>
            <small>{api_status['detail']}</small>
        </div>
        """, unsafe_allow_html=True)
    
    # Manual Controls
    st.subheader("🎮 System Controls")
    st.caption("Manage pipeline execution and view system status")
    
    # Create 3-column layout with consistent card structure
    col1, col2, col3 = st.columns(3)
    
    # COLUMN 1 - Pipeline Control
    with col1:
        # Title card
        st.markdown("""
        <div class="metric-card" style="padding: 1rem; margin-bottom: 0.5rem; border-left: 4px solid #1f77b4;">
            <h4 style="margin-top: 0; margin-bottom: 0; color: #1f77b4;">🚀 Pipeline Control</h4>
        </div>
        """, unsafe_allow_html=True)
        
        # Check pipeline status for button state
        api_host = "portfolio-data-pipeline:8080" if os.path.exists("/.dockerenv") else "localhost:8081"
        try:
            status_response = requests.get(f"http://{api_host}/status", timeout=2)
            if status_response.status_code == 200:
                status_data = status_response.json()
                execution_status = status_data.get("execution_status", {})
                is_running = execution_status.get("running", False)
                
                if is_running:
                    pipeline_button_disabled = True
                    button_text = "⏳ Running..."
                else:
                    pipeline_button_disabled = False
                    button_text = "🚀 Run Analysis"
            else:
                pipeline_button_disabled = True
                button_text = "🚀 Run Pipeline"
                execution_status = {}
        except:
            pipeline_button_disabled = True
            button_text = "🚀 Run Pipeline"
            execution_status = {}
            is_running = False
        
        # Button immediately below title
        if st.button(button_text, use_container_width=True, type="primary", disabled=pipeline_button_disabled,
                    help="Run complete NASDAQ-100 portfolio optimization"):
            trigger_full_pipeline()
            st.rerun()
        
        # Description text
        st.caption("📊 Analyzes NASDAQ-100 → Fetches history → Optimizes portfolios")
        
        # Status card with detailed progress
        with st.container():
            if is_running:
                st.info("⏳ **Pipeline Running**")
                
                # Try to get detailed progress
                try:
                    logs_response = requests.get(f"http://{api_host}/logs", params={"lines": 10}, timeout=2)
                    if logs_response.status_code == 200:
                        logs_data = logs_response.json()
                        recent_logs = logs_data.get("logs", [])
                        
                        # Parse progress from logs
                        for log in reversed(recent_logs):
                            if "Processing" in log and "/100:" in log:
                                # Extract stock progress
                                import re
                                match = re.search(r'Processing (\d+)/100: (.+?)\.\.\.$', log)
                                if match:
                                    progress = int(match.group(1))
                                    stock_name = match.group(2)
                                    st.progress(progress / 100, text=f"Stock {progress}/100: {stock_name}")
                                    break
                            elif "Phase" in log:
                                phase_text = log.split(' - ')[-1] if ' - ' in log else log
                                st.caption(f"📍 {phase_text}")
                                break
                except:
                    pass
                
                # Show elapsed time
                if execution_status.get('last_run'):
                    try:
                        from datetime import datetime
                        start_time = datetime.fromisoformat(execution_status['last_run'].replace('Z', '+00:00'))
                        elapsed = (datetime.now() - start_time.replace(tzinfo=None)).seconds
                        st.caption(f"⏱️ Running for {elapsed // 60}m {elapsed % 60}s")
                    except:
                        pass
            else:
                st.success("✅ **Ready to Run**")
                
                # Show last run info
                if execution_status.get('last_run'):
                    st.caption(f"Last run: {get_time_ago(execution_status['last_run'])}")
                if execution_status.get('last_duration'):
                    st.caption(f"Duration: {execution_status['last_duration']:.0f}s")
    
    # COLUMN 2 - Execution History  
    with col2:
        # Title card
        st.markdown("""
        <div class="metric-card" style="padding: 1rem; margin-bottom: 0.5rem; border-left: 4px solid #2ca02c;">
            <h4 style="margin-top: 0; margin-bottom: 0; color: #2ca02c;">📊 Execution History</h4>
        </div>
        """, unsafe_allow_html=True)
        
        # Button immediately below title
        if st.button("🔄 Refresh Data", use_container_width=True, 
                    help="Refresh dashboard data and clear cache"):
            st.cache_data.clear()
            st.rerun()
        
        # Description text
        st.caption("🔄 View execution history and refresh dashboard")
        
        # Status card with execution history
        with st.container():
            try:
                # Get execution history
                history_response = requests.get(f"http://{api_host}/execution-history", timeout=3)
                if history_response.status_code == 200:
                    history_data = history_response.json()
                    history = history_data.get("history", [])
                    
                    if history:
                        # Show most recent
                        recent = history[0]
                        if recent['status'] == 'running':
                            st.warning("⏳ **Currently Running**")
                        elif recent['status'] == 'success':
                            st.success("✅ **Last: Success**")
                        else:
                            st.error("❌ **Last: Failed**")
                        
                        # Show mini history
                        if len(history) > 1:
                            st.caption("Recent runs:")
                            for run in history[1:4]:
                                if run['status'] != 'running':
                                    icon = "✅" if run['status'] == 'success' else "❌"
                                    time_str = run['timestamp'].split(' ')[-1][:5] if ' ' in run['timestamp'] else run['timestamp'][:5]
                                    st.caption(f"{icon} {time_str}")
                    else:
                        st.info("🕰️ **No recent executions**")
                        st.caption("Run the pipeline to see history")
                else:
                    # Fallback to simple status
                    status_response = requests.get(f"http://{api_host}/status", timeout=3)
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        execution_status = status_data.get("execution_status", {})
                        
                        last_run = execution_status.get('last_run')
                        last_status = execution_status.get('last_status')
                        
                        if last_run:
                            if last_status == 'success':
                                st.success("✅ **Last: Success**")
                            elif last_status == 'error':
                                st.error("❌ **Last: Failed**")
                            else:
                                st.info("⏳ **Status Unknown**")
                            
                            st.caption(f"Time: {get_time_ago(last_run)}")
                        else:
                            st.info("🕰️ **No recent executions**")
                    else:
                        st.warning("⚠️ **Status unavailable**")
            except:
                st.error("🚫 **Cannot fetch status**")
    
    # COLUMN 3 - Health Check
    with col3:
        # Title card
        st.markdown("""
        <div class="metric-card" style="padding: 1rem; margin-bottom: 0.5rem; border-left: 4px solid #ff7f0e;">
            <h4 style="margin-top: 0; margin-bottom: 0; color: #ff7f0e;">🩺 Health Check</h4>
        </div>
        """, unsafe_allow_html=True)
        
        # Button immediately below title
        if st.button("🩺 Check Health", use_container_width=True,
                    help="Run comprehensive system health check"):
            st.rerun()
        
        # Description text
        st.caption("🩺 Monitor system health and data freshness")
        
        # Health status card
        with st.container():
            try:
                health_ok = True
                
                # Data freshness check
                freshness = get_data_freshness()
                if freshness and freshness.get('last_optimization'):
                    last_update = freshness.get('last_optimization')
                    time_ago = get_time_ago(last_update)
                    
                    # Check if stale (>24 hours)
                    from datetime import datetime, timedelta
                    update_time = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                    if datetime.now() - update_time.replace(tzinfo=None) > timedelta(hours=24):
                        st.warning(f"⚠️ **Data: {time_ago}**")
                        st.caption("Consider running fresh analysis")
                        health_ok = False
                    else:
                        st.success(f"✅ **Data: {time_ago}**")
                else:
                    st.warning("⚠️ **No recent data**")
                    health_ok = False
                
                # API health
                try:
                    health_response = requests.get(f"http://{api_host}/health", timeout=2)
                    if health_response.status_code == 200:
                        st.success("✅ **API: Healthy**")
                    else:
                        st.warning("⚠️ **API: Issues**")
                        health_ok = False
                except:
                    st.error("❌ **API: Unavailable**")
                    health_ok = False
                
                # Storage info
                try:
                    info_response = requests.get(f"http://{api_host}/data-info", timeout=2)
                    if info_response.status_code == 200:
                        info_data = info_response.json()
                        storage = info_data.get('storage', {})
                        total_mb = storage.get('total_size_mb', 0)
                        
                        if total_mb > 1000:  # Warning if >1GB
                            st.caption(f"📦 Storage: {total_mb:.0f}MB (high)")
                        else:
                            st.caption(f"📦 Storage: {total_mb:.0f}MB")
                except:
                    pass
                    
            except Exception as e:
                st.error("❌ **Health check failed**")
    
    # Data Storage Overview
    st.subheader("💾 Data Storage Overview")
    
    data_loader = st.session_state.data_loader
    
    # Get file counts and sizes
    data_files = data_loader.list_files("data")
    processed_files = data_loader.list_files("processed")
    results_files = data_loader.list_files("results")
    
    data_size = data_loader.get_directory_size("data")
    processed_size = data_loader.get_directory_size("processed")
    results_size = data_loader.get_directory_size("results")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <h4>📁 Raw Data</h4>
            <p><strong>Files:</strong> {len(data_files)}</p>
            <p><strong>Size:</strong> {data_size / (1024*1024):.1f} MB</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <h4>⚙️ Processed Data</h4>
            <p><strong>Files:</strong> {len(processed_files)}</p>
            <p><strong>Size:</strong> {processed_size / (1024*1024):.1f} MB</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <h4>📈 Results</h4>
            <p><strong>Files:</strong> {len(results_files)}</p>
            <p><strong>Size:</strong> {results_size / (1024*1024):.1f} MB</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Container Information
    st.subheader("🐳 Container Information")
    
    try:
        # Get container stats if available
        container_info = {
            'Python Version': f"{os.sys.version.split()[0]}",
            'Working Directory': str(Path.cwd()),
            'Data Mount': str(st.session_state.data_loader.base_path),
            'Container User': os.getenv('USER', 'unknown')
        }
        
        info_df = pd.DataFrame(list(container_info.items()), columns=['Property', 'Value'])
        st.dataframe(info_df, use_container_width=True)
        
    except Exception as e:
        st.error(f"Could not retrieve container information: {e}")
    
    # Log viewer section
    st.markdown("---")
    st.subheader("📜 Pipeline Logs")
    
    # Add controls
    log_col1, log_col2 = st.columns([1, 1])
    with log_col1:
        auto_refresh = st.checkbox("Auto-refresh logs (every 5 seconds)")
    with log_col2:
        log_lines = st.number_input("Number of lines", min_value=10, max_value=200, value=50, step=10)
    
    # Get logs from API
    try:
        api_host = "portfolio-data-pipeline:8080" if os.path.exists("/.dockerenv") else "localhost:8081"
        logs_response = requests.get(f"http://{api_host}/logs", params={"lines": log_lines}, timeout=5)
        
        if logs_response.status_code == 200:
            logs_data = logs_response.json()
            logs = logs_data.get("logs", [])
            
            if logs:
                # Display in a text area
                log_text = "\n".join(logs[-log_lines:])
                st.text_area("Recent Logs", value=log_text, height=400, disabled=True, key="log_viewer")
                
                # Show log statistics
                st.caption(f"Showing last {len(logs)} lines • Last updated: {datetime.now().strftime('%H:%M:%S')}")
            else:
                st.info("No logs available yet")
                
            # Auto-refresh if enabled
            if auto_refresh:
                time.sleep(5)
                st.rerun()
        else:
            st.warning("Could not fetch logs from API")
    except Exception as e:
        st.error(f"Error fetching logs: {str(e)}")
    
    # Pipeline execution information
    st.markdown("---")
    st.markdown("""
    <div class="success-card">
        <h4>🚀 Local Pipeline Execution</h4>
        <ul>
            <li><strong>Manual Execution:</strong> Use the "Run Analysis" button above to start the pipeline</li>
            <li><strong>Expected Duration:</strong> ~15-30 minutes end-to-end</li>
            <li><strong>Progress Monitoring:</strong> Check the logs above for real-time updates</li>
            <li><strong>Results:</strong> Automatically saved to local data directory and visible in this dashboard</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)


def main():
    """Main application function"""
    # Initialize session state
    initialize_session_state()
    
    # Authentication disabled - proceed directly to dashboard
    # if not authenticate_user():
    #     return
    
    # Sidebar - removed user info since authentication is disabled
    st.sidebar.title("🎯 Portfolio Dashboard")
    # Removed welcome message and logout button
    # st.sidebar.success(f"Welcome, {st.session_state.get('username', 'User')}!")
    # if st.sidebar.button("🚪 Logout", use_container_width=True):
    #     st.session_state.authenticated = False
    #     st.rerun()
    
    st.sidebar.markdown("---")
    
    # Navigation
    st.sidebar.markdown("### 📍 Navigate")
    
    # Page navigation with icons
    pages = {
        "🏠 Executive Summary": "Executive Summary",
        "🔍 NASDAQ-100 Analysis": "Stock Analysis", 
        "🎯 Portfolio Optimization": "Portfolio Optimization",
        "📊 Technical Analysis": "Technical Analysis",
        "📈 Historical Tracking": "Historical Tracking",
        "⚙️ System Status": "System Status"
    }
    
    page = st.sidebar.radio(
        "Go to page:",
        list(pages.keys()),
        format_func=lambda x: x,
        label_visibility="collapsed"
    )
    
    # Convert display name back to actual page name
    page = pages[page]
    
    st.sidebar.markdown("---")
    
    # Quick Start Guide
    st.sidebar.markdown("### 📖 Quick Start Guide")
    st.sidebar.markdown("""
    **Navigate through your investment analysis:**
    
    🏠 **Executive Summary** - Overview and key metrics
    
    🔍 **NASDAQ-100 Analysis** - Explore individual opportunities  
    
    🎯 **Portfolio Optimization** - Compare strategies and download portfolios
    
    📈 **Historical Tracking** - Monitor performance over time
    
    ⚙️ **System Status** - Health monitoring and manual controls
    
    ---
    
    💡 **Pro Tips:**
    - Download CSV files from Portfolio Optimization for your broker
    - Check System Status if data seems outdated
    - Use "Run Analysis" button to trigger fresh analysis
    """)
    
    # Load data
    with st.spinner("Loading data from local files..."):
        data = load_latest_data()
    
    # Store data in session state for access in render functions
    st.session_state.data = data
    
    # Render selected page
    if page == "Executive Summary":
        render_executive_summary(data)
    elif page == "Stock Analysis":
        render_stock_analysis(data)
    elif page == "Portfolio Optimization":
        portfolio_data = data.get('portfolio_data', {}) if data else {}
        render_portfolio_optimization(portfolio_data)
    elif page == "Technical Analysis":
        render_technical_analysis(data)
    elif page == "Historical Tracking":
        render_historical_tracking(data)
    elif page == "System Status":
        render_system_status(data)


def render_technical_analysis(data):
    """Render the technical analysis page for individual stock analysis"""
    st.markdown('<h1 class="main-header">📊 Individual Stock Technical Analysis</h1>', unsafe_allow_html=True)
    
    if not TECHNICAL_ANALYSIS_AVAILABLE:
        st.error("Technical analysis functionality is not available. Please ensure all required dependencies are installed.")
        return
    
    # Create two columns for the layout
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("### 🔍 Stock Selection")
        
        # Stock symbol input
        symbol = st.text_input(
            "Enter Stock Symbol",
            value="AAPL",
            help="Enter any valid stock ticker symbol (e.g., AAPL, MSFT, GOOGL)"
        ).upper()
        
        # Analysis period
        period = st.selectbox(
            "Analysis Period",
            ["1mo", "3mo", "6mo", "1y"],
            index=2,
            help="Select the historical data period for analysis"
        )
        
        # Analysis type
        analysis_type = st.radio(
            "Analysis Mode",
            ["Quick Analysis", "Detailed Analysis"],
            help="Quick Analysis shows key indicators, Detailed includes all metrics"
        )
        
        # Analyze button
        analyze_button = st.button("🚀 Analyze Stock", type="primary", use_container_width=True)
        
        # Quick stock buttons for NASDAQ-100 leaders
        st.markdown("### 🎯 Quick Analysis")
        st.markdown("**Top NASDAQ-100 Stocks:**")
        
        quick_stocks = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO"]
        cols = st.columns(2)
        for i, stock in enumerate(quick_stocks):
            with cols[i % 2]:
                if st.button(stock, key=f"quick_{stock}", use_container_width=True):
                    symbol = stock
                    analyze_button = True
    
    with col2:
        st.markdown("### 📈 Analysis Results")
        
        if analyze_button or symbol:
            if not symbol:
                st.warning("Please enter a stock symbol to analyze.")
                return
            
            try:
                # Initialize technical analysis components
                data_fetcher = StockDataFetcher()
                analyzer = TechnicalAnalyzer()
                
                with st.spinner(f"Analyzing {symbol}..."):
                    # Fetch stock data
                    stock_data = data_fetcher.get_stock_data(symbol, period)
                    
                    if stock_data.empty:
                        st.error(f"Unable to fetch data for {symbol}. Please check the symbol and try again.")
                        return
                    
                    # Get stock info
                    stock_info = data_fetcher.get_stock_info(symbol)
                    
                    # Calculate technical indicators
                    technical_data = analyzer.calculate_indicators(stock_data)
                    
                    # Analyze trend
                    trend_analysis = analyzer.analyze_trend(technical_data)
                    
                    # Calculate risk metrics
                    risk_metrics = calculate_risk_metrics(stock_data)
                    
                    # Get news sentiment
                    news_articles = get_news_sentiment(symbol)
                    news_sentiment = analyze_news_sentiment(news_articles)
                    
                    # Generate AI insights
                    ai_insights = generate_ai_insights(symbol, trend_analysis, news_sentiment, stock_info)
                
                # Display results
                st.success(f"Analysis complete for {symbol}")
                
                # Company Info Section
                if stock_info:
                    st.markdown("#### 📋 Company Information")
                    info_col1, info_col2, info_col3 = st.columns(3)
                    
                    with info_col1:
                        current_price = stock_info.get('Previous Close', 0)
                        st.metric("Current Price", f"${current_price:.2f}" if current_price else "N/A")
                        
                        volume = stock_info.get('Volume', 0)
                        avg_volume = stock_info.get('Avg. Volume', 0)
                        volume_ratio = volume / avg_volume if avg_volume else 0
                        delta_color = "normal" if volume_ratio < 1.2 else "inverse"
                        st.metric("Volume", f"{volume:,}" if volume else "N/A", 
                                f"{volume_ratio:.1f}x avg" if volume_ratio else "")
                    
                    with info_col2:
                        pe_ratio = stock_info.get('PE Ratio', 0)
                        st.metric("P/E Ratio", f"{pe_ratio:.2f}" if pe_ratio else "N/A")
                        
                        beta = stock_info.get('Beta', 0)
                        st.metric("Beta", f"{beta:.2f}" if beta else "N/A")
                    
                    with info_col3:
                        market_cap = stock_info.get('Market Cap', 0)
                        if market_cap:
                            if market_cap >= 1e12:
                                cap_display = f"${market_cap/1e12:.2f}T"
                            elif market_cap >= 1e9:
                                cap_display = f"${market_cap/1e9:.2f}B"
                            elif market_cap >= 1e6:
                                cap_display = f"${market_cap/1e6:.2f}M"
                            else:
                                cap_display = f"${market_cap:,.0f}"
                        else:
                            cap_display = "N/A"
                        st.metric("Market Cap", cap_display)
                        
                        day_range = stock_info.get('Day Range', 'N/A')
                        st.metric("Day Range", day_range)
                
                # Technical Analysis Summary
                st.markdown("#### 🎯 Technical Analysis Summary")
                
                trend_col1, trend_col2, trend_col3 = st.columns(3)
                
                with trend_col1:
                    trend = trend_analysis.get('trend', 'Neutral')
                    trend_color = 'positive' if trend == 'Bullish' else 'negative' if trend == 'Bearish' else 'neutral'
                    st.markdown(f"""
                    <div class="metric-card">
                        <h4>📈 Trend</h4>
                        <p><strong>Direction:</strong> <span class="{trend_color}">{trend}</span></p>
                        <p><strong>Strength:</strong> {trend_analysis.get('strength', 0):.1f}%</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with trend_col2:
                    recommendation = trend_analysis.get('recommendation', 'Hold')
                    rec_color = 'positive' if recommendation == 'Buy' else 'negative' if recommendation == 'Sell' else 'neutral'
                    confidence = trend_analysis.get('confidence', 0)
                    st.markdown(f"""
                    <div class="metric-card">
                        <h4>💡 Recommendation</h4>
                        <p><strong>Action:</strong> <span class="{rec_color}">{recommendation}</span></p>
                        <p><strong>Confidence:</strong> {confidence:.1f}%</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with trend_col3:
                    volatility = risk_metrics.get('volatility', 0)
                    sharpe_ratio = risk_metrics.get('sharpe_ratio', 0)
                    st.markdown(f"""
                    <div class="metric-card">
                        <h4>⚡ Risk Metrics</h4>
                        <p><strong>Volatility:</strong> {volatility:.1%}</p>
                        <p><strong>Sharpe Ratio:</strong> {sharpe_ratio:.2f}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Technical Indicators (Detailed Analysis)
                if analysis_type == "Detailed Analysis":
                    st.markdown("#### 📊 Technical Indicators")
                    
                    # Create tabs for different indicator categories
                    tab1, tab2, tab3, tab4 = st.tabs(["📈 Price & Trend", "📊 Momentum", "📐 Volatility", "📈 Volume"])
                    
                    with tab1:
                        # Price and Moving Averages
                        latest_data = technical_data.iloc[-1]
                        
                        ma_col1, ma_col2 = st.columns(2)
                        with ma_col1:
                            sma20 = latest_data.get('SMA_20', 0)
                            sma50 = latest_data.get('SMA_50', 0)
                            current_price = latest_data['Close']
                            
                            st.metric("20-Day SMA", f"${sma20:.2f}" if sma20 else "N/A",
                                    f"{((current_price/sma20-1)*100):+.1f}%" if sma20 else "")
                            st.metric("50-Day SMA", f"${sma50:.2f}" if sma50 else "N/A",
                                    f"{((current_price/sma50-1)*100):+.1f}%" if sma50 else "")
                        
                        with ma_col2:
                            support = latest_data.get('Support', 0)
                            resistance = latest_data.get('Resistance', 0)
                            st.metric("Support Level", f"${support:.2f}" if support else "N/A")
                            st.metric("Resistance Level", f"${resistance:.2f}" if resistance else "N/A")
                    
                    with tab2:
                        # Momentum Indicators
                        mom_col1, mom_col2 = st.columns(2)
                        with mom_col1:
                            rsi = latest_data.get('RSI', 0)
                            rsi_signal = "Overbought" if rsi > 70 else "Oversold" if rsi < 30 else "Neutral"
                            rsi_color = "negative" if rsi > 70 else "positive" if rsi < 30 else "neutral"
                            
                            st.metric("RSI (14)", f"{rsi:.1f}" if rsi else "N/A", rsi_signal)
                            
                            macd = latest_data.get('MACD', 0)
                            macd_signal = latest_data.get('MACD_Signal', 0)
                            macd_diff = macd - macd_signal if macd and macd_signal else 0
                            st.metric("MACD", f"{macd:.4f}" if macd else "N/A",
                                    f"{macd_diff:+.4f}" if macd_diff else "")
                        
                        with mom_col2:
                            stoch_k = latest_data.get('Stoch_K', 0)
                            stoch_d = latest_data.get('Stoch_D', 0)
                            st.metric("Stochastic %K", f"{stoch_k:.1f}" if stoch_k else "N/A")
                            st.metric("Stochastic %D", f"{stoch_d:.1f}" if stoch_d else "N/A")
                    
                    with tab3:
                        # Volatility Indicators
                        vol_col1, vol_col2 = st.columns(2)
                        with vol_col1:
                            bb_upper = latest_data.get('BB_Upper', 0)
                            bb_lower = latest_data.get('BB_Lower', 0)
                            bb_position = latest_data.get('BB_Position', 0)
                            
                            st.metric("BB Upper", f"${bb_upper:.2f}" if bb_upper else "N/A")
                            st.metric("BB Lower", f"${bb_lower:.2f}" if bb_lower else "N/A")
                        
                        with vol_col2:
                            st.metric("BB Position", f"{bb_position:.1%}" if bb_position else "N/A")
                            
                            atr = latest_data.get('ATR', 0)
                            st.metric("ATR (14)", f"${atr:.2f}" if atr else "N/A")
                    
                    with tab4:
                        # Volume Analysis
                        volume_ratio = latest_data.get('Volume_Ratio', 0)
                        volume_signal = "High" if volume_ratio > 1.5 else "Normal" if volume_ratio > 0.5 else "Low"
                        
                        st.metric("Volume vs Average", f"{volume_ratio:.1f}x" if volume_ratio else "N/A", volume_signal)
                
                # Price Chart
                st.markdown("#### 📈 Price Chart with Technical Indicators")
                
                # Create price chart with indicators
                fig = make_subplots(
                    rows=3, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.03,
                    subplot_titles=('Price & Moving Averages', 'RSI', 'Volume'),
                    row_width=[0.2, 0.1, 0.1]
                )
                
                # Price and moving averages
                fig.add_trace(go.Candlestick(
                    x=technical_data.index,
                    open=technical_data['Open'],
                    high=technical_data['High'],
                    low=technical_data['Low'],
                    close=technical_data['Close'],
                    name="Price"
                ), row=1, col=1)
                
                if 'SMA_20' in technical_data.columns:
                    fig.add_trace(go.Scatter(
                        x=technical_data.index,
                        y=technical_data['SMA_20'],
                        mode='lines',
                        name='SMA 20',
                        line=dict(color='orange', width=1)
                    ), row=1, col=1)
                
                if 'SMA_50' in technical_data.columns:
                    fig.add_trace(go.Scatter(
                        x=technical_data.index,
                        y=technical_data['SMA_50'],
                        mode='lines',
                        name='SMA 50',
                        line=dict(color='blue', width=1)
                    ), row=1, col=1)
                
                # Bollinger Bands
                if 'BB_Upper' in technical_data.columns:
                    fig.add_trace(go.Scatter(
                        x=technical_data.index,
                        y=technical_data['BB_Upper'],
                        mode='lines',
                        name='BB Upper',
                        line=dict(color='gray', width=1, dash='dash'),
                        showlegend=False
                    ), row=1, col=1)
                    
                    fig.add_trace(go.Scatter(
                        x=technical_data.index,
                        y=technical_data['BB_Lower'],
                        mode='lines',
                        name='BB Lower',
                        line=dict(color='gray', width=1, dash='dash'),
                        fill='tonexty',
                        fillcolor='rgba(128,128,128,0.1)',
                        showlegend=False
                    ), row=1, col=1)
                
                # RSI
                if 'RSI' in technical_data.columns:
                    fig.add_trace(go.Scatter(
                        x=technical_data.index,
                        y=technical_data['RSI'],
                        mode='lines',
                        name='RSI',
                        line=dict(color='purple')
                    ), row=2, col=1)
                    
                    # RSI reference lines
                    fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                    fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
                    fig.add_hline(y=50, line_dash="dot", line_color="gray", row=2, col=1)
                
                # Volume
                fig.add_trace(go.Bar(
                    x=technical_data.index,
                    y=technical_data['Volume'],
                    name='Volume',
                    marker_color='rgba(0,100,80,0.8)'
                ), row=3, col=1)
                
                fig.update_layout(
                    title=f"{symbol} Technical Analysis Chart",
                    xaxis_rangeslider_visible=False,
                    height=800,
                    showlegend=True
                )
                
                fig.update_yaxes(title_text="Price ($)", row=1, col=1)
                fig.update_yaxes(title_text="RSI", row=2, col=1, range=[0, 100])
                fig.update_yaxes(title_text="Volume", row=3, col=1)
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Trading Signals
                st.markdown("#### 🚨 Trading Signals")
                signals = trend_analysis.get('signals', [])
                if signals:
                    for signal in signals:
                        if 'Bullish' in signal:
                            st.success(f"🟢 {signal}")
                        elif 'Bearish' in signal:
                            st.error(f"🔴 {signal}")
                        else:
                            st.info(f"🟡 {signal}")
                else:
                    st.info("No specific trading signals at this time.")
                
                # AI Insights
                if ai_insights:
                    st.markdown("#### 🤖 AI-Powered Insights")
                    for insight in ai_insights:
                        st.info(insight)
                
                # News Sentiment
                if news_articles:
                    st.markdown("#### 📰 Recent News & Sentiment")
                    
                    sentiment_col1, sentiment_col2 = st.columns([1, 2])
                    
                    with sentiment_col1:
                        overall_sentiment = news_sentiment.get('overall_sentiment', 'Neutral')
                        sentiment_color = 'positive' if overall_sentiment == 'Positive' else 'negative' if overall_sentiment == 'Negative' else 'neutral'
                        
                        st.markdown(f"""
                        <div class="metric-card">
                            <h4>📊 Sentiment Analysis</h4>
                            <p><strong>Overall:</strong> <span class="{sentiment_color}">{overall_sentiment}</span></p>
                            <p><strong>Positive:</strong> {news_sentiment.get('positive_count', 0)}</p>
                            <p><strong>Negative:</strong> {news_sentiment.get('negative_count', 0)}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with sentiment_col2:
                        st.markdown("**Recent Headlines:**")
                        for article in news_articles[:3]:
                            st.markdown(f"• **{article['title']}** ({article['date']})")
                            st.caption(article['summary'])
                
                # Risk Assessment
                if analysis_type == "Detailed Analysis":
                    st.markdown("#### ⚠️ Risk Assessment")
                    
                    risk_col1, risk_col2, risk_col3 = st.columns(3)
                    
                    with risk_col1:
                        max_drawdown = risk_metrics.get('max_drawdown', 0)
                        var_95 = risk_metrics.get('var_95', 0)
                        st.metric("Max Drawdown", f"{max_drawdown:.1%}")
                        st.metric("VaR (95%)", f"{var_95:.1%}")
                    
                    with risk_col2:
                        calmar_ratio = risk_metrics.get('calmar_ratio', 0)
                        sortino_ratio = risk_metrics.get('sortino_ratio', 0)
                        st.metric("Calmar Ratio", f"{calmar_ratio:.2f}")
                        st.metric("Sortino Ratio", f"{sortino_ratio:.2f}")
                    
                    with risk_col3:
                        annual_return = risk_metrics.get('annualized_return', 0)
                        st.metric("Annual Return", f"{annual_return:.1%}")
                        st.metric("Risk-Adj. Return", f"{sharpe_ratio:.2f}")
                
            except Exception as e:
                st.error(f"Error analyzing {symbol}: {str(e)}")
                st.exception(e)
        else:
            st.info("👆 Enter a stock symbol and click 'Analyze Stock' to start the technical analysis.")


if __name__ == "__main__":
    main()