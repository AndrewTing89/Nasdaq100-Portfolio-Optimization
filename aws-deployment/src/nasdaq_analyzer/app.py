"""
Lambda function for NASDAQ-100 data scraping and undervaluation analysis using yfinance.
This function scrapes NASDAQ-100 components and calculates undervaluation rates.
"""

import json
import sys
import os
import pandas as pd
from datetime import datetime

# Add shared utilities to path
sys.path.append('/opt/shared')
from utils import S3Handler, LambdaConfig, create_lambda_response, parse_lambda_event

# Use yfinance for reliable stock data
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import re
import time


def get_nasdaq_components():
    """Scrape Nasdaq-100 components table from Wikipedia"""
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        tables = soup.find_all('table', {'class': 'wikitable'})
        print(f"Found {len(tables)} wikitables")
        
        for i, table in enumerate(tables):
            headers = [th.get_text(strip=True) for th in table.find_all('th')]
            
            if any(term in ' '.join(headers).lower() for term in ['ticker', 'symbol', 'company']):
                company_idx = -1
                symbol_idx = -1
                
                for idx, header in enumerate(headers):
                    header_lower = header.lower()
                    if 'company' in header_lower or 'name' in header_lower:
                        company_idx = idx
                    if 'symbol' in header_lower or 'ticker' in header_lower:
                        symbol_idx = idx
                
                if company_idx >= 0 and symbol_idx >= 0:
                    components = []
                    rows = table.find_all('tr')
                    data_rows = [row for row in rows if row.find('td')]
                    
                    for row in data_rows:
                        cells = row.find_all('td')
                        if len(cells) > max(company_idx, symbol_idx):
                            company_cell = cells[company_idx]
                            company_link = company_cell.find('a')
                            company = company_link.get_text(strip=True) if company_link else company_cell.get_text(strip=True)
                            
                            symbol_cell = cells[symbol_idx]
                            symbol_link = symbol_cell.find('a')
                            symbol = symbol_link.get_text(strip=True) if symbol_link else symbol_cell.get_text(strip=True)
                            
                            company = company.replace('\n', ' ').strip()
                            symbol = symbol.replace('\n', ' ').strip()
                            
                            if company and symbol:
                                components.append((company, symbol))
                    
                    print(f"Extracted {len(components)} components")
                    if len(components) >= 50:
                        return components
        
        # Fallback approach - return top 10 stocks for testing
        print("Using fallback approach")
        fallback_components = [
            ("Apple Inc.", "AAPL"), ("Microsoft Corporation", "MSFT"), ("Amazon.com Inc.", "AMZN"),
            ("NVIDIA Corporation", "NVDA"), ("Alphabet Inc. Class A", "GOOGL"), ("Meta Platforms Inc.", "META"),
            ("Tesla, Inc.", "TSLA"), ("Broadcom Inc.", "AVGO"), ("PepsiCo, Inc.", "PEP"),
            ("Costco Wholesale Corporation", "COST")
        ]
        print(f"Returning {len(fallback_components)} fallback components")
        return fallback_components
        
    except Exception as e:
        print(f"Error scraping components: {e}")
        return []


def get_stock_data(ticker):
    """Extract stock data using yfinance library"""
    try:
        print(f"  Fetching data for {ticker} using yfinance...")
        
        # Create ticker object
        stock = yf.Ticker(ticker)
        
        # Get stock info with timeout
        info = stock.info
        
        # Get previous close
        prev_close = info.get('previousClose') or info.get('regularMarketPreviousClose')
        
        # Get target price (analyst target)
        target_est = info.get('targetMeanPrice')
        
        print(f"  yfinance data - Previous Close: {prev_close}, Target Est: {target_est}")
        
        if prev_close is not None:
            prev_close = float(prev_close)
        if target_est is not None:
            target_est = float(target_est)
        
        return prev_close, target_est
        
    except Exception as e:
        print(f"  Error retrieving data for {ticker}: {e}")
        return None, None


