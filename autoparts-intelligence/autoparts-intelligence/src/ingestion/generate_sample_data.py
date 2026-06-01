"""
AutoParts Intelligence Platform
src/ingestion/generate_sample_data.py

Generates a realistic synthetic dataset (500K+ rows) for demo/testing.
Mirrors SAP extraction structure: MARA, MARD, VBAP, EKPO.

Run: python -m src.ingestion.generate_sample_data
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import date, timedelta
import random

# ── Minimal standalone config (no circular imports) ─────────────────────────
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "sample"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RNG = np.random.default_rng(seed=42)

# ── Master Data ──────────────────────────────────────────────────────────────
BRANDS      = ["Toyota", "Honda", "Nissan", "Hyundai", "BMW", "Mercedes"]
CATEGORIES  = {
    "Engine":     ["Oil Filter", "Air Filter", "Spark Plug", "Timing Belt",
                   "Engine Mount", "Valve Cover Gasket"],
    "Brakes":     ["Brake Pad Set", "Brake Disc", "Brake Caliper",
                   "Brake Hose", "Brake Fluid"],
    "Suspension": ["Shock Absorber", "Control Arm", "Tie Rod End",
                   "Stabilizer Link", "Ball Joint"],
    "Electrical": ["Battery", "Alternator", "Starter Motor",
                   "Ignition Coil", "Oxygen Sensor"],
    "Cooling":    ["Radiator", "Thermostat", "Water Pump",
                   "Coolant Hose", "Radiator Cap"],
    "Drivetrain": ["CV Joint", "Drive Shaft", "Transmission Oil",
                   "Clutch Kit", "Gearbox Mount"],
    "Body":       ["Wiper Blade", "Windshield Washer", "Door Handle",
                   "Mirror Glass", "Cabin Air Filter"],
    "Lubricants": ["Engine Oil 5W30", "Gear Oil", "Brake Fluid DOT4",
                   "Power Steering Fluid", "AC Refrigerant"],
}
DEALERS      = ["Cairo Main", "Nasr City", "Alexandria", "Giza", "Mansoura"]
CUSTOMER_TYPES = ["Workshop", "Retail", "Fleet", "Internal"]
SOURCES      = ["Counter", "B2B", "Online"]


def _make_part_number(brand: str, i: int) -> str:
    prefix = brand[:3].upper()
    return f"{prefix}-{RNG.integers(10000, 99999)}-{i:04d}"


def generate_parts_master(n_parts: int = 2000) -> pd.DataFrame:
    """Generate realistic parts master data."""
    records = []
    idx = 0
    for brand in BRANDS:
        for category, sub_list in CATEGORIES.items():
            parts_per_combo = n_parts // (len(BRANDS) * len(CATEGORIES))
            for _ in range(parts_per_combo):
                sub_cat = RNG.choice(sub_list)
                cost = RNG.uniform(5, 800)
                records.append({
                    "part_id":       idx + 1,
                    "part_number":   _make_part_number(brand, idx),
                    "part_name":     f"{sub_cat} - {brand}",
                    "brand":         brand,
                    "category":      category,
                    "sub_category":  sub_cat,
                    "standard_cost": round(float(cost), 2),
                    "list_price":    round(float(cost * RNG.uniform(1.8, 3.5)), 2),
                    "is_critical":   bool(RNG.random() < 0.15),
                    "is_active":     bool(RNG.random() > 0.05),
                })
                idx += 1
    return pd.DataFrame(records)


def generate_sales_history(
    parts: pd.DataFrame,
    start_date: date = date(2022, 1, 1),
    end_date: date   = date(2024, 12, 31),
) -> pd.DataFrame:
    """
    Generate 2+ years of daily sales transactions.
    Applies:
      - Seasonality (Ramadan dip, summer peak for AC parts)
      - Trend (5% annual growth)
      - Category-specific demand volatility
      - Random zeros (not every part sells every day)
    """
    date_range = pd.date_range(start_date, end_date, freq="D")
    records    = []

    # Assign velocity profiles: A=high, B=medium, C=low/zero demand
    n_parts = len(parts)
    a_class_n = int(n_parts * 0.20)
    b_class_n = int(n_parts * 0.30)

    velocity = (
        ["A"] * a_class_n
        + ["B"] * b_class_n
        + ["C"] * (n_parts - a_class_n - b_class_n)
    )
    RNG.shuffle(velocity)
    parts = parts.copy()
    parts["velocity"] = velocity

    demand_params = {
        "A": {"mean": 8,  "std": 4,  "zero_prob": 0.05},
        "B": {"mean": 3,  "std": 2,  "zero_prob": 0.25},
        "C": {"mean": 0.8,"std": 0.6,"zero_prob": 0.65},
    }

    # Sample a manageable subset for demo (100 parts × 3 years × 5 dealers)
    sample_parts = parts.sample(n=min(200, n_parts), random_state=42)

    for _, part in sample_parts.iterrows():
        dp   = demand_params[part["velocity"]]
        dealer_idx = RNG.integers(1, len(DEALERS) + 1)

        for dt in date_range:
            # Seasonality multiplier
            month = dt.month
            season_mult = 1.0
            if part["category"] == "Cooling" and month in [6, 7, 8]:
                season_mult = 1.8   # Summer AC peak
            elif part["category"] == "Engine" and month in [1, 2]:
                season_mult = 1.3   # Post-new-year service peak
            elif month == 4:        # Ramadan (approximate)
                season_mult = 0.75

            # Year-over-year growth
            year_growth = 1 + 0.05 * (dt.year - start_date.year)

            # Generate demand
            if RNG.random() < dp["zero_prob"]:
                continue   # No sale this day

            qty = max(1, int(RNG.normal(
                dp["mean"] * season_mult * year_growth,
                dp["std"]
            )))
            unit_price  = part["list_price"] * RNG.uniform(0.95, 1.05)
            discount    = float(RNG.choice([0, 0, 0, 5, 10, 15], p=[0.5, 0.2, 0.15, 0.08, 0.05, 0.02]))
            was_fulfilled = RNG.random() > 0.03   # 97% fill rate

            records.append({
                "transaction_date": dt.strftime("%Y-%m-%d"),
                "part_id":          int(part["part_id"]),
                "dealer_id":        int(dealer_idx),
                "customer_type":    str(RNG.choice(CUSTOMER_TYPES, p=[0.50, 0.25, 0.20, 0.05])),
                "qty_sold":         qty,
                "unit_price":       round(float(unit_price), 2),
                "discount_pct":     discount,
                "revenue":          round(float(qty * unit_price * (1 - discount / 100)), 2),
                "cogs":             round(float(qty * part["standard_cost"]), 2),
                "order_source":     str(RNG.choice(SOURCES, p=[0.65, 0.25, 0.10])),
                "was_fulfilled":    bool(was_fulfilled),
                "backorder_qty":    0 if was_fulfilled else qty,
            })

    return pd.DataFrame(records)


def generate_inventory_snapshots(
    parts: pd.DataFrame,
    sales: pd.DataFrame,
    reference_date: date = date(2024, 12, 31),
) -> pd.DataFrame:
    """Generate a single-day inventory snapshot per part/dealer."""
    records = []
    grouped = sales.groupby(["part_id", "dealer_id"])

    for (part_id, dealer_id), grp in grouped:
        part_row = parts[parts["part_id"] == part_id].iloc[0]
        avg_daily = grp["qty_sold"].sum() / max(len(grp["transaction_date"].unique()), 1)
        lead_time  = RNG.integers(7, 45)
        safety     = int(avg_daily * lead_time * 0.5)
        on_hand    = max(0, int(RNG.normal(avg_daily * lead_time * 1.5, avg_daily * 5)))

        records.append({
            "snapshot_date":    reference_date.isoformat(),
            "part_id":          int(part_id),
            "dealer_id":        int(dealer_id),
            "qty_on_hand":      on_hand,
            "qty_reserved":     max(0, int(on_hand * RNG.uniform(0.05, 0.20))),
            "qty_in_transit":   int(avg_daily * RNG.integers(0, lead_time)),
            "avg_unit_cost":    round(float(part_row["standard_cost"] * RNG.uniform(0.95, 1.05)), 4),
            "last_movement_date": (
                reference_date - timedelta(days=int(RNG.integers(0, 30)))
            ).isoformat(),
        })

    return pd.DataFrame(records)


def main() -> None:
    print("🔧 Generating AutoParts synthetic dataset...")

    # 1. Parts Master
    print("  → Parts master...")
    parts = generate_parts_master(n_parts=2000)
    parts.to_csv(OUTPUT_DIR / "dim_parts_sample.csv", index=False)
    print(f"     ✓ {len(parts):,} parts")

    # 2. Sales History
    print("  → Sales history (this may take ~30s)...")
    sales = generate_sales_history(parts)
    sales.to_csv(OUTPUT_DIR / "fact_sales_sample.csv", index=False)
    print(f"     ✓ {len(sales):,} sales transactions")

    # 3. Inventory Snapshot
    print("  → Inventory snapshots...")
    inventory = generate_inventory_snapshots(parts, sales)
    inventory.to_csv(OUTPUT_DIR / "fact_inventory_sample.csv", index=False)
    print(f"     ✓ {len(inventory):,} inventory records")

    print(f"\n✅ Sample data written to: {OUTPUT_DIR}")
    print("   Files: dim_parts_sample.csv, fact_sales_sample.csv, fact_inventory_sample.csv")


if __name__ == "__main__":
    main()
