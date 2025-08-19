"""
Comprehensive Portfolio Optimization Dashboard
A multi-page Streamlit dashboard for visualizing portfolio optimization results
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import boto3
import json
from datetime import datetime, timedelta
import io
from typing import Dict, List, Optional, Tuple
from technical_analysis import (
    StockDataFetcher, TechnicalAnalyzer, get_news_sentiment,
    generate_ai_insights, calculate_risk_metrics
)

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
    .warning-card h4 {
        color: #2d2d2d !important;
    }
    .warning-card p {
        color: #2d2d2d !important;
    }
    .warning-card ul {
        color: #2d2d2d !important;
    }
    .warning-card li {
        color: #2d2d2d !important;
    }
    .warning-card strong {
        color: #2d2d2d !important;
    }
    .warning-card em {
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
    .success-card h4 {
        color: #2d2d2d !important;
    }
    .success-card p {
        color: #2d2d2d !important;
    }
    .success-card ul {
        color: #2d2d2d !important;
    }
    .success-card li {
        color: #2d2d2d !important;
    }
    .success-card strong {
        color: #2d2d2d !important;
    }
    .success-card em {
        color: #2d2d2d !important;
    }
</style>
""", unsafe_allow_html=True)

class S3DataLoader:
    """Handle S3 data loading and caching"""
    
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
        self.s3_client = boto3.client('s3', region_name='us-west-1')  # Specify region
        
    @st.cache_data(ttl=300)  # Cache for 5 minutes
    def load_csv(_self, key: str) -> Optional[pd.DataFrame]:
        """Load CSV file from S3 with caching"""
        try:
            response = _self.s3_client.get_object(Bucket=_self.bucket_name, Key=key)
            csv_string = response['Body'].read().decode('utf-8')
            df = pd.read_csv(io.StringIO(csv_string))
            return df
        except Exception as e:
            st.error(f"Error loading {key}: {str(e)}")
            return None
    
    @st.cache_data(ttl=300)  # Cache for 5 minutes
    def load_json(_self, key: str) -> Optional[Dict]:
        """Load JSON file from S3 with caching"""
        try:
            response = _self.s3_client.get_object(Bucket=_self.bucket_name, Key=key)
            json_string = response['Body'].read().decode('utf-8')
            data = json.loads(json_string)
            return data
        except Exception as e:
            st.error(f"Error loading {key}: {str(e)}")
            return None
    
    def list_files(self, prefix: str) -> List[str]:
        """List files in S3 with given prefix"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            return [obj['Key'] for obj in response.get('Contents', [])]
        except Exception as e:
            st.error(f"Error listing files: {str(e)}")
            return []

def calculate_benchmark_metrics(portfolio_data: Dict, nasdaq_data: pd.DataFrame) -> Dict:
    """Calculate benchmark comparison metrics"""
    try:
        data_loader = st.session_state.data_loader
        
        # Calculate NASDAQ-100 index performance using market cap weighting
        nasdaq_symbols = nasdaq_data['Symbol'].tolist()
        
        # Load individual stock data to calculate index performance
        stock_files = data_loader.list_files("data/stocks/")
        index_returns = []
        portfolio_returns = {}
        
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
    if 'bucket_name' not in st.session_state:
        st.session_state.bucket_name = "portfolio-optimization-jwj"
    if 'data_loader' not in st.session_state:
        st.session_state.data_loader = S3DataLoader(st.session_state.bucket_name)

def load_latest_data():
    """Load the latest data from all phases"""
    data_loader = st.session_state.data_loader
    
    # Load latest processed data
    nasdaq_data = data_loader.load_csv("processed/nasdaq_100_analysis.csv")
    stock_data = data_loader.load_csv("processed/nasdaq_100_with_returns.csv")
    
    # Load portfolio optimization results from results/final/
    final_files = data_loader.list_files("results/final/")
    portfolio_data = {}
    comparison_data = []
    
    if final_files:
        # Define portfolio patterns to match your S3 structure
        portfolio_patterns = {
            'mv_historical_max_sharpe_significant': 'Mean-Variance Historical (Max Sharpe)',
            'mv_historical_min_vol_significant': 'Mean-Variance Historical (Min Vol)',
            'mv_undervalue_max_sharpe_significant': 'Mean-Variance Undervalue (Max Sharpe)',
            'mv_undervalue_min_vol_significant': 'Mean-Variance Undervalue (Min Vol)',
            'rp_historical_significant': 'Risk Parity Historical',
            'rp_undervalue_significant': 'Risk Parity Undervalue'
        }
        
        for pattern, display_name in portfolio_patterns.items():
            matching_files = [f for f in final_files if pattern in f and f.endswith('.csv')]
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
    
    # Find latest summaries
    phase1_files = data_loader.list_files("results/phase1/")
    phase2_files = data_loader.list_files("results/phase2/")
    
    phase1_summary = None
    phase2_summary = None
    
    if phase1_files:
        latest_phase1 = sorted(phase1_files)[-1]
        phase1_summary = data_loader.load_json(latest_phase1)
    
    if phase2_files:
        latest_phase2 = sorted(phase2_files)[-1]
        phase2_summary = data_loader.load_json(latest_phase2)
    
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
        'benchmark_metrics': benchmark_metrics
    }

def check_aws_service_health() -> Dict[str, Dict[str, str]]:
    """Check the health of AWS services"""
    services = {
        'lambda': {'status': 'Unknown', 'detail': 'Checking...'},
        's3': {'status': 'Unknown', 'detail': 'Checking...'},
        'step_functions': {'status': 'Unknown', 'detail': 'Checking...'},
        'eventbridge': {'status': 'Unknown', 'detail': 'Checking...'}
    }
    
    try:
        # Check Lambda functions
        lambda_client = boto3.client('lambda', region_name='us-west-1')
        function_names = ['nasdaq-analyzer-docker', 'stock-data-fetcher-docker', 'portfolio-optimizer-docker']
        healthy_functions = 0
        
        for func_name in function_names:
            try:
                response = lambda_client.get_function(FunctionName=func_name)
                if response['Configuration']['State'] == 'Active':
                    healthy_functions += 1
            except:
                pass
        
        if healthy_functions == 3:
            services['lambda'] = {'status': 'Healthy', 'detail': '3/3 functions active'}
        elif healthy_functions > 0:
            services['lambda'] = {'status': 'Partial', 'detail': f'{healthy_functions}/3 functions active'}
        else:
            services['lambda'] = {'status': 'Error', 'detail': 'Functions not found'}
            
    except Exception as e:
        services['lambda'] = {'status': 'Error', 'detail': 'Access denied'}
    
    try:
        # Check S3 bucket
        s3_client = boto3.client('s3', region_name='us-west-1')
        s3_client.head_bucket(Bucket=st.session_state.bucket_name)
        services['s3'] = {'status': 'Healthy', 'detail': 'Bucket accessible'}
    except Exception as e:
        services['s3'] = {'status': 'Error', 'detail': 'Bucket not accessible'}
    
    try:
        # Check Step Functions
        stepfunctions_client = boto3.client('stepfunctions', region_name='us-west-1')
        response = stepfunctions_client.describe_state_machine(
            stateMachineArn='arn:aws:states:us-west-1:901398601400:stateMachine:portfolio-optimization-pipeline'
        )
        if response['status'] == 'ACTIVE':
            services['step_functions'] = {'status': 'Healthy', 'detail': 'Pipeline ready'}
        else:
            services['step_functions'] = {'status': 'Error', 'detail': 'Pipeline inactive'}
    except Exception as e:
        services['step_functions'] = {'status': 'Error', 'detail': 'Pipeline not found'}
    
    try:
        # Check EventBridge Scheduler - try both old rules and new scheduler
        schedule_found = False
        
        # First try EventBridge Scheduler (newer service)
        try:
            scheduler_client = boto3.client('scheduler', region_name='us-west-1')
            response = scheduler_client.list_schedules()
            schedules = response.get('Schedules', [])
            
            # Look for portfolio-related schedules
            portfolio_schedules = [s for s in schedules if 'portfolio' in s['Name'].lower()]
            
            if portfolio_schedules:
                schedule = portfolio_schedules[0]  # Take the first one found
                schedule_name = schedule['Name']
                
                # Get detailed schedule information
                try:
                    schedule_details = scheduler_client.get_schedule(Name=schedule_name)
                    
                    # Parse schedule expression to get next run time
                    schedule_expr = schedule_details.get('ScheduleExpression', '')
                    
                    if schedule['State'] == 'ENABLED':
                        # Calculate next run time
                        next_run = "Not available"
                        
                        try:
                            # Get next run time from schedule expression
                            if 'cron(' in schedule_expr or 'rate(' in schedule_expr:
                                # For monthly cron like "cron(0 9 1 * ? *)" (1st of month at 9 AM)
                                if 'cron(0 9 1 * ? *)' in schedule_expr:
                                    from datetime import datetime, timedelta
                                    import calendar
                                    
                                    now = datetime.now()
                                    # Next run is 1st of next month at 9 AM
                                    if now.day == 1 and now.hour < 9:
                                        next_month = now.replace(day=1, hour=9, minute=0, second=0, microsecond=0)
                                    else:
                                        # Get first day of next month
                                        if now.month == 12:
                                            next_month = now.replace(year=now.year + 1, month=1, day=1, hour=9, minute=0, second=0, microsecond=0)
                                        else:
                                            next_month = now.replace(month=now.month + 1, day=1, hour=9, minute=0, second=0, microsecond=0)
                                    
                                    next_run = next_month.strftime('%Y-%m-%d %H:%M UTC')
                        except Exception:
                            pass
                        
                        services['eventbridge'] = {'status': 'Healthy', 'detail': f'Next: {next_run}'}
                    else:
                        services['eventbridge'] = {'status': 'Partial', 'detail': 'Schedule disabled'}
                        
                except Exception:
                    # Fallback if we can't get detailed schedule info
                    if schedule['State'] == 'ENABLED':
                        services['eventbridge'] = {'status': 'Healthy', 'detail': f'Scheduler: {schedule_name}'}
                    else:
                        services['eventbridge'] = {'status': 'Partial', 'detail': 'Schedule disabled'}
                
                schedule_found = True
        except Exception as e:
            # Scheduler API might not be available, continue to check old EventBridge rules
            pass
        
        # Fallback to old EventBridge rules if no scheduler found
        if not schedule_found:
            try:
                events_client = boto3.client('events', region_name='us-west-1')
                rule_names = ['portfolio-monthly-trigger', 'portfolio-daily-trigger', 'portfolio-optimization-trigger']
                
                for rule_name in rule_names:
                    try:
                        response = events_client.describe_rule(Name=rule_name)
                        schedule_found = True
                        if response['State'] == 'ENABLED':
                            services['eventbridge'] = {'status': 'Healthy', 'detail': f'Rule: {rule_name}'}
                        else:
                            services['eventbridge'] = {'status': 'Partial', 'detail': 'Rule disabled'}
                        break
                    except:
                        continue
            except:
                pass
        
        if not schedule_found:
            services['eventbridge'] = {'status': 'Error', 'detail': 'No schedule or rule found'}
    except Exception as e:
        services['eventbridge'] = {'status': 'Error', 'detail': 'Access denied'}
    
    return services

def get_data_age(data_loader, prefix: str) -> str:
    """Get the age of the most recent data in the specified S3 prefix"""
    try:
        # Get S3 client
        s3_client = boto3.client('s3', region_name='us-west-1')
        
        # List objects in the prefix
        response = s3_client.list_objects_v2(
            Bucket=st.session_state.bucket_name,
            Prefix=prefix,
            MaxKeys=100
        )
        
        if 'Contents' not in response:
            return "No data found"
        
        # Find the most recent file
        latest_file = max(response['Contents'], key=lambda x: x['LastModified'])
        last_modified = latest_file['LastModified']
        
        # Calculate time difference
        now = datetime.now(last_modified.tzinfo)  # Make timezone aware
        time_diff = now - last_modified
        
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
            models_count = len(data['portfolio_data'].get('optimization_results', {}))
            st.success(f"🎯 {models_count} Portfolio Models")
    
    with col4:
        if data['stock_data'] is not None:
            stocks_with_returns = len(data['stock_data'][data['stock_data']['Annual_Return_5Y'].notna()])
            st.success(f"📊 {stocks_with_returns} Historical Records")
    
    # Portfolio Performance Summary
    if data['portfolio_data']:
        st.subheader("🏆 Portfolio Performance Summary")
        
        results = data['portfolio_data'].get('optimization_results', {})
        
        # Create metrics for each model
        model_mapping = {
            'mean_variance': 'Mean-Variance',
            'risk_parity': 'Risk Parity', 
            'black_litterman': 'Black-Litterman'
        }
        
        cols = st.columns(len(model_mapping))
        
        for i, (model_key, model_name) in enumerate(model_mapping.items()):
            if model_key in results:
                model_data = results[model_key]
                expected_return = model_data.get('portfolio_metrics', {}).get('expected_annual_return', 0)
                volatility = model_data.get('portfolio_metrics', {}).get('portfolio_volatility', 0)
                sharpe_ratio = model_data.get('portfolio_metrics', {}).get('sharpe_ratio', 0)
                
                with cols[i]:
                    st.markdown(f"""
                    <div class="metric-card">
                        <h4>{model_name}</h4>
                        <p><strong>Expected Return:</strong> <span class="positive">{expected_return:.2%}</span></p>
                        <p><strong>Volatility:</strong> <span class="neutral">{volatility:.2%}</span></p>
                        <p><strong>Sharpe Ratio:</strong> <span class="{'positive' if sharpe_ratio > 1 else 'neutral'}">{sharpe_ratio:.2f}</span></p>
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
            best_sharpe = max(benchmark_data['portfolio_comparisons'], key=lambda x: x['Sharpe_Ratio'])
            
            col1, col2 = st.columns(2)
            with col1:
                alpha_color = "positive" if best_alpha['Alpha'] > 0 else "negative"
                st.markdown(f"""
                <div class="metric-card">
                    <h4>🏆 Best Alpha (Excess Return)</h4>
                    <p><strong>Model:</strong> {best_alpha['Model']}</p>
                    <p><strong>Alpha:</strong> <span class="{alpha_color}">{best_alpha['Alpha']:.2%}</span></p>
                    <p><small>{'Outperforming' if best_alpha['Alpha'] > 0 else 'Underperforming'} NASDAQ-100</small></p>
                    <p><small><strong>What is Alpha?</strong> The extra return above the market. Positive = beating NASDAQ-100!</small></p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="metric-card">
                    <h4>⚡ Best Risk-Adjusted Return</h4>
                    <p><strong>Model:</strong> {best_sharpe['Model']}</p>
                    <p><strong>Sharpe Ratio:</strong> <span class="positive">{best_sharpe['Sharpe_Ratio']:.2f}</span></p>
                    <p><strong>vs Benchmark:</strong> <span class="positive">{best_sharpe['Sharpe_Ratio'] - benchmark_data['benchmark_sharpe']:.2f}</span> higher</p>
                    <p><small><strong>What is Sharpe Ratio?</strong> Return per unit of risk. Higher = better reward for the risk taken!</small></p>
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
    
    # Portfolio Allocation Comparison
    if data['portfolio_data']:
        st.subheader("🥧 Portfolio Allocation Comparison")
        
        results = data['portfolio_data'].get('optimization_results', {})
        
        if len(results) >= 2:
            # Create subplots for pie charts
            fig = make_subplots(
                rows=1, cols=len(results),
                specs=[[{"type": "domain"}] * len(results)],
                subplot_titles=list(model_mapping.get(k, k.replace('_', ' ').title()) for k in results.keys())
            )
            
            col_idx = 1
            for model_key, model_data in results.items():
                weights = model_data.get('portfolio_weights', {})
                if weights:
                    # Get top 8 holdings
                    sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:8]
                    symbols = [item[0] for item in sorted_weights]
                    values = [item[1] for item in sorted_weights]
                    
                    # Add "Others" if there are more holdings
                    remaining_weight = sum(weights.values()) - sum(values)
                    if remaining_weight > 0.01:  # If more than 1%
                        symbols.append('Others')
                        values.append(remaining_weight)
                    
                    fig.add_trace(go.Pie(
                        labels=symbols,
                        values=values,
                        name=model_mapping.get(model_key, model_key)
                    ), row=1, col=col_idx)
                
                col_idx += 1
            
            fig.update_traces(textposition='inside', textinfo='percent+label')
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
    
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
    
    if data['portfolio_data']:
        activity_data.append({
            'Phase': 'Phase 3 - Portfolio Optimization',
            'Status': '✅ Completed',
            'Timestamp': data['portfolio_data'].get('timestamp', 'Unknown'),
            'Details': f"{len(data['portfolio_data'].get('optimization_results', {}))} models completed"
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
        st.error("No NASDAQ-100 analysis data available. Please run the pipeline first.")
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
            st.info("Historical return data not available. Run Phase 2 of the pipeline to see risk-return analysis.")
    
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
    
    # Page guidance
    st.markdown("""
    <div class="success-card">
        <h4>🎯 What can I optimize on this page?</h4>
        <ul>
            <li><strong>Compare Strategies:</strong> See how Mean-Variance, Risk Parity, and Black-Litterman perform</li>
            <li><strong>Analyze Allocations:</strong> Understand where each model suggests putting your money</li>
            <li><strong>Risk Assessment:</strong> Compare risk-return profiles across different approaches</li>
            <li><strong>Implementation Ready:</strong> Get exact portfolio weights for your chosen strategy</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    if data['portfolio_data'] is None:
        st.error("No portfolio optimization data available. Please run Phase 3 of the pipeline first.")
        return
    
    results = data['portfolio_data'].get('optimization_results', {})
    
    if not results:
        st.warning("Portfolio optimization results are empty. Please check the pipeline execution.")
        return
    
    # Model Performance Comparison
    st.subheader("📊 Model Performance Comparison")
    
    # Create comparison metrics
    comparison_data = []
    model_mapping = {
        'mean_variance': 'Mean-Variance',
        'risk_parity': 'Risk Parity', 
        'black_litterman': 'Black-Litterman'
    }
    
    for model_key, model_name in model_mapping.items():
        if model_key in results:
            metrics = results[model_key].get('portfolio_metrics', {})
            comparison_data.append({
                'Model': model_name,
                'Expected Return': metrics.get('expected_annual_return', 0),
                'Volatility': metrics.get('portfolio_volatility', 0),
                'Sharpe Ratio': metrics.get('sharpe_ratio', 0)
            })
    
    if comparison_data:
        comparison_df = pd.DataFrame(comparison_data)
        
        # Metrics cards
        col1, col2, col3 = st.columns(3)
        
        with col1:
            best_return = comparison_df.loc[comparison_df['Expected Return'].idxmax()]
            st.metric(
                "🚀 Highest Expected Return",
                f"{best_return['Expected Return']:.2%}",
                f"{best_return['Model']}"
            )
        
        with col2:
            best_sharpe = comparison_df.loc[comparison_df['Sharpe Ratio'].idxmax()]
            st.metric(
                "⚡ Best Risk-Adjusted Return",
                f"{best_sharpe['Sharpe Ratio']:.2f}",
                f"{best_sharpe['Model']}"
            )
        
        with col3:
            lowest_vol = comparison_df.loc[comparison_df['Volatility'].idxmin()]
            st.metric(
                "🛡️ Lowest Risk",
                f"{lowest_vol['Volatility']:.2%}",
                f"{lowest_vol['Model']}"
            )
        
        # Risk-Return Scatter Plot
        st.subheader("📈 Risk vs Return Comparison")
        
        fig = go.Figure()
        
        colors = {'Mean-Variance': '#1f77b4', 'Risk Parity': '#ff7f0e', 'Black-Litterman': '#2ca02c'}
        
        for _, row in comparison_df.iterrows():
            fig.add_trace(go.Scatter(
                x=[row['Volatility']],
                y=[row['Expected Return']],
                mode='markers+text',
                text=[row['Model']],
                textposition="top center",
                marker=dict(
                    size=row['Sharpe Ratio'] * 20 + 10,
                    color=colors.get(row['Model'], '#1f77b4'),
                    opacity=0.7
                ),
                name=row['Model'],
                hovertemplate=f"<b>{row['Model']}</b><br>" +
                              f"Return: {row['Expected Return']:.2%}<br>" +
                              f"Volatility: {row['Volatility']:.2%}<br>" +
                              f"Sharpe Ratio: {row['Sharpe Ratio']:.2f}<extra></extra>"
            ))
        
        fig.update_layout(
            title="Portfolio Models: Risk vs Return (Bubble size = Sharpe Ratio)",
            xaxis_title="Volatility (Risk)",
            yaxis_title="Expected Return",
            height=500,
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Portfolio Allocations
    st.subheader("🥧 Portfolio Allocations by Model")
    
    # Model selector
    available_models = [model_mapping.get(k, k) for k in results.keys() if k in model_mapping]
    
    if available_models:
        selected_model_display = st.selectbox(
            "Choose model to analyze:",
            available_models,
            help="Select which optimization model's portfolio allocation you want to examine in detail"
        )
        
        # Get the actual model key
        selected_model_key = None
        for k, v in model_mapping.items():
            if v == selected_model_display:
                selected_model_key = k
                break
        
        if selected_model_key and selected_model_key in results:
            model_result = results[selected_model_key]
            weights = model_result.get('portfolio_weights', {})
            
            if weights:
                # Convert to DataFrame for easier handling
                weights_df = pd.DataFrame(list(weights.items()), columns=['Symbol', 'Weight'])
                weights_df = weights_df.sort_values('Weight', ascending=False)
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    # Portfolio allocation pie chart
                    top_10 = weights_df.head(10)
                    other_weight = weights_df['Weight'].sum() - top_10['Weight'].sum()
                    
                    if other_weight > 0.01:  # If more than 1%
                        pie_data = pd.concat([
                            top_10,
                            pd.DataFrame({'Symbol': ['Others'], 'Weight': [other_weight]})
                        ])
                    else:
                        pie_data = top_10
                    
                    fig_pie = px.pie(
                        pie_data,
                        values='Weight',
                        names='Symbol',
                        title=f"{selected_model_display} Portfolio Allocation"
                    )
                    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                    fig_pie.update_layout(height=500)
                    st.plotly_chart(fig_pie, use_container_width=True)
                
                with col2:
                    st.markdown("### Portfolio Statistics")
                    
                    metrics = model_result.get('portfolio_metrics', {})
                    
                    st.metric("Expected Annual Return", f"{metrics.get('expected_annual_return', 0):.2%}")
                    st.metric("Portfolio Volatility", f"{metrics.get('portfolio_volatility', 0):.2%}")
                    st.metric("Sharpe Ratio", f"{metrics.get('sharpe_ratio', 0):.2f}")
                    
                    num_holdings = len([w for w in weights.values() if w > 0.001])
                    st.metric("Number of Holdings", f"{num_holdings}")
                    
                    max_weight = max(weights.values()) if weights else 0
                    st.metric("Largest Position", f"{max_weight:.1%}")
                
                # Top Holdings Table
                st.subheader(f"📋 Top Holdings - {selected_model_display}")
                
                # Show top 20 holdings
                top_20_holdings = weights_df.head(20).copy()
                top_20_holdings['Weight'] = top_20_holdings['Weight'].apply(lambda x: f"{x:.2%}")
                
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.dataframe(top_20_holdings, use_container_width=True, height=400)
                
                with col2:
                    # Download portfolio
                    csv_data = weights_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Full Portfolio",
                        data=csv_data,
                        file_name=f"{selected_model_display.lower().replace('-', '_')}_portfolio_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
                    

def render_historical_tracking(data):
    """Render the Historical Tracking page"""
    st.markdown('<h1 class="main-header">📈 Historical Tracking</h1>', unsafe_allow_html=True)
    
    # Page guidance
    st.markdown("""
    <div class="success-card">
        <h4>📈 What trends can I track on this page?</h4>
        <ul>
            <li><strong>Performance Over Time:</strong> See how your portfolio recommendations have changed</li>
            <li><strong>Model Consistency:</strong> Track which models perform consistently well</li>
            <li><strong>Market Timing:</strong> Understand how market conditions affect your strategy</li>
            <li><strong>Rebalancing Insights:</strong> Identify when portfolio changes are most significant</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    data_loader = st.session_state.data_loader
    
    # Load historical data from all phases
    st.subheader("📊 Pipeline Execution History")
    
    # Get historical files
    phase1_files = data_loader.list_files("results/phase1/")
    phase2_files = data_loader.list_files("results/phase2/")
    phase3_files = data_loader.list_files("results/phase3/")
    
    if not any([phase1_files, phase2_files, phase3_files]):
        st.warning("No historical data found. Run the pipeline multiple times to see trends.")
        return
    
    # Create timeline of executions
    execution_history = []
    
    # Parse timestamps from filenames
    for file in phase1_files:
        if 'nasdaq_analysis_summary_' in file:
            timestamp = file.split('_')[-1].replace('.json', '')
            try:
                dt = datetime.strptime(timestamp, '%Y%m%d_%H%M%S')
                execution_history.append({
                    'Date': dt,
                    'Phase': 'NASDAQ-100 Analysis',
                    'File': file
                })
            except:
                pass
    
    for file in phase2_files:
        if 'stock_metrics_summary_' in file:
            timestamp = file.split('_')[-1].replace('.json', '')
            try:
                dt = datetime.strptime(timestamp, '%Y%m%d_%H%M%S')
                execution_history.append({
                    'Date': dt,
                    'Phase': 'Historical Data',
                    'File': file
                })
            except:
                pass
    
    for file in phase3_files:
        if 'portfolio_optimization_' in file:
            timestamp = file.split('_')[-1].replace('.json', '')
            try:
                dt = datetime.strptime(timestamp, '%Y%m%d_%H%M%S')
                execution_history.append({
                    'Date': dt,
                    'Phase': 'Portfolio Optimization',
                    'File': file
                })
            except:
                pass
    
    if execution_history:
        history_df = pd.DataFrame(execution_history)
        history_df = history_df.sort_values('Date', ascending=False)
        
        # Display recent executions
        st.markdown("### Recent Pipeline Executions")
        
        display_history = history_df.copy()
        display_history['Date'] = display_history['Date'].dt.strftime('%Y-%m-%d %H:%M:%S')
        display_history = display_history[['Date', 'Phase']].head(20)
        
        st.dataframe(display_history, use_container_width=True)
        
        # Execution frequency chart
        if len(history_df) > 1:
            st.subheader("📅 Execution Frequency")
            
            daily_counts = history_df.groupby([history_df['Date'].dt.date, 'Phase']).size().reset_index(name='Count')
            daily_counts['Date'] = pd.to_datetime(daily_counts['Date'])
            
            fig = px.bar(
                daily_counts,
                x='Date',
                y='Count',
                color='Phase',
                title="Pipeline Executions Over Time",
                labels={'Count': 'Number of Executions', 'Date': 'Date'}
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
    
    # Historical Performance Comparison (if multiple portfolio results exist)
    if len(phase3_files) > 1:
        st.subheader("📊 Historical Model Performance")
        
        st.info("💡 **Coming Soon:** Track how model performance changes over time as market conditions evolve.")
        
        # Load recent portfolio results for comparison
        recent_files = sorted(phase3_files)[-5:]  # Last 5 results
        
        historical_performance = []
        
        for file in recent_files:
            portfolio_data = data_loader.load_json(file)
            if portfolio_data and 'optimization_results' in portfolio_data:
                timestamp = file.split('_')[-1].replace('.json', '')
                try:
                    dt = datetime.strptime(timestamp, '%Y%m%d_%H%M%S')
                    
                    for model_key, model_result in portfolio_data['optimization_results'].items():
                        metrics = model_result.get('portfolio_metrics', {})
                        historical_performance.append({
                            'Date': dt,
                            'Model': model_key.replace('_', ' ').title(),
                            'Expected Return': metrics.get('expected_annual_return', 0),
                            'Volatility': metrics.get('portfolio_volatility', 0),
                            'Sharpe Ratio': metrics.get('sharpe_ratio', 0)
                        })
                except:
                    pass
        
        if historical_performance:
            perf_df = pd.DataFrame(historical_performance)
            
            # Performance trends
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=('Expected Return Over Time', 'Volatility Over Time', 'Sharpe Ratio Over Time', 'Model Comparison'),
                specs=[[{"secondary_y": False}, {"secondary_y": False}],
                       [{"secondary_y": False}, {"secondary_y": False}]]
            )
            
            colors = {'Mean Variance': '#1f77b4', 'Risk Parity': '#ff7f0e', 'Black Litterman': '#2ca02c'}
            
            for model in perf_df['Model'].unique():
                model_data = perf_df[perf_df['Model'] == model]
                
                fig.add_trace(
                    go.Scatter(x=model_data['Date'], y=model_data['Expected Return'], 
                              mode='lines+markers', name=f'{model} Return',
                              line=dict(color=colors.get(model, '#1f77b4'))),
                    row=1, col=1
                )
                
                fig.add_trace(
                    go.Scatter(x=model_data['Date'], y=model_data['Volatility'], 
                              mode='lines+markers', name=f'{model} Vol',
                              line=dict(color=colors.get(model, '#1f77b4')), showlegend=False),
                    row=1, col=2
                )
                
                fig.add_trace(
                    go.Scatter(x=model_data['Date'], y=model_data['Sharpe Ratio'], 
                              mode='lines+markers', name=f'{model} Sharpe',
                              line=dict(color=colors.get(model, '#1f77b4')), showlegend=False),
                    row=2, col=1
                )
            
            fig.update_layout(height=600, title_text="Historical Model Performance Trends")
            st.plotly_chart(fig, use_container_width=True)

def render_system_status(data):
    """Render the System Status page"""
    st.markdown('<h1 class="main-header">⚙️ System Status</h1>', unsafe_allow_html=True)
    
    # Page guidance
    st.markdown("""
    <div class="success-card">
        <h4>⚙️ What can I monitor on this page?</h4>
        <ul>
            <li><strong>Pipeline Health:</strong> Check if all components are working properly</li>
            <li><strong>Data Freshness:</strong> See when data was last updated and if it's current</li>
            <li><strong>Error Monitoring:</strong> Identify any issues that need attention</li>
            <li><strong>Automated Schedule:</strong> Pipeline runs automatically on the 1st of each month</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    data_loader = st.session_state.data_loader
    
    # System Health Overview
    st.subheader("🔋 System Health Overview")
    
    # Check data availability
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if data['nasdaq_data'] is not None:
            st.success("✅ Phase 1: NASDAQ-100 Analysis")
            nasdaq_count = len(data['nasdaq_data'])
            st.metric("Stocks Analyzed", nasdaq_count)
        else:
            st.error("❌ Phase 1: No NASDAQ Data")
    
    with col2:
        if data['stock_data'] is not None:
            st.success("✅ Phase 2: Historical Data")
            stock_count = len(data['stock_data'][data['stock_data']['Annual_Return_5Y'].notna()])
            st.metric("Historical Records", stock_count)
        else:
            st.error("❌ Phase 2: No Historical Data")
    
    with col3:
        if data['portfolio_data'] is not None:
            st.success("✅ Phase 3: Portfolio Optimization")
            model_count = len(data['portfolio_data'].get('optimization_results', {}))
            st.metric("Optimization Models", model_count)
        else:
            st.error("❌ Phase 3: No Portfolio Data")
    
    # Data Freshness
    st.subheader("📅 Data Freshness")
    
    freshness_data = []
    
    if data['phase1_summary']:
        timestamp = data['phase1_summary'].get('timestamp', 'Unknown')
        try:
            dt = datetime.strptime(timestamp, '%Y%m%d_%H%M%S')
            age = datetime.now() - dt
            freshness_data.append({
                'Component': 'NASDAQ-100 Analysis',
                'Last Updated': dt.strftime('%Y-%m-%d %H:%M:%S'),
                'Age (Hours)': round(age.total_seconds() / 3600, 1),
                'Status': 'Fresh' if age.days < 7 else 'Stale'
            })
        except:
            freshness_data.append({
                'Component': 'NASDAQ-100 Analysis',
                'Last Updated': timestamp,
                'Age (Hours)': 'Unknown',
                'Status': 'Unknown'
            })
    
    if data['phase2_summary']:
        timestamp = data['phase2_summary'].get('timestamp', 'Unknown')
        try:
            dt = datetime.strptime(timestamp, '%Y%m%d_%H%M%S')
            age = datetime.now() - dt
            freshness_data.append({
                'Component': 'Historical Data',
                'Last Updated': dt.strftime('%Y-%m-%d %H:%M:%S'),
                'Age (Hours)': round(age.total_seconds() / 3600, 1),
                'Status': 'Fresh' if age.days < 7 else 'Stale'
            })
        except:
            freshness_data.append({
                'Component': 'Historical Data',
                'Last Updated': timestamp,
                'Age (Hours)': 'Unknown',
                'Status': 'Unknown'
            })
    
    if data['portfolio_data']:
        timestamp = data['portfolio_data'].get('timestamp', 'Unknown')
        try:
            dt = datetime.strptime(timestamp, '%Y%m%d_%H%M%S')
            age = datetime.now() - dt
            freshness_data.append({
                'Component': 'Portfolio Optimization',
                'Last Updated': dt.strftime('%Y-%m-%d %H:%M:%S'),
                'Age (Hours)': round(age.total_seconds() / 3600, 1),
                'Status': 'Fresh' if age.days < 7 else 'Stale'
            })
        except:
            freshness_data.append({
                'Component': 'Portfolio Optimization',
                'Last Updated': timestamp,
                'Age (Hours)': 'Unknown',
                'Status': 'Unknown'
            })
    
    if freshness_data:
        freshness_df = pd.DataFrame(freshness_data)
        st.dataframe(freshness_df, use_container_width=True)
    
    # S3 Storage Overview
    st.subheader("💾 S3 Storage Overview")
    
    # Get file counts
    raw_files = data_loader.list_files("raw/")
    processed_files = data_loader.list_files("processed/")
    results_files = data_loader.list_files("results/")
    stocks_files = data_loader.list_files("data/stocks/")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Raw Data Files", len(raw_files))
    
    with col2:
        st.metric("Processed Files", len(processed_files))
    
    with col3:
        st.metric("Result Files", len(results_files))
    
    with col4:
        st.metric("Individual Stock Files", len(stocks_files))
    
    # Pipeline Status (Read-Only)

def render_portfolio_optimization(data: Dict[str, pd.DataFrame]):
    """Render the Portfolio Optimization page"""
    st.markdown('<h1 class="main-header">🎯 Portfolio Optimization</h1>', unsafe_allow_html=True)
    
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


def render_historical_tracking(data: Dict[str, pd.DataFrame]):
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
    
    # Real Step Functions execution history
    st.subheader("🔄 Pipeline Execution History")
    st.caption("Track pipeline reliability and performance over time. Data from AWS Step Functions.")
    
    try:
        # Get real Step Functions execution history
        stepfunctions_client = boto3.client('stepfunctions', region_name='us-west-1')
        
        executions_response = stepfunctions_client.list_executions(
            stateMachineArn='arn:aws:states:us-west-1:901398601400:stateMachine:portfolio-optimization-pipeline',
            maxResults=50
        )
        
        execution_data = []
        for execution in executions_response['executions']:
            start_time = execution['startDate']
            end_time = execution.get('stopDate', pd.Timestamp.now())
            duration_minutes = (end_time - start_time).total_seconds() / 60
            
            execution_data.append({
                'Date': start_time,
                'Status': 'Success' if execution['status'] == 'SUCCEEDED' else 'Failed' if execution['status'] == 'FAILED' else 'Running',
                'Duration_Minutes': duration_minutes if execution['status'] in ['SUCCEEDED', 'FAILED'] else None,
                'Execution_Name': execution['name'],
                'Status_Raw': execution['status']
            })
        
        if execution_data:
            execution_history = pd.DataFrame(execution_data)
            
            # Metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                success_rate = (execution_history['Status'] == 'Success').mean()
                st.metric("Success Rate", f"{success_rate:.1%}")
            with col2:
                completed_executions = execution_history[execution_history['Duration_Minutes'].notna()]
                if not completed_executions.empty:
                    avg_duration = completed_executions['Duration_Minutes'].mean()
                    st.metric("Avg Duration", f"{avg_duration:.1f} min")
                else:
                    st.metric("Avg Duration", "N/A")
            with col3:
                last_run = execution_history['Date'].max().strftime('%Y-%m-%d %H:%M')
                st.metric("Last Execution", last_run)
            
            # Execution timeline
            if not execution_history.empty:
                # Only plot completed executions for timeline
                timeline_data = execution_history[execution_history['Duration_Minutes'].notna()].copy()
                
                if not timeline_data.empty:
                    fig_timeline = px.scatter(
                        timeline_data,
                        x='Date',
                        y='Duration_Minutes',
                        color='Status',
                        title="Pipeline Execution Timeline",
                        color_discrete_map={'Success': 'green', 'Failed': 'red', 'Running': 'orange'},
                        hover_data=['Execution_Name']
                    )
                    st.plotly_chart(fig_timeline, use_container_width=True)
                else:
                    st.info("No completed executions to display in timeline yet.")
            
            # Recent executions table
            st.subheader("📋 Recent Executions")
            recent_executions = execution_history.head(10).copy()
            recent_executions['Date'] = recent_executions['Date'].dt.strftime('%Y-%m-%d %H:%M:%S')
            recent_executions['Duration_Minutes'] = recent_executions['Duration_Minutes'].apply(
                lambda x: f"{x:.1f} min" if pd.notna(x) else "In Progress"
            )
            
            st.dataframe(
                recent_executions[['Date', 'Status_Raw', 'Duration_Minutes', 'Execution_Name']].rename(columns={
                    'Status_Raw': 'Status',
                    'Execution_Name': 'Execution ID'
                }),
                use_container_width=True
            )
        else:
            st.info("No pipeline executions found. Try running the pipeline first using the buttons above.")
            
    except Exception as e:
        st.error(f"Could not fetch Step Functions execution history: {e}")
        st.info("**Fallback:** Check AWS Step Functions console for execution history")
        st.text("State Machine: portfolio-optimization-pipeline")
    
    # Model performance over time
    st.subheader("📊 Model Performance Trends")
    st.caption("Historical model performance based on S3 results files over time.")
    
    try:
        # Get historical results from S3 by looking at different timestamps
        s3_client = boto3.client('s3', region_name='us-west-1')
        
        # List all results files to get historical data
        response = s3_client.list_objects_v2(
            Bucket=st.session_state.bucket_name,
            Prefix='results/final/',
            MaxKeys=100
        )
        
        files = [obj['Key'] for obj in response.get('Contents', [])]
        comparison_files = [f for f in files if 'performance_comparison' in f]
        
        if comparison_files:
            # Load multiple comparison files to show trends
            historical_data = []
            for file in sorted(comparison_files)[-10:]:  # Last 10 files
                try:
                    # Extract timestamp from filename
                    timestamp_str = file.split('_')[-2] + '_' + file.split('_')[-1].replace('.csv', '')
                    timestamp = pd.to_datetime(timestamp_str, format='%Y%m%d_%H%M%S')
                    
                    # Load the comparison data
                    response = s3_client.get_object(Bucket=st.session_state.bucket_name, Key=file)
                    csv_string = response['Body'].read().decode('utf-8')
                    df = pd.read_csv(io.StringIO(csv_string))
                    
                    # Add timestamp to each row
                    df['Date'] = timestamp
                    historical_data.append(df)
                    
                except Exception as e:
                    continue
            
            if historical_data:
                # Combine all historical data
                combined_df = pd.concat(historical_data, ignore_index=True)
                
                # Performance trend chart
                fig_trend = px.line(
                    combined_df,
                    x='Date',
                    y='Return',
                    color='Model',
                    title="Model Return Trends Over Time (Real Data)"
                )
                st.plotly_chart(fig_trend, use_container_width=True)
                
                # Show data table
                st.subheader("📋 Historical Performance Data")
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
            
    except Exception as e:
        st.error(f"Could not load historical performance data: {e}")
        st.info("Historical trends will appear as you run the pipeline multiple times over weeks/months.")
    
    # Data freshness
    st.subheader("📅 Data Freshness")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("**Stock Data:** Updated daily from Yahoo Finance")
        st.info("**Portfolio Analysis:** Refreshed monthly via automated pipeline")
    
    with col2:
        # Get real data ages from S3
        stock_data_age = get_data_age(data_loader, "data/stocks/")
        portfolio_age = get_data_age(data_loader, "results/final/")
        
        st.metric("Stock Data Age", stock_data_age)
        st.metric("Portfolio Results Age", portfolio_age)


def render_system_status(data: Dict[str, pd.DataFrame]):
    """Render the System Status page"""
    st.markdown('<h1 class="main-header">⚙️ System Status</h1>', unsafe_allow_html=True)
    
    # Page guidance
    st.markdown("""
    <div class="success-card">
        <h4>⚙️ What You'll Find Here</h4>
        <ul>
            <li><strong>Check System Health:</strong> See if all your AWS services are running (like checking if your engine is working)</li>
            <li><strong>View Data Status:</strong> Check when your stock data was last updated and if it's fresh</li>
            <li><strong>Automated Execution:</strong> Your investment analysis runs automatically each month without any manual intervention</li>
            <li><strong>Settings Panel:</strong> Adjust how many stocks to analyze and other preferences</li>
            <li><strong>View Logs:</strong> See what your system has been doing recently - like mission control for your investment robot</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # System Health Overview
    st.subheader("🏥 System Health")
    
    # Get real AWS service health
    with st.spinner("Checking AWS service health..."):
        health_status = check_aws_service_health()
    
    col1, col2, col3, col4 = st.columns(4)
    
    def get_status_color(status):
        if status == 'Healthy':
            return 'positive'
        elif status == 'Partial':
            return 'negative'  # Orange/warning color
        else:
            return 'negative'
    
    def get_status_icon(status):
        if status == 'Healthy':
            return '● Online'
        elif status == 'Partial':
            return '◐ Partial'
        else:
            return '● Error'
    
    with col1:
        lambda_status = health_status['lambda']
        st.markdown(f"""
        <div class="metric-card">
            <h4>Lambda Functions</h4>
            <div class="{get_status_color(lambda_status['status'])}">{get_status_icon(lambda_status['status'])}</div>
            <small>{lambda_status['detail']}</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        s3_status = health_status['s3']
        st.markdown(f"""
        <div class="metric-card">
            <h4>S3 Storage</h4>
            <div class="{get_status_color(s3_status['status'])}">{get_status_icon(s3_status['status'])}</div>
            <small>{s3_status['detail']}</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        sf_status = health_status['step_functions']
        st.markdown(f"""
        <div class="metric-card">
            <h4>Step Functions</h4>
            <div class="{get_status_color(sf_status['status'])}">{get_status_icon(sf_status['status'])}</div>
            <small>{sf_status['detail']}</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        eb_status = health_status['eventbridge']
        st.markdown(f"""
        <div class="metric-card">
            <h4>EventBridge</h4>
            <div class="{get_status_color(eb_status['status'])}">{get_status_icon(eb_status['status'])}</div>
            <small>{eb_status['detail']}</small>
        </div>
        """, unsafe_allow_html=True)
    
    # Pipeline Information (Read-Only)
    st.subheader("📋 Pipeline Information")
    st.caption("View-only information about your automated pipeline execution. All components run automatically on the 1st of each month.")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="metric-card">
            <h4>🔍 NASDAQ-100 Analysis</h4>
            <div class="neutral">📊 Automated Function</div>
            <small>Analyzes 100 NASDAQ-100 stocks</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="metric-card">
            <h4>📊 Stock Data Fetcher</h4>
            <div class="neutral">⏱️ ~5 min execution</div>
            <small>Downloads 5-year historical data</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="metric-card">
            <h4>🎯 Portfolio Optimizer</h4>
            <div class="neutral">🧮 ~10 min execution</div>
            <small>Runs 6 optimization models</small>
        </div>
        """, unsafe_allow_html=True)
    
    # Pipeline execution information
    st.markdown("---")
    st.markdown("""
    <div class="success-card">
        <h4>🚀 Automated Pipeline Execution</h4>
        <ul>
            <li><strong>Schedule:</strong> 1st of every month at 9:00 AM UTC</li>
            <li><strong>Total Duration:</strong> ~20-30 minutes end-to-end</li>
            <li><strong>Monitoring:</strong> Check AWS Step Functions console for real-time status</li>
            <li><strong>Results:</strong> Automatically saved to S3 and visible in this dashboard</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    


def render_technical_analysis(data):
    """Render the technical analysis page for individual stock analysis"""
    st.markdown('<h1 class="main-header">📊 Individual Stock Technical Analysis</h1>', unsafe_allow_html=True)
    
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
            index=1,
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
        if analyze_button or st.session_state.get('last_analyzed_symbol'):
            # Store the symbol in session state
            if analyze_button:
                st.session_state.last_analyzed_symbol = symbol
            else:
                symbol = st.session_state.last_analyzed_symbol
            
            # Initialize components
            fetcher = StockDataFetcher(period=period)
            analyzer = TechnicalAnalyzer()
            
            # Fetch data
            with st.spinner(f"Fetching data for {symbol}..."):
                stock_data = fetcher.get_stock_data(symbol)
                stock_info = fetcher.get_stock_info(symbol)
            
            if stock_data is not None and not stock_data.empty:
                # Calculate indicators
                indicators = analyzer.calculate_indicators(stock_data)
                trend_analysis = analyzer.analyze_trend(indicators)
                risk_metrics = calculate_risk_metrics(stock_data)
                
                # Display company info
                st.markdown(f"### 🏢 {stock_info.get('name', symbol)}")
                
                info_cols = st.columns(4)
                with info_cols[0]:
                    st.metric("Sector", stock_info.get('sector', 'N/A'))
                with info_cols[1]:
                    st.metric("Industry", stock_info.get('industry', 'N/A'))
                with info_cols[2]:
                    if stock_info.get('pe_ratio') != 'N/A':
                        st.metric("P/E Ratio", f"{stock_info.get('pe_ratio', 'N/A'):.2f}")
                    else:
                        st.metric("P/E Ratio", "N/A")
                with info_cols[3]:
                    if stock_info.get('beta') != 'N/A':
                        st.metric("Beta", f"{stock_info.get('beta', 'N/A'):.2f}")
                    else:
                        st.metric("Beta", "N/A")
                
                # Price and trend information
                st.markdown("### 💰 Price & Trend Analysis")
                
                price_cols = st.columns(4)
                with price_cols[0]:
                    st.metric(
                        "Current Price",
                        f"${indicators['Current_Price']:.2f}",
                        f"{indicators['Price_Change_Pct']:.2f}%"
                    )
                with price_cols[1]:
                    st.metric("Trend", trend_analysis['overall_trend'])
                with price_cols[2]:
                    st.metric("Momentum", trend_analysis['momentum'])
                with price_cols[3]:
                    rec_color = "🟢" if "Buy" in trend_analysis['recommendation'] else "🔴" if "Sell" in trend_analysis['recommendation'] else "🟡"
                    st.metric("Signal", f"{rec_color} {trend_analysis['recommendation']}")
                
                # Technical indicators
                st.markdown("### 📈 Technical Indicators")
                
                # Create tabs for different indicator categories
                tab1, tab2, tab3, tab4 = st.tabs(["Moving Averages", "Momentum", "Volatility", "Risk Metrics"])
                
                with tab1:
                    ma_cols = st.columns(3)
                    with ma_cols[0]:
                        st.metric("MA(20)", f"${indicators.get('MA_20', 0):.2f}")
                    with ma_cols[1]:
                        st.metric("MA(50)", f"${indicators.get('MA_50', 0):.2f}")
                    with ma_cols[2]:
                        ma_signal = "Above MAs ✅" if indicators['Current_Price'] > indicators.get('MA_20', 0) else "Below MAs ⚠️"
                        st.metric("Position", ma_signal)
                
                with tab2:
                    mom_cols = st.columns(3)
                    with mom_cols[0]:
                        rsi_val = indicators.get('RSI', 50)
                        rsi_color = "🔴" if rsi_val > 70 else "🟢" if rsi_val < 30 else "🟡"
                        st.metric("RSI(14)", f"{rsi_color} {rsi_val:.1f}")
                    with mom_cols[1]:
                        macd_val = indicators.get('MACD', 0)
                        macd_color = "🟢" if macd_val > 0 else "🔴"
                        st.metric("MACD", f"{macd_color} {macd_val:.3f}")
                    with mom_cols[2]:
                        st.metric("MACD Signal", f"{indicators.get('MACD_Signal', 0):.3f}")
                
                with tab3:
                    vol_cols = st.columns(3)
                    with vol_cols[0]:
                        st.metric("Volatility", f"{risk_metrics.get('volatility', 0):.1f}%")
                    with vol_cols[1]:
                        st.metric("Volume Ratio", f"{indicators.get('Volume_Ratio', 1):.2f}x")
                    with vol_cols[2]:
                        st.metric("Volatility Status", trend_analysis['volatility'])
                
                with tab4:
                    risk_cols = st.columns(4)
                    with risk_cols[0]:
                        st.metric("Max Drawdown", f"{risk_metrics.get('max_drawdown', 0):.1f}%")
                    with risk_cols[1]:
                        st.metric("Sharpe Ratio", f"{risk_metrics.get('sharpe_ratio', 0):.2f}")
                    with risk_cols[2]:
                        st.metric("95% VaR", f"{risk_metrics.get('var_95', 0):.2f}%")
                    with risk_cols[3]:
                        st.metric("Win Rate", f"{risk_metrics.get('winning_days_pct', 0):.1f}%")
                
                if analysis_type == "Detailed Analysis":
                    # Price chart with technical indicators
                    st.markdown("### 📊 Price Chart with Indicators")
                    
                    fig = make_subplots(
                        rows=3, cols=1,
                        shared_xaxes=True,
                        vertical_spacing=0.05,
                        row_heights=[0.5, 0.25, 0.25],
                        subplot_titles=("Price & Moving Averages", "RSI", "Volume")
                    )
                    
                    # Price and MAs
                    fig.add_trace(
                        go.Candlestick(
                            x=stock_data.index,
                            open=stock_data['Open'],
                            high=stock_data['High'],
                            low=stock_data['Low'],
                            close=stock_data['Close'],
                            name="Price"
                        ),
                        row=1, col=1
                    )
                    
                    # Add moving averages
                    ma_20 = stock_data['Close'].rolling(window=20).mean()
                    ma_50 = stock_data['Close'].rolling(window=50).mean()
                    
                    fig.add_trace(
                        go.Scatter(x=stock_data.index, y=ma_20, name="MA(20)", line=dict(color='orange')),
                        row=1, col=1
                    )
                    fig.add_trace(
                        go.Scatter(x=stock_data.index, y=ma_50, name="MA(50)", line=dict(color='blue')),
                        row=1, col=1
                    )
                    
                    # RSI
                    rsi_series = ta.rsi(stock_data['Close'], length=14)
                    fig.add_trace(
                        go.Scatter(x=stock_data.index, y=rsi_series, name="RSI", line=dict(color='purple')),
                        row=2, col=1
                    )
                    fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                    fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
                    
                    # Volume
                    colors = ['red' if close < open else 'green' 
                             for close, open in zip(stock_data['Close'], stock_data['Open'])]
                    fig.add_trace(
                        go.Bar(x=stock_data.index, y=stock_data['Volume'], name="Volume", marker_color=colors),
                        row=3, col=1
                    )
                    
                    fig.update_layout(
                        height=800,
                        showlegend=True,
                        xaxis_rangeslider_visible=False,
                        title_text=f"{symbol} Technical Analysis"
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Support and Resistance levels
                    st.markdown("### 🎯 Support & Resistance Levels")
                    levels_cols = st.columns(3)
                    with levels_cols[0]:
                        st.metric("Support", f"${indicators.get('Support', 0):.2f}")
                    with levels_cols[1]:
                        st.metric("Current", f"${indicators['Current_Price']:.2f}")
                    with levels_cols[2]:
                        st.metric("Resistance", f"${indicators.get('Resistance', 0):.2f}")
                    
                    # Bollinger Bands info
                    if indicators.get('BB_Upper'):
                        st.markdown("### 📉 Bollinger Bands")
                        bb_cols = st.columns(3)
                        with bb_cols[0]:
                            st.metric("Lower Band", f"${indicators.get('BB_Lower', 0):.2f}")
                        with bb_cols[1]:
                            st.metric("Middle Band", f"${indicators.get('BB_Middle', 0):.2f}")
                        with bb_cols[2]:
                            st.metric("Upper Band", f"${indicators.get('BB_Upper', 0):.2f}")
                
                # AI Insights
                st.markdown("### 🤖 AI-Powered Insights")
                insights = generate_ai_insights(indicators, trend_analysis, stock_info)
                st.info(insights)
                
                # News Sentiment
                st.markdown("### 📰 Recent News & Sentiment")
                news_data = get_news_sentiment(symbol)
                
                if news_data:
                    for article in news_data:
                        sentiment_emoji = "✅" if article['sentiment'] == "Positive" else "❌" if article['sentiment'] == "Negative" else "⚪"
                        with st.expander(f"{sentiment_emoji} {article['title'][:100]}..."):
                            st.write(f"**Publisher:** {article['publisher']}")
                            st.write(f"**Published:** {article['published']}")
                            st.write(f"**Sentiment:** {article['sentiment']}")
                            if article['link']:
                                st.write(f"[Read Full Article]({article['link']})")
                else:
                    st.info("No recent news available for this stock")
                
                # Integration with portfolio optimization
                st.markdown("### 🎯 Portfolio Integration")
                integration_cols = st.columns(2)
                
                with integration_cols[0]:
                    if st.button("➕ Add to Portfolio Analysis", type="secondary", use_container_width=True):
                        if 'portfolio_stocks' not in st.session_state:
                            st.session_state.portfolio_stocks = []
                        if symbol not in st.session_state.portfolio_stocks:
                            st.session_state.portfolio_stocks.append(symbol)
                            st.success(f"Added {symbol} to portfolio analysis list")
                        else:
                            st.info(f"{symbol} is already in portfolio analysis list")
                
                with integration_cols[1]:
                    if st.button("📊 Go to Portfolio Optimization", use_container_width=True):
                        st.info("Switch to Portfolio Optimization page from the sidebar")
                
            else:
                st.error(f"Unable to fetch data for {symbol}. Please check the symbol and try again.")
        else:
            st.info("👈 Enter a stock symbol and click 'Analyze Stock' to begin technical analysis")
            
            # Show some helpful information
            st.markdown("""
            ### 📚 How to Use This Tool
            
            1. **Enter a Stock Symbol:** Type any valid ticker symbol (e.g., AAPL for Apple)
            2. **Select Analysis Period:** Choose how far back to analyze (1 month to 1 year)
            3. **Choose Analysis Mode:** 
               - Quick Analysis: Key indicators and recommendations
               - Detailed Analysis: Full charts, all indicators, and comprehensive metrics
            4. **Click Analyze:** Get instant technical analysis with AI-powered insights
            
            ### 📈 What You'll Get
            
            - **Technical Indicators:** Moving averages, RSI, MACD, Bollinger Bands
            - **Trend Analysis:** Current trend direction and momentum
            - **Risk Metrics:** Volatility, Sharpe ratio, maximum drawdown
            - **AI Insights:** Smart recommendations based on all indicators
            - **News Sentiment:** Recent news with sentiment analysis
            - **Buy/Hold/Sell Signals:** Clear action recommendations
            
            ### 🎯 Perfect For
            
            - Pre-screening stocks before adding to portfolio
            - Deep-dive analysis of individual positions
            - Understanding technical entry/exit points
            - Risk assessment of potential investments
            """)

def main():
    """Main application function"""
    initialize_session_state()
    
    # Sidebar
    st.sidebar.title("🎯 Portfolio Dashboard")
    
    # Navigation at the top
    st.sidebar.markdown("### 📍 Navigate")
    
    # Page navigation with icons
    pages = {
        "🏠 Executive Summary": "Executive Summary",
        "🔍 NASDAQ-100 Analysis": "Stock Analysis",
        "📊 Technical Analysis": "Technical Analysis",
        "🎯 Portfolio Optimization": "Portfolio Optimization",
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
    
    
    st.sidebar.markdown("---")
    
    # Quick Start Guide at the bottom (always visible)
    st.sidebar.markdown("### 📖 Quick Start Guide")
    st.sidebar.markdown("""
    **Navigate through your investment analysis:**
    
    🏠 **Executive Summary** - Overview and key metrics
    
    🔍 **NASDAQ-100 Analysis** - Explore individual opportunities
    
    📊 **Technical Analysis** - Deep-dive into individual stocks
    
    🎯 **Portfolio Optimization** - Compare strategies and download portfolios
    
    📈 **Historical Tracking** - Monitor performance over time
    
    ⚙️ **System Status** - Health monitoring and manual controls
    
    ---
    
    💡 **Pro Tips:**
    - Download CSV files from Portfolio Optimization for your broker
    - Check System Status if data seems outdated
    - Use manual controls if you need fresh results
    """)
    
    
    # Load data
    with st.spinner("Loading data from S3..."):
        data = load_latest_data()
    
    # Store data in session state for access in render functions
    st.session_state.data = data
    
    # Render selected page
    if page == "Executive Summary":
        render_executive_summary(data)
    elif page == "Stock Analysis":
        render_stock_analysis(data)
    elif page == "Technical Analysis":
        render_technical_analysis(data)
    elif page == "Portfolio Optimization":
        # Pass the portfolio_data directly to the new function
        portfolio_data = data.get('portfolio_data', {}) if data else {}
        render_portfolio_optimization(portfolio_data)
    elif page == "Historical Tracking":
        # Pass the portfolio_data directly to the new function
        portfolio_data = data.get('portfolio_data', {}) if data else {}
        render_historical_tracking(portfolio_data)
    elif page == "System Status":
        # Pass the portfolio_data directly to the new function
        portfolio_data = data.get('portfolio_data', {}) if data else {}
        render_system_status(portfolio_data)

if __name__ == "__main__":
    main()