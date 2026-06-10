import duckdb
import numpy as np
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import WAREHOUSE_PATH, SYNTHETIC_EPISODE_COUNT, RANDOM_SEED, NWAU_PRICE_2023_24

rng = np.random.default_rng(RANDOM_SEED)

DRG_DISTRIBUTION = {
    "I23B": {"desc": "Chest Pain", "mdc": "MDC 05", "weight": 0.283, "avg_los": 1.2, "share": 0.045, "same_day_rate": 0.65},
    "I62A": {"desc": "Heart Failure & Shock w Catastrophic CC", "mdc": "MDC 05", "weight": 4.871, "avg_los": 8.5, "share": 0.012, "same_day_rate": 0.02},
    "I62B": {"desc": "Heart Failure & Shock w/o Catastrophic CC", "mdc": "MDC 05", "weight": 1.743, "avg_los": 4.8, "share": 0.025, "same_day_rate": 0.05},
    "J11A": {"desc": "Knee Replacement w Catastrophic CC", "mdc": "MDC 08", "weight": 5.672, "avg_los": 9.2, "share": 0.008, "same_day_rate": 0.0},
    "J11B": {"desc": "Knee Replacement w/o Catastrophic CC", "mdc": "MDC 08", "weight": 3.214, "avg_los": 5.8, "share": 0.018, "same_day_rate": 0.0},
    "J09A": {"desc": "Hip Replacement w Catastrophic CC", "mdc": "MDC 08", "weight": 6.123, "avg_los": 10.1, "share": 0.007, "same_day_rate": 0.0},
    "J09B": {"desc": "Hip Replacement w/o Catastrophic CC", "mdc": "MDC 08", "weight": 3.543, "avg_los": 6.2, "share": 0.015, "same_day_rate": 0.0},
    "E65A": {"desc": "Major Respiratory Procedures w Catastrophic CC", "mdc": "MDC 04", "weight": 8.234, "avg_los": 14.3, "share": 0.005, "same_day_rate": 0.0},
    "E65B": {"desc": "Major Respiratory Procedures w/o Catastrophic CC", "mdc": "MDC 04", "weight": 4.567, "avg_los": 8.7, "share": 0.009, "same_day_rate": 0.01},
    "B70A": {"desc": "Major Bladder Procedures w Catastrophic CC", "mdc": "MDC 11", "weight": 5.891, "avg_los": 9.5, "share": 0.006, "same_day_rate": 0.0},
    "B70B": {"desc": "Major Bladder Procedures w/o Catastrophic CC", "mdc": "MDC 11", "weight": 2.987, "avg_los": 5.1, "share": 0.011, "same_day_rate": 0.02},
    "D62A": {"desc": "Inguinal & Femoral Hernia Procedures w Catastrophic CC", "mdc": "MDC 06", "weight": 2.134, "avg_los": 4.2, "share": 0.014, "same_day_rate": 0.15},
    "D62B": {"desc": "Inguinal & Femoral Hernia Procedures w/o CC", "mdc": "MDC 06", "weight": 0.987, "avg_los": 1.8, "share": 0.028, "same_day_rate": 0.45},
    "F10A": {"desc": "Cholecystectomy w Catastrophic CC", "mdc": "MDC 07", "weight": 3.456, "avg_los": 6.1, "share": 0.010, "same_day_rate": 0.03},
    "F10B": {"desc": "Cholecystectomy w/o Catastrophic CC", "mdc": "MDC 07", "weight": 1.654, "avg_los": 2.9, "share": 0.022, "same_day_rate": 0.25},
    "I04A": {"desc": "Coronary Bypass w Cath w Catastrophic CC", "mdc": "MDC 05", "weight": 12.345, "avg_los": 15.2, "share": 0.003, "same_day_rate": 0.0},
    "G61A": {"desc": "Major Small & Large Bowel Procedures w Cat CC", "mdc": "MDC 06", "weight": 7.890, "avg_los": 13.4, "share": 0.006, "same_day_rate": 0.0},
    "G61B": {"desc": "Major Small & Large Bowel Procedures w/o Cat CC", "mdc": "MDC 06", "weight": 4.321, "avg_los": 7.8, "share": 0.010, "same_day_rate": 0.01},
    "H61A": {"desc": "Major Hepatobiliary Procedures w Cat CC", "mdc": "MDC 07", "weight": 9.876, "avg_los": 16.5, "share": 0.004, "same_day_rate": 0.0},
    "H61B": {"desc": "Major Hepatobiliary Procedures w/o Cat CC", "mdc": "MDC 07", "weight": 5.432, "avg_los": 9.1, "share": 0.007, "same_day_rate": 0.0},
    "E71A": {"desc": "Chest Pain", "mdc": "MDC 04", "weight": 0.543, "avg_los": 1.5, "share": 0.035, "same_day_rate": 0.70},
    "K60A": {"desc": "Kidney Transplant", "mdc": "MDC 11", "weight": 15.432, "avg_los": 18.7, "share": 0.002, "same_day_rate": 0.0},
    "R63A": {"desc": "Admit for Rehab w Catastrophic CC", "mdc": "MDC 19", "weight": 3.210, "avg_los": 22.5, "share": 0.008, "same_day_rate": 0.0},
    "R63B": {"desc": "Admit for Rehab w/o Catastrophic CC", "mdc": "MDC 19", "weight": 1.876, "avg_los": 14.3, "share": 0.012, "same_day_rate": 0.0},
    "U62A": {"desc": "Chemotherapy w Catastrophic CC", "mdc": "MDC 22", "weight": 2.345, "avg_los": 4.8, "share": 0.015, "same_day_rate": 0.10},
    "U62B": {"desc": "Chemotherapy w/o Catastrophic CC", "mdc": "MDC 22", "weight": 0.876, "avg_los": 1.2, "share": 0.030, "same_day_rate": 0.55},
    "Z60A": {"desc": "Oth Factors Influencing Health Status", "mdc": "MDC 23", "weight": 0.654, "avg_los": 2.1, "share": 0.020, "same_day_rate": 0.40},
    "A06A": {"desc": "Tracheostomy w MV >96h w Cat CC", "mdc": "MDC 01", "weight": 22.345, "avg_los": 35.2, "share": 0.001, "same_day_rate": 0.0},
    "L61A": {"desc": "Major Skin Procedures w Cat CC", "mdc": "MDC 12", "weight": 4.567, "avg_los": 8.9, "share": 0.008, "same_day_rate": 0.01},
    "L61B": {"desc": "Major Skin Procedures w/o Cat CC", "mdc": "MDC 12", "weight": 2.345, "avg_los": 3.7, "share": 0.016, "same_day_rate": 0.08},
    "O61A": {"desc": "Major Procedures for Reproductive Sys w Cat CC", "mdc": "MDC 13", "weight": 3.210, "avg_los": 6.5, "share": 0.009, "same_day_rate": 0.02},
    "O61B": {"desc": "Major Procedures for Reproductive Sys w/o CC", "mdc": "MDC 13", "weight": 1.543, "avg_los": 2.8, "share": 0.019, "same_day_rate": 0.20},
}

