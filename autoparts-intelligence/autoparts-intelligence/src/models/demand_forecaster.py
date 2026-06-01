"""
AutoParts Intelligence Platform
src/models/demand_forecaster.py

Production demand forecasting pipeline:
  - SARIMA for time-series with seasonality
  - Ensemble (SARIMA + simple exponential smoothing) for robustness
  - Per-part/dealer forecasting with automatic model selection
  - MAPE and RMSE evaluation on holdout set
"""
from __future__ import annotations

import warnings
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional
from joblib import Parallel, delayed

from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tools.sm_exceptions import ConvergenceWarning

warnings.filterwarnings("ignore", category=ConvergenceWarning)
warnings.filterwarnings("ignore", category=UserWarning)

try:
    from src.utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


@dataclass
class ForecastResult:
    part_id:       int
    dealer_id:     int
    forecast_qty:  np.ndarray    # shape: (horizon,)
    lower_bound:   np.ndarray
    upper_bound:   np.ndarray
    model_used:    str
    mape:          float         # Out-of-sample MAPE on holdout
    rmse:          float
    forecast_dates: pd.PeriodIndex


def _mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Mean Absolute Percentage Error, safe against zeros."""
    mask = actual > 0
    if not mask.any():
        return np.nan
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)


def _rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def _fit_sarima(
    train: np.ndarray,
    order: tuple = (1, 1, 1),
    seasonal_order: tuple = (1, 1, 1, 12),
    horizon: int = 6,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Fit SARIMA and return (forecast, lower_ci, upper_ci).
    Falls back to simpler model on convergence failure.
    """
    try:
        model = SARIMAX(
            train,
            order=order,
            seasonal_order=seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        result = model.fit(disp=False, maxiter=200)
        forecast = result.get_forecast(steps=horizon)
        pred      = forecast.predicted_mean
        ci        = forecast.conf_int(alpha=0.20)  # 80% CI
        return (
            np.maximum(pred.values, 0),
            np.maximum(ci.iloc[:, 0].values, 0),
            np.maximum(ci.iloc[:, 1].values, 0),
        )
    except Exception:
        return _fit_ets(train, horizon)


def _fit_ets(
    train: np.ndarray,
    horizon: int = 6,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """ETS (Exponential Smoothing) as fallback model."""
    try:
        model = ExponentialSmoothing(
            train,
            trend="add",
            seasonal="add" if len(train) >= 24 else None,
            seasonal_periods=12,
        )
        fit = model.fit(optimized=True)
        pred = fit.forecast(horizon)
        std  = np.std(train) * 1.28  # approximate 80% CI
        return (
            np.maximum(pred.values, 0),
            np.maximum(pred.values - std, 0),
            pred.values + std,
        )
    except Exception:
        # Last resort: naive seasonal
        season = train[-12:] if len(train) >= 12 else train
        pred   = np.tile(season, horizon)[:horizon]
        return np.maximum(pred, 0), np.zeros(horizon), pred * 2


def _forecast_single_part(
    part_id: int,
    dealer_id: int,
    monthly_series: pd.Series,
    horizon: int,
    holdout_months: int,
) -> Optional[ForecastResult]:
    """Forecast one part/dealer combination — designed to run in parallel."""
    try:
        if len(monthly_series) < 12:
            return None  # Insufficient history

        # Train/test split
        train = monthly_series.iloc[:-holdout_months].values.astype(float)
        test  = monthly_series.iloc[-holdout_months:].values.astype(float)

        if train.sum() == 0:
            return None  # No demand history

        # Try SARIMA first, fall back to ETS
        if len(train) >= 24:
            fc, lower, upper = _fit_sarima(train, horizon=holdout_months)
            model_label = "SARIMA"
        else:
            fc, lower, upper = _fit_ets(train, horizon=holdout_months)
            model_label = "ETS"

        mape_val = _mape(test, fc[:len(test)])
        rmse_val = _rmse(test, fc[:len(test)])

        # Auto-select: if SARIMA MAPE > 30%, retry with ETS
        if mape_val > 30.0 and model_label == "SARIMA":
            fc_ets, lower_ets, upper_ets = _fit_ets(train, horizon=holdout_months)
            mape_ets = _mape(test, fc_ets[:len(test)])
            if mape_ets < mape_val:
                fc, lower, upper = fc_ets, lower_ets, upper_ets
                mape_val = mape_ets
                model_label = "ETS"

        # Final forecast on full series
        full_train = monthly_series.values.astype(float)
        if model_label == "SARIMA" and len(full_train) >= 24:
            final_fc, final_lower, final_upper = _fit_sarima(full_train, horizon=horizon)
        else:
            final_fc, final_lower, final_upper = _fit_ets(full_train, horizon=horizon)

        last_period    = monthly_series.index[-1]
        forecast_dates = pd.period_range(start=last_period + 1, periods=horizon, freq="M")

        return ForecastResult(
            part_id       = part_id,
            dealer_id     = dealer_id,
            forecast_qty  = final_fc,
            lower_bound   = final_lower,
            upper_bound   = final_upper,
            model_used    = model_label,
            mape          = round(mape_val, 2),
            rmse          = round(rmse_val, 2),
            forecast_dates= forecast_dates,
        )

    except Exception as exc:
        logger.debug(f"Forecast failed for part {part_id}/dealer {dealer_id}: {exc}")
        return None


class DemandForecaster:
    """
    Parallel demand forecaster for all part/dealer combinations.

    Usage
    -----
    forecaster = DemandForecaster(horizon=6, holdout_months=3)
    forecast_df = forecaster.fit_predict(sales_df)
    """

    def __init__(
        self,
        horizon: int       = 6,
        holdout_months: int = 3,
        n_jobs: int        = -1,   # -1 = all CPU cores
        min_history_months: int = 12,
    ) -> None:
        self.horizon       = horizon
        self.holdout_months = holdout_months
        self.n_jobs        = n_jobs
        self.min_history   = min_history_months

    def fit_predict(self, sales: pd.DataFrame) -> pd.DataFrame:
        """
        Full pipeline: aggregate → forecast all SKUs in parallel → flatten results.

        Parameters
        ----------
        sales : Cleaned sales DataFrame (must contain transaction_date, part_id,
                dealer_id, qty_sold)

        Returns
        -------
        DataFrame with monthly forecast per (part_id, dealer_id, forecast_date)
        """
        logger.info("Aggregating monthly demand series...")

        # Monthly aggregation
        if "year_month" not in sales.columns:
            sales = sales.copy()
            sales["year_month"] = sales["transaction_date"].dt.to_period("M")

        monthly = (
            sales
            .groupby(["part_id", "dealer_id", "year_month"])["qty_sold"]
            .sum()
        )

        # Filter parts with enough history
        part_dealer_months = monthly.groupby(["part_id","dealer_id"]).size()
        eligible = part_dealer_months[part_dealer_months >= self.min_history].index
        logger.info(f"Forecasting {len(eligible):,} eligible part/dealer combinations...")

        # ── Parallel Forecasting ─────────────────────────────────────────────
        tasks = [
            delayed(_forecast_single_part)(
                part_id   = int(part_id),
                dealer_id = int(dealer_id),
                monthly_series = monthly.loc[(part_id, dealer_id)],
                horizon        = self.horizon,
                holdout_months = self.holdout_months,
            )
            for (part_id, dealer_id) in eligible
        ]

        results: list[Optional[ForecastResult]] = Parallel(
            n_jobs=self.n_jobs,
            backend="loky",
            verbose=5,
        )(tasks)

        # ── Flatten to DataFrame ─────────────────────────────────────────────
        rows = []
        success, failed = 0, 0
        for res in results:
            if res is None:
                failed += 1
                continue
            success += 1
            for i, dt in enumerate(res.forecast_dates):
                rows.append({
                    "forecast_date":   str(dt),
                    "part_id":         res.part_id,
                    "dealer_id":       res.dealer_id,
                    "forecast_qty":    round(float(max(res.forecast_qty[i], 0)), 2),
                    "forecast_lower":  round(float(max(res.lower_bound[i], 0)), 2),
                    "forecast_upper":  round(float(res.upper_bound[i]), 2),
                    "model_used":      res.model_used,
                    "mape":            res.mape,
                    "rmse":            res.rmse,
                })

        logger.info(f"Forecasting complete: {success:,} success, {failed:,} failed/skipped.")
        return pd.DataFrame(rows)

    def get_accuracy_summary(self, forecast_df: pd.DataFrame) -> pd.DataFrame:
        """MAPE summary by model type — for model comparison reporting."""
        return (
            forecast_df
            .groupby("model_used")["mape"]
            .agg(
                count      = "count",
                median_mape= "median",
                mean_mape  = "mean",
                pct_under_15 = lambda x: (x < 15).mean() * 100,
                pct_under_25 = lambda x: (x < 25).mean() * 100,
            )
            .round(2)
        )
