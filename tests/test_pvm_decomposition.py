import pandas as pd
import pytest

from analysis.pvm_decomposition import calculate_pvm


def test_pvm_bridge_reconciles_to_revenue_change():
    data = pd.DataFrame(
        [
            {
                "drg_code": "A",
                "drg_description": "DRG A",
                "mdc_code": "MDC 01",
                "financial_year": "2022-23",
                "separations": 100,
                "total_revenue": 100_000,
            },
            {
                "drg_code": "B",
                "drg_description": "DRG B",
                "mdc_code": "MDC 02",
                "financial_year": "2022-23",
                "separations": 50,
                "total_revenue": 100_000,
            },
            {
                "drg_code": "A",
                "drg_description": "DRG A",
                "mdc_code": "MDC 01",
                "financial_year": "2023-24",
                "separations": 120,
                "total_revenue": 132_000,
            },
            {
                "drg_code": "B",
                "drg_description": "DRG B",
                "mdc_code": "MDC 02",
                "financial_year": "2023-24",
                "separations": 80,
                "total_revenue": 176_000,
            },
        ]
    )

    result, summary = calculate_pvm(data, "2022-23", "2023-24")
    explained = sum(
        summary[key]
        for key in (
            "volume_effect",
            "mix_effect",
            "rate_effect",
            "new_business",
            "discontinued",
        )
    )

    assert explained == pytest.approx(summary["total_change"])
    assert summary["residual"] == pytest.approx(0, abs=0.02)
    assert result["residual"].abs().sum() <= 0.02


def test_pvm_reports_new_and_discontinued_business_separately():
    data = pd.DataFrame(
        [
            {
                "drg_code": "OLD",
                "drg_description": "Discontinued DRG",
                "mdc_code": "MDC 01",
                "financial_year": "2022-23",
                "separations": 10,
                "total_revenue": 20_000,
            },
            {
                "drg_code": "NEW",
                "drg_description": "New DRG",
                "mdc_code": "MDC 02",
                "financial_year": "2023-24",
                "separations": 20,
                "total_revenue": 50_000,
            },
        ]
    )

    result, summary = calculate_pvm(data, "2022-23", "2023-24")

    assert summary["new_business"] == 50_000
    assert summary["discontinued"] == -20_000
    assert summary["total_change"] == 30_000
    assert result["residual"].abs().sum() == 0
