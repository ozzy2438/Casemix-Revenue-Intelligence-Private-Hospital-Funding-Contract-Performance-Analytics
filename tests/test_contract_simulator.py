import pandas as pd

from analysis.contract_simulator import (
    simulate_drg_contract,
    simulate_per_diem_contract,
)


def sample_activity() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "drg_code": "J11B",
                "drg_description": "Knee replacement",
                "avg_cost_weight": 3.2,
                "avg_cost": 19_500.0,
                "avg_los": 5.5,
                "separations": 1_000,
            },
            {
                "drg_code": "I23B",
                "drg_description": "Chest pain",
                "avg_cost_weight": 0.3,
                "avg_cost": 2_100.0,
                "avg_los": 1.0,
                "separations": 2_000,
            },
        ]
    )


def test_drg_indexation_increases_projected_margin():
    activity = sample_activity()
    low = simulate_drg_contract(activity, indexation=0.03, years=3)
    high = simulate_drg_contract(activity, indexation=0.05, years=3)

    assert high["margin"].sum() > low["margin"].sum()
    assert set(high["contract_type"]) == {"DRG-based"}
    assert len(high) == 3


def test_per_diem_rate_increases_projected_margin():
    activity = sample_activity()
    low = simulate_per_diem_contract(
        activity, indexation=0.03, daily_rate=1_000, years=3
    )
    high = simulate_per_diem_contract(
        activity, indexation=0.03, daily_rate=1_500, years=3
    )

    assert high["margin"].sum() > low["margin"].sum()
    assert set(high["contract_type"]) == {"Per-Diem"}


def test_contract_outputs_are_financially_consistent():
    result = simulate_drg_contract(sample_activity(), indexation=0.04, years=2)

    expected_margin = result["total_revenue"] - result["total_cost"]
    pd.testing.assert_series_equal(
        result["margin"].reset_index(drop=True),
        expected_margin.round(2).reset_index(drop=True),
        check_names=False,
    )
