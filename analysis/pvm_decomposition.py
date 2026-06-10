import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import WAREHOUSE_PATH


def run_pvm(base_year: str = "2022-23", current_year: str = "2023-24"):
    print("=" * 60)
    print(f"Price-Volume-Mix Decomposition: {base_year} → {current_year}")
    print("=" * 60)
    if not WAREHOUSE_PATH.exists():
        print("  [ERROR] Warehouse not found.")
        return
    con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
    query = """
        SELECT e.drg_code, d.drg_description, d.mdc_code, p.financial_year,
            COUNT(*) AS separations, SUM(e.estimated_cost) AS total_cost,
            SUM(e.contracted_rate) AS total_revenue, SUM(e.nwau) AS total_nwau,
            AVG(e.cost_weight) AS avg_cost_weight
        FROM gold.fact_episodes e
        JOIN gold.dim_drg d ON e.drg_code = d.drg_code
        JOIN gold.dim_period p ON e.period_id = p.period_id
        WHERE p.financial_year IN ($1, $2)
        GROUP BY e.drg_code, d.drg_description, d.mdc_code, p.financial_year
    """
    df = con.execute(query, [base_year, current_year]).fetchdf()
    con.close()
    if df.empty:
        print("  [WARN] No episode data found.")
        return

    base_df = df[df["financial_year"] == base_year].set_index("drg_code")
    curr_df = df[df["financial_year"] == current_year].set_index("drg_code")
    all_drgs = set(base_df.index) | set(curr_df.index)
    pvm_results = []
    total_volume_effect = total_mix_effect = total_rate_effect = total_new_business = total_discontinued = 0.0
    base_total_seps = base_df["separations"].sum() if not base_df.empty else 1
    curr_total_seps = curr_df["separations"].sum() if not curr_df.empty else 1
    base_overall_rate = base_df["total_revenue"].sum() / base_total_seps if base_total_seps > 0 else 0

    for drg in sorted(all_drgs):
        b_seps = base_df.loc[drg, "separations"] if drg in base_df.index else 0
        b_rev = base_df.loc[drg, "total_revenue"] if drg in base_df.index else 0
        b_rate = b_rev / b_seps if b_seps > 0 else 0
        b_weight = b_seps / base_total_seps if base_total_seps > 0 else 0
        c_seps = curr_df.loc[drg, "separations"] if drg in curr_df.index else 0
        c_rev = curr_df.loc[drg, "total_revenue"] if drg in curr_df.index else 0
        c_rate = c_rev / c_seps if c_seps > 0 else 0
        c_weight = c_seps / curr_total_seps if curr_total_seps > 0 else 0
        description = (base_df.loc[drg, "drg_description"] if drg in base_df.index else
            curr_df.loc[drg, "drg_description"] if drg in curr_df.index else drg)
        mdc = (base_df.loc[drg, "mdc_code"] if drg in base_df.index else
            curr_df.loc[drg, "mdc_code"] if drg in curr_df.index else "")

        if b_seps == 0 and c_seps > 0:
            new_business = c_rev; volume_effect = mix_effect = rate_effect = 0.0
        elif c_seps == 0 and b_seps > 0:
            new_business = 0.0; discontinued = -b_rev; volume_effect = mix_effect = rate_effect = 0.0
        else:
            new_business = discontinued = 0.0
            volume_effect = (c_seps - b_seps) * b_rate
            mix_effect = c_seps * (c_weight - b_weight) * base_overall_rate
            rate_effect = c_seps * c_weight * (c_rate - base_overall_rate * b_weight / max(b_weight, 0.0001))

        total_change = c_rev - b_rev
        residual = total_change - (volume_effect + mix_effect + rate_effect + new_business + discontinued)
        pvm_results.append({
            "drg_code": drg, "drg_description": description, "mdc_code": mdc,
            "base_separations": b_seps, "current_separations": c_seps,
            "base_revenue": round(b_rev, 2), "current_revenue": round(c_rev, 2),
            "total_change": round(total_change, 2), "volume_effect": round(volume_effect, 2),
            "mix_effect": round(mix_effect, 2), "rate_effect": round(rate_effect, 2),
            "new_business": round(new_business, 2), "residual": round(residual, 2),
        })
        total_volume_effect += volume_effect
        total_mix_effect += mix_effect
        total_rate_effect += rate_effect
        total_new_business += new_business
        total_discontinued += discontinued

    pvm_df = pd.DataFrame(pvm_results)
    base_total = base_df["total_revenue"].sum() if not base_df.empty else 0
    curr_total = curr_df["total_revenue"].sum() if not curr_df.empty else 0
    total_change = curr_total - base_total

    print(f"\n  Base Year Revenue ({base_year}):    AUD {base_total:,.0f}")
    print(f"  Current Year Revenue ({current_year}): AUD {curr_total:,.0f}")
    print(f"  Total Change:                       AUD {total_change:,.0f}")
    print(f"\n  ┌─────────────────────────────────────────────────┐")
    print(f"  │  Volume Effect:  AUD {total_volume_effect:>14,.0f}  │")
    print(f"  │  Mix Effect:     AUD {total_mix_effect:>14,.0f}  │")
    print(f"  │  Rate Effect:    AUD {total_rate_effect:>14,.0f}  │")
    print(f"  │  New Business:   AUD {total_new_business:>14,.0f}  │")
    print(f"  │  Discontinued:   AUD {total_discontinued:>14,.0f}  │")
    print(f"  └─────────────────────────────────────────────────┘")

    if total_change != 0:
        vol_pct = total_volume_effect / total_change * 100
        mix_pct = total_mix_effect / total_change * 100
        rate_pct = total_rate_effect / total_change * 100
        print(f"\n  Volume: {vol_pct:+.1f}%  |  Mix: {mix_pct:+.1f}%  |  Rate: {rate_pct:+.1f}%")

    top_volume = pvm_df.nlargest(5, "volume_effect")
    print(f"\n  Top 5 DRGs by Volume Effect:")
    for _, row in top_volume.iterrows():
        print(f"    {row['drg_code']:8s} {row['drg_description'][:40]:40s} AUD {row['volume_effect']:>12,.0f}")

    output_path = WAREHOUSE_PATH.parent / "pvm_decomposition.csv"
    pvm_df.to_csv(output_path, index=False)
    print(f"\n  PVM results saved to: {output_path}")
    return pvm_df

def run():
    run_pvm()

if __name__ == "__main__":
    run()
