-- ============================================================
-- AutoParts Intelligence Platform
-- File: sql/queries/01_kpi_queries.sql
-- Advanced analytical queries for all business KPIs
-- ============================================================

-- ============================================================
-- 1. INVENTORY TURNOVER RATIO (by part category, trailing 12M)
-- ============================================================
WITH annual_cogs AS (
    SELECT
        p.category,
        SUM(s.cogs) AS total_cogs
    FROM fact_sales s
    JOIN dim_parts p ON s.part_id = p.part_id
    WHERE s.transaction_date >= CURRENT_DATE - INTERVAL '12 months'
    GROUP BY p.category
),
avg_inventory AS (
    SELECT
        p.category,
        AVG(i.total_stock_value) AS avg_inv_value
    FROM fact_inventory i
    JOIN dim_parts p ON i.part_id = p.part_id
    WHERE i.snapshot_date >= CURRENT_DATE - INTERVAL '12 months'
    GROUP BY p.category
)
SELECT
    c.category,
    ROUND(c.total_cogs, 2)                            AS annual_cogs,
    ROUND(a.avg_inv_value, 2)                         AS avg_inventory_value,
    ROUND(c.total_cogs / NULLIF(a.avg_inv_value, 0), 2) AS inventory_turnover,
    ROUND(365.0 / NULLIF(c.total_cogs / NULLIF(a.avg_inv_value, 0), 0), 1) AS days_on_hand
FROM annual_cogs c
JOIN avg_inventory a ON c.category = a.category
ORDER BY inventory_turnover DESC;


-- ============================================================
-- 2. FILL RATE BY DEALER (Last 90 days)
-- ============================================================
SELECT
    d.dealer_name,
    d.region,
    COUNT(*)                                             AS total_order_lines,
    SUM(CASE WHEN s.was_fulfilled THEN 1 ELSE 0 END)    AS fulfilled_lines,
    SUM(s.backorder_qty)                                 AS total_backorder_qty,
    ROUND(
        100.0 * SUM(CASE WHEN s.was_fulfilled THEN 1 ELSE 0 END)
        / COUNT(*), 2
    )                                                    AS fill_rate_pct,
    ROUND(
        100.0 * SUM(CASE WHEN NOT s.was_fulfilled THEN 1 ELSE 0 END)
        / COUNT(*), 2
    )                                                    AS backorder_rate_pct
FROM fact_sales s
JOIN dim_dealers d ON s.dealer_id = d.dealer_id
WHERE s.transaction_date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY d.dealer_name, d.region
ORDER BY fill_rate_pct DESC;


-- ============================================================
-- 3. DEAD STOCK DETECTION
--    Definition: Parts with zero movement > 180 days
--    AND currently holding positive inventory
-- ============================================================
WITH latest_inventory AS (
    SELECT DISTINCT ON (part_id, dealer_id)
        part_id,
        dealer_id,
        qty_on_hand,
        total_stock_value,
        last_movement_date,
        snapshot_date
    FROM fact_inventory
    ORDER BY part_id, dealer_id, snapshot_date DESC
),
last_sale AS (
    SELECT
        part_id,
        dealer_id,
        MAX(transaction_date) AS last_sale_date
    FROM fact_sales
    GROUP BY part_id, dealer_id
)
SELECT
    p.part_number,
    p.part_name,
    p.category,
    p.brand,
    d.dealer_name,
    li.qty_on_hand,
    ROUND(li.total_stock_value, 2)                         AS stock_value,
    COALESCE(ls.last_sale_date, li.last_movement_date)     AS last_movement,
    CURRENT_DATE - COALESCE(ls.last_sale_date, li.last_movement_date) AS days_no_movement,
    CASE
        WHEN CURRENT_DATE - COALESCE(ls.last_sale_date, li.last_movement_date) > 365 THEN 'Dead Stock'
        WHEN CURRENT_DATE - COALESCE(ls.last_sale_date, li.last_movement_date) > 180 THEN 'Slow Moving'
        WHEN CURRENT_DATE - COALESCE(ls.last_sale_date, li.last_movement_date) > 90  THEN 'Watch List'
        ELSE 'Active'
    END                                                    AS stock_status
FROM latest_inventory li
JOIN dim_parts p ON li.part_id = p.part_id
JOIN dim_dealers d ON li.dealer_id = d.dealer_id
LEFT JOIN last_sale ls ON li.part_id = ls.part_id AND li.dealer_id = ls.dealer_id
WHERE li.qty_on_hand > 0
  AND CURRENT_DATE - COALESCE(ls.last_sale_date, li.last_movement_date) > 90
