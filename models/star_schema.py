import duckdb
from pathlib import Path
import sys
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import WAREHOUSE_PATH, DATA_RAW, DATA_SILVER, DATA_GOLD

WAREHOUSE_PATH.parent.mkdir(parents=True, exist_ok=True)

SCHEMA_DDL = """

CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

CREATE SEQUENCE IF NOT EXISTS cost_seq START 1;
CREATE SEQUENCE IF NOT EXISTS benefit_seq START 1;
CREATE SEQUENCE IF NOT EXISTS episode_seq START 1;

CREATE TABLE IF NOT EXISTS gold.dim_drg (
    drg_code         VARCHAR PRIMARY KEY,
    drg_description  VARCHAR,
    mdc_code         VARCHAR,
    mdc_description  VARCHAR,
    partition_flag   VARCHAR,
    drg_version      VARCHAR DEFAULT 'AR-DRG v11.0',
    same_day_flag    BOOLEAN,
    medical_surgical VARCHAR,
    effective_from   DATE DEFAULT '2020-07-01',
    effective_to     DATE
);

CREATE TABLE IF NOT EXISTS gold.dim_hospital (
    hospital_id          INTEGER PRIMARY KEY,
    hospital_name        VARCHAR,
    state                VARCHAR,
    peer_group           VARCHAR,
    sector               VARCHAR DEFAULT 'private',
    local_hospital_network VARCHAR,
    beds                 INTEGER,
    effective_from       DATE,
    effective_to         DATE
);

CREATE TABLE IF NOT EXISTS gold.dim_payer (
    payer_id      INTEGER PRIMARY KEY,
    payer_name    VARCHAR,
    payer_type    VARCHAR,
    fund_category VARCHAR,
    effective_from DATE,
    effective_to   DATE
);

CREATE TABLE IF NOT EXISTS gold.dim_period (
    period_id     INTEGER PRIMARY KEY,
    financial_year VARCHAR,
    quarter        VARCHAR,
    quarter_start  DATE,
    quarter_end    DATE,
    is_current     BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS gold.fact_national_costs (
    cost_id             INTEGER PRIMARY KEY DEFAULT nextval('cost_seq'),
    drg_code            VARCHAR,
    period_id           INTEGER REFERENCES gold.dim_period(period_id),
    sector              VARCHAR,
    cost_weight         DOUBLE,
    average_los         DOUBLE,
    cost_per_separation DOUBLE,
    nwau_per_separation DOUBLE,
    separation_count    BIGINT,
    total_cost           DOUBLE,
    source_file          VARCHAR
);

CREATE TABLE IF NOT EXISTS gold.fact_phi_benefits (
    benefit_id          INTEGER PRIMARY KEY DEFAULT nextval('benefit_seq'),
    period_id           INTEGER REFERENCES gold.dim_period(period_id),
    payer_id            INTEGER REFERENCES gold.dim_payer(payer_id),
    state               VARCHAR,
    hospital_benefits   DOUBLE,
    medical_benefits    DOUBLE,
    total_benefits      DOUBLE,
    membership_count    BIGINT,
    episodes_paid       BIGINT,
    benefit_per_episode DOUBLE,
    source_file         VARCHAR
);

CREATE TABLE IF NOT EXISTS gold.fact_episodes (
    episode_id          INTEGER PRIMARY KEY DEFAULT nextval('episode_seq'),
    drg_code            VARCHAR REFERENCES gold.dim_drg(drg_code),
    hospital_id         INTEGER REFERENCES gold.dim_hospital(hospital_id),
    payer_id            INTEGER REFERENCES gold.dim_payer(payer_id),
    period_id           INTEGER REFERENCES gold.dim_period(period_id),
    los                 DOUBLE,
    cost_weight         DOUBLE,
    nwau                DOUBLE,
    estimated_cost      DOUBLE,
    contracted_rate     DOUBLE,
    is_same_day         BOOLEAN,
    is_outlier          BOOLEAN,
    is_synthetic        BOOLEAN DEFAULT TRUE,
    source              VARCHAR DEFAULT 'synthetic_calibrated'
);


CREATE OR REPLACE VIEW gold.v_casemix_index AS
SELECT
    h.hospital_id,
    h.hospital_name,
    h.peer_group,
    p.financial_year,
    SUM(e.nwau) AS total_nwau,
    COUNT(*) AS total_separations,
    SUM(e.nwau) / NULLIF(COUNT(*), 0) AS casemix_index,
    SUM(e.estimated_cost) AS total_cost,
    SUM(e.estimated_cost) / NULLIF(COUNT(*), 0) AS cost_per_separation
FROM gold.fact_episodes e
JOIN gold.dim_hospital h ON e.hospital_id = h.hospital_id
JOIN gold.dim_period p ON e.period_id = p.period_id
GROUP BY h.hospital_id, h.hospital_name, h.peer_group, p.financial_year;

CREATE OR REPLACE VIEW gold.v_drg_revenue AS
SELECT
    d.drg_code,
    d.drg_description,
    d.mdc_code,
    p.financial_year,
    COUNT(*) AS separations,
    SUM(e.nwau) AS total_nwau,
    AVG(e.cost_weight) AS avg_cost_weight,
    SUM(e.estimated_cost) AS total_cost,
    SUM(e.contracted_rate) AS total_revenue,
    SUM(e.contracted_rate) - SUM(e.estimated_cost) AS margin,
    (SUM(e.contracted_rate) - SUM(e.estimated_cost)) / NULLIF(SUM(e.contracted_rate), 0) AS margin_pct
FROM gold.fact_episodes e
JOIN gold.dim_drg d ON e.drg_code = d.drg_code
JOIN gold.dim_period p ON e.period_id = p.period_id
GROUP BY d.drg_code, d.drg_description, d.mdc_code, p.financial_year;

CREATE OR REPLACE VIEW gold.v_payer_performance AS
SELECT
    py.payer_name,
    py.payer_type,
    p.financial_year,
    COUNT(*) AS separations,
    SUM(e.estimated_cost) AS total_cost,
    SUM(e.contracted_rate) AS total_revenue,
    SUM(e.contracted_rate) - SUM(e.estimated_cost) AS margin,
    (SUM(e.contracted_rate) - SUM(e.estimated_cost)) / NULLIF(SUM(e.contracted_rate), 0) AS margin_pct
FROM gold.fact_episodes e
JOIN gold.dim_payer py ON e.payer_id = py.payer_id
JOIN gold.dim_period p ON e.period_id = p.period_id
GROUP BY py.payer_name, py.payer_type, p.financial_year;
"""


