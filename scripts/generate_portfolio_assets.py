from __future__ import annotations

from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.ticker import FuncFormatter

from analysis.contract_simulator import (
    get_current_activity,
    simulate_drg_contract,
    simulate_per_diem_contract,
)
from config import WAREHOUSE_PATH
from dashboard.data_access import (
    load_drg_performance,
    load_episode_summary,
    load_filter_options,
    load_payer_performance,
)


ROOT = Path(__file__).resolve().parent.parent
IMAGE_DIR = ROOT / "docs" / "images"
TEAL = "#087f73"
RED = "#b23a48"
AMBER = "#b7791f"
INK = "#17232d"
MUTED = "#526575"
LIGHT = "#e7edf0"
PAPER = "#f7f9fa"


def money_axis(value: float, _position: int) -> str:
    absolute = abs(value)
    sign = "-" if value < 0 else ""
    if absolute >= 1_000_000_000:
        return f"{sign}A${absolute / 1_000_000_000:.1f}B"
    if absolute >= 1_000_000:
        return f"{sign}A${absolute / 1_000_000:.1f}M"
    if absolute >= 1_000:
        return f"{sign}A${absolute / 1_000:.0f}K"
    return f"{sign}A${absolute:.0f}"


def money(value: float) -> str:
    absolute = abs(value)
    sign = "-" if value < 0 else ""
    if absolute >= 1_000_000_000:
        return f"{sign}A${absolute / 1_000_000_000:.2f}B"
    return f"{sign}A${absolute / 1_000_000:.1f}M"


def prepare_health_fund_data():
    options = load_filter_options()
    years = tuple(options["years"])
    hospitals = tuple(options["hospitals"])
    payers = tuple(options["payers"])
    summary = load_episode_summary(years, hospitals, payers)
    latest = (years[-1],)
    drg = load_drg_performance(latest, hospitals, payers)
    payer = load_payer_performance(latest, hospitals, payers)
    return summary, drg, payer


def generate_executive_dashboard() -> Path:
    summary, drg, payer = prepare_health_fund_data()
    latest = summary.iloc[-1]

    fig = plt.figure(figsize=(16, 9), facecolor=PAPER)
    grid = fig.add_gridspec(
        4,
        12,
        height_ratios=[0.75, 1.1, 3.2, 3.2],
        hspace=0.62,
        wspace=0.9,
    )
    title_ax = fig.add_subplot(grid[0, :])
    title_ax.axis("off")
    title_ax.text(
        0,
        0.68,
        "Casemix Revenue Intelligence",
        fontsize=25,
        weight="bold",
        color=INK,
    )
    title_ax.text(
        0,
        0.05,
        "Executive Summary | Latest health-fund scope",
        fontsize=12,
        color=MUTED,
    )

    metrics = [
        ("Revenue", money(latest["total_revenue"]), TEAL),
        ("Margin", money(latest["margin"]), TEAL),
        ("Separations", f"{latest['separations']:,.0f}", AMBER),
        ("Casemix index", f"{latest['casemix_index']:.2f}", MUTED),
        ("Cost base", money(latest["total_cost"]), RED),
    ]
    starts = [0, 2.4, 4.8, 7.2, 9.6]
    for (label, value, color), start in zip(metrics, starts):
        ax = fig.add_subplot(grid[1, int(start) : int(start) + 2])
        ax.set_facecolor("white")
        for spine in ax.spines.values():
            spine.set_color(LIGHT)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.axvline(0, color=color, linewidth=5)
        ax.text(0.08, 0.67, label, transform=ax.transAxes, color=MUTED, fontsize=10)
        ax.text(
            0.08,
            0.22,
            value,
            transform=ax.transAxes,
            color=INK,
            fontsize=20,
            weight="bold",
        )

    trend_ax = fig.add_subplot(grid[2, :7])
    x = np.arange(len(summary))
    width = 0.34
    trend_ax.bar(
        x - width / 2,
        summary["total_revenue"],
        width,
        label="Revenue",
        color=TEAL,
    )
    trend_ax.bar(
        x + width / 2,
        summary["total_cost"],
        width,
        label="Cost",
        color=MUTED,
    )
    trend_ax.set_title("Revenue and cost trend", loc="left", weight="bold", color=INK)
    trend_ax.set_xticks(x, summary["financial_year"])
    trend_ax.yaxis.set_major_formatter(FuncFormatter(money_axis))
    trend_ax.grid(axis="y", color=LIGHT, linewidth=0.8)
    trend_ax.spines[["top", "right", "left"]].set_visible(False)
    trend_ax.legend(frameon=False, loc="upper left")

    payer_ax = fig.add_subplot(grid[2, 7:])
    payer_plot = payer.sort_values("margin")
    payer_colors = [RED if value < 0 else TEAL for value in payer_plot["margin"]]
    payer_labels = payer_plot["payer_name"].replace(
        {
            "Medibank Private": "Medibank",
            "HCF (Hospital Contribution Fund)": "HCF",
            "Bupa Australia": "Bupa",
            "HBF Health Fund": "HBF",
            "NIB Health Funds": "nib",
        }
    )
    payer_ax.barh(payer_labels, payer_plot["margin"], color=payer_colors)
    payer_ax.set_title("Payer margin", loc="left", weight="bold", color=INK)
    payer_ax.xaxis.set_major_formatter(FuncFormatter(money_axis))
    payer_ax.axvline(0, color=MUTED, linewidth=0.8)
    payer_ax.grid(axis="x", color=LIGHT, linewidth=0.8)
    payer_ax.spines[["top", "right", "left"]].set_visible(False)
    payer_ax.tick_params(axis="y", labelsize=9)

    risk_ax = fig.add_subplot(grid[3, :7])
    risks = drg.nsmallest(8, "margin").sort_values("margin")
    risk_ax.barh(risks["drg_code"], risks["margin"], color=AMBER)
    risk_ax.set_title(
        "Lowest DRG margins",
        loc="left",
        weight="bold",
        color=INK,
    )
    risk_ax.xaxis.set_major_formatter(FuncFormatter(money_axis))
    risk_ax.grid(axis="x", color=LIGHT, linewidth=0.8)
    risk_ax.spines[["top", "right", "left"]].set_visible(False)

    action_ax = fig.add_subplot(grid[3, 7:])
    action_ax.axis("off")
    action_ax.set_title(
        "Commercial actions",
        loc="left",
        weight="bold",
        color=INK,
        pad=10,
    )
    actions = [
        "1  Anchor complex acute activity to DRG reimbursement",
        "2  Add explicit outlier and stop-loss protection",
        "3  Review negative-margin DRGs before fund negotiations",
        "4  Separate volume, mix and rate in monthly reporting",
    ]
    for index, action in enumerate(actions):
        action_ax.text(
            0,
            0.82 - index * 0.22,
            action,
            color=INK,
            fontsize=11,
            va="center",
        )
        action_ax.axhline(
            0.72 - index * 0.22,
            xmin=0,
            xmax=1,
            color=LIGHT,
            linewidth=0.8,
        )

    fig.text(
        0.99,
        0.015,
        "Synthetic episode data calibrated to IHACPA, AIHW and APRA public sources",
        ha="right",
        color=MUTED,
        fontsize=8,
    )
    output = IMAGE_DIR / "executive-dashboard.png"
    fig.savefig(output, dpi=160, bbox_inches="tight", facecolor=PAPER)
    plt.close(fig)
    return output


