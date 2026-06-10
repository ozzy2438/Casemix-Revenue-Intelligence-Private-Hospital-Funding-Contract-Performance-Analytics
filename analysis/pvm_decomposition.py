import duckdb
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import WAREHOUSE_PATH


def calculate_pvm(
    df: pd.DataFrame,
    base_year: str,
    current_year: str,
) -> tuple[pd.DataFrame, dict[str, float]]:
    base_df = df[df["financial_year"] == base_year].set_index("drg_code")
    curr_df = df[df["financial_year"] == current_year].set_index("drg_code")
    all_drgs = set(base_df.index) | set(curr_df.index)
    continuing_drgs = set(base_df.index) & set(curr_df.index)

    continuing_base_seps = (
        base_df.loc[list(continuing_drgs), "separations"].sum()
        if continuing_drgs
        else 0
    )
    continuing_current_seps = (
        curr_df.loc[list(continuing_drgs), "separations"].sum()
        if continuing_drgs
        else 0
    )

    results = []
    for drg in sorted(all_drgs):
        in_base = drg in base_df.index
        in_current = drg in curr_df.index
        b_seps = float(base_df.loc[drg, "separations"]) if in_base else 0.0
        b_rev = float(base_df.loc[drg, "total_revenue"]) if in_base else 0.0
        c_seps = float(curr_df.loc[drg, "separations"]) if in_current else 0.0
        c_rev = float(curr_df.loc[drg, "total_revenue"]) if in_current else 0.0
        description = (
            base_df.loc[drg, "drg_description"]
            if in_base
            else curr_df.loc[drg, "drg_description"]
        )
        mdc = (
            base_df.loc[drg, "mdc_code"]
            if in_base
            else curr_df.loc[drg, "mdc_code"]
        )

        volume_effect = mix_effect = rate_effect = 0.0
        new_business = discontinued = 0.0
        if in_base and in_current:
            b_rate = b_rev / b_seps if b_seps else 0.0
            c_rate = c_rev / c_seps if c_seps else 0.0
            b_mix = (
                b_seps / continuing_base_seps if continuing_base_seps else 0.0
            )
            c_mix = (
                c_seps / continuing_current_seps if continuing_current_seps else 0.0
            )
            volume_effect = (
                (continuing_current_seps - continuing_base_seps) * b_mix * b_rate
            )
            mix_effect = continuing_current_seps * (c_mix - b_mix) * b_rate
            rate_effect = continuing_current_seps * c_mix * (c_rate - b_rate)
        elif in_current:
            new_business = c_rev
        else:
            discontinued = -b_rev

        total_change = c_rev - b_rev
        explained_change = (
            volume_effect
            + mix_effect
            + rate_effect
            + new_business
            + discontinued
        )
        residual = total_change - explained_change
        results.append(
            {
                "drg_code": drg,
                "drg_description": description,
                "mdc_code": mdc,
                "base_separations": b_seps,
                "current_separations": c_seps,
                "base_revenue": round(b_rev, 2),
                "current_revenue": round(c_rev, 2),
                "total_change": round(total_change, 2),
                "volume_effect": round(volume_effect, 2),
                "mix_effect": round(mix_effect, 2),
                "rate_effect": round(rate_effect, 2),
                "new_business": round(new_business, 2),
                "discontinued": round(discontinued, 2),
                "residual": round(residual, 2),
            }
        )

    pvm_df = pd.DataFrame(results)
    summary = {
        "base_revenue": float(base_df["total_revenue"].sum()),
        "current_revenue": float(curr_df["total_revenue"].sum()),
        "volume_effect": float(pvm_df["volume_effect"].sum()),
        "mix_effect": float(pvm_df["mix_effect"].sum()),
        "rate_effect": float(pvm_df["rate_effect"].sum()),
        "new_business": float(pvm_df["new_business"].sum()),
        "discontinued": float(pvm_df["discontinued"].sum()),
        "residual": float(pvm_df["residual"].sum()),
    }
    summary["total_change"] = summary["current_revenue"] - summary["base_revenue"]
    return pvm_df, summary


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

    pvm_df, summary = calculate_pvm(df, base_year, current_year)
    base_total = summary["base_revenue"]
    curr_total = summary["current_revenue"]
    total_change = summary["total_change"]

    print(f"\n  Base Year Revenue ({base_year}):    AUD {base_total:,.0f}")
    print(f"  Current Year Revenue ({current_year}): AUD {curr_total:,.0f}")
    print(f"  Total Change:                       AUD {total_change:,.0f}")
    print(f"\n  ┌─────────────────────────────────────────────────┐")
    print(f"  │  Volume Effect:  AUD {summary['volume_effect']:>14,.0f}  │")
    print(f"  │  Mix Effect:     AUD {summary['mix_effect']:>14,.0f}  │")
    print(f"  │  Rate Effect:    AUD {summary['rate_effect']:>14,.0f}  │")
    print(f"  │  New Business:   AUD {summary['new_business']:>14,.0f}  │")
    print(f"  │  Discontinued:   AUD {summary['discontinued']:>14,.0f}  │")
    print(f"  │  Residual:       AUD {summary['residual']:>14,.0f}  │")
    print(f"  └─────────────────────────────────────────────────┘")

    if total_change != 0:
        vol_pct = summary["volume_effect"] / total_change * 100
        mix_pct = summary["mix_effect"] / total_change * 100
        rate_pct = summary["rate_effect"] / total_change * 100
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