def load_nhcdc_to_warehouse(con: duckdb.DuckDBPyConnection):
    nhcdc_dir = DATA_RAW / "ihacpa"
    if not nhcdc_dir.exists():
        print("  [SKIP] No IHACPA raw data found.")
        return
    
    file_path = nhcdc_dir / "nhcdc_cost_weights_ar-drg_version_11.0_2020-21_0.xlsx"
    if not file_path.exists():
        print("  [SKIP] IHACPA cost weights file not found.")
        return
        
    print(f"  Processing IHACPA file: {file_path.name}")
    try:
        # Read the 'National' sheet, skipping the first 4 rows of headers
        df = pd.read_excel(file_path, sheet_name="National", skiprows=4, engine="openpyxl")
        
        # Rename columns to standard names
        df = df.rename(columns={
            "Unnamed: 0": "drg_code", 
            "Cost": "cost_weight",
            "No. of ": "separation_count",
            "ALOS": "average_los",
            "Total": "cost_per_separation"
        })
        
        # Filter out sub-totals and invalid rows
        df = df[df["drg_code"].str.match(r"^[A-Z0-9]{3}[A-Z]$", na=False)].copy()
        
        # Select only the needed columns
        df_clean = df[["drg_code", "cost_weight", "separation_count", "average_los", "cost_per_separation"]]
        df_clean["period_id"] = 1
        df_clean["sector"] = "public"
        df_clean["nwau_per_separation"] = df_clean["cost_weight"]
        df_clean["source_file"] = file_path.name
        
        con.register("staging_nhcdc", df_clean)
        
        # Clear existing synthetic data and insert real data
        con.execute("DELETE FROM gold.fact_national_costs WHERE sector = 'public'")
        con.execute("""
            INSERT INTO gold.fact_national_costs
            (drg_code, period_id, sector, cost_weight, average_los,
             cost_per_separation, nwau_per_separation, separation_count, source_file)
            SELECT drg_code, period_id, sector, cost_weight, average_los,
                   cost_per_separation, nwau_per_separation, separation_count, source_file
            FROM staging_nhcdc
        """)
        print(f"    Loaded {len(df_clean)} real cost weight records into gold.fact_national_costs")
    except Exception as e:
        print(f"    [ERROR] Processing IHACPA data: {e}")


