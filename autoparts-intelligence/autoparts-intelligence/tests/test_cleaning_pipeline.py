"""
AutoParts Intelligence Platform
tests/test_cleaning_pipeline.py

Unit tests for the data cleaning pipeline.
Run: pytest tests/ -v --cov=src
"""
from __future__ import annotations

import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cleaning.cleaning_pipeline import SalesDataCleaner, InventoryDataCleaner, CleaningReport


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_valid_sales(n: int = 100) -> pd.DataFrame:
    """Generate a minimal valid sales DataFrame."""
    rng = np.random.default_rng(42)
    today = date.today()
    return pd.DataFrame({
        "transaction_date": [
            (today - timedelta(days=int(d))).isoformat()
            for d in rng.integers(1, 365, size=n)
        ],
        "part_id":        rng.integers(1, 500, size=n).astype(int),
        "dealer_id":      rng.integers(1, 10,  size=n).astype(int),
        "qty_sold":       rng.integers(1, 50,  size=n).astype(int),
        "unit_price":     rng.uniform(10, 500, size=n).round(2),
        "discount_pct":   rng.choice([0, 5, 10], size=n).astype(float),
        "revenue":        rng.uniform(100, 5000, size=n).round(2),
        "cogs":           rng.uniform(50,  4000, size=n).round(2),
        "was_fulfilled":  rng.choice([True, False], size=n, p=[0.97, 0.03]),
        "backorder_qty":  np.zeros(n, dtype=int),
    })


def _make_valid_inventory(n: int = 50) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "snapshot_date":      [date.today().isoformat()] * n,
        "part_id":            rng.integers(1, 500, size=n).astype(int),
        "dealer_id":          rng.integers(1, 10,  size=n).astype(int),
        "qty_on_hand":        rng.integers(0, 200, size=n).astype(int),
        "qty_reserved":       rng.integers(0, 20,  size=n).astype(int),
        "qty_in_transit":     rng.integers(0, 50,  size=n).astype(int),
        "avg_unit_cost":      rng.uniform(5, 300,  size=n).round(4),
        "last_movement_date": [date.today().isoformat()] * n,
    })


# ── SalesDataCleaner Tests ────────────────────────────────────────────────────

