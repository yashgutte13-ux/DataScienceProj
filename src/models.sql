-- ====================================================================
-- E-COMMERCE ENTERPRISE DATA WAREHOUSE (STAR SCHEMA DDL)
-- Target Engine: SQLite 3 / Relational Data Warehouse
-- ====================================================================

-- 1. Dimension: Customers
CREATE TABLE IF NOT EXISTS dim_customers (
    customer_key INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT UNIQUE NOT NULL,
    customer_city TEXT NOT NULL,
    customer_state TEXT NOT NULL,
    customer_zip_code_prefix TEXT NOT NULL,
    recency_days INTEGER,
    order_frequency INTEGER,
    monetary_spend REAL,
    rfm_segment TEXT NOT NULL
);

-- 2. Dimension: Products
CREATE TABLE IF NOT EXISTS dim_products (
    product_key INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT UNIQUE NOT NULL,
    product_category_name TEXT NOT NULL,
    product_weight_g REAL,
    product_length_cm REAL,
    product_height_cm REAL,
    product_width_cm REAL
);

-- 3. Dimension: Sellers
CREATE TABLE IF NOT EXISTS dim_sellers (
    seller_key INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id TEXT UNIQUE NOT NULL,
    seller_city TEXT NOT NULL,
    seller_state TEXT NOT NULL,
    seller_zip_code_prefix TEXT NOT NULL
);

-- 4. Dimension: Date Calendar
CREATE TABLE IF NOT EXISTS dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date TEXT NOT NULL,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name TEXT NOT NULL,
    month_year TEXT NOT NULL,
    day INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    day_name TEXT NOT NULL,
    is_weekend INTEGER NOT NULL,
    fiscal_quarter TEXT NOT NULL
);

