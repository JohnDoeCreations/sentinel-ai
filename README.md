# Sentinel AI

Sentinel AI is a modern Streamlit market-analysis workspace for researching stocks, scanning watchlists, testing strategies, and practicing trades without risking real money.

## Features

- Live and historical market data from Yahoo Finance
- Technical indicators, scoring, and plain-language signal explanations
- Explainable single-stock analysis with trend, volatility, price levels, and scenarios
- Risk-first trade planning with position sizing, stop levels, targets, and reward-to-risk checks
- Multi-symbol market scanner
- Persistent watchlists and price alerts
- Timed in-app alert monitoring with trigger history and duplicate protection
- Massive-powered company news with explainable headline sentiment
- Automatic local backups, portable data export, and validated restore
- Strategy backtesting with trade logs and equity curves
- Paper trading, trade history, and portfolio-performance views
- Automated tests for market data, signals, scanning, persistence, and backtesting

## Requirements

- Python 3.12
- Internet access for live market data

## Windows setup

Open PowerShell in the project folder and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks the activation script, the virtual environment can be used directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run the app

With the virtual environment activated:

```powershell
python -m streamlit run app.py
```

Then open the local address shown in the terminal, normally `http://localhost:8501`.

For everyday use on Windows, double-click `Start Sentinel AI.cmd` in the project folder. It starts the local server when needed and opens the app in your browser.

Without activation:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Run the tests

```powershell
python -m unittest discover -s tests -v
```

## Project layout

- `app.py` — application entry point and navigation
- `app_pages/` — dashboard, scanner, backtester, alerts, and trading pages
- `data/` — market-data access and local application data
- `strategies/` — indicators and signal scoring
- `utils/` — scanners, alerts, watchlists, paper trading, and symbol handling
- `backtesting/` — backtest engine and generated results
- `tests/` — automated test suite

## Disclaimer

Sentinel AI is an educational research tool. Its signals and simulations are not financial advice, and paper-trading results do not guarantee future performance.
