from __future__ import annotations

from collections.abc import Sequence

import duckdb
import pandas as pd

from config import WAREHOUSE_PATH


def warehouse_ready() -> bool:
    return WAREHOUSE_PATH.exists()


def _query(sql: str, params: Sequence[object] | None = None) -> pd.DataFrame:
    con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
    try:
        return con.execute(sql, params or []).fetchdf()
    finally:
        con.close()


def load_filter_options() -> dict[str, list[str]]:
    years = _query(
        "SELECT DISTINCT financial_year FROM gold.dim_period ORDER BY financial_year"
    )["financial_year"].tolist()
    hospitals = _query(
        """
        SELECT hospital_name
        FROM gold.dim_hospital
        WHERE sector = 'private'
        ORDER BY hospital_name
        """
    )["hospital_name"].tolist()
    payers = _query(
        """
        SELECT payer_name
        FROM gold.dim_payer
        WHERE payer_type = 'health_fund'
        ORDER BY payer_name
        """
    )["payer_name"].tolist()
    return {"years": years, "hospitals": hospitals, "payers": payers}


def _filter_clause(
    years: Sequence[str],
    hospitals: Sequence[str],
    payers: Sequence[str],
) -> tuple[str, list[object]]:
    clauses: list[str] = []
    params: list[object] = []
    for column, values in (
        ("p.financial_year", years),
        ("h.hospital_name", hospitals),
        ("py.payer_name", payers),
    ):
        if values:
            placeholders = ", ".join(["?"] * len(values))
            clauses.append(f"{column} IN ({placeholders})")
            params.extend(values)
    return (" AND ".join(clauses) if clauses else "TRUE"), params


def load_episode_summary(
    years: Sequence[str],
    hospitals: Sequence[str],
    payers: Sequence[str],
) -> pd.DataFrame:
    filters, params = _filter_clause(years, hospitals, payers)
    return _query(
        f"""
        SELECT
            p.financial_year,
            COUNT(*) AS separations,
            SUM(e.nwau) AS total_nwau,
            SUM(e.estimated_cost) AS total_cost,
            SUM(e.contracted_rate) AS total_revenue,
            SUM(e.contracted_rate) - SUM(e.estimated_cost) AS margin,
            (SUM(e.contracted_rate) - SUM(e.estimated_cost))
                / NULLIF(SUM(e.contracted_rate), 0) AS margin_pct,
            SUM(e.nwau) / NULLIF(COUNT(*), 0) AS casemix_index
        FROM gold.fact_episodes e
        JOIN gold.dim_period p ON e.period_id = p.period_id
        JOIN gold.dim_hospital h ON e.hospital_id = h.hospital_id
        JOIN gold.dim_payer py ON e.payer_id = py.payer_id
        WHERE {filters}
        GROUP BY p.financial_year
        ORDER BY p.financial_year
        """,
        params,
    )


def load_drg_performance(
    years: Sequence[str],
    hospitals: Sequence[str],
    payers: Sequence[str],
) -> pd.DataFrame:
    filters, params = _filter_clause(years, hospitals, payers)
    return _query(
        f"""
        SELECT
            d.drg_code,
            d.drg_description,
            d.mdc_code,
            d.mdc_description,
            d.medical_surgical,
            COUNT(*) AS separations,
            AVG(e.cost_weight) AS avg_cost_weight,
            AVG(e.los) AS avg_los,
            SUM(e.estimated_cost) AS total_cost,
            SUM(e.contracted_rate) AS total_revenue,
            SUM(e.contracted_rate) - SUM(e.estimated_cost) AS margin,
            (SUM(e.contracted_rate) - SUM(e.estimated_cost))
                / NULLIF(SUM(e.contracted_rate), 0) AS margin_pct,
            (SUM(e.contracted_rate) - SUM(e.estimated_cost))
                / NULLIF(COUNT(*), 0) AS margin_per_separation
        FROM gold.fact_episodes e
        JOIN gold.dim_drg d ON e.drg_code = d.drg_code
        JOIN gold.dim_period p ON e.period_id = p.period_id
        JOIN gold.dim_hospital h ON e.hospital_id = h.hospital_id
        JOIN gold.dim_payer py ON e.payer_id = py.payer_id
        WHERE {filters}
        GROUP BY
            d.drg_code,
            d.drg_description,
            d.mdc_code,
            d.mdc_description,
            d.medical_surgical
        ORDER BY margin
        """,
        params,
    )


def load_payer_performance(
    years: Sequence[str],
    hospitals: Sequence[str],
    payers: Sequence[str],
) -> pd.DataFrame:
    filters, params = _filter_clause(years, hospitals, payers)
    return _query(
        f"""
        SELECT
            py.payer_name,
            py.payer_type,
            py.fund_category,
            COUNT(*) AS separations,
            SUM(e.estimated_cost) AS total_cost,
            SUM(e.contracted_rate) AS total_revenue,
            SUM(e.contracted_rate) - SUM(e.estimated_cost) AS margin,
            (SUM(e.contracted_rate) - SUM(e.estimated_cost))
                / NULLIF(SUM(e.contracted_rate), 0) AS margin_pct,
            AVG(e.contracted_rate) AS revenue_per_separation,
            AVG(e.estimated_cost) AS cost_per_separation
        FROM gold.fact_episodes e
        JOIN gold.dim_period p ON e.period_id = p.period_id
        JOIN gold.dim_hospital h ON e.hospital_id = h.hospital_id
        JOIN gold.dim_payer py ON e.payer_id = py.payer_id
        WHERE {filters}
        GROUP BY py.payer_name, py.payer_type, py.fund_category
        ORDER BY margin
        """,
        params,
    )


def load_contract_activity(
    years: Sequence[str],
    hospitals: Sequence[str],
    payers: Sequence[str],
) -> pd.DataFrame:
    filters, params = _filter_clause(years, hospitals, payers)
    return _query(
        f"""
        SELECT
            e.drg_code,
            d.drg_description,
            AVG(e.cost_weight) AS avg_cost_weight,
            AVG(e.estimated_cost) AS avg_cost,
            AVG(e.los) AS avg_los,
            COUNT(*) AS separations
        FROM gold.fact_episodes e
        JOIN gold.dim_drg d ON e.drg_code = d.drg_code
        JOIN gold.dim_period p ON e.period_id = p.period_id
        JOIN gold.dim_hospital h ON e.hospital_id = h.hospital_id
        JOIN gold.dim_payer py ON e.payer_id = py.payer_id
        WHERE {filters}
        GROUP BY e.drg_code, d.drg_description
        ORDER BY separations DESC
        """,
        params,
    )
