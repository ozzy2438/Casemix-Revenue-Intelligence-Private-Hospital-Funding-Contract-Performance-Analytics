from pathlib import Path

import pytest

from dashboard.data_access import warehouse_ready
from powerbi.export_data import export_powerbi_data


def test_powerbi_export_contains_core_model(tmp_path: Path):
    if not warehouse_ready():
        pytest.skip("Demo warehouse has not been built")

    row_counts = export_powerbi_data(tmp_path)

    expected = {
        "dim_drg",
        "dim_hospital",
        "dim_payer",
        "dim_period",
        "fact_episodes",
        "drg_revenue",
        "payer_performance",
    }
    assert expected.issubset(row_counts)
    assert row_counts["fact_episodes"] == 50_000
    assert (tmp_path / "manifest.json").exists()
    assert all((tmp_path / f"{name}.csv").exists() for name in expected)
