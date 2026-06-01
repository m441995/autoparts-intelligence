-- ============================================================
-- AutoParts Intelligence Platform
-- Schema: 02_insert_sample_data.sql
-- Realistic sample data for demo & testing
-- ============================================================

-- SUPPLIERS
INSERT INTO dim_suppliers (supplier_code, supplier_name, country, city, supplier_type, payment_terms, currency, lead_time_days, min_order_value, is_preferred, rating) VALUES
('SUP-001', 'Toyota Genuine Parts MENA',    'Japan',        'Tokyo',      'OEM',         'NET60', 'USD', 45, 5000.00,  TRUE,  4.8),
('SUP-002', 'Denso Arabia LLC',             'UAE',          'Dubai',      'OEM',         'NET45', 'USD', 14, 2000.00,  TRUE,  4.6),
('SUP-003', 'NGK Spark Plugs Egypt',        'Egypt',        'Cairo',      'OES',         'NET30', 'EGP', 7,  500.00,   TRUE,  4.5),
('SUP-004', 'Gates Belts & Hoses MENA',     'UAE',          'Dubai',      'OES',         'NET30', 'USD', 21, 1000.00,  FALSE, 4.2),
('SUP-005', 'Castrol Lubricants Egypt',     'Egypt',        'Alexandria', 'OES',         'NET30', 'EGP', 5,  300.00,   TRUE,  4.7),
('SUP-006', 'Bosch Auto Parts GmbH',        'Germany',      'Stuttgart',  'OEM',         'NET60', 'EUR', 35, 3000.00,  TRUE,  4.9),
('SUP-007', 'Febi Bilstein Trading',        'Germany',      'Ennepetal',  'OES',         'NET45', 'EUR', 28, 1500.00,  FALSE, 4.3),
('SUP-008', 'Al-Yousuf Auto Parts',         'Egypt',        'Cairo',      'Aftermarket', 'NET15', 'EGP', 3,  200.00,   FALSE, 3.8);

-- DEALERS (Branches)
INSERT INTO dim_dealers (dealer_code, dealer_name, region, city, country, warehouse_type) VALUES
('DLR-CAI-01', 'Cairo Main Branch',        'Greater Cairo',      'Cairo',       'Egypt', 'Central'),
('DLR-CAI-02', 'Nasr City Service Center', 'Greater Cairo',      'Cairo',       'Egypt', 'Regional'),
('DLR-ALX-01', 'Alexandria Branch',        'Mediterranean Coast','Alexandria',  'Egypt', 'Regional'),
('DLR-GIZ-01', 'Giza Branch',              'Greater Cairo',      'Giza',        'Egypt', 'Regional'),
('DLR-MAN-01', 'Mansoura Branch',          'Delta',              'Mansoura',    'Egypt', 'Regional');

-- PARTS (Realistic Toyota / General Automotive)
INSERT INTO dim_parts (part_number, oem_number, part_name, part_description, brand, category, sub_category, unit_of_measure, standard_cost, list_price, weight_kg, is_critical) VALUES
('TOY-04152-YZZA6', '04152-YZZA6', 'Oil Filter - 2.0L Engine',          'Genuine Toyota oil filter for 1AZ/2AZ engines',          'Toyota', 'Engine',     'Oil System',      'EA',  8.50,   22.00,  0.30, FALSE),
('TOY-90915-YZZD4', '90915-YZZD4', 'Oil Filter - Camry/Corolla',        'Genuine Toyota oil filter, high-flow design',            'Toyota', 'Engine',     'Oil System',      'EA',  9.20,   25.00,  0.32, FALSE),
('TOY-04465-02260', '04465-02260', 'Front Brake Pad Set - Camry',        'OEM ceramic front brake pads, Camry 2018-2023',          'Toyota', 'Brakes',     'Brake Pads',      'SET', 65.00,  145.00, 1.20, TRUE),
('TOY-04466-02310', '04466-02310', 'Rear Brake Pad Set - Camry',         'OEM ceramic rear brake pads, Camry 2018-2023',           'Toyota', 'Brakes',     'Brake Pads',      'SET', 45.00,  110.00, 0.90, TRUE),
('TOY-90080-91203', '90080-91203', 'Air Filter - Camry 2.5L',            'High-flow OEM air filter for 2AR-FE engine',             'Toyota', 'Engine',     'Air System',      'EA',  18.00,  48.00,  0.45, FALSE),
('TOY-SK16HR11',    'SK16HR11',    'Spark Plug - Iridium (single)',       'NGK Iridium spark plug, laser welded tip',               'Toyota', 'Ignition',   'Spark Plugs',     'EA',  14.00,  38.00,  0.08, FALSE),
('TOY-90916-02096', '90916-02096', 'Alternator Belt - 2.5L',             'V-ribbed serpentine belt for Camry/RAV4 2.5L',          'Toyota', 'Engine',     'Belts & Hoses',   'EA',  22.00,  58.00,  0.55, TRUE),
('TOY-04945-02080', '04945-02080', 'Brake Disc Front - Corolla',         'OEM ventilated front disc, Corolla 2019+',               'Toyota', 'Brakes',     'Brake Discs',     'EA',  75.00,  195.00, 3.80, TRUE),
('TOY-04996-02060', '04996-02060', 'Brake Disc Rear - Corolla',          'OEM solid rear disc, Corolla 2019+',                    'Toyota', 'Brakes',     'Brake Discs',     'EA',  55.00,  145.00, 2.90, TRUE),
('TOY-08880-80375', '08880-80375', 'AC Compressor Oil',                  'PAG oil for Toyota AC systems, 250ml',                   'Toyota', 'Cooling',    'AC System',       'EA',  12.00,  32.00,  0.28, FALSE),
('TOY-90501-23012', '90501-23012', 'Radiator Cap - 1.1 Bar',             'OEM pressure radiator cap, universal fit',              'Toyota', 'Cooling',    'Cooling System',  'EA',  8.00,   22.00,  0.12, FALSE),
('TOY-48520-49285', '48520-49285', 'Front Shock Absorber - Left Camry',  'KYB OEM-spec front shock, Camry 2018+',                  'Toyota', 'Suspension', 'Shock Absorbers', 'EA',  185.00, 420.00, 4.50, TRUE),
('TOY-48510-49285', '48510-49285', 'Front Shock Absorber - Right Camry', 'KYB OEM-spec front shock, Camry 2018+',                  'Toyota', 'Suspension', 'Shock Absorbers', 'EA',  185.00, 420.00, 4.50, TRUE),
('TOY-08880-10705', '08880-10705', 'CVT Fluid WS - 1 Liter',             'World Standard Toyota CVT transmission fluid',          'Toyota', 'Drivetrain', 'Transmission',    'L',   18.00,  48.00,  0.95, TRUE),
('TOY-08826-00080', '08826-00080', 'Windshield Washer Fluid - 2L',       'Toyota-approved washer concentrate',                    'Toyota', 'Body',       'Fluids',          'EA',  3.50,   9.00,   2.10, FALSE);

