"""
Lambda function for downloading historical stock data and calculating returns/volatility.
This function reads NASDAQ-100 stock list from S3, downloads stock data, and calculates metrics.
"""

import json
import sys
import os
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add shared utilities to path
sys.path.append('/opt/shared')
from utils import S3Handler, LambdaConfig, create_lambda_response, parse_lambda_event


def download_stock_data(symbol: str, period: str = "5y") -> pd.DataFrame:
    """Download historical stock data using yfinance"""
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period)
        
        if data.empty:
            print(f"No data found for {symbol}")
            return None
        
        # Reset index to make Date a column
        data.reset_index(inplace=True)
        
        # Ensure we have the required columns
        required_columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in data.columns for col in required_columns):
            print(f"Missing required columns for {symbol}")
            return None
        
        return data[required_columns]
        
    except Exception as e:
        print(f"Error downloading data for {symbol}: {e}")
        return None


def calculate_metrics(stock_data: pd.DataFrame) -> Dict[str, float]:
    """Calculate annual return and volatility from stock data"""
    try:
        # Calculate daily returns
        stock_data['Daily_Return'] = stock_data['Close'].pct_change()
        returns = stock_data['Daily_Return'].dropna()
        
        if len(returns) < 252:  # Need at least one year of data
            return {"error": f"Insufficient data: only {len(returns)} trading days"}
        
        # Calculate annualized return (geometric mean)
        annual_return = returns.mean() * 252
        
        # Calculate annualized volatility
        annual_volatility = returns.std() * np.sqrt(252)
        
        return {
            "Annual_Return_5Y": float(annual_return),
            "Annual_Volatility_5Y": float(annual_volatility),
            "data_points": len(returns)
        }
        
    except Exception as e:
        return {"error": str(e)}


