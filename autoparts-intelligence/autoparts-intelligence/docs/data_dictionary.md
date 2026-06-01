# Data Dictionary — AutoParts Intelligence Platform

## Tables Overview

| Table | Type | Rows (Production) | Description |
|-------|------|-------------------|-------------|
| `dim_parts` | Dimension | ~80,000 | Parts master data (SAP MARA/MAKT) |
| `dim_suppliers` | Dimension | ~150 | Supplier/vendor master (SAP LFA1) |
| `dim_dealers` | Dimension | ~50 | Branch/warehouse master |
| `fact_inventory` | Fact (daily snapshot) | ~50M/year | Daily stock positions (SAP MARD) |
| `fact_sales` | Fact (transactional) | ~5M/year | Sales transactions (SAP VBAP/VF) |
| `fact_purchase_orders` | Fact (transactional) | ~200K/year | Purchase orders (SAP EKPO) |
| `fact_demand_forecast` | Fact (analytical) | ~500K/run | Model-generated forecasts |
| `analytics_abc_xyz` | Analytical | ~80K/month | Monthly ABC/XYZ classification |
| `analytics_reorder_policy` | Analytical | ~80K/month | Computed reorder policies |

---

## dim_parts — Columns

| Column | Type | Nullable | Description | SAP Equivalent |
|--------|------|----------|-------------|----------------|
| `part_id` | INTEGER | No | Surrogate key | Internal |
| `part_number` | VARCHAR(40) | No | Internal part number | MATNR |
| `oem_number` | VARCHAR(40) | Yes | Original Equipment Manufacturer number | MFRNR |
| `part_name` | VARCHAR(200) | No | Short description | MAKTX |
| `part_description` | TEXT | Yes | Long description | MAKTL |
| `brand` | VARCHAR(80) | No | Vehicle brand | MFRNR (vendor) |
| `category` | VARCHAR(80) | No | Product category | MATKL (material group) |
| `sub_category` | VARCHAR(80) | Yes | Product sub-category | WGBEZ |
| `unit_of_measure` | VARCHAR(10) | No | Base unit (EA, SET, L, KG) | MEINS |
| `standard_cost` | NUMERIC(12,2) | No | Standard cost for COGS | STPRS (MBEW) |
| `list_price` | NUMERIC(12,2) | No | Recommended retail price | KBETR (KONP) |
| `is_critical` | BOOLEAN | No | Ops-critical flag (impacts service SLA) | Custom |
| `is_active` | BOOLEAN | No | Part active in catalog | LVORM |
| `superseded_by` | VARCHAR(40) | Yes | Successor part number for obsolete items | KMAT |

---

## fact_sales — Columns

| Column | Type | Description | Business Rule |
|--------|------|-------------|---------------|
| `transaction_date` | DATE | Invoice/billing date | Must be ≤ TODAY() |
| `part_id` | INTEGER | FK → dim_parts | Required |
| `dealer_id` | INTEGER | FK → dim_dealers | Required |
| `customer_type` | VARCHAR(30) | Workshop / Retail / Fleet / Internal | SAP: distribution channel |
| `qty_sold` | INTEGER | Quantity sold | Must be > 0 |
| `unit_price` | NUMERIC(12,2) | Actual selling price | Must be > 0 |
| `discount_pct` | NUMERIC(5,2) | Discount applied (%) | 0–100 |
| `revenue` | NUMERIC(16,2) | Generated: qty × price × (1 - disc%) | Auto-calculated |
| `cogs` | NUMERIC(16,2) | Cost of goods sold | qty × standard_cost |
| `gross_profit` | NUMERIC(16,2) | revenue - cogs | Auto-calculated |
| `was_fulfilled` | BOOLEAN | Was order fully satisfied from stock | FALSE = backorder |
| `backorder_qty` | INTEGER | Qty not fulfilled | 0 if was_fulfilled = TRUE |

---

## analytics_abc_xyz — Business Logic

### ABC Classification
| Class | Criterion | Typical SKU % | Revenue % |
|-------|-----------|---------------|-----------|
| A | Top 80% of cumulative revenue | ~20% | 80% |
| B | Next 15% (80–95%) | ~30% | 15% |
| C | Bottom 5% (>95%) | ~50% | 5% |

### XYZ Classification (Coefficient of Variation = σ/μ)
| Class | CoV Threshold | Demand Pattern |
|-------|--------------|----------------|
| X | ≤ 0.50 | Stable, predictable |
| Y | 0.50–1.00 | Variable, seasonal |
| Z | > 1.00 | Irregular, sporadic |

### Action Matrix
| Segment | SKU Profile | Recommended Action |
|---------|-------------|-------------------|
| AX | High value, stable | Tight control, min safety stock |
| AY | High value, variable | Safety stock + short-term forecast |
| AZ | High value, irregular | Emergency buffer + supplier contract |
| BX | Medium value, stable | Standard replenishment, monthly review |
| CZ | Low value, irregular | Order on demand only — candidate for removal |

---

## KPI Definitions

| KPI | Formula | Target | Frequency |
|-----|---------|--------|-----------|
| Inventory Turnover | Annual COGS / Avg Inventory Value | > 8x | Monthly |
| Fill Rate | Fulfilled Lines / Total Order Lines | > 95% | Daily |
| Service Level | 1 − (Stockout Events / Demand Events) | > 97% | Weekly |
| Backorder Rate | Backorder Lines / Total Lines | < 3% | Daily |
| Dead Stock % | Dead Stock Value / Total Inventory Value | < 5% | Monthly |
| MAPE | Mean Absolute % Forecast Error | < 15% | Monthly |
| Supplier OTD | On-time PO Lines / Total Closed PO Lines | > 90% | Monthly |
