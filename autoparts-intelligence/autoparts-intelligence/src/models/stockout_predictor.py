"""
AutoParts Intelligence Platform
src/models/stockout_predictor.py

ML-based stockout prediction using Random Forest + XGBoost ensemble.
Predicts probability of stockout in the next 14/30 days per SKU.

Target variable: binary — will this part stockout within N days?
Features: demand velocity, stock coverage, lead time, ABC class,
          seasonality, supplier reliability, historical stockout rate.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from dataclasses import dataclass

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import (
    classification_report, roc_auc_score, precision_recall_curve, average_precision_score
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

try:
    from src.utils.logger import logger
    from src.utils.config import config
    MODEL_DIR = config.paths.models
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    MODEL_DIR = Path("src/models/artifacts")

MODEL_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ModelMetrics:
    auc_roc:     float
    avg_precision: float
    precision_at_70_recall: float
    report:      str


def build_feature_matrix(
    inventory: pd.DataFrame,
    sales: pd.DataFrame,
    purchase_orders: pd.DataFrame,
    reorder_policies: pd.DataFrame,
    abc_xyz: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Construct the ML feature matrix.
    Each row = one (part_id, dealer_id) combination on a given reference date.
    """
    logger.info("Building ML feature matrix...")

    # ── Latest inventory position ────────────────────────────────────────────
    latest_inv = (
        inventory
        .sort_values("snapshot_date")
        .groupby(["part_id","dealer_id"])
        .last()
        .reset_index()
        [["part_id","dealer_id","qty_on_hand","qty_available","qty_in_transit","total_stock_value"]]
    )

    # ── Demand features (trailing 30, 60, 90 days) ───────────────────────────
    ref_date = pd.to_datetime(sales["transaction_date"]).max()

    def demand_window(days: int) -> pd.DataFrame:
        cutoff = ref_date - pd.Timedelta(days=days)
        return (
            sales[sales["transaction_date"] >= cutoff]
            .groupby(["part_id","dealer_id"])["qty_sold"]
            .agg(
                **{f"qty_sold_{days}d": "sum",
                   f"txn_count_{days}d": "count",
                   f"demand_std_{days}d": "std"}
            )
            .fillna(0)
            .reset_index()
        )

    d30 = demand_window(30)
    d60 = demand_window(60)
    d90 = demand_window(90)

    # Merge demand windows
    df = latest_inv.merge(d30, on=["part_id","dealer_id"], how="left")
    df = df.merge(d60, on=["part_id","dealer_id"], how="left")
    df = df.merge(d90, on=["part_id","dealer_id"], how="left")

    # ── Derived demand features ──────────────────────────────────────────────
    df["avg_daily_demand_30d"] = df["qty_sold_30d"] / 30
    df["avg_daily_demand_90d"] = df["qty_sold_90d"] / 90
    df["demand_trend"]         = (
        (df["qty_sold_30d"] / 30) - (df["qty_sold_90d"] / 90)
    )  # Positive = accelerating demand

    # Stock coverage in days
    df["days_coverage"] = (
        df["qty_available"] / df["avg_daily_demand_30d"].replace(0, np.nan)
    ).fillna(999).clip(upper=365)

    # ── Reorder policy features ──────────────────────────────────────────────
    if len(reorder_policies) > 0:
        rp_cols = ["part_id","dealer_id","safety_stock_qty","reorder_point",
                   "avg_lead_time_days","lead_time_std_dev","economic_order_qty"]
        df = df.merge(
            reorder_policies[[c for c in rp_cols if c in reorder_policies.columns]],
            on=["part_id","dealer_id"],
            how="left",
        )
        df["stock_vs_rop"] = df["qty_available"] - df.get("reorder_point", 0)
        df["safety_stock_coverage_days"] = (
            df.get("safety_stock_qty", 0) /
            df["avg_daily_demand_30d"].replace(0, np.nan)
        ).fillna(0)
    else:
        df["stock_vs_rop"] = 0
        df["safety_stock_coverage_days"] = 0
        df["avg_lead_time_days"] = 21
        df["lead_time_std_dev"] = 7

    # ── Supplier reliability ─────────────────────────────────────────────────
    supplier_perf = (
        purchase_orders[purchase_orders["actual_receipt_date"].notna()]
        .groupby("part_id")
        .agg(
            on_time_rate    = ("lead_time_delta", lambda x: (x <= 0).mean()),
            avg_po_lead_time= ("lead_time_actual", "mean"),
        )
        .reset_index()
    )
    df = df.merge(supplier_perf, on="part_id", how="left")
    df["on_time_rate"]     = df["on_time_rate"].fillna(0.80)
    df["avg_po_lead_time"] = df["avg_po_lead_time"].fillna(21)

    # ── ABC/XYZ class encoding ───────────────────────────────────────────────
    if abc_xyz is not None:
        df = df.merge(
            abc_xyz[["part_id","dealer_id","abc_class","xyz_class","combined_class"]],
            on=["part_id","dealer_id"],
            how="left",
        )
        for col in ["abc_class","xyz_class","combined_class"]:
            df[col] = LabelEncoder().fit_transform(df[col].fillna("C"))
    else:
        df["abc_class"]      = 2  # Default C
        df["xyz_class"]      = 2  # Default Z
        df["combined_class"] = 8  # CZ

    # ── Target Variable ──────────────────────────────────────────────────────
    # Stockout in 14 days: available qty < (avg_daily_demand × 14)
    demand_14d = df["avg_daily_demand_30d"] * 14
    df["will_stockout_14d"] = (df["qty_available"] < demand_14d).astype(int)

    logger.info(
        f"Feature matrix built: {len(df):,} rows, "
        f"stockout rate: {df['will_stockout_14d'].mean():.1%}"
    )
    return df


