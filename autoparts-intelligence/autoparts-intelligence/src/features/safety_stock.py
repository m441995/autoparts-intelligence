"""
AutoParts Intelligence Platform
src/features/safety_stock.py

Statistical safety stock and reorder point calculation.
Formula: SS = Z × √(LT × σ_d² + d̄² × σ_LT²)
Where:
  Z    = service level Z-score
  LT   = average lead time (days)
  σ_d  = demand std dev (daily)
  d̄    = average daily demand
  σ_LT = lead time std dev (days)
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from scipy import stats as scipy_stats
from dataclasses import dataclass

try:
    from src.utils.logger import logger
    from src.utils.config import config
    DEFAULT_Z     = config.analytics.default_service_level_z
    HIGH_VALUE_Z  = config.analytics.high_value_service_level_z
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    DEFAULT_Z    = 1.645
    HIGH_VALUE_Z = 2.054


@dataclass(frozen=True)
class ReorderPolicy:
    part_id:            int
    dealer_id:          int
    avg_daily_demand:   float
    demand_std_dev:     float
    avg_lead_time_days: float
    lead_time_std_dev:  float
    service_level_z:    float
    safety_stock_qty:   int
    reorder_point:      int
    economic_order_qty: int
    max_stock_level:    int

    @property
    def demand_cov(self) -> float:
        return self.demand_std_dev / max(self.avg_daily_demand, 0.001)

    @property
    def days_of_safety_stock(self) -> float:
        return self.safety_stock_qty / max(self.avg_daily_demand, 0.001)


def calculate_eoq(
    annual_demand: float,
    ordering_cost: float,
    holding_cost_per_unit: float,
) -> int:
    """
    Classic Wilson EOQ formula.
    EOQ = √(2 × D × S / H)
    """
    if annual_demand <= 0 or ordering_cost <= 0 or holding_cost_per_unit <= 0:
        return 1
    eoq = np.sqrt((2 * annual_demand * ordering_cost) / holding_cost_per_unit)
    return max(1, int(round(eoq)))


def calculate_safety_stock(
    demand_std_daily: float,
    avg_lead_time: float,
    lead_time_std: float,
    avg_daily_demand: float,
    z: float,
) -> int:
    """
    Combined demand + lead time variability safety stock formula.
    Handles cases where either variability source dominates.
    """
    # Variance from demand variability during lead time
    demand_variance_component = avg_lead_time * (demand_std_daily ** 2)

    # Variance from lead time variability at average demand
    leadtime_variance_component = (avg_daily_demand ** 2) * (lead_time_std ** 2)

    # Combined standard deviation
    combined_std = np.sqrt(demand_variance_component + leadtime_variance_component)
    safety_stock = z * combined_std
    return max(0, int(np.ceil(safety_stock)))


class SafetyStockEngine:
    """
    Calculates reorder policies for all part/dealer combinations.

    Applies:
      - Higher Z-score for A-class and critical parts
      - EOQ for economic order sizing
      - Max stock = ROP + EOQ (prevents overstock)
    """

    ORDERING_COST    = 25.0    # USD per purchase order line
    HOLDING_RATE     = 0.25    # 25% annual carrying cost rate

    def compute_policies(
        self,
        sales: pd.DataFrame,
        purchase_orders: pd.DataFrame,
        abc_xyz: Optional[pd.DataFrame] = None,
        parts_master: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Main entry point.

        Parameters
        ----------
        sales           : Cleaned sales data
        purchase_orders : Cleaned PO data (for lead time stats)
        abc_xyz         : ABC/XYZ classification results (for Z-score selection)
        parts_master    : Parts master (for is_critical flag and standard_cost)

        Returns
        -------
        DataFrame with one reorder policy per (part_id, dealer_id)
        """
        logger.info("Computing safety stock and reorder policies...")

        # ── Demand Statistics (daily) ────────────────────────────────────────
        demand_stats = self._compute_demand_stats(sales)

        # ── Lead Time Statistics ─────────────────────────────────────────────
        lt_stats = self._compute_lead_time_stats(purchase_orders)

        # ── Merge ────────────────────────────────────────────────────────────
        df = demand_stats.merge(lt_stats, on="part_id", how="left")

        # Fill missing lead time with global fallback
        df["avg_lead_time_days"] = df["avg_lead_time_days"].fillna(21.0)
        df["lead_time_std_dev"]  = df["lead_time_std_dev"].fillna(7.0)

        # ── Service Level Z-score Selection ─────────────────────────────────
        df["service_level_z"] = DEFAULT_Z  # Base: 95%

        if abc_xyz is not None:
            df = df.merge(
                abc_xyz[["part_id","dealer_id","abc_class"]],
                on=["part_id","dealer_id"],
                how="left",
            )
            # A-class → higher service level
            df.loc[df["abc_class"] == "A", "service_level_z"] = HIGH_VALUE_Z

        if parts_master is not None and "is_critical" in parts_master.columns:
            df = df.merge(
                parts_master[["part_id","is_critical","standard_cost"]],
                on="part_id",
                how="left",
            )
            # Critical parts → highest service level
            df.loc[df["is_critical"] == True, "service_level_z"] = HIGH_VALUE_Z

        # ── Safety Stock Calculation ─────────────────────────────────────────
        df["safety_stock_qty"] = df.apply(
            lambda row: calculate_safety_stock(
                demand_std_daily=row["demand_std_daily"],
                avg_lead_time=row["avg_lead_time_days"],
                lead_time_std=row["lead_time_std_dev"],
                avg_daily_demand=row["avg_daily_demand"],
                z=row["service_level_z"],
            ),
            axis=1,
        )

        # ── Reorder Point ────────────────────────────────────────────────────
        # ROP = (avg daily demand × avg lead time) + safety stock
        df["reorder_point"] = (
            df["avg_daily_demand"] * df["avg_lead_time_days"]
            + df["safety_stock_qty"]
        ).apply(lambda x: max(1, int(np.ceil(x))))

        # ── EOQ ──────────────────────────────────────────────────────────────
        unit_cost = df.get("standard_cost", pd.Series(50.0, index=df.index)).fillna(50.0)
        holding_cost = unit_cost * self.HOLDING_RATE
        annual_demand = df["avg_daily_demand"] * 365

        df["economic_order_qty"] = [
            calculate_eoq(d, self.ORDERING_COST, h)
            for d, h in zip(annual_demand, holding_cost)
        ]

        # ── Max Stock Level ──────────────────────────────────────────────────
        df["max_stock_level"] = df["reorder_point"] + df["economic_order_qty"]

        logger.info(f"Policies computed for {len(df):,} part/dealer combinations.")
        return df

    # ── Private Helpers ──────────────────────────────────────────────────────

    def _compute_demand_stats(self, sales: pd.DataFrame) -> pd.DataFrame:
        """Daily demand statistics: mean, std, and CoV per part/dealer."""
        # Aggregate to daily granularity first
        daily = (
            sales
            .groupby(["part_id", "dealer_id", "transaction_date"])["qty_sold"]
            .sum()
            .reset_index()
        )
        stats = (
            daily
            .groupby(["part_id", "dealer_id"])["qty_sold"]
            .agg(
                avg_daily_demand="mean",
                demand_std_daily="std",
            )
            .fillna({"demand_std_daily": 0})
            .reset_index()
        )
        return stats

    def _compute_lead_time_stats(self, pos: pd.DataFrame) -> pd.DataFrame:
        """Lead time statistics per part from PO history."""
        completed_pos = pos[
            pos["actual_receipt_date"].notna()
            & pos["lead_time_actual"].notna()
            & (pos["lead_time_actual"] > 0)
        ]
        if len(completed_pos) == 0:
            logger.warning("No completed POs found for lead time analysis. Using defaults.")
            return pd.DataFrame(columns=["part_id","avg_lead_time_days","lead_time_std_dev"])

        lt_stats = (
            completed_pos
            .groupby("part_id")["lead_time_actual"]
            .agg(
                avg_lead_time_days="mean",
                lead_time_std_dev="std",
            )
            .fillna({"lead_time_std_dev": 3.0})
            .reset_index()
        )
        return lt_stats


# Allow Optional import at module level
from typing import Optional
