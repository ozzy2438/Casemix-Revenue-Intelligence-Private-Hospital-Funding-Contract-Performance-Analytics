import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import WAREHOUSE_PATH


def run_margin_squeeze(base_year: str = "2022-23", current_year: str = "2023-24"):
    print("=" * 60)
    print(f"Margin Squeeze Analysis: {base_year} → {current_year}")
    print("=" * 60)
    if not WAREHOUSE_PATH.exists():
        print("  [ERROR] Warehouse not found."); return

    con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
    cost_query = """
        SELECT e.drg_code, d.drg_description, d.mdc_code, p.financial_year,
            COUNT(*) AS separations, AVG(e.estimated_cost) AS avg_cost_per_sep,
            AVG(e.contracted_rate) AS avg_revenue_per_sep
        FROM gold.fact_episodes e
        JOIN gold.dim_drg d ON e.drg_code = d.drg_code
        JOIN gold.dim_period p ON e.period_id = p.period_id
        WHERE p.financial_year IN ($1, $2)
        GROUP BY e.drg_code, d.drg_description, d.mdc_code, p.financial_year
    """
    cost_df = con.execute(cost_query, [base_year, current_year]).fetchdf()

    benefit_query = """
        SELECT p.financial_year, py.payer_name,
            SUM(hospital_benefits) AS total_hospital_benefits,
            SUM(episodes_paid) AS total_episodes,
            AVG(benefit_per_episode) AS avg_benefit_per_episode
        FROM gold.fact_phi_benefits b
        JOIN gold.dim_period p ON b.period_id = p.period_id
        JOIN gold.dim_payer py ON b.payer_id = py.payer_id
        WHERE p.financial_year IN ($1, $2)
        GROUP BY p.financial_year, py.payer_name
    """
    benefit_df = con.execute(benefit_query, [base_year, current_year]).fetchdf()
    con.close()

    if cost_df.empty:
        print("  [WARN] No episode data found."); return

    base_cost = cost_df[cost_df["financial_year"] == base_year].set_index("drg_code")
    curr_cost = cost_df[cost_df["financial_year"] == current_year].set_index("drg_code")
    squeeze_results = []

    for drg in set(base_cost.index) & set(curr_cost.index):
        b_cost = base_cost.loc[drg, "avg_cost_per_sep"]
        c_cost = curr_cost.loc[drg, "avg_cost_per_sep"]
        b_rev = base_cost.loc[drg, "avg_revenue_per_sep"]
        c_rev = curr_cost.loc[drg, "avg_revenue_per_sep"]
        cost_growth = (c_cost - b_cost) / b_cost if b_cost > 0 else 0
        revenue_growth = (c_rev - b_rev) / b_rev if b_rev > 0 else 0
        squeeze_gap = cost_growth - revenue_growth
        if squeeze_gap > 0.05: squeeze_category = "SEVERE SQUEEZE"
        elif squeeze_gap > 0.02: squeeze_category = "MODERATE SQUEEZE"
        elif squeeze_gap > 0: squeeze_category = "MILD SQUEEZE"
        elif squeeze_gap > -0.02: squeeze_category = "STABLE"
        else: squeeze_category = "IMPROVING"
        margin_base = b_rev - b_cost
        margin_curr = c_rev - c_cost
        squeeze_results.append({
            "drg_code": drg, "drg_description": base_cost.loc[drg, "drg_description"],
            "mdc_code": base_cost.loc[drg, "mdc_code"],
            "base_avg_cost": round(b_cost, 2), "current_avg_cost": round(c_cost, 2),
            "cost_growth_pct": round(cost_growth * 100, 2),
            "base_avg_revenue": round(b_rev, 2), "current_avg_revenue": round(c_rev, 2),
            "revenue_growth_pct": round(revenue_growth * 100, 2),
            "squeeze_gap_pct": round(squeeze_gap * 100, 2),
            "base_margin": round(margin_base, 2), "current_margin": round(margin_curr, 2),
            "margin_change": round(margin_curr - margin_base, 2),
            "squeeze_category": squeeze_category,
        })

    squeeze_df = pd.DataFrame(squeeze_results).sort_values("squeeze_gap_pct", ascending=False)
    print(f"\n  {'DRG':8s} {'Description':35s} {'Cost%':>7s} {'Rev%':>7s} {'Gap%':>7s} {'Category':20s}")
    print(f"  {'-'*8} {'-'*35} {'-'*7} {'-'*7} {'-'*7} {'-'*20}")
    for _, row in squeeze_df.iterrows():
        print(f"  {row['drg_code']:8s} {row['drg_description'][:35]:35s} {row['cost_growth_pct']:>+6.1f}% {row['revenue_growth_pct']:>+6.1f}% {row['squeeze_gap_pct']:>+6.1f}% {row['squeeze_category']:20s}")

    category_counts = squeeze_df["squeeze_category"].value_counts()
    print(f"\n  Squeeze Category Distribution:")
    for cat in ["SEVERE SQUEEZE", "MODERATE SQUEEZE", "MILD SQUEEZE", "STABLE", "IMPROVING"]:
        print(f"    {cat:20s}: {category_counts.get(cat, 0):3d} DRGs")

    if not benefit_df.empty:
        print(f"\n  APRA Benefit Trends by Payer:")
        for payer in benefit_df["payer_name"].unique():
            payer_data = benefit_df[benefit_df["payer_name"] == payer].sort_values("financial_year")
            if len(payer_data) >= 2:
                base_b = payer_data.iloc[0]["avg_benefit_per_episode"]
                curr_b = payer_data.iloc[-1]["avg_benefit_per_episode"]
                growth = (curr_b - base_b) / base_b * 100 if base_b > 0 else 0
                print(f"    {payer:35s}: ${base_b:,.0f} → ${curr_b:,.0f} ({growth:+.1f}%)")

    output_path = WAREHOUSE_PATH.parent / "margin_squeeze.csv"
    squeeze_df.to_csv(output_path, index=False)
    print(f"\n  Results saved to: {output_path}")
    return squeeze_df

def run():
    run_margin_squeeze()

if __name__ == "__main__":
    run()