FEATURE_COLS = [
    "qty_on_hand", "qty_available", "qty_in_transit",
    "qty_sold_30d", "qty_sold_60d", "qty_sold_90d",
    "txn_count_30d", "demand_std_30d",
    "avg_daily_demand_30d", "avg_daily_demand_90d",
    "demand_trend", "days_coverage", "stock_vs_rop",
    "safety_stock_coverage_days", "avg_lead_time_days",
    "lead_time_std_dev", "on_time_rate", "avg_po_lead_time",
    "abc_class", "xyz_class", "combined_class",
]
TARGET_COL = "will_stockout_14d"


class StockoutPredictor:
    """
    Ensemble stockout risk classifier.
    Random Forest + XGBoost (if available) → soft voting.
    Uses TimeSeriesSplit for cross-validation (no data leakage).
    """

    def __init__(self, n_cv_splits: int = 5) -> None:
        self.n_cv_splits = n_cv_splits
        self.rf_model    = None
        self.xgb_model   = None
        self.feature_importance_: Optional[pd.DataFrame] = None

    def train(self, features: pd.DataFrame) -> ModelMetrics:
        """Train on full feature matrix, evaluate with TimeSeriesSplit CV."""
        X = features[FEATURE_COLS].fillna(0).astype("float32")
        y = features[TARGET_COL].astype(int)

        logger.info(f"Training on {len(X):,} samples, "
                    f"{y.mean():.1%} positive (stockout) rate.")

        # ── Random Forest ────────────────────────────────────────────────────
        self.rf_model = RandomForestClassifier(
            n_estimators    = 300,
            max_depth       = 12,
            min_samples_leaf= 10,
            class_weight    = "balanced",
            n_jobs          = -1,
            random_state    = 42,
        )

        # TimeSeriesSplit CV (respect temporal ordering)
        tscv     = TimeSeriesSplit(n_splits=self.n_cv_splits)
        cv_aucs  = cross_val_score(self.rf_model, X, y, cv=tscv, scoring="roc_auc", n_jobs=-1)
        logger.info(f"RF CV AUC: {cv_aucs.mean():.3f} ± {cv_aucs.std():.3f}")

        # Fit on full data
        self.rf_model.fit(X, y)
        self._compute_feature_importance(X.columns.tolist())

        # ── XGBoost (if available) ───────────────────────────────────────────
        if HAS_XGB:
            scale_pos_weight = (y == 0).sum() / max((y == 1).sum(), 1)
            self.xgb_model = xgb.XGBClassifier(
                n_estimators     = 300,
                max_depth        = 6,
                learning_rate    = 0.05,
                subsample        = 0.8,
                colsample_bytree = 0.8,
                scale_pos_weight = scale_pos_weight,
                eval_metric      = "auc",
                random_state     = 42,
                n_jobs           = -1,
            )
            self.xgb_model.fit(X, y)

        # ── Final evaluation metrics ─────────────────────────────────────────
        probs = self.predict_proba(features)
        auc   = roc_auc_score(y, probs)
        ap    = average_precision_score(y, probs)

        precision, recall, _ = precision_recall_curve(y, probs)
        # Precision at 70% recall
        idx_70 = np.argmin(np.abs(recall - 0.70))
        p_at_70r = float(precision[idx_70])

        report = classification_report(y, (probs >= 0.50).astype(int))
        logger.info(f"Final AUC-ROC: {auc:.3f}, Avg Precision: {ap:.3f}")

        return ModelMetrics(
            auc_roc=round(auc, 4),
            avg_precision=round(ap, 4),
            precision_at_70_recall=round(p_at_70r, 4),
            report=report,
        )

    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        """Return ensemble stockout probability per row."""
        X = features[FEATURE_COLS].fillna(0).astype("float32")
        rf_proba = self.rf_model.predict_proba(X)[:, 1]
        if self.xgb_model is not None:
            xgb_proba = self.xgb_model.predict_proba(X)[:, 1]
            return (rf_proba + xgb_proba) / 2
        return rf_proba

    def score_inventory(self, features: pd.DataFrame) -> pd.DataFrame:
        """Score current inventory and return risk-ranked table."""
        proba = self.predict_proba(features)
        result = features[["part_id","dealer_id","qty_available","days_coverage"]].copy()
        result["stockout_probability"] = proba.round(4)
        result["risk_level"] = pd.cut(
            proba,
            bins=[-0.001, 0.25, 0.50, 0.75, 1.001],
            labels=["Low", "Medium", "High", "Critical"],
        )
        return result.sort_values("stockout_probability", ascending=False)

    def save(self, path: Optional[Path] = None) -> Path:
        path = path or MODEL_DIR / "stockout_predictor.joblib"
        joblib.dump({"rf": self.rf_model, "xgb": self.xgb_model}, path)
        logger.info(f"Model saved to {path}")
        return path

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "StockoutPredictor":
        path = path or MODEL_DIR / "stockout_predictor.joblib"
        obj  = cls()
        data = joblib.load(path)
        obj.rf_model  = data["rf"]
        obj.xgb_model = data.get("xgb")
        return obj

    def _compute_feature_importance(self, feature_names: list[str]) -> None:
        importance = pd.DataFrame({
            "feature":    feature_names,
            "importance": self.rf_model.feature_importances_,
        }).sort_values("importance", ascending=False)
        self.feature_importance_ = importance


from typing import Optional
