import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import WAREHOUSE_PATH, FORECAST_HORIZON_QUARTERS, FORECAST_CONFIDENCE


def prepare_time_series(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    query = """
        SELECT p.quarter_start AS period_date, p.financial_year, p.quarter,
            COUNT(*) AS separations, SUM(e.estimated_cost) AS total_cost,
            SUM(e.contracted_rate) AS total_revenue,
            AVG(e.estimated_cost) AS avg_cost_per_sep,
            AVG(e.contracted_rate) AS avg_revenue_per_sep
        FROM gold.fact_episodes e
        JOIN gold.dim_period p ON e.period_id = p.period_id
        GROUP BY p.quarter_start, p.financial_year, p.quarter
        ORDER BY p.quarter_start
    """
    return con.execute(query).fetchdf()


def run_sarimax(ts_df: pd.DataFrame, target_col: str = "separations"):
    try:
        from statsmodels.tsa.statespace.sarimax import SARIMAX
    except ImportError:
        print("  [WARN] statsmodels not installed. Skipping SARIMAX."); return None
    ts = ts_df.set_index("period_date")[target_col].sort_index()
    ts.index = pd.DatetimeIndex(ts.index, freq="QS")
    if len(ts) < 8:
        print(f"  [WARN] Only {len(ts)} data points. Need >= 8."); return None
    try:
        model = SARIMAX(ts, order=(1, 1, 1), seasonal_order=(1, 1, 1, 4),
            enforce_stationarity=False, enforce_invertibility=False)
        fitted = model.fit(disp=False, maxiter=100)
        forecast_result = fitted.get_forecast(steps=FORECAST_HORIZON_QUARTERS)
        forecast_mean = forecast_result.predicted_mean
        conf_int = forecast_result.conf_int(alpha=1 - FORECAST_CONFIDENCE)
        forecast_dates = pd.date_range(start=ts.index[-1] + pd.DateOffset(months=3),
            periods=FORECAST_HORIZON_QUARTERS, freq="QS")
        results = pd.DataFrame({
            "forecast_date": forecast_dates, "forecast_value": forecast_mean.values,
            "lower_ci": conf_int.iloc[:, 0].values, "upper_ci": conf_int.iloc[:, 1].values,
            "model": "SARIMAX", "target": target_col,
        })
        print(f"\n  SARIMAX Forecast — {target_col}:")
        print(f"  {'Quarter':12s} {'Forecast':>12s} {'95% CI Lower':>14s} {'95% CI Upper':>14s}")
        for _, row in results.iterrows():
            q = f"Q{((row['forecast_date'].month-1)//3)+1} {row['forecast_date'].year}"
            print(f"  {q:12s} {row['forecast_value']:>12,.0f} {row['lower_ci']:>14,.0f} {row['upper_ci']:>14,.0f}")
        return results
    except Exception as e:
        print(f"  [ERROR] SARIMAX failed: {e}"); return None


def run_prophet(ts_df: pd.DataFrame, target_col: str = "separations"):
    try:
        from prophet import Prophet
    except ImportError:
        print("  [WARN] prophet not installed. Skipping Prophet."); return None
    ts = ts_df[["period_date", target_col]].rename(columns={"period_date": "ds", target_col: "y"})
    ts["ds"] = pd.to_datetime(ts["ds"])
    if len(ts) < 8:
        print(f"  [WARN] Only {len(ts)} data points. Need >= 8."); return None
    try:
        model = Prophet(yearly_seasonality=True, weekly_seasonality=False,
            daily_seasonality=False, growth="linear", interval_width=FORECAST_CONFIDENCE)
        model.fit(ts)
        future = model.make_future_dataframe(periods=FORECAST_HORIZON_QUARTERS, freq="QS")
        forecast = model.predict(future)
        tail = forecast.tail(FORECAST_HORIZON_QUARTERS)
        results = pd.DataFrame({
            "forecast_date": tail["ds"].values, "forecast_value": tail["yhat"].values,
            "lower_ci": tail["yhat_lower"].values, "upper_ci": tail["yhat_upper"].values,
            "model": "Prophet", "target": target_col,
        })
        print(f"\n  Prophet Forecast — {target_col}:")
        print(f"  {'Quarter':12s} {'Forecast':>12s} {'95% CI Lower':>14s} {'95% CI Upper':>14s}")
        for _, row in results.iterrows():
            q = f"Q{((row['forecast_date'].month-1)//3)+1} {row['forecast_date'].year}"
            print(f"  {q:12s} {row['forecast_value']:>12,.0f} {row['lower_ci']:>14,.0f} {row['upper_ci']:>14,.0f}")
        return results
    except Exception as e:
        print(f"  [ERROR] Prophet failed: {e}"); return None


def run():
    print("=" * 60)
    print("Forecasting: Separations & Revenue")
    print("=" * 60)
    if not WAREHOUSE_PATH.exists():
        print("  [ERROR] Warehouse not found."); return
    con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
    ts_df = prepare_time_series(con)
    con.close()
    if ts_df.empty:
        print("  [WARN] No time series data."); return
    print(f"  Data: {len(ts_df)} quarters, {ts_df['period_date'].min()} → {ts_df['period_date'].max()}")
    all_forecasts = []
    for target in ["separations", "total_revenue", "avg_cost_per_sep"]:
        print(f"\n{'─' * 50}\n  Forecasting: {target}\n{'─' * 50}")
        r1 = run_sarimax(ts_df, target)
        if r1 is not None: all_forecasts.append(r1)
        r2 = run_prophet(ts_df, target)
        if r2 is not None: all_forecasts.append(r2)
    if all_forecasts:
        combined = pd.concat(all_forecasts, ignore_index=True)
        output_path = WAREHOUSE_PATH.parent / "forecasts.csv"
        combined.to_csv(output_path, index=False)
        print(f"\n  Forecasts saved to: {output_path}")
    else:
        print("\n  No forecasts generated.")

if __name__ == "__main__":
    run()
