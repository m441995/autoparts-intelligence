"""
AutoParts Intelligence Platform
src/main.py

Pipeline orchestrator — runs the full analytics pipeline end-to-end
or individual stages via CLI flags.

Usage
-----
  python src/main.py --mode full             # Full pipeline
  python src/main.py --mode clean            # Data cleaning only
  python src/main.py --mode classify         # ABC/XYZ only
  python src/main.py --mode forecast         # Forecasting only
  python src/main.py --mode score            # Stockout scoring only
  python src/main.py --mode report           # Save all outputs
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.logger import logger
from src.utils.config import config
from src.cleaning.cleaning_pipeline import SalesDataCleaner, InventoryDataCleaner
from src.features.abc_xyz_classifier import ABCXYZClassifier
from src.features.safety_stock import SafetyStockEngine
from src.models.demand_forecaster import DemandForecaster
from src.models.stockout_predictor import StockoutPredictor, build_feature_matrix


def load_sample_data() -> dict[str, pd.DataFrame]:
    """Load sample CSVs from data/sample/ for demo run."""
    sample_dir = config.paths.data_sample
    data = {}

    for fname, key in [
        ("fact_sales_sample.csv",     "sales"),
        ("fact_inventory_sample.csv", "inventory"),
        ("dim_parts_sample.csv",      "parts"),
    ]:
        fpath = sample_dir / fname
        if fpath.exists():
            logger.info(f"Loading {fname}...")
            data[key] = pd.read_csv(fpath, low_memory=False)
            logger.info(f"  → {len(data[key]):,} rows")
        else:
            logger.warning(f"  ⚠ {fname} not found. Run generate_sample_data.py first.")

    # Create empty PO stub if not available
    if "purchase_orders" not in data:
        data["purchase_orders"] = pd.DataFrame(columns=[
            "po_id","part_id","supplier_id","dealer_id",
            "order_date","actual_receipt_date","lead_time_actual",
            "lead_time_delta","qty_ordered","unit_cost","po_status",
        ])
    return data


def stage_clean(data: dict) -> dict:
    """Stage 1: Data Cleaning."""
    logger.info("=" * 60)
    logger.info("STAGE 1: Data Cleaning")
    logger.info("=" * 60)

    sales_cleaner = SalesDataCleaner()
    inv_cleaner   = InventoryDataCleaner()

    if "sales" in data:
        data["sales_clean"], sales_report = sales_cleaner.clean(data["sales"])
        logger.info(f"\n{sales_report.summary()}")

    if "inventory" in data:
        data["inventory_clean"], inv_report = inv_cleaner.clean(data["inventory"])
        logger.info(f"\n{inv_report.summary()}")

    return data


def stage_classify(data: dict) -> dict:
    """Stage 2: ABC/XYZ Classification."""
    logger.info("=" * 60)
    logger.info("STAGE 2: ABC/XYZ Classification")
    logger.info("=" * 60)

    if "sales_clean" not in data:
        logger.error("No clean sales data. Run cleaning stage first.")
        return data

    clf = ABCXYZClassifier()
    data["abc_xyz"] = clf.fit(data["sales_clean"])
    data["abc_xyz_summary"] = clf.summary(data["abc_xyz"])

    logger.info(f"\nABC/XYZ Summary:\n{data['abc_xyz_summary'].to_string()}")
    return data


def stage_safety_stock(data: dict) -> dict:
    """Stage 3: Safety Stock & Reorder Point Calculation."""
    logger.info("=" * 60)
    logger.info("STAGE 3: Safety Stock & Reorder Policies")
    logger.info("=" * 60)

    engine = SafetyStockEngine()
    data["reorder_policies"] = engine.compute_policies(
        sales           = data.get("sales_clean", pd.DataFrame()),
        purchase_orders = data.get("purchase_orders", pd.DataFrame()),
        abc_xyz         = data.get("abc_xyz"),
        parts_master    = data.get("parts"),
    )
    logger.info(f"Computed {len(data['reorder_policies']):,} reorder policies.")
    return data


def stage_forecast(data: dict) -> dict:
    """Stage 4: Demand Forecasting."""
    logger.info("=" * 60)
    logger.info("STAGE 4: Demand Forecasting")
    logger.info("=" * 60)

    if "sales_clean" not in data or len(data["sales_clean"]) == 0:
        logger.error("No clean sales data for forecasting.")
        return data

    forecaster = DemandForecaster(horizon=6, holdout_months=3, n_jobs=-1)
    data["forecasts"] = forecaster.fit_predict(data["sales_clean"])

    if len(data["forecasts"]) > 0:
        accuracy = forecaster.get_accuracy_summary(data["forecasts"])
        logger.info(f"\nForecast Accuracy:\n{accuracy.to_string()}")

    return data


def stage_stockout_score(data: dict) -> dict:
    """Stage 5: ML Stockout Risk Scoring."""
    logger.info("=" * 60)
    logger.info("STAGE 5: Stockout Risk Prediction")
    logger.info("=" * 60)

    required = ["inventory_clean", "sales_clean", "purchase_orders"]
    if not all(k in data for k in ["inventory_clean", "sales_clean"]):
        logger.error("Missing cleaned data for stockout prediction.")
        return data

    features = build_feature_matrix(
        inventory        = data["inventory_clean"],
        sales            = data["sales_clean"],
        purchase_orders  = data.get("purchase_orders", pd.DataFrame()),
        reorder_policies = data.get("reorder_policies", pd.DataFrame()),
        abc_xyz          = data.get("abc_xyz"),
    )

    predictor = StockoutPredictor()
    metrics   = predictor.train(features)
    logger.info(f"\nModel AUC-ROC: {metrics.auc_roc}")
    logger.info(f"Average Precision: {metrics.avg_precision}")
    logger.info(f"\nClassification Report:\n{metrics.report}")

    data["stockout_scores"] = predictor.score_inventory(features)
    data["stockout_predictor"] = predictor

    # Save model
    predictor.save()
    return data


def stage_save_outputs(data: dict) -> None:
    """Save all analytical outputs to data/processed/."""
    logger.info("=" * 60)
    logger.info("Saving Outputs")
    logger.info("=" * 60)

    run_ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out_dir = config.paths.data_proc / run_ts
    out_dir.mkdir(parents=True, exist_ok=True)

    output_map = {
        "abc_xyz":          "abc_xyz_classification.parquet",
        "reorder_policies": "reorder_policies.parquet",
        "forecasts":        "demand_forecasts.parquet",
        "stockout_scores":  "stockout_risk_scores.parquet",
        "abc_xyz_summary":  "abc_xyz_summary.csv",
    }

    for key, fname in output_map.items():
        if key in data and len(data[key]) > 0:
            fpath = out_dir / fname
            if fname.endswith(".parquet"):
                data[key].to_parquet(fpath, index=False, compression="snappy")
            else:
                data[key].to_csv(fpath, index=False)
            logger.info(f"  ✓ {fname}")

    logger.info(f"\nAll outputs saved to: {out_dir}")


def run_pipeline(mode: str = "full") -> None:
    """Main orchestrator."""
    logger.info(f"\n{'='*60}")
    logger.info(f"AutoParts Intelligence Platform — Pipeline [{mode.upper()}]")
    logger.info(f"{'='*60}\n")

    data = load_sample_data()

    if mode in ("full", "clean"):
        data = stage_clean(data)

    if mode in ("full", "classify"):
        if "sales_clean" not in data:
            data = stage_clean(data)
        data = stage_classify(data)

    if mode in ("full",):
        data = stage_safety_stock(data)
        data = stage_forecast(data)
        data = stage_stockout_score(data)
        stage_save_outputs(data)

    elif mode == "forecast":
        if "sales_clean" not in data:
            data = stage_clean(data)
        data = stage_forecast(data)
        stage_save_outputs(data)

    elif mode == "score":
        data = stage_clean(data)
        data = stage_classify(data)
        data = stage_safety_stock(data)
        data = stage_stockout_score(data)
        stage_save_outputs(data)

    logger.info("\n✅ Pipeline complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AutoParts Intelligence Pipeline")
    parser.add_argument(
        "--mode",
        choices=["full", "clean", "classify", "forecast", "score", "report"],
        default="full",
        help="Pipeline stage to run",
    )
    args = parser.parse_args()
    run_pipeline(mode=args.mode)