def contract_results():
    con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
    try:
        activity = get_current_activity(con)
    finally:
        con.close()
    drg = simulate_drg_contract(activity, indexation=0.05, years=3)
    per_diem = simulate_per_diem_contract(
        activity,
        indexation=0.03,
        daily_rate=1200,
        years=3,
    )
    return drg, per_diem


def generate_contract_dashboard() -> Path:
    drg, per_diem = contract_results()
    drg_margin = drg["margin"].sum()
    per_diem_margin = per_diem["margin"].sum()

    fig = plt.figure(figsize=(16, 9), facecolor=PAPER)
    grid = fig.add_gridspec(
        3,
        12,
        height_ratios=[0.9, 1.5, 5.4],
        hspace=0.55,
        wspace=0.8,
    )
    title_ax = fig.add_subplot(grid[0, :])
    title_ax.axis("off")
    title_ax.text(
        0,
        0.65,
        "Contract Scenario Modeller",
        fontsize=25,
        weight="bold",
        color=INK,
    )
    title_ax.text(
        0,
        0.05,
        "All-payer activity | 3-year projection | DRG 5% vs per-diem 3%",
        fontsize=12,
        color=MUTED,
    )

    outcomes = [
        ("DRG margin", money(drg_margin), TEAL),
        ("Per-diem margin", money(per_diem_margin), RED),
        ("DRG advantage", money(drg_margin - per_diem_margin), AMBER),
    ]
    for index, (label, value, color) in enumerate(outcomes):
        ax = fig.add_subplot(grid[1, index * 4 : (index + 1) * 4])
        ax.set_facecolor("white")
        for spine in ax.spines.values():
            spine.set_color(LIGHT)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.axvline(0, color=color, linewidth=6)
        ax.text(0.07, 0.68, label, transform=ax.transAxes, color=MUTED, fontsize=11)
        ax.text(
            0.07,
            0.2,
            value,
            transform=ax.transAxes,
            color=INK,
            fontsize=26,
            weight="bold",
        )

    chart_ax = fig.add_subplot(grid[2, :8])
    x = np.arange(len(drg))
    width = 0.35
    chart_ax.bar(x - width / 2, drg["margin"], width, color=TEAL, label="DRG-based")
    chart_ax.bar(
        x + width / 2,
        per_diem["margin"],
        width,
        color=RED,
        label="Per-diem",
    )
    chart_ax.axhline(0, color=MUTED, linewidth=1)
    chart_ax.set_xticks(x, ["Year 1", "Year 2", "Year 3"])
    chart_ax.yaxis.set_major_formatter(FuncFormatter(money_axis))
    chart_ax.set_title("Annual margin comparison", loc="left", weight="bold", color=INK)
    chart_ax.grid(axis="y", color=LIGHT, linewidth=0.8)
    chart_ax.spines[["top", "right", "left"]].set_visible(False)
    chart_ax.legend(frameon=False, loc="upper left")

    insight_ax = fig.add_subplot(grid[2, 8:])
    insight_ax.axis("off")
    insight_ax.set_title(
        "Negotiation readout",
        loc="left",
        weight="bold",
        color=INK,
        pad=10,
    )
    statements = [
        ("Contract structure", "Materially larger impact than indexation"),
        ("Complexity risk", "Per-diem underfunds high-weight episodes"),
        ("Protection", "Use explicit outlier and stop-loss clauses"),
        ("Decision", "Anchor negotiation to DRG-based reimbursement"),
    ]
    for index, (heading, body) in enumerate(statements):
        y = 0.88 - index * 0.23
        insight_ax.text(0, y, heading, color=AMBER, weight="bold", fontsize=11)
        insight_ax.text(0, y - 0.08, body, color=INK, fontsize=10)
        insight_ax.axhline(y - 0.15, color=LIGHT, linewidth=0.8)

    fig.text(
        0.99,
        0.015,
        "Scenario output only; not actual hospital or payer financial performance",
        ha="right",
        color=MUTED,
        fontsize=8,
    )
    output = IMAGE_DIR / "contract-modeller.png"
    fig.savefig(output, dpi=160, bbox_inches="tight", facecolor=PAPER)
    plt.close(fig)
    return output


