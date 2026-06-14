# Huntr

Huntr is an automated M&A target signal for public EMEA technology companies. It screens a curated universe of listed companies, scores them on acquisition-friendly characteristics, and publishes a refreshed static dashboard through GitHub Pages.

The project is designed as a lightweight research tool: a nightly data pipeline, a JSON score output, and a browser-based dashboard that can be opened from desktop, tablet, or phone.

> Important: Huntr is for research and education only. It is not investment advice, a trading recommendation, or a prediction that any company will be acquired.

## Live Tool

If GitHub Pages is enabled for this repository, the hosted dashboard is available at:

https://agudoal.github.io/Huntr/

## What Huntr Does

- Loads a curated company universe from `universe.csv`.
- Pulls market and fundamental data using Yahoo Finance via `yfinance`.
- Enriches the score with free SEC EDGAR signals for sector consolidation and strategic interest.
- Scores each company across six factors, weighted into a single 0-100 signal.
- Builds `huntr_scored.json` as the machine-readable output.
- Injects the latest data into `template.html` to generate `index.html`, the hosted dashboard.
- Adds named potential buyers and structured deal theses from the curated logic in `insights.py`.
- Refreshes automatically every night through GitHub Actions.

## Scoring Model

Higher factor scores mean the company looks more acquisition-friendly on that dimension.

| Factor | Weight | What it captures | Main source |
| --- | ---: | --- | --- |
| `f_val` | 20% | Relative valuation, using EV/EBITDA and EV/Sales | Yahoo Finance |
| `f_own` | 20% | Free float and ownership openness | Yahoo Finance, adjusted with insider ownership |
| `f_bs` | 15% | Balance sheet capacity, using net debt / EBITDA | Yahoo Finance |
| `f_sz` | 15% | Deal feasibility based on market capitalisation | Yahoo Finance |
| `f_sc` | 15% | Sector consolidation activity over the trailing 24 months | SEC EDGAR |
| `f_si` | 15% | Company-specific strategic interest, such as tender, activist, or merger filings | SEC EDGAR |

The score is a relative screening signal, not a probability model. It should be read as a way to prioritise names for further work, not as a standalone conclusion.

## Repository Structure

| Path | Purpose |
| --- | --- |
| `pipeline.py` | Runs the nightly scoring pipeline and writes `huntr_scored.json`. |
| `edgar_data.py` | Pulls SEC EDGAR signals for sector consolidation and strategic interest. |
| `insights.py` | Ranks named potential buyers and generates structured deal theses. |
| `universe.csv` | Defines the active company universe. |
| `build_index.py` | Injects scored data into `template.html` and writes `index.html`. |
| `template.html` | Source dashboard template. |
| `index.html` | Generated live dashboard published by GitHub Pages. |
| `.github/workflows/nightly.yml` | Scheduled workflow that refreshes the data and hosted page. |

## Run Locally

Requirements:

- Python 3.11+
- `yfinance`
- `pandas`
- `numpy`
- `requests`

Install dependencies:

```bash
python -m pip install yfinance pandas numpy requests
```

Run the pipeline and rebuild the dashboard:

```bash
python pipeline.py
python build_index.py
```

Then open `index.html` in a browser.

## Nightly Automation

The workflow in `.github/workflows/nightly.yml` runs at `02:00 UTC` each day and can also be triggered manually from the GitHub Actions tab.

Each run:

1. Checks out the repository.
2. Installs Python dependencies.
3. Runs `pipeline.py`.
4. Runs `build_index.py`.
5. Commits updated `huntr_scored.json` and `index.html` back to `main` if anything changed.

GitHub Pages should be configured to deploy from the `main` branch at the repository root.

## Updating The Company Universe

Edit `universe.csv` and commit the change. The expected fields are:

```csv
name,ticker,region,subsector,status,country
```

Use `status=active` for names that should be included. Set `status=delisted` to keep a name in the file but exclude it from future runs.

The next manual or scheduled workflow run will pick up the updated universe.

## Data Caveats

Huntr deliberately uses public and lightweight data sources, which keeps the project easy to run but creates limitations:

- Yahoo Finance data can be incomplete, delayed, restated, or unavailable for some tickers.
- EDGAR signals are more useful for SEC-covered or SEC-referenced situations than for all EMEA companies equally.
- Low data coverage should reduce confidence in a score.
- Extreme multiples, unusual free-float values, and stale market data should be checked manually.
- The buyer lists are curated logic, while the ranking and injected figures refresh with the latest pipeline output.

Use Huntr as a first-pass screen, then validate any interesting name with primary filings, market data, broker research, and your own judgement.

## Near-Term Priorities

- Add clearer confidence labels for low-coverage companies.
- Make every score driver traceable to source URL, source date, raw value, cleaned value, and transformation.
- Replace any illustrative charting with real historical price data in live mode.
- Add export, watchlist, and shareable-filter workflows.
- Add backtesting or decile-lift analysis once enough historical snapshots exist.

## Disclaimer

This repository contains experimental research tooling. It does not provide regulated financial advice, investment recommendations, or an offer to buy or sell securities. Always perform independent due diligence before making investment decisions.