def load_aihw_to_warehouse(con: duckdb.DuckDBPyConnection):
    aihw_dir = DATA_RAW / "aihw"
    if not aihw_dir.exists():
        print("  [SKIP] No AIHW raw data found.")
        return
        
    file_path = aihw_dir / "Australian-Refined-Diagnosis-Related-Group-cube-2023-24.xlsx"
    if not file_path.exists():
        print("  [SKIP] AIHW DRG cube file not found.")
        return
        
    print(f"  Processing AIHW file: {file_path.name}")
    try:
        # Read the 'DRG Counts Data' sheet, skipping 4 header rows
        df = pd.read_excel(file_path, sheet_name="DRG Counts Data", skiprows=4, engine="openpyxl")
        
        # Rename columns for database use
        df = df.rename(columns={
            "DRG V11.0": "drg_code",
            "Separations": "separations",
            "Patient Days": "patient_days"
        })
        
        # Extract the 4-character DRG code (e.g. "A13A" from "A13A Ventilation >= 336...")
        df["drg_code"] = df["drg_code"].str[:4]
        
        # Filter valid DRG codes only
        df = df[df["drg_code"].str.match(r"^[A-Z0-9]{3}[A-Z]$", na=False)].copy()
        
        # Aggregate by DRG code (summing public and private sector splits if any)
        df_grouped = df.groupby("drg_code", as_index=False)[["separations", "patient_days"]].sum()
        df_grouped["average_los"] = df_grouped["patient_days"] / df_grouped["separations"]
        
        con.register("staging_aihw", df_grouped)
        
        # Create a table in silver schema to store these national volumes
        con.execute("DROP TABLE IF EXISTS silver.aihw_drg_volumes")
        con.execute("""
            CREATE TABLE silver.aihw_drg_volumes AS
            SELECT drg_code, separations, patient_days, average_los
            FROM staging_aihw
        """)
        print(f"    Loaded {len(df_grouped)} DRG volume records into silver.aihw_drg_volumes")
    except Exception as e:
        print(f"    [ERROR] Processing AIHW data: {e}")


def load_apra_to_warehouse(con: duckdb.DuckDBPyConnection):
    apra_dir = DATA_RAW / "apra"
    if not apra_dir.exists():
        print("  [SKIP] No APRA raw data found.")
        return
        
    file_path = apra_dir / "Quarterly Private Health Insurance Benefit Trends March 2026 (2).xlsx"
    if not file_path.exists():
        print("  [SKIP] APRA Benefit Trends file not found.")
        return
        
    print(f"  Processing APRA file: {file_path.name}")
    try:
        # Read the 'DataAcuteHospital' sheet
        df = pd.read_excel(file_path, sheet_name="DataAcuteHospital", engine="openpyxl")
        
        # We need specific columns: State, MonthEnd, Episodes, BenefitsPaid
        # Ensure we don't pick up the first row which usually has metric labels
        df_clean = df[["State.1", "MonthEnd", "Episodes", "BenefitsPaid"]].copy()
        df_clean = df_clean.rename(columns={"State.1": "state"})
        
        # Drop rows where state is NaN or not a known state
        df_clean = df_clean.dropna(subset=["state", "BenefitsPaid", "Episodes"])
        df_clean = df_clean[df_clean["state"].isin(["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"])]
        
        # Convert numeric columns
        df_clean["BenefitsPaid"] = pd.to_numeric(df_clean["BenefitsPaid"], errors="coerce")
        df_clean["Episodes"] = pd.to_numeric(df_clean["Episodes"], errors="coerce")
        
        # Group by State and MonthEnd
        df_agg = df_clean.groupby(["state", "MonthEnd"], as_index=False).sum()
        df_agg["benefit_per_episode"] = df_agg["BenefitsPaid"] / df_agg["Episodes"]
        
        # Assign dummy IDs for period and payer to link to our star schema
        df_agg["period_id"] = 1
        df_agg["payer_id"] = 1
        df_agg["source_file"] = file_path.name
        
        con.register("staging_apra", df_agg)
        
        con.execute("DELETE FROM gold.fact_phi_benefits WHERE source_file = ?", [file_path.name])
        con.execute("""
            INSERT INTO gold.fact_phi_benefits
            (period_id, payer_id, state, hospital_benefits, total_benefits, episodes_paid, benefit_per_episode, source_file)
            SELECT period_id, payer_id, state, BenefitsPaid, BenefitsPaid, Episodes, benefit_per_episode, source_file
            FROM staging_apra
        """)
        print(f"    Loaded {len(df_agg)} real PHI benefit records into gold.fact_phi_benefits")
    except Exception as e:
        print(f"    [ERROR] Processing APRA data: {e}")


