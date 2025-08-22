#!/usr/bin/env python3
"""
Check analyst coverage for all NASDAQ-100 stocks using FMP API
"""

import requests
import json
import time
import csv
from datetime import datetime

# FMP API configuration
API_KEY = "USIa8HA0z2NCAdBwL1ZEHnpMaxe73DF8"
BASE_URL = "https://financialmodelingprep.com/api/v4"

def get_nasdaq_100_symbols():
    """Get list of NASDAQ-100 symbols from local data"""
    try:
        # Try to read from existing processed data
        with open('/home/beehiveting/apps/portfolio-optimization/self-hosted/data/processed/nasdaq_100_analysis.csv', 'r') as f:
            reader = csv.DictReader(f)
            return [row['Symbol'] for row in reader]
    except:
        # Fallback to a sample of major NASDAQ-100 stocks for testing
        return ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO', 'ASML', 'COST',
                'PEP', 'ADBE', 'CSCO', 'CMCSA', 'NFLX', 'INTC', 'AMD', 'QCOM', 'TXN', 'INTU']

def get_analyst_coverage(symbol):
    """Get analyst price target data for a single stock"""
    # Try consensus endpoint first (likely has analyst count)
    consensus_url = f"{BASE_URL}/price-target-consensus?symbol={symbol}&apikey={API_KEY}"
    
    try:
        response = requests.get(consensus_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                # Get the most recent consensus data
                latest = data[0] if isinstance(data, list) else data
                
                # If no analyst count in consensus, try regular price-target endpoint
                analyst_count = latest.get('numberOfAnalysts', 0)
                if analyst_count == 0:
                    # Try the regular price target endpoint
                    target_url = f"{BASE_URL}/price-target?symbol={symbol}&apikey={API_KEY}"
                    target_response = requests.get(target_url, timeout=10)
                    if target_response.status_code == 200:
                        target_data = target_response.json()
                        if target_data and len(target_data) > 0:
                            # Count the number of individual price targets
                            analyst_count = len(target_data) if isinstance(target_data, list) else 1
                
                return {
                    'symbol': symbol,
                    'analyst_count': analyst_count,
                    'consensus_target': latest.get('targetConsensus', None),
                    'min_target': latest.get('targetLow', None),
                    'max_target': latest.get('targetHigh', None),
                    'median_target': latest.get('targetMedian', None),
                    'last_updated': latest.get('publishedDate', None)
                }
        return {'symbol': symbol, 'analyst_count': 0, 'error': f'HTTP {response.status_code}'}
    except Exception as e:
        return {'symbol': symbol, 'analyst_count': 0, 'error': str(e)}

def analyze_all_stocks():
    """Analyze analyst coverage for all NASDAQ-100 stocks"""
    print("Starting NASDAQ-100 analyst coverage analysis...")
    print("-" * 60)
    
    symbols = get_nasdaq_100_symbols()
    print(f"Analyzing {len(symbols)} stocks...")
    
    results = []
    
    for i, symbol in enumerate(symbols, 1):
        print(f"[{i}/{len(symbols)}] Checking {symbol}...", end=" ")
        
        coverage = get_analyst_coverage(symbol)
        results.append(coverage)
        
        analyst_count = coverage.get('analyst_count', 0)
        if analyst_count > 0:
            print(f"✓ {analyst_count} analysts")
        else:
            print(f"✗ No coverage data")
        
        # Rate limiting - FMP allows 250 requests per minute
        if i % 10 == 0:
            time.sleep(2)  # Pause every 10 requests
    
    return results

def generate_report(results):
    """Generate summary report of analyst coverage"""
    # Calculate statistics
    total_stocks = len(results)
    stocks_with_coverage = [r for r in results if r['analyst_count'] > 0]
    no_coverage = [r for r in results if r['analyst_count'] == 0]
    low_coverage = [r for r in results if 0 < r['analyst_count'] < 5]
    medium_coverage = [r for r in results if 5 <= r['analyst_count'] < 15]
    high_coverage = [r for r in results if r['analyst_count'] >= 15]
    
    print("\n" + "=" * 60)
    print("ANALYST COVERAGE SUMMARY")
    print("=" * 60)
    
    print(f"\nTotal stocks analyzed: {total_stocks}")
    print(f"Stocks with analyst coverage: {len(stocks_with_coverage)} ({len(stocks_with_coverage)/total_stocks*100:.1f}%)")
    print(f"Stocks with NO coverage: {len(no_coverage)} ({len(no_coverage)/total_stocks*100:.1f}%)")
    
    print("\nCoverage Distribution:")
    print(f"  High (≥15 analysts): {len(high_coverage)} stocks ({len(high_coverage)/total_stocks*100:.1f}%)")
    print(f"  Medium (5-14 analysts): {len(medium_coverage)} stocks ({len(medium_coverage)/total_stocks*100:.1f}%)")
    print(f"  Low (<5 analysts): {len(low_coverage)} stocks ({len(low_coverage)/total_stocks*100:.1f}%)")
    
    if len(stocks_with_coverage) > 0:
        analyst_counts = [s['analyst_count'] for s in stocks_with_coverage]
        avg_count = sum(analyst_counts) / len(analyst_counts)
        sorted_counts = sorted(analyst_counts)
        median_count = sorted_counts[len(sorted_counts)//2]
        print(f"\nAverage analyst count: {avg_count:.1f}")
        print(f"Median analyst count: {median_count}")
        print(f"Max analyst count: {max(analyst_counts)}")
        print(f"Min analyst count (excluding 0): {min(analyst_counts)}")
    
    # Show low coverage stocks
    if len(low_coverage) > 0:
        print("\n" + "-" * 40)
        print("STOCKS WITH LOW COVERAGE (<5 analysts):")
        print("-" * 40)
        for stock in low_coverage:
            print(f"  {stock['symbol']}: {stock['analyst_count']} analysts")
    
    # Show no coverage stocks
    if len(no_coverage) > 0:
        print("\n" + "-" * 40)
        print("STOCKS WITH NO COVERAGE:")
        print("-" * 40)
        for stock in no_coverage:
            error = stock.get('error', 'Unknown')
            print(f"  {stock['symbol']}: {error}")
    
    # Save detailed results
    output_file = f"/home/beehiveting/apps/portfolio-optimization/analyst_coverage_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(output_file, 'w', newline='') as f:
        if results:
            fieldnames = results[0].keys()
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
    print(f"\nDetailed results saved to: {output_file}")
    
    return results

if __name__ == "__main__":
    results = analyze_all_stocks()
    results = generate_report(results)
    
    print("\n" + "=" * 60)
    print("RECOMMENDATION FOR BLACK-LITTERMAN IMPLEMENTATION:")
    print("=" * 60)
    
    low_count = len([r for r in results if 0 < r['analyst_count'] < 5])
    no_count = len([r for r in results if r['analyst_count'] == 0])
    
    if (low_count + no_count) > 0:
        print(f"\n⚠️  {low_count + no_count} stocks have low/no analyst coverage")
        print("\nSuggested approach:")
        print("1. Use market-cap weighted confidence scaling")
        print("2. For stocks with <5 analysts: Use 20-30% confidence")
        print("3. For stocks with 0 analysts: Use market equilibrium only (0% confidence)")
        print("4. Scale confidence: confidence = min(num_analysts/20, 1.0) * 0.8")
    else:
        print("\n✓ All stocks have adequate analyst coverage")