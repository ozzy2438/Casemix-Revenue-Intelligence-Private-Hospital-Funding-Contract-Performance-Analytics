import duckdb
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import WAREHOUSE_PATH


def get_connection() -> duckdb.DuckDBPyConnection:
    if not WAREHOUSE_PATH.exists():
        pytest.skip("Warehouse not yet built — run models/star_schema.py first")
    return duckdb.connect(str(WAREHOUSE_PATH), read_only=True)


class TestDimensionIntegrity:

    def test_dim_drg_has_data(self):
        con = get_connection()
        count = con.execute("SELECT COUNT(*) FROM gold.dim_drg").fetchone()[0]
        con.close()
        assert count > 0, "dim_drg should have at least one row"

    def test_dim_drg_primary_key_unique(self):
        con = get_connection()
        dupes = con.execute("""
            SELECT drg_code, COUNT(*) as cnt FROM gold.dim_drg
            GROUP BY drg_code HAVING cnt > 1
        """).fetchall()
        con.close()
        assert len(dupes) == 0, f"dim_drg has duplicate drg_codes: {dupes[:5]}"

    def test_dim_drg_no_null_codes(self):
        con = get_connection()
        nulls = con.execute("SELECT COUNT(*) FROM gold.dim_drg WHERE drg_code IS NULL").fetchone()[0]
        con.close()
        assert nulls == 0, f"dim_drg has {nulls} null drg_codes"

    def test_dim_hospital_has_data(self):
        con = get_connection()
        count = con.execute("SELECT COUNT(*) FROM gold.dim_hospital").fetchone()[0]
        con.close()
        assert count >= 5, "dim_hospital should have at least 5 hospitals"

    def test_dim_hospital_primary_key_unique(self):
        con = get_connection()
        dupes = con.execute("""
            SELECT hospital_id, COUNT(*) as cnt FROM gold.dim_hospital
            GROUP BY hospital_id HAVING cnt > 1
        """).fetchall()
        con.close()
        assert len(dupes) == 0, "dim_hospital has duplicate hospital_ids"

    def test_dim_payer_has_data(self):
        con = get_connection()
        count = con.execute("SELECT COUNT(*) FROM gold.dim_payer").fetchone()[0]
        con.close()
        assert count >= 5, "dim_payer should have at least 5 payers"

    def test_dim_period_has_data(self):
        con = get_connection()
        count = con.execute("SELECT COUNT(*) FROM gold.dim_period").fetchone()[0]
        con.close()
        assert count >= 8, "dim_period should have at least 8 quarters"

    def test_dim_period_quarter_format(self):
        con = get_connection()
        invalid = con.execute("""
            SELECT COUNT(*) FROM gold.dim_period
            WHERE quarter NOT IN ('Q1', 'Q2', 'Q3', 'Q4')
        """).fetchone()[0]
        con.close()
        assert invalid == 0, f"dim_period has {invalid} invalid quarter values"