def seed_dimensions(con: duckdb.DuckDBPyConnection):
    periods = [
        (1, "2021-22", "Q1", "2021-07-01", "2021-09-30", False),
        (2, "2021-22", "Q2", "2021-10-01", "2021-12-31", False),
        (3, "2021-22", "Q3", "2022-01-01", "2022-03-31", False),
        (4, "2021-22", "Q4", "2022-04-01", "2022-06-30", False),
        (5, "2022-23", "Q1", "2022-07-01", "2022-09-30", False),
        (6, "2022-23", "Q2", "2022-10-01", "2022-12-31", False),
        (7, "2022-23", "Q3", "2023-01-01", "2023-03-31", False),
        (8, "2022-23", "Q4", "2023-04-01", "2023-06-30", False),
        (9, "2023-24", "Q1", "2023-07-01", "2023-09-30", True),
        (10, "2023-24", "Q2", "2023-10-01", "2023-12-31", True),
        (11, "2023-24", "Q3", "2024-01-01", "2024-03-31", True),
        (12, "2023-24", "Q4", "2024-04-01", "2024-06-30", True),
    ]
    con.executemany("INSERT OR IGNORE INTO gold.dim_period VALUES (?,?,?,?,?,?)", periods)

    payers = [
        (1, "Medibank Private", "health_fund", "large_fund", "2020-07-01", None),
        (2, "Bupa Australia", "health_fund", "large_fund", "2020-07-01", None),
        (3, "HCF (Hospital Contribution Fund)", "health_fund", "large_fund", "2020-07-01", None),
        (4, "NIB Health Funds", "health_fund", "mid_fund", "2020-07-01", None),
        (5, "HBF Health Fund", "health_fund", "mid_fund", "2020-07-01", None),
        (6, "DVA (Dept Veterans Affairs)", "government", "dva", "2020-07-01", None),
        (7, "Self-Funded / Uninsured", "self_funded", "none", "2020-07-01", None),
        (8, "Workers Compensation", "government", "wc", "2020-07-01", None),
    ]
    con.executemany("INSERT OR IGNORE INTO gold.dim_payer VALUES (?,?,?,?,?,?)", payers)

    hospitals = [
        (1, "SJOG Subiaco", "WA", "Group A - Major", "private", "SJOG WA", 500, "2020-07-01", None),
        (2, "SJOG Murdoch", "WA", "Group A - Major", "private", "SJOG WA", 400, "2020-07-01", None),
        (3, "SJOG Ballarat", "VIC", "Group B - Medium", "private", "SJOG VIC", 200, "2020-07-01", None),
        (4, "SJOG Bendigo", "VIC", "Group B - Medium", "private", "SJOG VIC", 180, "2020-07-01", None),
        (5, "SJOG Berwick", "VIC", "Group B - Medium", "private", "SJOG VIC", 220, "2020-07-01", None),
        (6, "National Average (Benchmark)", "ALL", "All Peer Groups", "public", "N/A", None, "2020-07-01", None),
    ]
    con.executemany("INSERT OR IGNORE INTO gold.dim_hospital VALUES (?,?,?,?,?,?,?,?,?)", hospitals)
    print("  Seeded dimension tables: dim_period (12), dim_payer (8), dim_hospital (6).")


def build():
    print("=" * 60)
    print("Building Star Schema in DuckDB...")
    print("=" * 60)
    con = duckdb.connect(str(WAREHOUSE_PATH))
    con.execute("DROP SEQUENCE IF EXISTS cost_seq")
    con.execute("DROP SEQUENCE IF EXISTS benefit_seq")
    con.execute("DROP SEQUENCE IF EXISTS episode_seq")
    con.execute("DROP SCHEMA IF EXISTS gold CASCADE")
    con.execute("DROP SCHEMA IF EXISTS silver CASCADE")
    con.execute("DROP SCHEMA IF EXISTS bronze CASCADE")
    for stmt in SCHEMA_DDL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            con.execute(stmt)
    print("  Schema DDL executed.")
    seed_dimensions(con)
    load_nhcdc_to_warehouse(con)
    load_aihw_to_warehouse(con)
    load_apra_to_warehouse(con)
    tables = con.execute("""
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema IN ('gold', 'silver', 'bronze')
        ORDER BY table_schema, table_name
    """).fetchall()
    print("\n  Warehouse tables:")
    for schema, table in tables:
        row_count = con.execute(f"SELECT COUNT(*) FROM {schema}.{table}").fetchone()[0]
        print(f"    {schema}.{table}: {row_count:,} rows")
    con.close()
    print(f"\n  Warehouse saved to: {WAREHOUSE_PATH}")


if __name__ == "__main__":
    build()