PAYER_MIX = {1: 0.25, 2: 0.22, 3: 0.12, 4: 0.08, 5: 0.06, 6: 0.04, 7: 0.18, 8: 0.05}
HOSPITAL_WEIGHTS = {1: 0.30, 2: 0.25, 3: 0.15, 4: 0.12, 5: 0.18}
CONTRACTED_RATE_MARKUP = {1: 1.05, 2: 1.03, 3: 1.08, 4: 0.98, 5: 1.02, 6: 1.00, 7: 0.85, 8: 1.10}


MDC_DESCRIPTIONS = {
    "MDC 01": "Diseases & Disorders of the Nervous System",
    "MDC 04": "Diseases & Disorders of the Respiratory System",
    "MDC 05": "Diseases & Disorders of the Circulatory System",
    "MDC 06": "Diseases & Disorders of the Digestive System",
    "MDC 07": "Diseases & Disorders of the Hepatobiliary System & Pancreas",
    "MDC 08": "Diseases & Disorders of the Musculoskeletal System & Connective Tissue",
    "MDC 11": "Diseases & Disorders of the Kidney & Urinary Tract",
    "MDC 12": "Diseases & Disorders of the Skin, Subcutaneous Tissue & Breast",
    "MDC 13": "Diseases & Disorders of the Female Reproductive System",
    "MDC 19": "Mental Diseases & Disorders (Rehabilitation)",
    "MDC 22": "Burns",
    "MDC 23": "Factors Influencing Health Status & Other Contacts with Health Services",
}


