#!/usr/bin/env python3
"""Test FMP historical data fetching"""

import requests
import json
from datetime import datetime, timedelta

API_KEY = "USIa8HA0z2NCAdBwL1ZEHnpMaxe73DF8"

# Test with a few stocks
symbols = ["AAPL", "MSFT", "NVDA"]

for symbol in symbols:
    print(f"\nTesting {symbol}:")
    print("-" * 40)
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*5)
    
    # FMP historical endpoint
    url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol}"
    params = {
        "from": start_date.strftime("%Y-%m-%d"),
        "to": end_date.strftime("%Y-%m-%d"),
        "apikey": API_KEY
    }
    
    print(f"URL: {url}")
    print(f"Date range: {params['from']} to {params['to']}")
    
    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if 'historical' in data:
                historical_data = data['historical']
                print(f"Data points: {len(historical_data)}")
                
                if len(historical_data) > 0:
                    # Show first and last data point
                    print(f"First date: {historical_data[-1]['date']}")
                    print(f"Last date: {historical_data[0]['date']}")
                    print(f"Sample data point: {json.dumps(historical_data[0], indent=2)}")
                    
                    # Check if we have the required fields
                    sample = historical_data[0]
                    required_fields = ['date', 'open', 'high', 'low', 'close', 'volume']
                    has_all = all(field in sample for field in required_fields)
                    print(f"Has all required fields: {has_all}")
                else:
                    print("Historical data is empty")
            else:
                print(f"No 'historical' key in response. Keys: {list(data.keys())}")
        else:
            print(f"API error: {response.text[:200]}")
            
    except Exception as e:
        print(f"Error: {e}")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print("If data is available, the issue might be:")
print("1. Rate limiting (we're making too many requests)")
print("2. Data processing error in the pipeline")
print("3. Network issues in the Docker container")