-- INVENTORY SNAPSHOTS (latest day per branch, 5 branches × 15 parts)
-- For brevity, showing key entries; in production this is millions of rows
INSERT INTO fact_inventory (snapshot_date, part_id, dealer_id, qty_on_hand, qty_reserved, qty_in_transit, avg_unit_cost, last_movement_date) VALUES
-- Cairo Main (DLR-CAI-01)
('2024-12-31', 1,  1, 85,  12, 24, 8.75,   '2024-12-30'),
('2024-12-31', 2,  1, 102, 8,  36, 9.40,   '2024-12-31'),
('2024-12-31', 3,  1, 34,  10, 20, 66.20,  '2024-12-29'),
('2024-12-31', 4,  1, 28,  6,  10, 45.80,  '2024-12-28'),
('2024-12-31', 5,  1, 67,  5,  0,  18.40,  '2024-12-31'),
('2024-12-31', 6,  1, 148, 20, 48, 14.20,  '2024-12-31'),
('2024-12-31', 7,  1, 23,  4,  12, 22.50,  '2024-12-27'),
('2024-12-31', 8,  1, 12,  4,  8,  76.00,  '2024-12-26'),
('2024-12-31', 9,  1, 15,  2,  8,  56.00,  '2024-12-25'),
('2024-12-31', 10, 1, 45,  0,  0,  12.20,  '2024-12-20'),  -- Slow mover
('2024-12-31', 11, 1, 89,  2,  0,  8.10,   '2024-12-31'),
('2024-12-31', 12, 1, 6,   2,  4,  187.00, '2024-12-22'),
('2024-12-31', 13, 1, 7,   2,  4,  187.00, '2024-12-22'),
('2024-12-31', 14, 1, 38,  4,  12, 18.40,  '2024-12-30'),
('2024-12-31', 15, 1, 220, 0,  0,  3.60,   '2024-12-10');   -- Dead stock risk

