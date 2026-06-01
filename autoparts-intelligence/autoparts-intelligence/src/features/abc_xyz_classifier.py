"""
AutoParts Intelligence Platform
src/features/abc_xyz_classifier.py

Production-grade ABC/XYZ dual-axis inventory classification.
  - ABC: Revenue-based Pareto (A=80%, B=15%, C=5%)
  - XYZ: Demand variability via Coefficient of Variation (CoV)
  - Combined: AX, AY, AZ, BX, BY, BZ, CX, CY, CZ

Designed to run on 70,000+ SKUs. Vectorized, no Python loops on rows.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Optional

try:
    from src.utils.logger import logger
    from src.utils.config import config
    ABC_A = config.analytics.abc_a_threshold
    ABC_B = config.analytics.abc_b_threshold
    XYZ_X = config.analytics.xyz_x_max_cov
    XYZ_Y = config.analytics.xyz_y_max_cov
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    ABC_A, ABC_B = 80.0, 95.0
    XYZ_X, XYZ_Y = 0.50, 1.00


# ── Classification Strategies ────────────────────────────────────────────────

def classify_abc(
    revenue_series: pd.Series,
    a_threshold: float = ABC_A,
    b_threshold: float = ABC_B,
) -> pd.Series:
    """
    Pure-function ABC classification on a revenue Series.
    Returns a Series of 'A', 'B', 'C' values with same index.
    """
    total = revenue_series.sum()
    if total == 0:
        logger.warning("Total revenue is zero — all parts classified as C.")
        return pd.Series("C", index=revenue_series.index)

    sorted_rev = revenue_series.sort_values(ascending=False)
    cum_pct     = sorted_rev.cumsum() / total * 100

    abc = pd.cut(
        cum_pct,
        bins=[0, a_threshold, b_threshold, 100],
        labels=["A", "B", "C"],
        right=True,
    )
    return abc.reindex(revenue_series.index)


def classify_xyz(
    monthly_demand: pd.DataFrame,
    x_max_cov: float = XYZ_X,
    y_max_cov: float = XYZ_Y,
) -> pd.DataFrame:
    """
    XYZ classification based on Coefficient of Variation (σ / μ).

    Parameters
    ----------
    monthly_demand : DataFrame with columns [part_id, dealer_id, year_month, qty_sold]
    x_max_cov      : CoV threshold for X class (≤ this = stable)
    y_max_cov      : CoV threshold for Y class (≤ this = variable)

    Returns
    -------
    DataFrame with [part_id, dealer_id, avg_monthly_demand, demand_std, demand_cov, xyz_class]
    """
    # Pivot to part/dealer × month matrix
    pivot = (
        monthly_demand
        .groupby(["part_id", "dealer_id", "year_month"])["qty_sold"]
        .sum()
        .unstack(fill_value=0)
    )

    stats = pd.DataFrame(index=pivot.index)
    stats["avg_monthly_demand"] = pivot.mean(axis=1)
    stats["demand_std"]         = pivot.std(axis=1, ddof=1).fillna(0)
    stats["demand_cov"]         = (
        stats["demand_std"] / stats["avg_monthly_demand"].replace(0, np.nan)
    ).fillna(9999)  # No demand = maximum variability

    conditions = [
        stats["demand_cov"] <= x_max_cov,
        stats["demand_cov"] <= y_max_cov,
    ]
    choices    = ["X", "Y"]
    stats["xyz_class"] = np.select(conditions, choices, default="Z")

    return stats.reset_index()


# ── Main Classifier ──────────────────────────────────────────────────────────

class ABCXYZClassifier:
    """
    Full ABC/XYZ dual-axis classifier.

    Usage
    -----
    clf = ABCXYZClassifier()
    results = clf.fit(sales_df)
    summary = clf.summary(results)
    """

    def fit(
        self,
        sales: pd.DataFrame,
        reference_period_months: int = 12,
    ) -> pd.DataFrame:
        """
        Compute ABC/XYZ classification from sales history.

        Parameters
        ----------
        sales : Cleaned sales DataFrame (output of SalesDataCleaner)
        reference_period_months : Trailing months to include

        Returns
        -------
        DataFrame with full classification per (part_id, dealer_id)
        """
        logger.info(f"Running ABC/XYZ classification on {len(sales):,} sales rows...")

        # ── Restrict to reference window ─────────────────────────────────────
        cutoff = sales["transaction_date"].max() - pd.DateOffset(months=reference_period_months)
        sales  = sales[sales["transaction_date"] >= cutoff].copy()

        if len(sales) == 0:
            raise ValueError("No sales data in the reference period.")

        # ── ABC: Annual revenue per part/dealer ──────────────────────────────
        revenue_df = (
            sales
            .groupby(["part_id", "dealer_id"])["revenue"]
            .sum()
            .reset_index(name="annual_revenue")
        )
        revenue_df = revenue_df.sort_values("annual_revenue", ascending=False).reset_index(drop=True)

        total_revenue              = revenue_df["annual_revenue"].sum()
        revenue_df["revenue_pct"]  = revenue_df["annual_revenue"] / total_revenue * 100
        revenue_df["cum_rev_pct"]  = revenue_df["revenue_pct"].cumsum()

        revenue_df["abc_class"] = classify_abc(revenue_df.set_index(["part_id","dealer_id"])["annual_revenue"])
        revenue_df["abc_class"] = revenue_df["abc_class"].values  # strip index

        # ── XYZ: Demand variability ──────────────────────────────────────────
        if "year_month" not in sales.columns:
            sales["year_month"] = sales["transaction_date"].dt.to_period("M")

        xyz_df = classify_xyz(sales[["part_id","dealer_id","year_month","qty_sold"]])

        # ── Merge ────────────────────────────────────────────────────────────
        result = revenue_df.merge(
            xyz_df[["part_id","dealer_id","avg_monthly_demand","demand_std","demand_cov","xyz_class"]],
            on=["part_id","dealer_id"],
            how="left",
        )
        result["combined_class"] = result["abc_class"].fillna("C") + result["xyz_class"].fillna("Z")

        logger.info(
            f"Classification done. Distribution:\n"
            f"{result['combined_class'].value_counts().to_string()}"
        )
        return result

    def summary(self, classified: pd.DataFrame) -> pd.DataFrame:
        """Aggregate statistics by combined class — for management reports."""
        return (
            classified
            .groupby("combined_class")
            .agg(
                part_count        = ("part_id",           "count"),
                total_revenue     = ("annual_revenue",    "sum"),
                avg_monthly_demand= ("avg_monthly_demand","mean"),
                avg_cov           = ("demand_cov",        "mean"),
            )
            .assign(
                revenue_share_pct = lambda x: x["total_revenue"] / x["total_revenue"].sum() * 100,
                part_share_pct    = lambda x: x["part_count"]    / x["part_count"].sum()    * 100,
            )
            .round(2)
            .sort_values("total_revenue", ascending=False)
        )

    def get_action_matrix(self) -> pd.DataFrame:
        """
        Returns the standard ABC/XYZ action recommendations matrix.
        Use in reports and presentations.
        """
        matrix = {
            "AX": ("High Value / Stable",   "Tight control. Min safety stock. Frequent replenishment."),
            "AY": ("High Value / Variable",  "Maintain safety stock. Short-term forecasting. Weekly review."),
            "AZ": ("High Value / Irregular", "Close monitoring. Emergency supplier contract. Hold buffer."),
            "BX": ("Med Value / Stable",     "Standard replenishment. Monthly review."),
            "BY": ("Med Value / Variable",   "Moderate safety stock. Monthly forecast review."),
            "BZ": ("Med Value / Irregular",  "Demand analysis needed. Consider de-listing."),
            "CX": ("Low Value / Stable",     "Bulk ordering. Reduce review frequency."),
            "CY": ("Low Value / Variable",   "Consignment or JIT. Reduce stock holding."),
            "CZ": ("Low Value / Irregular",  "Candidate for removal. Order on demand only."),
        }
        return pd.DataFrame(
            [(k, v[0], v[1]) for k, v in matrix.items()],
            columns=["combined_class", "segment_label", "recommended_action"],
        )
