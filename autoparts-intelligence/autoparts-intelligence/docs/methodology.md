# Analytical Methodology — AutoParts Intelligence Platform

## 1. ABC/XYZ Classification

### Why Dual-Axis?
Single-axis ABC only tells you *how valuable* a part is. XYZ adds *how predictable* the demand is. Together they drive fundamentally different inventory policies:

| | X (Stable) | Y (Variable) | Z (Sporadic) |
|--|-----------|-------------|-------------|
| **A (High Value)** | Tight, lean | Safety stock | Emergency buffer |
| **B (Medium Value)** | Standard cycle | Moderate buffer | Demand monitoring |
| **C (Low Value)** | Bulk order | Consignment | Order on demand |

### Coefficient of Variation (CoV)
```
CoV = σ / μ
```
Where σ = standard deviation of monthly demand, μ = mean monthly demand.
- CoV < 0.5 → X (stable)
- 0.5 ≤ CoV ≤ 1.0 → Y (variable)
- CoV > 1.0 → Z (highly irregular)

---

## 2. Safety Stock Formula

We use the **combined demand and lead time variability formula**:

```
SS = Z × √( LT × σ_d² + d̄² × σ_LT² )
```

Where:
- `Z` = service level Z-score (1.645 for 95%, 2.054 for 98%)
- `LT` = average lead time in days
- `σ_d` = standard deviation of daily demand
- `d̄` = average daily demand
- `σ_LT` = standard deviation of lead time in days

### Why not the simple formula (Z × σ_d × √LT)?
The simple formula assumes lead time is constant, which is unrealistic in automotive supply chains. Our formula accounts for both demand AND lead time variability — critical for suppliers from overseas (Japan, Germany) with high LT variance.

### Reorder Point (ROP)
```
ROP = (d̄ × LT) + SS
```

### Economic Order Quantity (EOQ)
```
EOQ = √( 2 × D × S / H )
```
Where:
- `D` = annual demand units
- `S` = ordering cost per order ($25 default)
- `H` = holding cost per unit per year (25% of unit cost)

---

## 3. Time-Series Forecasting

### Model Selection Logic
```
If history ≥ 24 months:
    Try SARIMA(1,1,1)(1,1,1,12) first
    If MAPE > 30%: fall back to ETS
Else:
    Use ETS (Holt-Winters additive)
    If len(history) < 12: skip (insufficient data)
```

### SARIMA
- **S**easonal **A**uto**R**egressive **I**ntegrated **M**oving **A**verage
- Handles: trend, seasonality (12-month), autocorrelation
- Parameters: (p,d,q)(P,D,Q,s) = (1,1,1)(1,1,1,12)
- Validation: 3-month holdout set, MAPE evaluation

### ETS (Exponential Smoothing)
- Holt-Winters additive model
- Handles: trend + seasonality
- More robust on shorter series than SARIMA
- Used as automatic fallback

### Evaluation Metric: MAPE
```
MAPE = (1/n) × Σ |actual - forecast| / actual × 100%
```
Target: < 15% MAPE on holdout set.

---

## 4. Stockout Prediction Model

### Feature Categories
1. **Stock position**: qty_available, days_coverage, stock_vs_rop
2. **Demand velocity**: avg_daily_demand_30d, demand_trend (30d vs 90d)
3. **Demand variability**: demand_std_30d, CoV
4. **Replenishment**: avg_lead_time_days, lead_time_std_dev
5. **Supplier**: on_time_rate, avg_po_lead_time
6. **Classification**: abc_class, xyz_class (encoded)

### Target Variable
```
will_stockout_14d = 1 if qty_available < (avg_daily_demand × 14) else 0
```
Binary classification — stockout risk in the next 14 days.

### Model Architecture
- **Random Forest**: 300 trees, max_depth=12, class_weight='balanced'
- **XGBoost**: 300 estimators, lr=0.05, scale_pos_weight=auto
- **Ensemble**: Simple average of RF + XGB probabilities

### Validation
- **TimeSeriesSplit** (5 folds) — no data leakage from future to past
- Primary metric: AUC-ROC (target > 0.85)
- Secondary: Precision at 70% Recall (operational threshold)

### Class Imbalance Handling
Stockouts are rare events (typically 3–8% of inventory positions).
- RF: `class_weight='balanced'` (auto-adjusts sample weights)
- XGB: `scale_pos_weight = n_negative / n_positive`

---

## 5. Pipeline Execution Order

```
1. Data Ingestion (CSV/DB extraction)
        ↓
2. Data Cleaning (validation, dedup, outlier removal)
        ↓
3. Feature Engineering:
   3a. ABC/XYZ Classification
   3b. Safety Stock + ROP Calculation
        ↓
4. Demand Forecasting (per part/dealer, parallel)
        ↓
5. ML Stockout Scoring (ensemble model)
        ↓
6. Output: Parquet files → Power BI / PostgreSQL
```

### Scalability Notes
- Chunked CSV reading (50K rows/chunk) for memory safety
- Joblib parallel forecasting (uses all CPU cores)
- Vectorized pandas operations throughout (no row-level Python loops)
- Parquet output with Snappy compression (~4–6x smaller than CSV)
- Production target: 1M sales rows processed in < 3 minutes on 8-core machine

---

## 6. Power BI Dashboard Design Principles

### Page 1 — Executive Overview
**Audience**: GM, Branch Manager
**Decision**: Portfolio health at a glance, revenue trends, fill rate
**Visuals**: KPI cards, revenue trend line, top 10 parts by revenue bar chart

### Page 2 — Inventory Health
**Audience**: Inventory Controller, Parts Manager
**Decision**: Where is capital locked? What's aging?
**Visuals**: Dead stock aging matrix, stock health waterfall, ABC heatmap

### Page 3 — Demand Analysis
**Audience**: Parts Manager, Procurement
**Decision**: What's moving, trend direction, seasonal peaks
**Visuals**: Monthly demand trend, category mix, customer type breakdown

### Page 4 — Supplier Performance
**Audience**: Procurement Manager
**Decision**: Supplier scorecard, lead time risk, preferred vendor selection
**Visuals**: Supplier OTD rate bar, lead time variance scatter, late delivery heat

### Page 5 — Forecasting & Replenishment
**Audience**: Procurement, Inventory Controller
**Decision**: What to order, how much, when
**Visuals**: Forecast vs actual line, reorder alert table, replenishment cost estimate
