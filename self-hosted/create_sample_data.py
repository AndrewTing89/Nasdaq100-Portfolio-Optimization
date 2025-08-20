#!/usr/bin/env python3
"""Create sample data files for testing the dashboard"""

import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from pathlib import Path

# Set data directory
data_dir = Path("/home/beehiveting/apps/portfolio-optimization/self-hosted/data")

# Create sample NASDAQ-100 analysis data
nasdaq_stocks = [
    "AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "GOOG", "TSLA", "AVGO", "PEP",
    "COST", "ADBE", "CSCO", "CMCSA", "NFLX", "TMUS", "TXN", "INTC", "AMD", "QCOM"
]

# Create nasdaq_100_analysis.csv
nasdaq_data = {
    "Ticker": nasdaq_stocks[:20],
    "Last Price": np.random.uniform(50, 500, 20),
    "Market Cap (M)": np.random.uniform(100000, 2000000, 20),
    "Weight (%)": np.random.uniform(0.5, 10, 20),
    "Stock Exchange": ["NASDAQ"] * 20,
    "P/E Ratio": np.random.uniform(10, 40, 20),
    "Undervaluation Score": np.random.uniform(-2, 2, 20),
    "Is Undervalued": np.random.choice([True, False], 20),
    "Summary": [f"Strong fundamentals with growth potential" for _ in range(20)]
}

nasdaq_df = pd.DataFrame(nasdaq_data)
nasdaq_df.to_csv(data_dir / "processed" / "nasdaq_100_analysis.csv", index=False)
print(f"Created: {data_dir / 'processed' / 'nasdaq_100_analysis.csv'}")

# Create nasdaq_100_with_returns.csv (includes historical returns)
returns_data = nasdaq_data.copy()
returns_data.update({
    "Annual Return": np.random.uniform(-0.1, 0.4, 20),
    "Annual Volatility": np.random.uniform(0.1, 0.4, 20),
    "Sharpe Ratio": np.random.uniform(-0.5, 2.5, 20),
    "Max Drawdown": np.random.uniform(-0.5, -0.1, 20),
    "Beta": np.random.uniform(0.5, 2, 20)
})

returns_df = pd.DataFrame(returns_data)
returns_df.to_csv(data_dir / "processed" / "nasdaq_100_with_returns.csv", index=False)
print(f"Created: {data_dir / 'processed' / 'nasdaq_100_with_returns.csv'}")

# Create sample portfolio optimization results
portfolio_results = {
    "mean_variance_max_sharpe.csv": {
        "Ticker": nasdaq_stocks[:10],
        "Weight": np.random.dirichlet(np.ones(10)),
        "Annual Return": np.random.uniform(0.05, 0.25, 10),
        "Volatility": np.random.uniform(0.1, 0.3, 10)
    },
    "mean_variance_min_volatility.csv": {
        "Ticker": nasdaq_stocks[:10],
        "Weight": np.random.dirichlet(np.ones(10)),
        "Annual Return": np.random.uniform(0.03, 0.15, 10),
        "Volatility": np.random.uniform(0.05, 0.15, 10)
    },
    "risk_parity.csv": {
        "Ticker": nasdaq_stocks[:10],
        "Weight": np.random.dirichlet(np.ones(10)),
        "Risk Contribution": np.ones(10) / 10,
        "Annual Return": np.random.uniform(0.05, 0.20, 10)
    }
}

# Save portfolio results
for filename, data in portfolio_results.items():
    df = pd.DataFrame(data)
    df.to_csv(data_dir / "results" / "final" / filename, index=False)
    print(f"Created: {data_dir / 'results' / 'final' / filename}")

# Create sample individual stock data
for ticker in nasdaq_stocks[:5]:
    dates = pd.date_range(end=datetime.now(), periods=252*5, freq='D')  # 5 years of data
    stock_data = {
        "Date": dates,
        "Open": np.random.uniform(100, 200, len(dates)),
        "High": np.random.uniform(100, 210, len(dates)),
        "Low": np.random.uniform(90, 200, len(dates)),
        "Close": np.random.uniform(95, 205, len(dates)),
        "Volume": np.random.uniform(1000000, 50000000, len(dates))
    }
    df = pd.DataFrame(stock_data)
    df.to_csv(data_dir / "stocks" / f"{ticker}.csv", index=False)
    print(f"Created: {data_dir / 'stocks' / ticker}.csv")

# Create summary JSON files
phase1_summary = {
    "timestamp": datetime.now().isoformat(),
    "total_stocks": len(nasdaq_stocks),
    "undervalued_count": 8,
    "average_pe": 22.5,
    "market_cap_total": 15000000
}

with open(data_dir / "results" / "phase1" / "nasdaq_analysis_summary.json", "w") as f:
    json.dump(phase1_summary, f, indent=2)
print(f"Created: {data_dir / 'results' / 'phase1' / 'nasdaq_analysis_summary.json'}")

phase2_summary = {
    "timestamp": datetime.now().isoformat(),
    "stocks_processed": len(nasdaq_stocks),
    "average_return": 0.12,
    "average_volatility": 0.25,
    "average_sharpe": 0.85
}

with open(data_dir / "results" / "phase2" / "historical_data_summary.json", "w") as f:
    json.dump(phase2_summary, f, indent=2)
print(f"Created: {data_dir / 'results' / 'phase2' / 'historical_data_summary.json'}")

print("\nSample data creation complete! The dashboard should now be able to load.")