def process_stock_list(config: LambdaConfig, s3_handler: S3Handler, stock_list_key: str):
    """Process the stock list and download/calculate metrics for each stock"""
    
    # Download the stock list from S3
    print(f"Downloading stock list from {stock_list_key}")
    stock_df = s3_handler.download_csv(stock_list_key)
    
    if stock_df is None:
        raise Exception(f"Could not download stock list from {stock_list_key}")
    
    if 'Symbol' not in stock_df.columns:
        raise Exception("Stock list must contain 'Symbol' column")
    
    # Prepare new columns for metrics
    if "Annual_Return_5Y" not in stock_df.columns:
        stock_df["Annual_Return_5Y"] = np.nan
    if "Annual_Volatility_5Y" not in stock_df.columns:
        stock_df["Annual_Volatility_5Y"] = np.nan
    
    # Get number of stocks to process from environment variable
    max_stocks = int(os.environ.get('MAX_STOCKS', str(len(stock_df))))  # Default to all stocks
    stock_df_subset = stock_df.head(max_stocks)
    
    print(f"Processing {len(stock_df_subset)} stocks (MAX_STOCKS={max_stocks}, Total available: {len(stock_df)})...")
    
    processed_count = 0
    failed_stocks = []
    individual_stock_data = {}
    
    for i, row in stock_df_subset.iterrows():
        symbol = row['Symbol']
        print(f"[{i+1}/{len(stock_df_subset)}] Processing {symbol}...")
        
        # Download stock data
        stock_data = download_stock_data(symbol)
        
        if stock_data is None:
            print(f"  -> {symbol} failed to download")
            failed_stocks.append(symbol)
            continue
        
        # Calculate metrics
        metrics = calculate_metrics(stock_data)
        
        if "error" in metrics:
            print(f"  -> {symbol} calculation failed: {metrics['error']}")
            failed_stocks.append(symbol)
            continue
        
        # Update the main dataframe
        stock_df.loc[i, "Annual_Return_5Y"] = metrics["Annual_Return_5Y"]
        stock_df.loc[i, "Annual_Volatility_5Y"] = metrics["Annual_Volatility_5Y"]
        
        # Store individual stock data for upload to S3
        individual_stock_data[symbol] = stock_data
        
        print(f"  -> Success: Annual Return = {metrics['Annual_Return_5Y']:.4f}, "
              f"Annual Volatility = {metrics['Annual_Volatility_5Y']:.4f}")
        
        processed_count += 1
    
    # Upload individual stock data files to S3
    print("Uploading individual stock data files...")
    for symbol, data in individual_stock_data.items():
        stock_key = f"{config.stocks_data_prefix}{symbol}.csv"
        s3_handler.upload_csv(data, stock_key)
    
    # Upload the updated stock list with metrics
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Raw results with timestamp
    raw_key = f"{config.raw_data_prefix}nasdaq_100_with_returns_{timestamp}.csv"
    s3_handler.upload_csv(stock_df, raw_key)
    
    # Processed results (latest)
    processed_key = f"{config.processed_data_prefix}nasdaq_100_with_returns.csv"
    s3_handler.upload_csv(stock_df, processed_key)
    
    # Create summary statistics
    stocks_with_data = stock_df[stock_df["Annual_Return_5Y"].notnull()]
    
    summary = {
        "total_stocks": len(stock_df),
        "successfully_processed": processed_count,
        "failed_stocks": len(failed_stocks),
        "failed_stock_list": failed_stocks,
        "timestamp": timestamp
    }
    
    if len(stocks_with_data) > 0:
        summary.update({
            "mean_annual_return": float(stocks_with_data["Annual_Return_5Y"].mean()),
            "median_annual_return": float(stocks_with_data["Annual_Return_5Y"].median()),
            "mean_annual_volatility": float(stocks_with_data["Annual_Volatility_5Y"].mean()),
            "median_annual_volatility": float(stocks_with_data["Annual_Volatility_5Y"].median()),
            "top_performers": stocks_with_data.nlargest(10, "Annual_Return_5Y")[["Symbol", "Annual_Return_5Y"]].to_dict('records'),
            "most_volatile": stocks_with_data.nlargest(10, "Annual_Volatility_5Y")[["Symbol", "Annual_Volatility_5Y"]].to_dict('records')
        })
    
    # Upload summary
    summary_key = f"{config.results_prefix}phase2/stock_metrics_summary_{timestamp}.json"
    s3_handler.upload_json(summary, summary_key)
    
    return {
        "processed_stocks": processed_count,
        "failed_stocks": len(failed_stocks),
        "raw_data_key": raw_key,
        "processed_data_key": processed_key,
        "summary_key": summary_key,
        "individual_files_uploaded": len(individual_stock_data),
        "summary": summary
    }


def lambda_handler(event, context):
    """AWS Lambda handler function"""
    try:
        # Parse event
        parsed_event = parse_lambda_event(event)
        print(f"Received event: {json.dumps(parsed_event, indent=2)}")
        
        # Initialize configuration and S3 handler
        config = LambdaConfig()
        s3_handler = S3Handler(config.bucket_name)
        
        # Determine input file
        stock_list_key = None
        
        # Check if input file is specified in event
        if 'input_file' in parsed_event:
            stock_list_key = parsed_event['input_file']
        elif parsed_event.get('trigger_type') == 's3':
            # If triggered by S3 event, use the uploaded file
            stock_list_key = parsed_event['key']
        else:
            # Default: use the latest processed NASDAQ analysis
            stock_list_key = f"{config.processed_data_prefix}nasdaq_100_analysis.csv"
        
        print(f"Using input file: {stock_list_key}")
        
        # Process the stock list
        result = process_stock_list(config, s3_handler, stock_list_key)
        
        print(f"Stock data processing completed successfully: {result}")
        
        return create_lambda_response(200, {
            "message": "Stock data processing completed successfully",
            "result": result
        })
        
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return create_lambda_response(500, {
            "message": "Error during stock data processing",
            "error": str(e)
        })


# For local testing
if __name__ == "__main__":
    # Mock event for testing
    test_event = {
        "trigger_type": "manual",
        "input_file": "processed/nasdaq_100_analysis.csv"
    }
    result = lambda_handler(test_event, None)
    print(f"Test result: {result}")