ORDER BY days_no_movement DESC, stock_value DESC;


-- ============================================================
-- 4. SLOW MOVING ITEMS ANALYSIS
--    Compare current stock to 90-day average daily demand
-- ============================================================
WITH demand_90d AS (
    SELECT
        part_id,
        dealer_id,
        SUM(qty_sold) AS qty_sold_90d,
        ROUND(SUM(qty_sold)::NUMERIC / 90, 4) AS avg_daily_demand
    FROM fact_sales
    WHERE transaction_date >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY part_id, dealer_id
),
latest_stock AS (
    SELECT DISTINCT ON (part_id, dealer_id)
        part_id, dealer_id, qty_on_hand, total_stock_value
    FROM fact_inventory
    ORDER BY part_id, dealer_id, snapshot_date DESC
)
SELECT
    p.part_number,
    p.part_name,
    p.category,
    d.dealer_name,
    ls.qty_on_hand,
    ROUND(ls.total_stock_value, 2)          AS stock_value,
    COALESCE(dm.qty_sold_90d, 0)            AS qty_sold_90d,
    COALESCE(dm.avg_daily_demand, 0)        AS avg_daily_demand,
    CASE
        WHEN COALESCE(dm.avg_daily_demand, 0) = 0 THEN 9999
        ELSE ROUND(ls.qty_on_hand / dm.avg_daily_demand, 0)
    END                                     AS days_of_stock,
    CASE
        WHEN COALESCE(dm.avg_daily_demand, 0) = 0 THEN 'No Demand'
        WHEN ls.qty_on_hand / dm.avg_daily_demand > 180 THEN 'Overstock'
        WHEN ls.qty_on_hand / dm.avg_daily_demand > 90  THEN 'High Stock'
        WHEN ls.qty_on_hand / dm.avg_daily_demand < 14  THEN 'Low Stock'
        ELSE 'Normal'
    END                                     AS stock_health
FROM latest_stock ls
JOIN dim_parts p ON ls.part_id = p.part_id
JOIN dim_dealers d ON ls.dealer_id = d.dealer_id
LEFT JOIN demand_90d dm ON ls.part_id = dm.part_id AND ls.dealer_id = dm.dealer_id
ORDER BY days_of_stock DESC NULLS FIRST;


-- ============================================================
-- 5. SUPPLIER LEAD TIME VARIABILITY ANALYSIS
--    Essential for safety stock calculations
-- ============================================================
SELECT
    s.supplier_name,
    s.supplier_type,
    s.country,
    COUNT(po.po_id)                          AS po_count,
    ROUND(AVG(po.lead_time_actual), 1)       AS avg_actual_lead_time,
    s.lead_time_days                         AS contracted_lead_time,
    ROUND(STDDEV(po.lead_time_actual), 2)    AS lead_time_std_dev,
    ROUND(
        STDDEV(po.lead_time_actual) /
        NULLIF(AVG(po.lead_time_actual), 0) * 100, 1
    )                                        AS lead_time_cov_pct,
    ROUND(AVG(po.lead_time_delta), 1)        AS avg_delay_days,
    SUM(CASE WHEN po.lead_time_delta > 3 THEN 1 ELSE 0 END)  AS late_deliveries,
    ROUND(
        100.0 * SUM(CASE WHEN po.lead_time_delta <= 0 THEN 1 ELSE 0 END)
        / COUNT(*), 1
    )                                        AS on_time_pct,
    ROUND(AVG(po.total_cost), 2)             AS avg_po_value
FROM fact_purchase_orders po
JOIN dim_suppliers s ON po.supplier_id = s.supplier_id
WHERE po.actual_receipt_date IS NOT NULL
  AND po.po_status = 'Closed'
GROUP BY s.supplier_id, s.supplier_name, s.supplier_type, s.country, s.lead_time_days
HAVING COUNT(po.po_id) >= 3
ORDER BY on_time_pct DESC;