-- 5. Fact Table: Orders & Item Fulfillment
CREATE TABLE IF NOT EXISTS fact_orders (
    order_item_key INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    order_item_id INTEGER NOT NULL,
    customer_key INTEGER NOT NULL,
    product_key INTEGER NOT NULL,
    seller_key INTEGER NOT NULL,
    order_date_key INTEGER NOT NULL,
    delivery_date_key INTEGER,
    order_status TEXT NOT NULL,
    price REAL NOT NULL,
    freight_value REAL NOT NULL,
    total_item_value REAL NOT NULL,
    payment_type TEXT,
    payment_installments INTEGER,
    payment_value REAL,
    actual_delivery_days REAL,
    estimated_delivery_days REAL,
    delivery_delay_days REAL,
    sla_breached INTEGER DEFAULT 0,
    delivery_performance_status TEXT,
    review_score INTEGER,
    FOREIGN KEY (customer_key) REFERENCES dim_customers(customer_key),
    FOREIGN KEY (product_key) REFERENCES dim_products(product_key),
    FOREIGN KEY (seller_key) REFERENCES dim_sellers(seller_key),
    FOREIGN KEY (order_date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (delivery_date_key) REFERENCES dim_date(date_key)
);

-- ====================================================================
-- PERFORMANCE INDEXES
-- ====================================================================
CREATE INDEX IF NOT EXISTS idx_fact_customer_key ON fact_orders(customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_product_key ON fact_orders(product_key);
CREATE INDEX IF NOT EXISTS idx_fact_seller_key ON fact_orders(seller_key);
CREATE INDEX IF NOT EXISTS idx_fact_order_date_key ON fact_orders(order_date_key);
CREATE INDEX IF NOT EXISTS idx_fact_order_status ON fact_orders(order_status);
CREATE INDEX IF NOT EXISTS idx_fact_sla_breached ON fact_orders(sla_breached);
CREATE INDEX IF NOT EXISTS idx_dim_cust_segment ON dim_customers(rfm_segment);
CREATE INDEX IF NOT EXISTS idx_dim_prod_cat ON dim_products(product_category_name);

-- ====================================================================
-- ANALYTICAL BI VIEWS
-- ====================================================================

-- View 1: Executive KPI Summary
CREATE VIEW IF NOT EXISTS vw_executive_kpis AS
SELECT
    COUNT(DISTINCT order_id) AS total_orders,
    ROUND(SUM(total_item_value), 2) AS total_gross_merchandise_value,
    ROUND(AVG(total_item_value), 2) AS average_item_value,
    COUNT(DISTINCT customer_key) AS total_customers_served,
    ROUND(AVG(CASE WHEN order_status = 'delivered' THEN actual_delivery_days END), 1) AS avg_delivery_days,
    ROUND(100.0 * SUM(CASE WHEN order_status = 'delivered' AND sla_breached = 0 THEN 1 ELSE 0 END) / 
          NULLIF(SUM(CASE WHEN order_status = 'delivered' THEN 1 ELSE 0 END), 0), 2) AS on_time_delivery_rate_pct,
    ROUND(AVG(review_score), 2) AS average_review_score
FROM fact_orders;

-- View 2: Monthly Revenue & Order Trajectory
CREATE VIEW IF NOT EXISTS vw_monthly_revenue_trend AS
SELECT
    d.year,
    d.month,
    d.month_year,
    COUNT(DISTINCT f.order_id) AS total_orders,
    ROUND(SUM(f.total_item_value), 2) AS gross_revenue,
    ROUND(SUM(f.freight_value), 2) AS total_freight_revenue,
    ROUND(AVG(f.review_score), 2) AS avg_review_score,
    ROUND(100.0 * SUM(CASE WHEN f.sla_breached = 0 THEN 1 ELSE 0 END) / COUNT(f.order_item_key), 2) AS on_time_pct
FROM fact_orders f
JOIN dim_date d ON f.order_date_key = d.date_key
GROUP BY d.year, d.month, d.month_year
ORDER BY d.year, d.month;

-- View 3: Delivery SLA Performance by State
CREATE VIEW IF NOT EXISTS vw_delivery_sla_performance AS
SELECT
    c.customer_state,
    COUNT(DISTINCT f.order_id) AS total_orders,
    ROUND(AVG(f.actual_delivery_days), 1) AS avg_actual_days,
    ROUND(AVG(f.estimated_delivery_days), 1) AS avg_estimated_days,
    ROUND(AVG(f.delivery_delay_days), 1) AS avg_delay_days,
    SUM(f.sla_breached) AS sla_breach_count,
    ROUND(100.0 * (COUNT(f.order_item_key) - SUM(f.sla_breached)) / COUNT(f.order_item_key), 1) AS on_time_rate_pct
FROM fact_orders f
JOIN dim_customers c ON f.customer_key = c.customer_key
WHERE f.order_status = 'delivered'
GROUP BY c.customer_state
ORDER BY total_orders DESC;

-- View 4: Customer RFM Segmentation Analysis
CREATE VIEW IF NOT EXISTS vw_customer_rfm_summary AS
SELECT
    c.rfm_segment,
    COUNT(DISTINCT c.customer_key) AS customer_count,
    ROUND(AVG(c.recency_days), 1) AS avg_recency_days,
    ROUND(AVG(c.order_frequency), 2) AS avg_order_frequency,
    ROUND(SUM(c.monetary_spend), 2) AS total_revenue_generated,
    ROUND(AVG(c.monetary_spend), 2) AS avg_customer_spend
FROM dim_customers c
GROUP BY c.rfm_segment
ORDER BY total_revenue_generated DESC;

-- View 5: Product Category Sales & Performance
CREATE VIEW IF NOT EXISTS vw_product_category_performance AS
SELECT
    p.product_category_name,
    COUNT(f.order_item_key) AS units_sold,
    ROUND(SUM(f.total_item_value), 2) AS total_sales_volume,
    ROUND(AVG(f.price), 2) AS avg_unit_price,
    ROUND(AVG(f.review_score), 2) AS avg_satisfaction_score,
    ROUND(100.0 * SUM(f.sla_breached) / COUNT(f.order_item_key), 2) AS delay_incidence_pct
FROM fact_orders f
JOIN dim_products p ON f.product_key = p.product_key
GROUP BY p.product_category_name
ORDER BY total_sales_volume DESC;