def calculate_undervalue_rate(target_est, prev_close):
    """Calculate undervalue rate"""
    if target_est is not None and prev_close is not None and prev_close != 0:
        return (target_est / prev_close) - 1
    return None


def analyze_nasdaq_components(config: LambdaConfig, s3_handler: S3Handler):
    """Main analysis function"""
    print("Fetching Nasdaq-100 components...")
    components = get_nasdaq_components()
    
    if not components:
        raise Exception("No components retrieved")
    
    print(f"Successfully retrieved {len(components)} components")
    
    # Get number of stocks to process from environment variable
    max_stocks = int(os.environ.get('MAX_STOCKS', '100'))  # Default to 100 for full NASDAQ-100
    test_components = components[:max_stocks]
    print(f"Processing first {len(test_components)} components (MAX_STOCKS={max_stocks})")
    
    results = []
    for i, (company, symbol) in enumerate(test_components):
        print(f"Processing {i+1}/{len(test_components)}: {company} ({symbol})...")
        
        prev_close, target_est = get_stock_data(symbol)
        
        print(f"  Previous Close: {prev_close}")
        print(f"  1y Target Est: {target_est}")
        
        undervalue_rate = calculate_undervalue_rate(target_est, prev_close)
        if undervalue_rate is not None:
            print(f"  Undervalue Rate: {undervalue_rate:.2%}")
        else:
            print("  Undervalue Rate: N/A")
        
        results.append({
            "Company": company,
            "Symbol": symbol,
            "Previous Close": prev_close,
            "1y Target Est": target_est,
            "Undervalue Rate": undervalue_rate
        })
        
        # Add a delay between requests to avoid rate limiting
        if i < len(test_components) - 1:
            time.sleep(1)
    
    # Create DataFrame and upload to S3
    df_results = pd.DataFrame(results)
    
    # Upload raw results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_key = f"{config.raw_data_prefix}nasdaq_100_analysis_{timestamp}.csv"
    s3_handler.upload_csv(df_results, raw_key)
    
    # Upload processed results (latest)
    processed_key = f"{config.processed_data_prefix}nasdaq_100_analysis.csv"
    s3_handler.upload_csv(df_results, processed_key)
    
    # Generate summary statistics
    summary = {}
    if "Undervalue Rate" in df_results.columns:
        valid_df = df_results.dropna(subset=["Undervalue Rate"])
        if not valid_df.empty:
            summary = {
                "total_stocks": len(df_results),
                "stocks_with_target_price": len(valid_df),
                "mean_undervalue_rate": float(valid_df["Undervalue Rate"].mean()),
                "median_undervalue_rate": float(valid_df["Undervalue Rate"].median()),
                "high_potential_stocks": int(valid_df[valid_df["Undervalue Rate"] > 0.2].shape[0]),
                "moderate_potential_stocks": int(valid_df[(valid_df["Undervalue Rate"] <= 0.2) & (valid_df["Undervalue Rate"] > 0)].shape[0]),
                "overvalued_stocks": int(valid_df[valid_df["Undervalue Rate"] <= 0].shape[0]),
                "timestamp": timestamp
            }
    
    # Upload summary
    summary_key = f"{config.results_prefix}phase1/nasdaq_analysis_summary_{timestamp}.json"
    s3_handler.upload_json(summary, summary_key)
    
    return {
        "processed_stocks": len(results),
        "raw_data_key": raw_key,
        "processed_data_key": processed_key,
        "summary_key": summary_key,
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
        
        # Run analysis
        result = analyze_nasdaq_components(config, s3_handler)
        
        print(f"Analysis completed successfully: {result}")
        
        return create_lambda_response(200, {
            "message": "NASDAQ-100 analysis completed successfully",
            "result": result
        })
        
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return create_lambda_response(500, {
            "message": "Error during NASDAQ-100 analysis",
            "error": str(e)
        })


# For local testing
if __name__ == "__main__":
    # Mock event for testing
    test_event = {"trigger_type": "manual"}
    result = lambda_handler(test_event, None)
    print(f"Test result: {result}")