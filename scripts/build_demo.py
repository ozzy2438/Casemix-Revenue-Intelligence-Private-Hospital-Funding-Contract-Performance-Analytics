from __future__ import annotations

import argparse

from analysis.contract_simulator import run as run_contract_scenarios
from analysis.forecast import run as run_forecasts
from analysis.margin_squeeze import run as run_margin_squeeze
from analysis.pvm_decomposition import run as run_pvm
from models.star_schema import build
from simulation.synthetic_episodes import load_into_warehouse


def build_demo(include_forecast: bool = False) -> None:
    build()
    load_into_warehouse()
    run_pvm()
    run_margin_squeeze()
    run_contract_scenarios()
    if include_forecast:
        run_forecasts()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the reproducible Casemix Revenue Intelligence demo."
    )
    parser.add_argument(
        "--include-forecast",
        action="store_true",
        help="Fit SARIMAX and Prophet models after building the analytical outputs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_demo(include_forecast=args.include_forecast)


if __name__ == "__main__":
    main()