-- SALES TRANSACTIONS (sample: 3 months across branches)
INSERT INTO fact_sales (transaction_date, part_id, dealer_id, customer_type, qty_sold, unit_price, discount_pct, cogs, gross_profit, order_source, was_fulfilled) VALUES
('2024-10-01', 1,  1, 'Workshop', 8,  22.00, 0,   70.00,  106.00, 'Counter', TRUE),
('2024-10-01', 6,  1, 'Retail',   4,  38.00, 5,   56.80,   87.40, 'Counter', TRUE),
('2024-10-03', 3,  1, 'Workshop', 3,  145.00, 0,  198.00,  237.00, 'Counter', TRUE),
('2024-10-05', 2,  1, 'Fleet',    12, 22.00, 10,  110.40,  147.60, 'B2B',    TRUE),
('2024-10-07', 5,  1, 'Workshop', 5,  48.00, 0,   92.00,   148.00, 'Counter', TRUE),
('2024-10-10', 14, 1, 'Workshop', 4,  48.00, 0,   73.60,   118.40, 'Counter', TRUE),
('2024-10-12', 3,  1, 'Workshop', 2,  145.00, 0,  132.00,  158.00, 'Counter', TRUE),
('2024-10-15', 1,  1, 'Retail',   3,  22.00, 0,   26.25,   39.75,  'Counter', TRUE),
('2024-10-15', 12, 1, 'Workshop', 1,  420.00, 0,  187.00,  233.00, 'Counter', TRUE),
('2024-10-18', 6,  1, 'Retail',   6,  38.00, 0,   85.20,  142.80,  'Counter', TRUE),
('2024-10-20', 8,  1, 'Workshop', 2,  195.00, 5,  152.00,  218.00, 'Counter', TRUE),
('2024-10-22', 4,  1, 'Workshop', 3,  110.00, 0,  137.40,  192.60, 'Counter', TRUE),
-- November
('2024-11-01', 1,  1, 'Workshop', 10, 22.00, 0,   87.50,  132.50, 'Counter', TRUE),
('2024-11-03', 3,  1, 'Workshop', 4,  145.00, 0,  264.80,  315.20, 'Counter', TRUE),
('2024-11-05', 6,  1, 'Fleet',    20, 38.00, 8,  284.00,  319.60, 'B2B',     TRUE),
('2024-11-08', 2,  1, 'Workshop', 8,  22.00, 0,   75.20,  100.80, 'Counter', TRUE),
('2024-11-10', 5,  1, 'Retail',   6,  48.00, 0,  110.40,  177.60, 'Counter', TRUE),
('2024-11-12', 7,  1, 'Workshop', 3,  58.00, 0,   67.50,  106.50, 'Counter', TRUE),
('2024-11-15', 14, 1, 'Workshop', 6,  48.00, 0,  110.40,  177.60, 'Counter', TRUE),
('2024-11-18', 8,  1, 'Workshop', 3,  195.00, 0,  228.00,  357.00, 'Counter', TRUE),
('2024-11-20', 12, 1, 'Workshop', 2,  420.00, 0,  374.00,  466.00, 'Counter', TRUE),
-- December
('2024-12-01', 1,  1, 'Workshop', 12, 22.00, 0,  105.00,  159.00, 'Counter', TRUE),
('2024-12-03', 6,  1, 'Retail',   8,  38.00, 5,  113.60,  175.60, 'Counter', TRUE),
('2024-12-05', 3,  1, 'Workshop', 5,  145.00, 0,  331.00,  394.00, 'Counter', TRUE),
('2024-12-08', 2,  1, 'Fleet',    15, 22.00, 10, 141.00,  156.00, 'B2B',     TRUE),
('2024-12-10', 14, 1, 'Workshop', 8,  48.00, 0,  147.20,  236.80, 'Counter', TRUE),
('2024-12-12', 5,  1, 'Workshop', 4,  48.00, 0,   73.60,  118.40, 'Counter', TRUE),
('2024-12-15', 8,  1, 'Workshop', 4,  195.00, 5,  304.00,  472.00, 'Counter', TRUE),
('2024-12-18', 7,  1, 'Workshop', 2,  58.00, 0,   45.00,   71.00,  'Counter', TRUE),
-- Backorder example
('2024-12-20', 12, 1, 'Workshop', 3,  420.00, 0,  561.00,  699.00, 'Counter', FALSE);  -- Not fulfilled

-- PURCHASE ORDERS
INSERT INTO fact_purchase_orders (po_number, po_line, part_id, supplier_id, dealer_id, order_date, promised_date, actual_receipt_date, qty_ordered, qty_received, unit_cost, po_status) VALUES
('PO-2024-001', 1, 1,  2, 1, '2024-10-01', '2024-10-15', '2024-10-16', 200, 200, 8.50,  'Closed'),
('PO-2024-001', 2, 2,  2, 1, '2024-10-01', '2024-10-15', '2024-10-16', 200, 200, 9.20,  'Closed'),
('PO-2024-002', 1, 6,  3, 1, '2024-10-05', '2024-10-12', '2024-10-13', 300, 300, 14.00, 'Closed'),
('PO-2024-003', 1, 3,  1, 1, '2024-10-10', '2024-11-24', '2024-11-28', 50,  50,  65.00, 'Closed'),
('PO-2024-004', 1, 14, 2, 1, '2024-11-01', '2024-11-15', '2024-11-14', 60,  60,  18.00, 'Closed'),
('PO-2024-005', 1, 12, 1, 1, '2024-11-15', '2024-12-29', NULL,         20,  0,   185.00,'Open'),   -- In transit
('PO-2024-006', 1, 5,  2, 1, '2024-12-01', '2024-12-15', '2024-12-17', 100, 100, 18.00, 'Closed'),
('PO-2024-007', 1, 8,  1, 1, '2024-12-10', '2025-01-23', NULL,         30,  0,   75.00, 'Open'),
('PO-2024-008', 1, 2,  2, 1, '2024-12-15', '2024-12-29', '2024-12-31', 150, 150, 9.40,  'Closed'),
('PO-2024-009', 1, 7,  4, 1, '2024-12-20', '2025-01-10', NULL,         40,  0,   22.00, 'Open');
