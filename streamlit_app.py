from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analysis.contract_simulator import (
    simulate_drg_contract,
    simulate_per_diem_contract,
)
from config import NWAU_PRICE_2023_24
from dashboard.data_access import (
    load_contract_activity,
    load_drg_performance,
    load_episode_summary,
    load_filter_options,
    load_payer_performance,
    warehouse_ready,
)


st.set_page_config(
    page_title="Casemix Revenue Intelligence",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --ink: #17232d;
        --muted: #5b6770;
        --teal: #087f73;
        --red: #b23a48;
        --amber: #b7791f;
        --line: #d9e0e5;
    }
    .stApp { color: var(--ink); }
    [data-testid="stMetric"] {
        border-left: 3px solid var(--teal);
        padding-left: 0.8rem;
    }
    [data-testid="stMetricLabel"] { color: var(--muted); }
    [data-testid="stSidebar"] { border-right: 1px solid var(--line); }
    h1, h2, h3 { letter-spacing: 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

COLOR_MAP = {
    "positive": "#087f73",
    "negative": "#b23a48",
    "neutral": "#526575",
    "accent": "#b7791f",
}


def aud(value: float, decimals: int = 1) -> str:
    sign = "-" if value < 0 else ""
    absolute = abs(value)
    if absolute >= 1_000_000_000:
        return f"{sign}A${absolute / 1_000_000_000:.{decimals}f}B"
    if absolute >= 1_000_000:
        return f"{sign}A${absolute / 1_000_000:.{decimals}f}M"
    if absolute >= 1_000:
        return f"{sign}A${absolute / 1_000:.{decimals}f}K"
    return f"{sign}A${absolute:,.0f}"


def percentage(value: float) -> str:
    return f"{value * 100:.1f}%"


@st.cache_data(show_spinner=False)
def options() -> dict[str, list[str]]:
    return load_filter_options()


@st.cache_data(show_spinner=False)
def summary_data(
    years: tuple[str, ...],
    hospitals: tuple[str, ...],
    payers: tuple[str, ...],
) -> pd.DataFrame:
    return load_episode_summary(years, hospitals, payers)


@st.cache_data(show_spinner=False)
def drg_data(
    years: tuple[str, ...],
    hospitals: tuple[str, ...],
    payers: tuple[str, ...],
) -> pd.DataFrame:
    return load_drg_performance(years, hospitals, payers)


@st.cache_data(show_spinner=False)
def payer_data(
    years: tuple[str, ...],
    hospitals: tuple[str, ...],
    payers: tuple[str, ...],
) -> pd.DataFrame:
    return load_payer_performance(years, hospitals, payers)


@st.cache_data(show_spinner=False)
def activity_data(
    years: tuple[str, ...],
    hospitals: tuple[str, ...],
    payers: tuple[str, ...],
) -> pd.DataFrame:
    return load_contract_activity(years, hospitals, payers)


def show_missing_warehouse() -> None:
    st.title("Casemix Revenue Intelligence")
    st.error("The DuckDB warehouse has not been built in this environment.")
    st.code(
        "\n".join(
            [
                "python -m models.star_schema",
                "python -m simulation.synthetic_episodes",
                "python -m analysis.pvm_decomposition",
                "python -m analysis.margin_squeeze",
                "python -m analysis.forecast",
            ]
        ),
        language="bash",
    )
    st.stop()


if not warehouse_ready():
    show_missing_warehouse()

filter_options = options()

with st.sidebar:
    st.header("Analysis scope")
    selected_years = st.multiselect(
        "Financial year",
        filter_options["years"],
        default=[filter_options["years"][-1]],
    )
    selected_hospitals = st.multiselect(
        "Hospital",
        filter_options["hospitals"],
        default=filter_options["hospitals"],
    )
    selected_payers = st.multiselect(
        "Health fund",
        filter_options["payers"],
        default=filter_options["payers"],
    )
    st.caption("Episode-level records are synthetic and calibrated to public national data.")

if not selected_years or not selected_hospitals or not selected_payers:
    st.warning("Select at least one financial year, hospital and health fund.")
    st.stop()

years_key = tuple(selected_years)
hospitals_key = tuple(selected_hospitals)
payers_key = tuple(selected_payers)

summary = summary_data(years_key, hospitals_key, payers_key)
drg = drg_data(years_key, hospitals_key, payers_key)
payer = payer_data(years_key, hospitals_key, payers_key)

st.title("Casemix Revenue Intelligence")
st.caption("Private hospital funding, contract performance and negotiation decision support")

tabs = st.tabs(
    [
        "Executive Summary",
        "Casemix Explorer",
        "Payer Performance",
        "Contract Modeller",
    ]
)

with tabs[0]:
    totals = summary[
        ["separations", "total_nwau", "total_cost", "total_revenue", "margin"]
    ].sum()
    margin_pct = totals["margin"] / totals["total_revenue"]
    casemix_index = totals["total_nwau"] / totals["separations"]

    metric_cols = st.columns(5)
    metric_cols[0].metric("Revenue", aud(totals["total_revenue"]))
    metric_cols[1].metric("Margin", aud(totals["margin"]), percentage(margin_pct))
    metric_cols[2].metric("Separations", f"{totals['separations']:,.0f}")
    metric_cols[3].metric("Casemix index", f"{casemix_index:.2f}")
    metric_cols[4].metric("Cost base", aud(totals["total_cost"]))

    trend_col, risk_col = st.columns([1.25, 1])
    with trend_col:
        st.subheader("Revenue and cost trend")
        trend = summary.melt(
            id_vars="financial_year",
            value_vars=["total_revenue", "total_cost"],
            var_name="measure",
            value_name="value",
        )
        trend["measure"] = trend["measure"].map(
            {"total_revenue": "Revenue", "total_cost": "Cost"}
        )
        fig = px.line(
            trend,
            x="financial_year",
            y="value",
            color="measure",
            markers=True,
            color_discrete_map={"Revenue": "#087f73", "Cost": "#526575"},
        )
        fig.update_layout(
            xaxis_title=None,
            yaxis_title="AUD",
            legend_title=None,
            hovermode="x unified",
        )
        st.plotly_chart(fig, width="stretch")

    with risk_col:
        st.subheader("Lowest DRG margins")
        loss_drgs = drg.nsmallest(8, "margin").sort_values("margin")
        risk_fig = px.bar(
            loss_drgs,
            x="margin",
            y="drg_code",
            orientation="h",
            hover_data=["drg_description", "separations", "margin_pct"],
            color_discrete_sequence=[COLOR_MAP["accent"]],
        )
        risk_fig.update_layout(xaxis_title="Margin (AUD)", yaxis_title=None)
        st.plotly_chart(risk_fig, width="stretch")

    st.subheader("Commercial attention queue")
    attention = drg.nsmallest(10, "margin")[
        [
            "drg_code",
            "drg_description",
            "separations",
            "avg_cost_weight",
            "total_revenue",
            "total_cost",
            "margin",
            "margin_pct",
        ]
    ]
    st.dataframe(
        attention,
        width="stretch",
        hide_index=True,
        column_config={
            "total_revenue": st.column_config.NumberColumn(format="A$ %.0f"),
            "total_cost": st.column_config.NumberColumn(format="A$ %.0f"),
            "margin": st.column_config.NumberColumn(format="A$ %.0f"),
            "margin_pct": st.column_config.NumberColumn(format="percent"),
            "avg_cost_weight": st.column_config.NumberColumn(format="%.2f"),
        },
    )

with tabs[1]:
    st.subheader("Complexity, volume and margin")
    mdc_options = sorted(drg["mdc_code"].dropna().unique().tolist())
    selected_mdc = st.multiselect("Major diagnostic category", mdc_options)
    explorer = drg[drg["mdc_code"].isin(selected_mdc)] if selected_mdc else drg

    scatter = px.scatter(
        explorer,
        x="avg_cost_weight",
        y="margin_per_separation",
        size="separations",
        color="medical_surgical",
        hover_name="drg_code",
        hover_data=["drg_description", "mdc_code", "avg_los", "margin_pct"],
        color_discrete_map={"Medical": "#087f73", "Surgical": "#b7791f"},
        size_max=46,
    )
    scatter.add_hline(y=0, line_dash="dash", line_color="#b23a48")
    scatter.update_layout(
        xaxis_title="Average cost weight",
        yaxis_title="Margin per separation (AUD)",
        legend_title=None,
    )
    st.plotly_chart(scatter, width="stretch")

    st.dataframe(
        explorer[
            [
                "drg_code",
                "drg_description",
                "mdc_code",
                "medical_surgical",
                "separations",
                "avg_cost_weight",
                "avg_los",
                "margin_per_separation",
                "margin_pct",
            ]
        ].sort_values("margin_per_separation"),
        width="stretch",
        hide_index=True,
        column_config={
            "avg_cost_weight": st.column_config.NumberColumn(format="%.2f"),
            "avg_los": st.column_config.NumberColumn(format="%.1f"),
            "margin_per_separation": st.column_config.NumberColumn(format="A$ %.0f"),
            "margin_pct": st.column_config.NumberColumn(format="percent"),
        },
    )

with tabs[2]:
    st.subheader("Health fund commercial performance")
    payer_chart = payer.sort_values("margin")
    payer_fig = px.bar(
        payer_chart,
        x="margin",
        y="payer_name",
        orientation="h",
        color="margin",
        color_continuous_scale=["#b23a48", "#e7edf0", "#087f73"],
        hover_data=["separations", "total_revenue", "total_cost", "margin_pct"],
    )
    payer_fig.update_layout(
        xaxis_title="Margin (AUD)",
        yaxis_title=None,
        coloraxis_showscale=False,
    )
    st.plotly_chart(payer_fig, width="stretch")
    st.dataframe(
        payer[
            [
                "payer_name",
                "fund_category",
                "separations",
                "revenue_per_separation",
                "cost_per_separation",
                "total_revenue",
                "margin",
                "margin_pct",
            ]
        ].sort_values("margin"),
        width="stretch",
        hide_index=True,
        column_config={
            "revenue_per_separation": st.column_config.NumberColumn(format="A$ %.0f"),
            "cost_per_separation": st.column_config.NumberColumn(format="A$ %.0f"),
            "total_revenue": st.column_config.NumberColumn(format="A$ %.0f"),
            "margin": st.column_config.NumberColumn(format="A$ %.0f"),
            "margin_pct": st.column_config.NumberColumn(format="percent"),
        },
    )

with tabs[3]:
    st.subheader("Contract negotiation scenario modeller")
    control_cols = st.columns(4)
    drg_indexation = control_cols[0].slider(
        "DRG indexation", 0.0, 0.10, 0.05, 0.005, format="%.1f%%"
    )
    per_diem_indexation = control_cols[1].slider(
        "Per-diem indexation", 0.0, 0.10, 0.03, 0.005, format="%.1f%%"
    )
    daily_rate = control_cols[2].number_input(
        "Per-diem daily rate (AUD)", 500, 5000, 1200, 50
    )
    years = control_cols[3].slider("Projection years", 1, 5, 3)
    outlier_cap = st.slider(
        "DRG outlier reimbursement cap",
        0.5,
        1.2,
        0.8,
        0.05,
        format="%.0f%%",
    )

    activity = activity_data(years_key, hospitals_key, payers_key)
    drg_scenario = simulate_drg_contract(
        activity,
        indexation=drg_indexation,
        years=years,
        base_nwau_price=NWAU_PRICE_2023_24,
        outlier_cap_pct=outlier_cap,
    )
    per_diem_scenario = simulate_per_diem_contract(
        activity,
        indexation=per_diem_indexation,
        daily_rate=daily_rate,
        years=years,
    )
    scenarios = pd.concat([drg_scenario, per_diem_scenario], ignore_index=True)
    scenario_totals = scenarios.groupby("contract_type", as_index=False).agg(
        total_revenue=("total_revenue", "sum"),
        total_cost=("total_cost", "sum"),
        margin=("margin", "sum"),
    )
    drg_total = scenario_totals.loc[
        scenario_totals["contract_type"] == "DRG-based", "margin"
    ].iloc[0]
    per_diem_total = scenario_totals.loc[
        scenario_totals["contract_type"] == "Per-Diem", "margin"
    ].iloc[0]

    outcome_cols = st.columns(3)
    outcome_cols[0].metric(f"{years}Y DRG margin", aud(drg_total))
    outcome_cols[1].metric(f"{years}Y per-diem margin", aud(per_diem_total))
    outcome_cols[2].metric("DRG advantage", aud(drg_total - per_diem_total))

    scenario_fig = px.bar(
        scenarios,
        x="year",
        y="margin",
        color="contract_type",
        barmode="group",
        color_discrete_map={"DRG-based": "#087f73", "Per-Diem": "#b23a48"},
        hover_data=["total_revenue", "total_cost", "margin_pct"],
    )
    scenario_fig.add_hline(y=0, line_color="#526575")
    scenario_fig.update_layout(
        xaxis_title=None,
        yaxis_title="Margin (AUD)",
        legend_title=None,
    )
    st.plotly_chart(scenario_fig, width="stretch")

    st.dataframe(
        scenarios[
            [
                "year",
                "contract_type",
                "indexation_pct",
                "total_revenue",
                "total_cost",
                "margin",
                "margin_pct",
                "outlier_shortfall",
            ]
        ],
        width="stretch",
        hide_index=True,
        column_config={
            "indexation_pct": st.column_config.NumberColumn(format="%.1f%%"),
            "total_revenue": st.column_config.NumberColumn(format="A$ %.0f"),
            "total_cost": st.column_config.NumberColumn(format="A$ %.0f"),
            "margin": st.column_config.NumberColumn(format="A$ %.0f"),
            "margin_pct": st.column_config.NumberColumn(format="%.1f%%"),
            "outlier_shortfall": st.column_config.NumberColumn(format="A$ %.0f"),
        },
    )

st.divider()
st.caption(
    "Sources: IHACPA NHCDC cost weights, AIHW activity distributions and APRA private "
    "health insurance statistics. Episode-level records are synthetic and nationally calibrated."
)