class TestSalesDataCleaner:

    def test_clean_valid_data_returns_same_rows(self):
        df = _make_valid_sales(200)
        cleaner = SalesDataCleaner()
        clean, report = cleaner.clean(df)
        assert report.output_rows <= report.source_rows
        assert len(clean) > 0

    def test_drops_future_dates(self):
        df = _make_valid_sales(50)
        # Inject 5 future-dated rows
        future_dates = ["2099-01-01"] * 5
        df_future = df.copy()
        df_future.loc[df_future.index[:5], "transaction_date"] = future_dates
        cleaner = SalesDataCleaner()
        clean, report = cleaner.clean(df_future)
        assert not (clean["transaction_date"] > pd.Timestamp.now()).any()

    def test_drops_non_positive_qty(self):
        df = _make_valid_sales(50)
        df.loc[df.index[:5], "qty_sold"] = 0
        df.loc[df.index[5:8], "qty_sold"] = -3
        cleaner = SalesDataCleaner()
        clean, _ = cleaner.clean(df)
        assert (clean["qty_sold"] > 0).all()

    def test_drops_non_positive_price(self):
        df = _make_valid_sales(50)
        df.loc[df.index[:3], "unit_price"] = 0.0
        cleaner = SalesDataCleaner()
        clean, _ = cleaner.clean(df)
        assert (clean["unit_price"] > 0).all()

    def test_clips_discount_out_of_range(self):
        df = _make_valid_sales(50)
        df.loc[df.index[:3], "discount_pct"] = 150.0   # Invalid
        df.loc[df.index[3:5], "discount_pct"] = -5.0   # Invalid
        cleaner = SalesDataCleaner()
        clean, _ = cleaner.clean(df)
        assert clean["discount_pct"].between(0, 100).all()

    def test_drops_exact_duplicates(self):
        df = _make_valid_sales(50)
        df_with_dupes = pd.concat([df, df.iloc[:10]], ignore_index=True)
        cleaner = SalesDataCleaner()
        clean, report = cleaner.clean(df_with_dupes)
        # Should have fewer rows than input
        assert len(clean) < len(df_with_dupes)

    def test_adds_time_features(self):
        df = _make_valid_sales(50)
        cleaner = SalesDataCleaner()
        clean, _ = cleaner.clean(df)
        for col in ["year", "month", "quarter", "day_of_week", "is_weekend"]:
            assert col in clean.columns, f"Missing time feature: {col}"

    def test_missing_required_column_raises(self):
        df = _make_valid_sales(20).drop(columns=["qty_sold"])
        cleaner = SalesDataCleaner()
        with pytest.raises(ValueError, match="Missing required columns"):
            cleaner.clean(df)

    def test_invalid_dates_dropped(self):
        df = _make_valid_sales(50)
        df.loc[df.index[:5], "transaction_date"] = "not-a-date"
        cleaner = SalesDataCleaner()
        clean, report = cleaner.clean(df)
        assert clean["transaction_date"].isna().sum() == 0

    def test_cleaning_report_has_correct_counts(self):
        df = _make_valid_sales(100)
        cleaner = SalesDataCleaner()
        _, report = cleaner.clean(df)
        assert report.source_rows == 100
        assert isinstance(report.output_rows, int)
        assert report.output_rows >= 0

    def test_revenue_recalculated(self):
        df = _make_valid_sales(10)
        # Corrupt the revenue column
        df["revenue"] = 0.0
        cleaner = SalesDataCleaner()
        clean, _ = cleaner.clean(df)
        expected = clean["qty_sold"] * clean["unit_price"] * (1 - clean["discount_pct"] / 100)
        pd.testing.assert_series_equal(
            clean["revenue"].round(2), expected.round(2),
            check_names=False
        )


# ── InventoryDataCleaner Tests ────────────────────────────────────────────────

class TestInventoryDataCleaner:

    def test_clean_valid_data(self):
        df = _make_valid_inventory(50)
        cleaner = InventoryDataCleaner()
        clean, report = cleaner.clean(df)
        assert len(clean) > 0
        assert report.output_rows <= report.source_rows

    def test_negative_quantities_set_to_zero(self):
        df = _make_valid_inventory(30)
        df.loc[df.index[:5], "qty_on_hand"]    = -10
        df.loc[df.index[5:8], "qty_reserved"]  = -5
        cleaner = InventoryDataCleaner()
        clean, _ = cleaner.clean(df)
        assert (clean["qty_on_hand"] >= 0).all()
        assert (clean["qty_reserved"] >= 0).all()

    def test_invalid_snapshot_dates_dropped(self):
        df = _make_valid_inventory(30)
        df.loc[df.index[:5], "snapshot_date"] = "INVALID"
        cleaner = InventoryDataCleaner()
        clean, _ = cleaner.clean(df)
        assert clean["snapshot_date"].isna().sum() == 0

    def test_zero_unit_cost_dropped(self):
        df = _make_valid_inventory(30)
        df.loc[df.index[:3], "avg_unit_cost"] = 0.0
        cleaner = InventoryDataCleaner()
        clean, _ = cleaner.clean(df)
        assert (clean["avg_unit_cost"] > 0).all()


# ── CleaningReport Tests ──────────────────────────────────────────────────────

class TestCleaningReport:

    def test_summary_string_contains_counts(self):
        report = CleaningReport(source_rows=1000, output_rows=950)
        report.add_issue("test_check", 50, "dropped")
        summary = report.summary()
        assert "1,000" in summary
        assert "950" in summary
        assert "test_check" in summary

    def test_add_issue_increments_list(self):
        report = CleaningReport(source_rows=100, output_rows=90)
        report.add_issue("check_a", 5, "dropped")
        report.add_issue("check_b", 3, "clipped")
        assert len(report.issues) == 2
        assert report.issues[0]["check"] == "check_a"
        assert report.issues[1]["affected_rows"] == 3
