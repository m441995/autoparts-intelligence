"""
AutoParts Intelligence Platform
tests/test_abc_xyz_classifier.py

Unit tests for ABC/XYZ classification logic.
"""
from __future__ import annotations

import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features.abc_xyz_classifier import (
    classify_abc,
    classify_xyz,
    ABCXYZClassifier,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_sales(n_parts: int = 20, n_months: int = 24) -> pd.DataFrame:
    """Create a clean synthetic sales DataFrame for classifier testing."""
    rng = np.random.default_rng(0)
    rows = []
    start = date(2023, 1, 1)
    for part_id in range(1, n_parts + 1):
        demand_mean = rng.uniform(1, 50)
        for month in range(n_months):
            dt = start + timedelta(days=month * 30)
            qty = max(0, int(rng.normal(demand_mean, demand_mean * 0.3)))
            if qty == 0:
                continue
            rows.append({
                "transaction_date": pd.Timestamp(dt),
                "part_id":          part_id,
                "dealer_id":        1,
                "qty_sold":         qty,
                "revenue":          qty * rng.uniform(20, 200),
                "year_month":       pd.Period(dt, "M"),
            })
    return pd.DataFrame(rows)


# ── classify_abc ─────────────────────────────────────────────────────────────

class TestClassifyABC:

    def test_returns_only_valid_classes(self):
        revenue = pd.Series([1000, 500, 200, 100, 50, 20, 10, 5, 2, 1])
        result  = classify_abc(revenue)
        assert set(result.dropna().unique()).issubset({"A", "B", "C"})

    def test_top_revenue_is_class_a(self):
        # Single part with 90% of revenue → must be A
        revenue = pd.Series([9000, 100, 50, 30, 20])
        result  = classify_abc(revenue)
        assert result.iloc[0] == "A"

    def test_bottom_low_revenue_is_class_c(self):
        revenue = pd.Series([10000, 2000, 500, 1, 1, 1, 1, 1])
        result  = classify_abc(revenue)
        assert result.iloc[-1] == "C"

    def test_all_same_revenue(self):
        revenue = pd.Series([100.0] * 10)
        result  = classify_abc(revenue)
        # All equal → all hit A threshold together or cascade → valid classes
        assert set(result.dropna().unique()).issubset({"A", "B", "C"})

    def test_zero_total_revenue_returns_all_c(self):
        revenue = pd.Series([0.0, 0.0, 0.0])
        result  = classify_abc(revenue)
        assert (result == "C").all()

    def test_custom_thresholds(self):
        revenue = pd.Series([8000, 1000, 500, 100, 50])
        result  = classify_abc(revenue, a_threshold=70.0, b_threshold=90.0)
        # At least one A and one C expected
        assert "A" in result.values
        assert "C" in result.values

    def test_output_index_matches_input(self):
        revenue = pd.Series([500, 300, 100], index=[10, 20, 30])
        result  = classify_abc(revenue)
        assert list(result.index) == [10, 20, 30]


# ── classify_xyz ─────────────────────────────────────────────────────────────

class TestClassifyXYZ:

    def _make_monthly(self, part_id: int, values: list, dealer_id: int = 1) -> pd.DataFrame:
        months = pd.period_range("2023-01", periods=len(values), freq="M")
        return pd.DataFrame({
            "part_id":    [part_id] * len(values),
            "dealer_id":  [dealer_id] * len(values),
            "year_month": months,
            "qty_sold":   values,
        })

    def test_stable_demand_is_x(self):
        # CoV = 0 (perfectly constant)
        df = self._make_monthly(1, [10] * 24)
        result = classify_xyz(df)
        assert result.loc[result["part_id"] == 1, "xyz_class"].values[0] == "X"

    def test_zero_demand_is_z(self):
        df = self._make_monthly(2, [0] * 24)
        result = classify_xyz(df)
        assert result.loc[result["part_id"] == 2, "xyz_class"].values[0] == "Z"

    def test_highly_variable_demand_is_z(self):
        # Very high CoV: alternating 0 and 100
        df = self._make_monthly(3, [0, 100] * 12)
        result = classify_xyz(df)
        assert result.loc[result["part_id"] == 3, "xyz_class"].values[0] == "Z"

    def test_returns_only_valid_classes(self):
        df = _make_sales(n_parts=10, n_months=24)
        monthly = df[["part_id","dealer_id","year_month","qty_sold"]]
        result  = classify_xyz(monthly)
        assert set(result["xyz_class"].unique()).issubset({"X", "Y", "Z"})

    def test_output_contains_required_columns(self):
        df = _make_sales(n_parts=5, n_months=24)
        monthly = df[["part_id","dealer_id","year_month","qty_sold"]]
        result  = classify_xyz(monthly)
        for col in ["part_id","dealer_id","avg_monthly_demand","demand_cov","xyz_class"]:
            assert col in result.columns, f"Missing column: {col}"


# ── ABCXYZClassifier Integration ──────────────────────────────────────────────

class TestABCXYZClassifier:

    def test_fit_returns_dataframe(self):
        sales = _make_sales(n_parts=15, n_months=24)
        clf   = ABCXYZClassifier()
        result = clf.fit(sales)
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0

    def test_fit_contains_combined_class(self):
        sales  = _make_sales(n_parts=15, n_months=24)
        clf    = ABCXYZClassifier()
        result = clf.fit(sales)
        assert "combined_class" in result.columns
        valid_classes = {r+c for r in "ABC" for c in "XYZ"}
        assert set(result["combined_class"].unique()).issubset(valid_classes)

    def test_summary_returns_9_segments_max(self):
        sales  = _make_sales(n_parts=30, n_months=24)
        clf    = ABCXYZClassifier()
        result = clf.fit(sales)
        summary = clf.summary(result)
        assert len(summary) <= 9  # Max 9 ABC/XYZ combinations

    def test_summary_revenue_share_sums_to_100(self):
        sales  = _make_sales(n_parts=20, n_months=24)
        clf    = ABCXYZClassifier()
        result = clf.fit(sales)
        summary = clf.summary(result)
        assert abs(summary["revenue_share_pct"].sum() - 100.0) < 0.5

    def test_summary_part_share_sums_to_100(self):
        sales  = _make_sales(n_parts=20, n_months=24)
        clf    = ABCXYZClassifier()
        result = clf.fit(sales)
        summary = clf.summary(result)
        assert abs(summary["part_share_pct"].sum() - 100.0) < 0.5

    def test_action_matrix_has_9_rows(self):
        clf    = ABCXYZClassifier()
        matrix = clf.get_action_matrix()
        assert len(matrix) == 9
        assert set(matrix["combined_class"]) == {r+c for r in "ABC" for c in "XYZ"}

    def test_fit_raises_on_empty_period(self):
        """If all sales are older than the reference window, raise ValueError."""
        sales = _make_sales(n_parts=5, n_months=6)
        # Backdate all to more than 12 months ago
        sales["transaction_date"] = sales["transaction_date"] - pd.DateOffset(years=5)
        clf = ABCXYZClassifier()
        with pytest.raises(ValueError, match="No sales data in the reference period"):
            clf.fit(sales, reference_period_months=12)

    def test_a_class_drives_most_revenue(self):
        """Business invariant: A-class should always contribute ≥ 70% of revenue."""
        sales  = _make_sales(n_parts=50, n_months=24)
        clf    = ABCXYZClassifier()
        result = clf.fit(sales)
        summary = clf.summary(result)
        a_revenue_share = summary.loc[
            summary.index.str.startswith("A"), "revenue_share_pct"
        ].sum()
        assert a_revenue_share >= 70.0, (
            f"A-class revenue share was {a_revenue_share:.1f}% — expected ≥ 70%"
        )