-- ============================================================
-- 6. ABC REVENUE CLASSIFICATION
--    Standard Pareto: A=top 80%, B=next 15%, C=bottom 5%
-- ============================================================
WITH part_revenue AS (
    SELECT
        s.part_id,
        s.dealer_id,
        SUM(s.revenue) AS annual_revenue
    FROM fact_sales s
    WHERE s.transaction_date >= DATE_TRUNC('year', CURRENT_DATE)
    GROUP BY s.part_id, s.dealer_id
),
ranked AS (
    SELECT
        part_id,
        dealer_id,
        annual_revenue,
        annual_revenue / SUM(annual_revenue) OVER () * 100 AS revenue_pct,
        SUM(annual_revenue) OVER (
            ORDER BY annual_revenue DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) / SUM(annual_revenue) OVER () * 100 AS cumulative_pct
    FROM part_revenue
)
SELECT
    p.part_number,
    p.part_name,
    p.category,
    d.dealer_name,
    ROUND(r.annual_revenue, 2)     AS annual_revenue,
    ROUND(r.revenue_pct, 3)        AS revenue_pct,
    ROUND(r.cumulative_pct, 2)     AS cumulative_pct,
    CASE
        WHEN r.cumulative_pct <= 80  THEN 'A'
        WHEN r.cumulative_pct <= 95  THEN 'B'
        ELSE 'C'
    END                            AS abc_class
FROM ranked r
JOIN dim_parts p ON r.part_id = p.part_id
JOIN dim_dealers d ON r.dealer_id = d.dealer_id
ORDER BY r.annual_revenue DESC;


-- ============================================================
-- 7. MONTHLY DEMAND TREND (for seasonality detection)
-- ============================================================
SELECT
    TO_CHAR(DATE_TRUNC('month', s.transaction_date), 'YYYY-MM') AS month,
    p.category,
    SUM(s.qty_sold)     AS total_qty,
    SUM(s.revenue)      AS total_revenue,
    COUNT(DISTINCT s.part_id) AS unique_parts_sold,
    ROUND(AVG(s.qty_sold), 2) AS avg_qty_per_line,
    LAG(SUM(s.qty_sold)) OVER (
        PARTITION BY p.category
        ORDER BY DATE_TRUNC('month', s.transaction_date)
    )                   AS prev_month_qty,
    ROUND(
        100.0 * (SUM(s.qty_sold) - LAG(SUM(s.qty_sold)) OVER (
            PARTITION BY p.category
            ORDER BY DATE_TRUNC('month', s.transaction_date)
        )) / NULLIF(LAG(SUM(s.qty_sold)) OVER (
            PARTITION BY p.category
            ORDER BY DATE_TRUNC('month', s.transaction_date)
        ), 0), 1
    )                   AS mom_growth_pct
FROM fact_sales s
JOIN dim_parts p ON s.part_id = p.part_id
GROUP BY DATE_TRUNC('month', s.transaction_date), p.category
ORDER BY DATE_TRUNC('month', s.transaction_date), p.category;


-- ============================================================
-- 8. STOCKOUT RISK DASHBOARD VIEW
--    Parts where available qty < reorder point
-- ============================================================
CREATE OR REPLACE VIEW vw_stockout_risk AS
WITH latest_stock AS (
    SELECT DISTINCT ON (part_id, dealer_id)
        part_id, dealer_id, qty_on_hand, qty_reserved, qty_available, qty_in_transit
    FROM fact_inventory
    ORDER BY part_id, dealer_id, snapshot_date DESC
)
SELECT
    p.part_number,
    p.part_name,
    p.category,
    p.is_critical,
    d.dealer_name,
    ls.qty_available,
    ls.qty_in_transit,
    rp.reorder_point,
    rp.safety_stock_qty,
    rp.avg_daily_demand,
    rp.avg_lead_time_days,
    ROUND(ls.qty_available / NULLIF(rp.avg_daily_demand, 0), 1) AS days_of_stock_remaining,
    CASE
        WHEN ls.qty_available <= 0                 THEN 'STOCKOUT'
        WHEN ls.qty_available < rp.safety_stock_qty THEN 'CRITICAL'
        WHEN ls.qty_available < rp.reorder_point   THEN 'ORDER NOW'
        WHEN ls.qty_available < rp.reorder_point * 1.2 THEN 'WATCH'
        ELSE 'OK'
    END AS risk_level
FROM latest_stock ls
JOIN dim_parts p ON ls.part_id = p.part_id
JOIN dim_dealers d ON ls.dealer_id = d.dealer_id
LEFT JOIN analytics_reorder_policy rp
    ON ls.part_id = rp.part_id
    AND ls.dealer_id = rp.dealer_id
    AND rp.effective_date = (
        SELECT MAX(effective_date)
        FROM analytics_reorder_policy
        WHERE part_id = ls.part_id AND dealer_id = ls.dealer_id
    )
ORDER BY
    CASE risk_level
        WHEN 'STOCKOUT'  THEN 1
        WHEN 'CRITICAL'  THEN 2
        WHEN 'ORDER NOW' THEN 3
        WHEN 'WATCH'     THEN 4
        ELSE 5
    END,
    p.is_critical DESC;
