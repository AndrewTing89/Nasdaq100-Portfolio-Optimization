#!/usr/bin/env python3
"""Test FMP API endpoints for analyst data"""

import requests
import json

API_KEY = "USIa8HA0z2NCAdBwL1ZEHnpMaxe73DF8"

# Test different endpoints
test_symbols = ["AAPL", "NVDA", "MSFT"]

for symbol in test_symbols:
    print(f"\nTesting {symbol}:")
    print("-" * 40)
    
    # Test v4 consensus endpoint
    consensus_url = f"https://financialmodelingprep.com/api/v4/price-target-consensus?symbol={symbol}&apikey={API_KEY}"
    print(f"Consensus URL: {consensus_url}")
    
    try:
        response = requests.get(consensus_url, timeout=10)
        print(f"Consensus Response Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Consensus Data: {json.dumps(data, indent=2)[:500]}...")
    except Exception as e:
        print(f"Consensus Error: {e}")
    
    # Test v4 regular price target endpoint
    target_url = f"https://financialmodelingprep.com/api/v4/price-target?symbol={symbol}&apikey={API_KEY}"
    print(f"\nPrice Target URL: {target_url}")
    
    try:
        response = requests.get(target_url, timeout=10)
        print(f"Price Target Response Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                print(f"Number of analyst reports: {len(data)}")
                if len(data) > 0:
                    print(f"First report: {json.dumps(data[0], indent=2)[:500]}...")
            else:
                print(f"Price Target Data: {json.dumps(data, indent=2)[:500]}...")
    except Exception as e:
        print(f"Price Target Error: {e}")