def generate_executive_pdf() -> Path:
    drg, per_diem = contract_results()
    output = ROOT / "docs" / "executive_summary.pdf"
    with PdfPages(output) as pdf:
        fig = plt.figure(figsize=(11.69, 8.27), facecolor="white")
        ax = fig.add_axes([0.06, 0.06, 0.88, 0.88])
        ax.axis("off")
        ax.text(
            0,
            0.96,
            "Casemix Revenue Intelligence",
            fontsize=24,
            weight="bold",
            color=INK,
        )
        ax.text(
            0,
            0.91,
            "Executive decision brief",
            fontsize=12,
            color=MUTED,
        )
        ax.axhline(0.875, color=TEAL, linewidth=3)
        ax.text(0, 0.81, "Decision", fontsize=14, weight="bold", color=INK)
        ax.text(
            0,
            0.755,
            "Use DRG-based reimbursement as the negotiation anchor for complex acute activity.",
            fontsize=13,
            color=INK,
        )
        ax.text(
            0,
            0.70,
            "A fixed per-diem structure creates material loss exposure that indexation alone does not repair.",
            fontsize=11,
            color=MUTED,
        )

        cards = [
            ("DRG 5% margin", money(drg["margin"].sum()), TEAL),
            ("Per-diem 3% margin", money(per_diem["margin"].sum()), RED),
            (
                "DRG advantage",
                money(drg["margin"].sum() - per_diem["margin"].sum()),
                AMBER,
            ),
        ]
        for index, (label, value, color) in enumerate(cards):
            left = index * 0.33
            ax.add_patch(
                plt.Rectangle(
                    (left, 0.52),
                    0.29,
                    0.12,
                    facecolor=PAPER,
                    edgecolor=LIGHT,
                    linewidth=1,
                )
            )
            ax.add_patch(
                plt.Rectangle(
                    (left, 0.52),
                    0.008,
                    0.12,
                    facecolor=color,
                    edgecolor=color,
                )
            )
            ax.text(left + 0.025, 0.60, label, fontsize=9, color=MUTED)
            ax.text(
                left + 0.025,
                0.545,
                value,
                fontsize=18,
                weight="bold",
                color=INK,
            )

        ax.text(0, 0.44, "Recommended actions", fontsize=14, weight="bold", color=INK)
        actions = [
            "1. Define DRG-based pricing and explicit outlier protection.",
            "2. Rank DRGs by absolute margin exposure before each fund negotiation.",
            "3. Separate price, volume and casemix in monthly commercial reporting.",
            "4. Validate contract rules with Finance, Clinical Costing and Health Funds.",
        ]
        for index, action in enumerate(actions):
            ax.text(0.02, 0.38 - index * 0.06, action, fontsize=11, color=INK)

        ax.text(0, 0.11, "Governance", fontsize=12, weight="bold", color=INK)
        ax.text(
            0,
            0.06,
            "Public national inputs are sourced from IHACPA, AIHW and APRA. Episode records and contract terms are synthetic.",
            fontsize=9,
            color=MUTED,
        )
        ax.text(
            0,
            0.025,
            "Results demonstrate analytical method and decision workflow; they are not actual hospital-group outcomes.",
            fontsize=9,
            color=MUTED,
        )
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
    return output


def main() -> None:
    if not WAREHOUSE_PATH.exists():
        raise FileNotFoundError("Run python -m scripts.build_demo first.")
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    outputs = [
        generate_executive_dashboard(),
        generate_contract_dashboard(),
        generate_executive_pdf(),
    ]
    for output in outputs:
        print(f"Generated: {output}")


if __name__ == "__main__":
    main()
