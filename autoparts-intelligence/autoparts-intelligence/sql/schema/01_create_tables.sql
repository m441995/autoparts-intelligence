-- ============================================================
-- AutoParts Intelligence Platform
-- Schema: 01_create_tables.sql
-- Target: PostgreSQL 14+
-- Author: Mohamed Adel
-- Description: Full data warehouse schema for automotive
--              spare parts analytics (SAP-aligned structure)
-- ============================================================

-- Enable extension for UUID support
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- DIMENSION TABLE: dim_parts
-- Maps to SAP MM60 / Material Master (MARA/MAKT)
-- ============================================================
CREATE TABLE IF NOT EXISTS dim_parts (
    part_id          SERIAL PRIMARY KEY,
    part_number      VARCHAR(40)  NOT NULL UNIQUE,  -- SAP: MATNR
    oem_number       VARCHAR(40),                    -- Original OEM reference
    part_name        VARCHAR(200) NOT NULL,
    part_description TEXT,
    brand            VARCHAR(80)  NOT NULL,          -- Toyota, Honda, BMW...
    category         VARCHAR(80)  NOT NULL,          -- Engine, Brake, Filter...
    sub_category     VARCHAR(80),
    unit_of_measure  VARCHAR(10)  NOT NULL DEFAULT 'EA',  -- EA, SET, L, KG
    standard_cost    NUMERIC(12,2) NOT NULL,
    list_price       NUMERIC(12,2) NOT NULL,
    weight_kg        NUMERIC(8,3),
    is_critical      BOOLEAN      NOT NULL DEFAULT FALSE,  -- Ops-critical flag
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
    superseded_by    VARCHAR(40),                    -- Successor part number
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ============================================================
-- DIMENSION TABLE: dim_suppliers
-- Maps to SAP LFA1 / Vendor Master
-- ============================================================
CREATE TABLE IF NOT EXISTS dim_suppliers (
    supplier_id      SERIAL PRIMARY KEY,
    supplier_code    VARCHAR(20)  NOT NULL UNIQUE,  -- SAP: LIFNR
    supplier_name    VARCHAR(200) NOT NULL,
    country          VARCHAR(60)  NOT NULL,
    city             VARCHAR(60),
    supplier_type    VARCHAR(30)  NOT NULL,          -- OEM, OES, Aftermarket
    payment_terms    VARCHAR(20),                    -- NET30, NET60...
    currency         VARCHAR(3)   NOT NULL DEFAULT 'USD',
    lead_time_days   INTEGER      NOT NULL,          -- Average lead time
    min_order_value  NUMERIC(12,2),
    is_preferred     BOOLEAN      NOT NULL DEFAULT FALSE,
    rating           NUMERIC(3,1) CHECK (rating BETWEEN 0 AND 5),
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ============================================================
-- DIMENSION TABLE: dim_dealers (branches / warehouses)
-- Maps to SAP Organizational Units
-- ============================================================
CREATE TABLE IF NOT EXISTS dim_dealers (
    dealer_id        SERIAL PRIMARY KEY,
    dealer_code      VARCHAR(20)  NOT NULL UNIQUE,
    dealer_name      VARCHAR(200) NOT NULL,
    region           VARCHAR(60)  NOT NULL,
    city             VARCHAR(60)  NOT NULL,
    country          VARCHAR(60)  NOT NULL DEFAULT 'Egypt',
    warehouse_type   VARCHAR(30)  NOT NULL DEFAULT 'Regional',
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE
);

-- ============================================================
-- FACT TABLE: fact_inventory
-- Daily snapshot of stock positions
-- Maps to SAP MB52 / Stock Overview (MARD, MSKA)
-- ============================================================
CREATE TABLE IF NOT EXISTS fact_inventory (
    inventory_id       BIGSERIAL PRIMARY KEY,
    snapshot_date      DATE         NOT NULL,
    part_id            INTEGER      NOT NULL REFERENCES dim_parts(part_id),
    dealer_id          INTEGER      NOT NULL REFERENCES dim_dealers(dealer_id),
    qty_on_hand        INTEGER      NOT NULL DEFAULT 0,
    qty_reserved       INTEGER      NOT NULL DEFAULT 0,    -- Committed to orders
    qty_in_transit     INTEGER      NOT NULL DEFAULT 0,    -- On PO, not received
    qty_available      INTEGER      GENERATED ALWAYS AS
                           (qty_on_hand - qty_reserved) STORED,
    avg_unit_cost      NUMERIC(12,4) NOT NULL,
    total_stock_value  NUMERIC(16,2) GENERATED ALWAYS AS
                           (qty_on_hand * avg_unit_cost) STORED,
    last_movement_date DATE,                               -- Last GI/GR date
    shelf_location     VARCHAR(20),                        -- Bin location
    UNIQUE (snapshot_date, part_id, dealer_id)
);

-- ============================================================
-- FACT TABLE: fact_sales
-- Line-level sales transactions
-- Maps to SAP SD: VBAK/VBAP (Sales Orders) + VF (Billing)
-- ============================================================
CREATE TABLE IF NOT EXISTS fact_sales (
    sale_id          BIGSERIAL PRIMARY KEY,
    transaction_date DATE         NOT NULL,
    part_id          INTEGER      NOT NULL REFERENCES dim_parts(part_id),
    dealer_id        INTEGER      NOT NULL REFERENCES dim_dealers(dealer_id),
    customer_type    VARCHAR(30)  NOT NULL,  -- Retail, Workshop, Fleet, Internal
    qty_sold         INTEGER      NOT NULL CHECK (qty_sold > 0),
    unit_price       NUMERIC(12,2) NOT NULL,
    discount_pct     NUMERIC(5,2) NOT NULL DEFAULT 0,
    revenue          NUMERIC(16,2) GENERATED ALWAYS AS
                         (qty_sold * unit_price * (1 - discount_pct/100)) STORED,
    cogs             NUMERIC(16,2),
    gross_profit     NUMERIC(16,2),
    order_source     VARCHAR(30),            -- Counter, Online, B2B
    was_fulfilled    BOOLEAN      NOT NULL DEFAULT TRUE,
    backorder_qty    INTEGER      NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ============================================================
-- FACT TABLE: fact_purchase_orders
-- Procurement transactions
-- Maps to SAP MM: EKKO/EKPO (Purchase Orders)
-- ============================================================
CREATE TABLE IF NOT EXISTS fact_purchase_orders (
    po_id            BIGSERIAL PRIMARY KEY,
    po_number        VARCHAR(30)  NOT NULL UNIQUE,    -- SAP: EBELN
    po_line          INTEGER      NOT NULL DEFAULT 1,  -- SAP: EBELP
    part_id          INTEGER      NOT NULL REFERENCES dim_parts(part_id),
    supplier_id      INTEGER      NOT NULL REFERENCES dim_suppliers(supplier_id),
    dealer_id        INTEGER      NOT NULL REFERENCES dim_dealers(dealer_id),
    order_date       DATE         NOT NULL,
    promised_date    DATE         NOT NULL,
    actual_receipt_date DATE,
    qty_ordered      INTEGER      NOT NULL CHECK (qty_ordered > 0),
    qty_received     INTEGER      NOT NULL DEFAULT 0,
    unit_cost        NUMERIC(12,4) NOT NULL,
    total_cost       NUMERIC(16,2) GENERATED ALWAYS AS
                         (qty_ordered * unit_cost) STORED,
    po_status        VARCHAR(20)  NOT NULL DEFAULT 'Open',
                     -- Open, Partially Received, Closed, Cancelled
    lead_time_actual INTEGER GENERATED ALWAYS AS
                         (actual_receipt_date - order_date) STORED,
    lead_time_delta  INTEGER GENERATED ALWAYS AS
                         (actual_receipt_date - promised_date) STORED,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ============================================================
-- FACT TABLE: fact_demand_forecast
-- Stores model output forecasts per part/dealer/month
-- ============================================================
CREATE TABLE IF NOT EXISTS fact_demand_forecast (
    forecast_id      BIGSERIAL PRIMARY KEY,
    forecast_date    DATE         NOT NULL,   -- First day of forecast period
    part_id          INTEGER      NOT NULL REFERENCES dim_parts(part_id),
    dealer_id        INTEGER      NOT NULL REFERENCES dim_dealers(dealer_id),
    forecast_qty     NUMERIC(10,2) NOT NULL,
    forecast_lower   NUMERIC(10,2),           -- 80% CI lower bound
    forecast_upper   NUMERIC(10,2),           -- 80% CI upper bound
    model_used       VARCHAR(30)  NOT NULL,   -- SARIMA, Prophet, Ensemble
    mape             NUMERIC(6,2),            -- Model accuracy %
    generated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (forecast_date, part_id, dealer_id, model_used)
);

-- ============================================================
-- ANALYTICS TABLE: analytics_abc_xyz
-- Classification results, refreshed monthly
-- ============================================================
CREATE TABLE IF NOT EXISTS analytics_abc_xyz (
    classification_id BIGSERIAL PRIMARY KEY,
    classification_month DATE      NOT NULL,
    part_id           INTEGER     NOT NULL REFERENCES dim_parts(part_id),
    dealer_id         INTEGER     NOT NULL REFERENCES dim_dealers(dealer_id),
    abc_class         CHAR(1)     NOT NULL CHECK (abc_class IN ('A','B','C')),
    xyz_class         CHAR(1)     NOT NULL CHECK (xyz_class IN ('X','Y','Z')),
    combined_class    CHAR(2)     GENERATED ALWAYS AS (abc_class || xyz_class) STORED,
    annual_revenue    NUMERIC(16,2) NOT NULL,
    revenue_pct       NUMERIC(6,3) NOT NULL,
    cumulative_revenue_pct NUMERIC(6,3) NOT NULL,
    demand_cov        NUMERIC(8,4) NOT NULL,   -- Coefficient of Variation
    avg_monthly_demand NUMERIC(10,2) NOT NULL,
    UNIQUE (classification_month, part_id, dealer_id)
);

-- ============================================================
-- ANALYTICS TABLE: analytics_reorder_policy
-- Computed reorder points and safety stock per SKU
-- ============================================================
CREATE TABLE IF NOT EXISTS analytics_reorder_policy (
    policy_id         BIGSERIAL PRIMARY KEY,
    effective_date    DATE        NOT NULL,
    part_id           INTEGER     NOT NULL REFERENCES dim_parts(part_id),
    dealer_id         INTEGER     NOT NULL REFERENCES dim_dealers(dealer_id),
    avg_daily_demand  NUMERIC(10,4) NOT NULL,
    demand_std_dev    NUMERIC(10,4) NOT NULL,
    avg_lead_time_days NUMERIC(8,2) NOT NULL,
    lead_time_std_dev NUMERIC(8,2) NOT NULL,
    service_level_z   NUMERIC(5,3) NOT NULL,   -- Z-score (1.65=95%, 2.05=98%)
    safety_stock_qty  INTEGER     NOT NULL,
    reorder_point     INTEGER     NOT NULL,
    economic_order_qty INTEGER    NOT NULL,     -- EOQ
    max_stock_level   INTEGER     NOT NULL,
    UNIQUE (effective_date, part_id, dealer_id)
);

-- ============================================================
-- INDEXES — Performance Optimization
-- ============================================================

-- High-frequency query patterns
CREATE INDEX idx_inventory_date_part   ON fact_inventory(snapshot_date, part_id);
CREATE INDEX idx_inventory_dealer      ON fact_inventory(dealer_id, snapshot_date DESC);
CREATE INDEX idx_sales_date            ON fact_sales(transaction_date);
CREATE INDEX idx_sales_part_date       ON fact_sales(part_id, transaction_date);
CREATE INDEX idx_sales_dealer_date     ON fact_sales(dealer_id, transaction_date);
CREATE INDEX idx_po_supplier           ON fact_purchase_orders(supplier_id, order_date);
CREATE INDEX idx_po_status             ON fact_purchase_orders(po_status);
CREATE INDEX idx_abc_class             ON analytics_abc_xyz(combined_class, classification_month);

-- ============================================================
-- TRIGGER: Auto-update updated_at on dim_parts changes
-- ============================================================
CREATE OR REPLACE FUNCTION fn_update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_parts_updated_at
    BEFORE UPDATE ON dim_parts
    FOR EACH ROW EXECUTE FUNCTION fn_update_timestamp();
