"""
AutoParts Intelligence Platform
src/cleaning/cleaning_pipeline.py

Production-grade data cleaning pipeline.
Handles: nulls, type coercion, outliers, duplicates, business rule validation.
Designed for large datasets using chunked processing and vectorized operations.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path

try:
    from src.utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


@dataclass
class CleaningReport:
    """Audit trail for all cleaning operations."""
    source_rows: int = 0
    output_rows: int = 0
    issues: list[dict[str, Any]] = field(default_factory=list)

    def add_issue(self, check: str, count: int, action: str) -> None:
        self.issues.append({"check": check, "affected_rows": count, "action": action})
        if count > 0:
            logger.warning(f"[CLEAN] {check}: {count:,} rows → {action}")

    def summary(self) -> str:
        removed = self.source_rows - self.output_rows
        lines = [
            f"=== Cleaning Report ===",
            f"  Source rows : {self.source_rows:>10,}",
            f"  Output rows : {self.output_rows:>10,}",
            f"  Removed     : {removed:>10,} ({removed/max(self.source_rows,1)*100:.1f}%)",
        ]
        for issue in self.issues:
            lines.append(
                f"  [{issue['check']}] {issue['affected_rows']:,} rows → {issue['action']}"
            )
        return "\n".join(lines)


class SalesDataCleaner:
    """
    Cleans fact_sales data from SAP/CSV extraction.
    All transformations are logged and auditable.
    """

    REQUIRED_COLUMNS = {
        "transaction_date", "part_id", "dealer_id",
        "qty_sold", "unit_price", "revenue",
    }

    DTYPE_MAP = {
        "part_id":        "int32",
        "dealer_id":      "int16",
        "qty_sold":       "int16",
        "unit_price":     "float32",
        "discount_pct":   "float32",
        "revenue":        "float32",
        "cogs":           "float32",
        "backorder_qty":  "int16",
    }

    def __init__(self, iqr_multiplier: float = 3.0) -> None:
        self.iqr_multiplier = iqr_multiplier

    def clean(self, df: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
        report = CleaningReport(source_rows=len(df))
        df = df.copy()

        df = self._validate_schema(df, report)
        df = self._parse_dates(df, report)
        df = self._drop_nulls(df, report)
        df = self._drop_duplicates(df, report)
        df = self._enforce_business_rules(df, report)
        df = self._remove_price_outliers(df, report)
        df = self._cast_dtypes(df)
        df = self._engineer_time_features(df)

        report.output_rows = len(df)
        logger.info(f"Cleaning complete. {report.output_rows:,} rows retained.")
        return df, report

    # ── Private Methods ──────────────────────────────────────────────────────

    def _validate_schema(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        missing = self.REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        return df

    def _parse_dates(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        before = len(df)
        df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
        bad_dates = df["transaction_date"].isna().sum()
        report.add_issue("invalid_dates", bad_dates, "dropped")
        df = df.dropna(subset=["transaction_date"])

        # Future dates are data entry errors
        future = (df["transaction_date"] > pd.Timestamp.now()).sum()
        report.add_issue("future_dates", future, "dropped")
        df = df[df["transaction_date"] <= pd.Timestamp.now()]
        return df

    def _drop_nulls(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        null_counts = df[list(self.REQUIRED_COLUMNS)].isna().any(axis=1).sum()
        report.add_issue("null_required_fields", null_counts, "dropped")
        return df.dropna(subset=list(self.REQUIRED_COLUMNS))

    def _drop_duplicates(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        # In SAP context, same part+dealer+date+qty at same price = duplicate extraction
        dupe_cols = ["transaction_date", "part_id", "dealer_id", "qty_sold", "unit_price"]
        dupes = df.duplicated(subset=dupe_cols).sum()
        report.add_issue("duplicate_rows", dupes, "dropped (kept first)")
        return df.drop_duplicates(subset=dupe_cols, keep="first")

    def _enforce_business_rules(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        # Rule 1: qty_sold must be positive
        bad_qty = (df["qty_sold"] <= 0).sum()
        report.add_issue("non_positive_qty", bad_qty, "dropped")
        df = df[df["qty_sold"] > 0]

        # Rule 2: unit_price must be positive
        bad_price = (df["unit_price"] <= 0).sum()
        report.add_issue("non_positive_price", bad_price, "dropped")
        df = df[df["unit_price"] > 0]

        # Rule 3: discount must be in [0, 100]
        if "discount_pct" in df.columns:
            bad_disc = (~df["discount_pct"].between(0, 100)).sum()
            report.add_issue("invalid_discount", bad_disc, "clipped to [0,100]")
            df["discount_pct"] = df["discount_pct"].clip(0, 100)

        # Rule 4: Recalculate revenue to ensure consistency
        if "discount_pct" in df.columns:
            df["revenue"] = (
                df["qty_sold"] * df["unit_price"] * (1 - df["discount_pct"] / 100)
            ).round(4)

        return df

    def _remove_price_outliers(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        """
        IQR-based outlier removal on unit_price, grouped by part_id.
        Prevents extreme pricing errors from distorting ABC classification.
        """
        before = len(df)
        q1 = df.groupby("part_id")["unit_price"].transform("quantile", 0.25)
        q3 = df.groupby("part_id")["unit_price"].transform("quantile", 0.75)
        iqr = q3 - q1
        lower = q1 - self.iqr_multiplier * iqr
        upper = q3 + self.iqr_multiplier * iqr
        outlier_mask = (df["unit_price"] < lower) | (df["unit_price"] > upper)
        report.add_issue("price_outliers_iqr", outlier_mask.sum(), "dropped")
        return df[~outlier_mask]

    def _cast_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Downcast to memory-efficient dtypes — critical for millions of rows."""
        for col, dtype in self.DTYPE_MAP.items():
            if col in df.columns:
                try:
                    df[col] = df[col].astype(dtype)
                except (ValueError, OverflowError):
                    logger.warning(f"Could not cast column '{col}' to {dtype}, skipping.")
        return df

    def _engineer_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Lightweight time features added during cleaning for downstream use."""
        df["year"]          = df["transaction_date"].dt.year.astype("int16")
        df["month"]         = df["transaction_date"].dt.month.astype("int8")
        df["quarter"]       = df["transaction_date"].dt.quarter.astype("int8")
        df["day_of_week"]   = df["transaction_date"].dt.dayofweek.astype("int8")
        df["is_weekend"]    = (df["day_of_week"] >= 5).astype("int8")
        df["year_month"]    = df["transaction_date"].dt.to_period("M")
        return df


class InventoryDataCleaner:
    """Cleans fact_inventory snapshot data."""

    def clean(self, df: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
        report = CleaningReport(source_rows=len(df))
        df = df.copy()

        # Parse snapshot date
        df["snapshot_date"] = pd.to_datetime(df["snapshot_date"], errors="coerce")
        bad = df["snapshot_date"].isna().sum()
        report.add_issue("invalid_snapshot_dates", bad, "dropped")
        df = df.dropna(subset=["snapshot_date"])

        # Negative quantities are SAP system errors
        for qty_col in ["qty_on_hand", "qty_reserved", "qty_in_transit"]:
            if qty_col in df.columns:
                neg = (df[qty_col] < 0).sum()
                report.add_issue(f"negative_{qty_col}", neg, "set to 0")
                df[qty_col] = df[qty_col].clip(lower=0)

        # avg_unit_cost must be positive
        bad_cost = (df["avg_unit_cost"] <= 0).sum()
        report.add_issue("invalid_unit_cost", bad_cost, "dropped")
        df = df[df["avg_unit_cost"] > 0]

        # Downcast
        for col in ["qty_on_hand", "qty_reserved", "qty_in_transit"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], downcast="integer")
        df["avg_unit_cost"] = df["avg_unit_cost"].astype("float32")

        report.output_rows = len(df)
        return df, report


def clean_file(
    input_path: Path,
    output_path: Path,
    table_type: str = "sales",
    chunk_size: int = 50_000,
) -> CleaningReport:
    """
    Stream-clean a large CSV file in chunks.
    Memory-safe for files > 1GB.
    """
    cleaner_map = {
        "sales":     SalesDataCleaner(),
        "inventory": InventoryDataCleaner(),
    }
    cleaner = cleaner_map.get(table_type)
    if cleaner is None:
        raise ValueError(f"Unknown table_type: {table_type}. Choose from {list(cleaner_map)}")

    all_reports: list[CleaningReport] = []
    first_chunk = True

    logger.info(f"Cleaning {input_path.name} in chunks of {chunk_size:,}...")

    for chunk in pd.read_csv(input_path, chunksize=chunk_size, low_memory=False):
        cleaned_chunk, chunk_report = cleaner.clean(chunk)
        all_reports.append(chunk_report)

        mode = "w" if first_chunk else "a"
        header = first_chunk
        cleaned_chunk.to_csv(output_path, index=False, mode=mode, header=header)
        first_chunk = False

    # Aggregate report
    final_report = CleaningReport(
        source_rows=sum(r.source_rows for r in all_reports),
        output_rows=sum(r.output_rows for r in all_reports),
    )
    logger.info(f"\n{final_report.summary()}")
    return final_report