def generate_drg_dimension() -> pd.DataFrame:
    records = []
    for drg_code, info in DRG_DISTRIBUTION.items():
        records.append({
            "drg_code": drg_code, "drg_description": info["desc"],
            "mdc_code": info["mdc"],
            "mdc_description": MDC_DESCRIPTIONS.get(info["mdc"], info["mdc"]),
            "partition_flag": "A" if "Catastrophic" in info["desc"] else "B",
            "drg_version": "AR-DRG v11.0",
            "same_day_flag": info["same_day_rate"] > 0.5,
            "medical_surgical": "Surgical" if any(kw in info["desc"] for kw in ["Replacement","Procedures","Transplant","Bypass","Cholecystectomy","Hernia"]) else "Medical",
            "effective_from": "2021-07-01", "effective_to": None,
        })
    return pd.DataFrame(records)


def generate_episodes(n: int = SYNTHETIC_EPISODE_COUNT) -> pd.DataFrame:
    drg_codes = list(DRG_DISTRIBUTION.keys())
    shares = np.array([DRG_DISTRIBUTION[d]["share"] for d in drg_codes])
    shares = shares / shares.sum()
    drg_assignments = rng.choice(drg_codes, size=n, p=shares)

    payer_ids = list(PAYER_MIX.keys())
    payer_probs = np.array([PAYER_MIX[p] for p in payer_ids])
    payer_probs = payer_probs / payer_probs.sum()

    hospital_ids = list(HOSPITAL_WEIGHTS.keys())
    hospital_probs = np.array([HOSPITAL_WEIGHTS[h] for h in hospital_ids])
    hospital_probs = hospital_probs / hospital_probs.sum()

    period_ids = list(range(5, 13))
    period_probs = np.array([0.10, 0.10, 0.10, 0.10, 0.15, 0.15, 0.15, 0.15])
    period_probs = period_probs / period_probs.sum()

    episodes = []
    for i, drg_code in enumerate(drg_assignments):
        info = DRG_DISTRIBUTION[drg_code]
        cost_weight = info["weight"] * rng.lognormal(0, 0.05)
        cost_weight = max(0.01, cost_weight)
        avg_los = info["avg_los"]
        los = max(0, rng.lognormal(np.log(avg_los), 0.4))
        los = round(los, 1)
        is_same_day = rng.random() < info["same_day_rate"]
        if is_same_day:
            los = 0.0
        nwau = cost_weight
        estimated_cost = cost_weight * NWAU_PRICE_2023_24 * rng.lognormal(0, 0.08)
        payer_id = rng.choice(payer_ids, p=payer_probs)
        hospital_id = rng.choice(hospital_ids, p=hospital_probs)
        period_id = rng.choice(period_ids, p=period_probs)
        markup = CONTRACTED_RATE_MARKUP[payer_id]
        contracted_rate = estimated_cost * markup * rng.lognormal(0, 0.03)
        is_outlier = los > avg_los * 3
        episodes.append({
            "episode_id": i + 1, "drg_code": drg_code,
            "hospital_id": int(hospital_id), "payer_id": int(payer_id),
            "period_id": int(period_id), "los": los,
            "cost_weight": round(cost_weight, 4), "nwau": round(nwau, 4),
            "estimated_cost": round(estimated_cost, 2),
            "contracted_rate": round(contracted_rate, 2),
            "is_same_day": is_same_day, "is_outlier": is_outlier,
            "is_synthetic": True, "source": "synthetic_calibrated",
        })
    return pd.DataFrame(episodes)


