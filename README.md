# Casemix Revenue Intelligence — Private Hospital Funding & Contract Performance Analytics

*A commercial analytics build for private hospital health-fund revenue management, constructed entirely on Australia's national hospital costing (IHACPA NHCDC), activity (AIHW) and private health insurance (APRA) datasets.*

---

## Engagement Context

This project replicates the core analytical workload of a Health Funds Team within a private hospital group (modeled on St John of God Health Care's commercial structure). The objective is to build end-to-end revenue intelligence: from raw national data ingestion, through star schema warehousing, to commercial analytics outputs including price-volume-mix variance decomposition, margin squeeze detection, contract scenario modelling, and operational forecasting.

**This is not a portfolio project.** It is a consulting-grade engagement deliverable, built with the discipline of a professional services team: data dictionary, methodology documentation, quality gates, and auditable assumptions.

---

## Data Sources

| Source | Agency | Purpose | Format |
|--------|--------|---------|--------|
| NHCDC Public Sector Cost Weights (AR-DRG v11.0) | IHACPA | Cost per separation, cost weights, NWAU | XLSX |
| NHCDC Private Sector Report 2022-23 | IHACPA | Private hospital cost benchmarks | PDF/XLSX |
| AR-DRG Data Cubes | AIHW | Separation volumes by DRG, age, sex, same-day | XLSX |
| MyHospitals API | AIHW | Hospital-level activity metrics | JSON/CSV |
| Quarterly PHI Statistics | APRA | Health fund benefits, payer mix, membership | XLSX |

All data is publicly available under Australian government open data licensing (CC-BY where applicable).

---

## Episode-Level Data — Professional Approach

Patient-level episode data is not publicly available due to privacy legislation (Australian Privacy Act 1988, Healthcare Identifiers Act 2010). Instead, this project generates a **synthetically generated, nationally calibrated episode-level dataset** using published aggregate distributions:

- DRG separation distributions from AIHW data cubes
- Cost weights from IHACPA NHCDC
- Payer mix proportions from APRA quarterly statistics
- Length of stay calibrated to DRG averages with lognormal variance

This methodology is documented in `docs/methodology.md` and is the same approach used by consulting firms in demo/test environments.

---

## Project Structure

```
casemix-revenue-intelligence/
├── README.md                    ← This file — engagement context
├── requirements.txt             ← Python dependencies
├── config.py                    ← Centralised configuration (paths, URLs, params)
├── docs/
│   ├── methodology.md           ← Synthetic data calibration, PVM formulas, assumptions
│   └── data_dictionary.md       ← Every table, column, type, grain, and business definition
├── ingestion/
│   ├── download_ihacpa.py       ← NHCDC cost weights & private sector data
│   ├── download_aihw.py         ← AR-DRG data cubes & MyHospitals downloads
│   ├── download_apra.py         ← Quarterly PHI statistics
│   ├── myhospitals_api.py       ← MyHospitals API client
│   └── run_ingestion.py         ← Master ingestion orchestrator
├── models/
│   ├── star_schema.py           ← DuckDB star schema DDL & ETL
│   └── data_quality.py          ← 20+ data quality tests (pytest-compatible)
├── simulation/
│   └── synthetic_episodes.py    ← Calibrated synthetic episode generator
├── analysis/
│   ├── pvm_decomposition.py     ← Price-Volume-Mix variance decomposition
│   ├── margin_squeeze.py        ← Margin squeeze detection (cost vs benefit growth)
│   ├── forecast.py              ← SARIMAX/Prophet forecasting
│   └── contract_simulator.py    ← Contract scenario modelling (DRG-based vs per-diem)
└── powerbi/
    └── (Phase 2 — .pbix dashboard)
```

---

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate        # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

python -m ingestion.run_ingestion      # Download data from IHACPA/AIHW/APRA
python -m models.star_schema           # Build DuckDB warehouse
python -m simulation.synthetic_episodes  # Generate calibrated synthetic data
pytest models/data_quality.py -v       # Run 20+ data quality tests
python -m analysis.pvm_decomposition   # Price-Volume-Mix analysis
python -m analysis.margin_squeeze      # Margin squeeze detection
python -m analysis.forecast            # SARIMAX + Prophet forecasts
python -m analysis.contract_simulator  # Contract scenario comparison
```

---

## Technical Stack

| Component | Technology |
|-----------|-----------|
| Data Warehouse | DuckDB (embedded OLAP) |
| ETL | Python (pandas, requests, beautifulsoup4) |
| Data Quality | pytest + custom framework |
| Analytics | pandas, numpy, scipy |
| Forecasting | statsmodels (SARIMAX), prophet |
| Visualisation | matplotlib, plotly |
| API Client | httpx (MyHospitals API) |

---

## Design Decisions

1. **DuckDB over PostgreSQL**: Embedded, zero-config, columnar storage optimised for OLAP.
2. **Medallion architecture (Bronze → Silver → Gold)**: Industry-standard data platform pattern.
3. **Synthetic data with calibration**: Honesty about data provenance is professional virtue.
4. **pytest for data quality**: Industry standard, CI/CD compatible.
5. **Separation of ingestion from analysis**: Each stage is independently runnable.

---

## Roadmap (Phase 2)

- MyHospitals API integration
- IHACPA National Efficient Price Determination
- Power BI .pbix dashboard (4 pages)
- Executive summary PDF generation
- Streamlit contract scenario what-if tool
- CI/CD pipeline with GitHub Actions

---

## License

MIT License. Data subject to original agencies' licensing terms (CC-BY 4.0).
