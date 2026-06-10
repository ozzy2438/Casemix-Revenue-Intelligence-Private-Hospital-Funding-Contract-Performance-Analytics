from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from config import WAREHOUSE_PATH


EXPORT_QUERIES = {
    "dim_drg": "SELECT * FROM gold.dim_drg ORDER BY drg_code",
    "dim_hospital": "SELECT * FROM gold.dim_hospital ORDER BY hospital_id",
    "dim_payer": "SELECT * FROM gold.dim_payer ORDER BY payer_id",
    "dim_period": "SELECT * FROM gold.dim_period ORDER BY period_id",
    "fact_episodes": "SELECT * FROM gold.fact_episodes ORDER BY episode_id",
    "fact_national_costs": (
        "SELECT * FROM gold.fact_national_costs ORDER BY period_id, drg_code"
    ),
    "fact_phi_benefits": (
        "SELECT * FROM gold.fact_phi_benefits ORDER BY period_id, payer_id, state"
    ),
    "casemix_index": (
        "SELECT * FROM gold.v_casemix_index ORDER BY financial_year, hospital_name"
    ),
    "drg_revenue": (
        "SELECT * FROM gold.v_drg_revenue ORDER BY financial_year, drg_code"
    ),
    "payer_performance": (
        "SELECT * FROM gold.v_payer_performance ORDER BY financial_year, payer_name"
    ),
}

ANALYSIS_OUTPUTS = (
    "pvm_decomposition.csv",
    "margin_squeeze.csv",
    "contract_scenarios.csv",
    "forecasts.csv",
)


def export_powerbi_data(output_dir: Path) -> dict[str, int]:
    if not WAREHOUSE_PATH.exists():
        raise FileNotFoundError(
            f"Warehouse not found at {WAREHOUSE_PATH}. Run python -m scripts.build_demo."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    row_counts: dict[str, int] = {}
    con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
    try:
        for name, query in EXPORT_QUERIES.items():
            frame = con.execute(query).fetchdf()
            frame.to_csv(output_dir / f"{name}.csv", index=False)
            row_counts[name] = len(frame)
    finally:
        con.close()

    for filename in ANALYSIS_OUTPUTS:
        source = WAREHOUSE_PATH.parent / filename
        if source.exists():
            frame = pd.read_csv(source)
            name = source.stem
            frame.to_csv(output_dir / filename, index=False)
            row_counts[name] = len(frame)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "warehouse": str(WAREHOUSE_PATH),
        "tables": row_counts,
        "synthetic_episode_data": True,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    return row_counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Power BI-ready CSV extracts.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "exports",
        help="Directory for generated CSV files and manifest.json.",
    )
    args = parser.parse_args()
    row_counts = export_powerbi_data(args.output)

    print(f"Power BI extracts written to: {args.output.resolve()}")
    for name, count in sorted(row_counts.items()):
        print(f"  {name:24s} {count:>10,} rows")


if __name__ == "__main__":
    main()
