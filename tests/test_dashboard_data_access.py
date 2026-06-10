import pytest

from dashboard.data_access import (
    load_contract_activity,
    load_drg_performance,
    load_episode_summary,
    load_filter_options,
    load_payer_performance,
    warehouse_ready,
)


@pytest.fixture(scope="module")
def filters():
    if not warehouse_ready():
        pytest.skip("Demo warehouse has not been built")
    options = load_filter_options()
    return (
        (options["years"][-1],),
        tuple(options["hospitals"]),
        tuple(options["payers"]),
    )


def test_filter_options_are_business_usable():
    if not warehouse_ready():
        pytest.skip("Demo warehouse has not been built")
    options = load_filter_options()

    assert options["years"]
    assert len(options["hospitals"]) >= 5
    assert len(options["payers"]) >= 5


def test_dashboard_queries_return_consistent_aggregates(filters):
    years, hospitals, payers = filters
    summary = load_episode_summary(years, hospitals, payers)
    drg = load_drg_performance(years, hospitals, payers)
    payer = load_payer_performance(years, hospitals, payers)
    activity = load_contract_activity(years, hospitals, payers)

    assert not summary.empty
    assert summary["separations"].sum() > 0
    assert drg["separations"].sum() == summary["separations"].sum()
    assert payer["separations"].sum() == summary["separations"].sum()
    assert activity["separations"].sum() == summary["separations"].sum()
    assert drg["drg_code"].is_unique
    assert payer["payer_name"].is_unique
