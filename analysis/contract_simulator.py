import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import WAREHOUSE_PATH, CONTRACT_SCENARIOS, NWAU_PRICE_2023_24


def get_current_activity(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    query = """
        SELECT e.drg_code, d.drg_description, AVG(e.cost_weight) AS avg_cost_weight,
            AVG(e.estimated_cost) AS avg_cost, AVG(e.los) AS avg_los, COUNT(*) AS separations
        FROM gold.fact_episodes e
        JOIN gold.dim_drg d ON e.drg_code = d.drg_code
        JOIN gold.dim_period p ON e.period_id = p.period_id
        WHERE p.is_current = TRUE
        GROUP BY e.drg_code, d.drg_description
    """
    return con.execute(query).fetchdf()


def simulate_drg_contract(activity, indexation, years=3, base_nwau_price=NWAU_PRICE_2023_24, outlier_cap_pct=0.8):
    results = []
    current_price = base_nwau_price
    for year in range(1, years + 1):
        current_price *= (1 + indexation)
        total_revenue = total_cost = outlier_cost = outlier_shortfall = 0.0
        for _, row in activity.iterrows():
            cw = row["avg_cost_weight"]; ac = row["avg_cost"]; seps = row["separations"]
            rev_per_sep = cw * current_price
            outlier_rate = min(0.02 + 0.01 * (cw / 10), 0.15)
            normal = int(seps * (1 - outlier_rate)); out = seps - normal
            out_cost = ac * (1 + cw / 5)
            total_revenue += normal * rev_per_sep + out * rev_per_sep * outlier_cap_pct
            total_cost += normal * ac + out * out_cost
            outlier_shortfall += out * (out_cost - rev_per_sep * outlier_cap_pct)
        margin = total_revenue - total_cost
        results.append({"year": f"Year {year} ({2024+year})", "contract_type": "DRG-based",
            "indexation_pct": indexation * 100, "nwau_price": round(current_price, 2),
            "total_revenue": round(total_revenue, 2), "total_cost": round(total_cost, 2),
            "margin": round(margin, 2), "margin_pct": round(margin/total_revenue*100, 2) if total_revenue else 0,
            "outlier_shortfall": round(outlier_shortfall, 2)})
    return pd.DataFrame(results)


def simulate_per_diem_contract(activity, indexation, daily_rate, years=3):
    results = []
    current_rate = daily_rate
    for year in range(1, years + 1):
        current_rate *= (1 + indexation)
        total_revenue = total_cost = 0.0
        for _, row in activity.iterrows():
            eff_los = max(row["avg_los"], 1.0)
            total_revenue += row["separations"] * eff_los * current_rate
            total_cost += row["separations"] * row["avg_cost"]
        margin = total_revenue - total_cost
        results.append({"year": f"Year {year} ({2024+year})", "contract_type": "Per-Diem",
            "indexation_pct": indexation * 100, "daily_rate": round(current_rate, 2),
            "total_revenue": round(total_revenue, 2), "total_cost": round(total_cost, 2),
            "margin": round(margin, 2), "margin_pct": round(margin/total_revenue*100, 2) if total_revenue else 0,
            "outlier_shortfall": 0.0})
    return pd.DataFrame(results)


def run():
    print("=" * 60)
    print("Contract Scenario Simulator")
    print("=" * 60)
    if not WAREHOUSE_PATH.exists():
        print("  [ERROR] Warehouse not found."); return
    con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
    activity = get_current_activity(con)
    con.close()
    if activity.empty:
        print("  [WARN] No current activity data."); return
    print(f"  Activity: {len(activity)} DRGs, {activity['separations'].sum():,.0f} separations")
    all_scenarios = []
    for name, params in CONTRACT_SCENARIOS.items():
        print(f"\n  ── Scenario: {name} ({params['type']}, {params['indexation']*100:.0f}% idx) ──")
        if params["type"] == "drg":
            result = simulate_drg_contract(activity, indexation=params["indexation"])
        else:
            result = simulate_per_diem_contract(activity, indexation=params["indexation"], daily_rate=params.get("daily_rate", 1200))
        result["scenario"] = name
        all_scenarios.append(result)
        print(f"  {'Year':18s} {'Revenue':>14s} {'Cost':>14s} {'Margin':>14s} {'Margin%':>8s}")
        for _, r in result.iterrows():
            print(f"  {r['year']:18s} AUD {r['total_revenue']:>12,.0f} AUD {r['total_cost']:>12,.0f} AUD {r['margin']:>12,.0f} {r['margin_pct']:>7.1f}%")

    if all_scenarios:
        combined = pd.concat(all_scenarios, ignore_index=True)
        output_path = WAREHOUSE_PATH.parent / "contract_scenarios.csv"
        combined.to_csv(output_path, index=False)
        print(f"\n  Scenarios saved to: {output_path}")
        summary = combined.groupby("scenario").agg({"total_revenue": "sum", "total_cost": "sum", "margin": "sum"}).reset_index()
        summary["margin_pct"] = (summary["margin"] / summary["total_revenue"] * 100).round(2)
        summary = summary.sort_values("margin", ascending=False)
        print(f"\n  {'Scenario':25s} {'3Y Revenue':>14s} {'3Y Margin':>14s} {'3Y Margin%':>10s}")
        for _, r in summary.iterrows():
            print(f"  {r['scenario']:25s} AUD {r['total_revenue']:>12,.0f} AUD {r['margin']:>12,.0f} {r['margin_pct']:>9.1f}%")
        best = summary.iloc[0]; worst = summary.iloc[-1]
        print(f"\n  ★ Best: {best['scenario']} (AUD {best['margin']:,.0f}, {best['margin_pct']:.1f}%)")
        print(f"  ✗ Worst: {worst['scenario']} (AUD {worst['margin']:,.0f}, {worst['margin_pct']:.1f}%)")

if __name__ == "__main__":
    run()