class TestFactIntegrity:

    def test_fact_episodes_has_data(self):
        con = get_connection()
        count = con.execute("SELECT COUNT(*) FROM gold.fact_episodes").fetchone()[0]
        con.close()
        assert count > 0, "fact_episodes should have data"

    def test_fact_episodes_positive_los(self):
        con = get_connection()
        negative = con.execute("SELECT COUNT(*) FROM gold.fact_episodes WHERE los < 0").fetchone()[0]
        con.close()
        assert negative == 0, f"fact_episodes has {negative} episodes with negative LOS"

    def test_fact_episodes_positive_cost(self):
        con = get_connection()
        negative = con.execute("SELECT COUNT(*) FROM gold.fact_episodes WHERE estimated_cost <= 0").fetchone()[0]
        con.close()
        assert negative == 0, f"fact_episodes has {negative} episodes with non-positive cost"

    def test_fact_episodes_cost_weight_range(self):
        con = get_connection()
        out_of_range = con.execute("""
            SELECT COUNT(*) FROM gold.fact_episodes
            WHERE cost_weight < 0 OR cost_weight > 50
        """).fetchone()[0]
        total = con.execute("SELECT COUNT(*) FROM gold.fact_episodes").fetchone()[0]
        con.close()
        if total > 0:
            assert out_of_range / total < 0.01, f"Too many episodes with cost weights outside [0, 50]: {out_of_range}"

    def test_fact_episodes_referential_drg(self):
        con = get_connection()
        orphans = con.execute("""
            SELECT COUNT(*) FROM gold.fact_episodes e
            LEFT JOIN gold.dim_drg d ON e.drg_code = d.drg_code
            WHERE d.drg_code IS NULL
        """).fetchone()[0]
        con.close()
        assert orphans == 0, f"fact_episodes has {orphans} orphan DRG references"

    def test_fact_episodes_referential_hospital(self):
        con = get_connection()
        orphans = con.execute("""
            SELECT COUNT(*) FROM gold.fact_episodes e
            LEFT JOIN gold.dim_hospital h ON e.hospital_id = h.hospital_id
            WHERE h.hospital_id IS NULL
        """).fetchone()[0]
        con.close()
        assert orphans == 0, f"fact_episodes has {orphans} orphan hospital references"

    def test_fact_episodes_referential_payer(self):
        con = get_connection()
        orphans = con.execute("""
            SELECT COUNT(*) FROM gold.fact_episodes e
            LEFT JOIN gold.dim_payer p ON e.payer_id = p.payer_id
            WHERE p.payer_id IS NULL
        """).fetchone()[0]
        con.close()
        assert orphans == 0, f"fact_episodes has {orphans} orphan payer references"

    def test_fact_national_costs_cost_weight_range(self):
        con = get_connection()
        if con.execute("SELECT COUNT(*) FROM gold.fact_national_costs").fetchone()[0] == 0:
            con.close()
            pytest.skip("fact_national_costs is empty")
        out_of_range = con.execute("""
            SELECT COUNT(*) FROM gold.fact_national_costs
            WHERE cost_weight < 0 OR cost_weight > 100
        """).fetchone()[0]
        con.close()
        assert out_of_range == 0, f"fact_national_costs has {out_of_range} rows with cost weights outside [0, 100]"

    def test_fact_national_costs_positive_cost(self):
        con = get_connection()
        if con.execute("SELECT COUNT(*) FROM gold.fact_national_costs").fetchone()[0] == 0:
            con.close()
            pytest.skip("fact_national_costs is empty")
        negative = con.execute("""
            SELECT COUNT(*) FROM gold.fact_national_costs WHERE cost_per_separation < 0
        """).fetchone()[0]
        con.close()
        assert negative == 0, f"fact_national_costs has {negative} rows with negative cost_per_separation"

    def test_fact_phi_benefits_positive(self):
        con = get_connection()
        if con.execute("SELECT COUNT(*) FROM gold.fact_phi_benefits").fetchone()[0] == 0:
            con.close()
            pytest.skip("fact_phi_benefits is empty")
        negative = con.execute("""
            SELECT COUNT(*) FROM gold.fact_phi_benefits
            WHERE hospital_benefits < 0 OR total_benefits < 0
        """).fetchone()[0]
        con.close()
        assert negative == 0, f"fact_phi_benefits has {negative} rows with negative benefits"


class TestCasemixViews:

    def test_v_casemix_index_exists(self):
        con = get_connection()
        result = con.execute("SELECT COUNT(*) FROM gold.v_casemix_index").fetchone()[0]
        con.close()
        assert result >= 0

    def test_v_drg_revenue_exists(self):
        con = get_connection()
        result = con.execute("SELECT COUNT(*) FROM gold.v_drg_revenue").fetchone()[0]
        con.close()
        assert result >= 0

    def test_v_payer_performance_exists(self):
        con = get_connection()
        result = con.execute("SELECT COUNT(*) FROM gold.v_payer_performance").fetchone()[0]
        con.close()
        assert result >= 0

    def test_casemix_index_in_reasonable_range(self):
        con = get_connection()
        if con.execute("SELECT COUNT(*) FROM gold.v_casemix_index").fetchone()[0] == 0:
            con.close()
            pytest.skip("No casemix index data yet")
        result = con.execute("""
            SELECT MIN(casemix_index), MAX(casemix_index) FROM gold.v_casemix_index
        """).fetchone()
        con.close()
        min_cmi, max_cmi = result
        assert 0.5 <= min_cmi <= 5.0, f"CMI minimum {min_cmi} outside expected range"
        assert 0.5 <= max_cmi <= 5.0, f"CMI maximum {max_cmi} outside expected range"


class TestBusinessLogic:

    def test_margin_percentage_bounded(self):
        con = get_connection()
        if con.execute("SELECT COUNT(*) FROM gold.v_drg_revenue").fetchone()[0] == 0:
            con.close()
            pytest.skip("No DRG revenue data yet")
        out_of_bounds = con.execute("""
            SELECT COUNT(*) FROM gold.v_drg_revenue
            WHERE margin_pct < -2.0 OR margin_pct > 2.0
        """).fetchone()[0]
        con.close()
        assert out_of_bounds == 0, f"v_drg_revenue has {out_of_bounds} rows with margin_pct outside [-200%, 200%]"

    def test_total_revenue_exceeds_cost(self):
        con = get_connection()
        if con.execute("SELECT COUNT(*) FROM gold.fact_episodes").fetchone()[0] == 0:
            con.close()
            pytest.skip("No episode data yet")
        total_cost = con.execute("SELECT SUM(estimated_cost) FROM gold.fact_episodes").fetchone()[0]
        total_revenue = con.execute("SELECT SUM(contracted_rate) FROM gold.fact_episodes").fetchone()[0]
        con.close()
        if total_revenue and total_cost:
            assert total_revenue > total_cost * 0.8, "Total revenue should be reasonably close to or above total cost"