def generate_apra_benefits() -> pd.DataFrame:
    states = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"]
    quarters = list(range(1, 13))
    base_benefit_per_episode = 4500
    records = []
    for period_id in quarters:
        growth_factor = 1.0 + 0.02 * (period_id - 1) / 4
        for state in states:
            state_adj = {"NSW": 1.05, "VIC": 1.02, "QLD": 0.98, "WA": 1.03, "SA": 0.95, "TAS": 0.90, "ACT": 1.00, "NT": 0.88}
            for payer_id in [1, 2, 3, 4, 5]:
                benefit = base_benefit_per_episode * growth_factor * state_adj.get(state, 1.0) * rng.lognormal(0, 0.05)
                membership = int(rng.lognormal(np.log(500000), 0.3) * (1 + 0.01 * (period_id - 1) / 4))
                episodes_paid = int(membership * rng.uniform(0.01, 0.03))
                records.append({
                    "period_id": period_id, "payer_id": payer_id, "state": state,
                    "hospital_benefits": round(benefit * episodes_paid, 2),
                    "medical_benefits": round(benefit * episodes_paid * 0.3, 2),
                    "total_benefits": round(benefit * episodes_paid * 1.3, 2),
                    "membership_count": membership, "episodes_paid": episodes_paid,
                    "benefit_per_episode": round(benefit, 2), "source_file": "synthetic_apra",
                })
    return pd.DataFrame(records)


def load_into_warehouse():
    print("=" * 60)
    print("Generating & Loading Synthetic Data...")
    print("=" * 60)
    if not WAREHOUSE_PATH.exists():
        print("  [ERROR] Warehouse not found. Run models/star_schema.py first.")
        return
    con = duckdb.connect(str(WAREHOUSE_PATH))

    drg_df = generate_drg_dimension()
    con.execute("DELETE FROM gold.dim_drg")
    con.register("staging_dim_drg", drg_df)
    con.execute("""
        INSERT INTO gold.dim_drg (drg_code, drg_description, mdc_code, mdc_description,
            partition_flag, drg_version, same_day_flag, medical_surgical, effective_from, effective_to)
        SELECT drg_code, drg_description, mdc_code, mdc_description,
            partition_flag, drg_version, same_day_flag, medical_surgical, effective_from, effective_to
        FROM staging_dim_drg
    """)
    print(f"  Loaded dim_drg: {len(drg_df)} DRGs")

    episodes_df = generate_episodes()
    con.execute("DELETE FROM gold.fact_episodes")
    con.register("staging_episodes", episodes_df)
    con.execute("INSERT INTO gold.fact_episodes SELECT * FROM staging_episodes")
    print(f"  Loaded fact_episodes: {len(episodes_df):,} episodes")

    benefits_df = generate_apra_benefits()
    con.execute("DELETE FROM gold.fact_phi_benefits")
    con.register("staging_benefits", benefits_df)
    con.execute("""
        INSERT INTO gold.fact_phi_benefits
        (period_id, payer_id, state, hospital_benefits, medical_benefits,
         total_benefits, membership_count, episodes_paid, benefit_per_episode, source_file)
        SELECT period_id, payer_id, state, hospital_benefits, medical_benefits,
         total_benefits, membership_count, episodes_paid, benefit_per_episode, source_file
        FROM staging_benefits
    """)
    print(f"  Loaded fact_phi_benefits: {len(benefits_df):,} records")

    total_episodes = con.execute("SELECT COUNT(*) FROM gold.fact_episodes").fetchone()[0]
    total_drgs = con.execute("SELECT COUNT(*) FROM gold.dim_drg").fetchone()[0]
    total_benefits = con.execute("SELECT COUNT(*) FROM gold.fact_phi_benefits").fetchone()[0]
    print(f"\n  Summary: {total_drgs} DRGs, {total_episodes:,} episodes, {total_benefits:,} benefit records")
    con.close()
    print(f"  Warehouse updated: {WAREHOUSE_PATH}")


def run():
    load_into_warehouse()

if __name__ == "__main__":
    run()
