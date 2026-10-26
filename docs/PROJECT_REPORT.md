# MINI PROJECT REPORT
# End-to-End Data Engineering Solution: E-Commerce Analytics Platform

**Course:** Data Engineering & Analytics  
**Project Title:** OmniCart: Scalable End-to-End E-Commerce Data Engineering Pipeline & Star Schema Data Warehouse  
**Repository:** [https://github.com/yashgutte13-ux/DataScienceProj](https://github.com/yashgutte13-ux/DataScienceProj)  

---

## 1. Problem Statement & Objectives

### 1.1 Problem Statement (5-6 Lines)
Modern e-commerce enterprises generate millions of fragmented transactional data points across customer profiles, product catalogs, multi-channel payment gateways, and third-party logistics fulfillment networks. This fragmentation severely impacts operations directors, supply chain managers, and commercial growth teams who lack unified visibility into order fulfillment bottlenecks, shipping SLA breaches, and customer churn drivers. Without clean, standardized, and modeled dimensional data, business leaders face delayed delivery escalations, inaccurate revenue attribution, and wasted marketing spend. This end-to-end data engineering solution automates multi-entity ingestion, profiles and remediates data quality anomalies, builds an optimized Star Schema data warehouse, and powers interactive BI reporting to guide carrier renegotiation, regional inventory restocking, and customer retention strategies.

### 1.2 Core Business & Technical Objectives
1. **Automated Ingestion:** Build an automated pipeline ingesting 7 core transactional entities: Customers, Products, Sellers, Orders, Order Items, Payments, and Reviews.
2. **Data Quality Profiling & Remediation:** Implement automated pre- and post-cleaning profiling across 4 quality dimensions (Completeness, Uniqueness, Validity, Outlier detection) to empirically measure pipeline improvement.
3. **Data Transformation & Feature Engineering:** Cleanse irregular timestamps, calculate order fulfillment duration, flag logistics SLA breaches, and engineer Customer Recency-Frequency-Monetary (RFM) behavioral segments.
4. **Kimball Star Schema Data Warehouse:** Model and deploy an OLAP schema with surrogate keys, indexes, and analytical views in SQLite, accompanied by Power BI/Tableau exportable data structures.
5. **Interactive BI Visualization:** Provide a multi-tab executive dashboard with real-time KPI metrics, carrier performance rankings, RFM customer grids, and an interactive SQL Query Studio.

---

## 2. Dataset Description and Source

The dataset simulates enterprise e-commerce operations based on industry benchmarks (modeled after the Kaggle Olist Brazilian E-Commerce public dataset):

| Entity Name | Source File | Description | Primary Key / Grain |
| :--- | :--- | :--- | :--- |
| **Customers** | `raw_customers.csv` | Customer location, city, state, zip prefix | `customer_id` |
| **Products** | `raw_products.csv` | Category, physical dimensions, weight | `product_id` |
| **Sellers** | `raw_sellers.csv` | Merchant ID, regional hub city and state | `seller_id` |
| **Orders** | `raw_orders.csv` | Purchase timestamp, approval, delivery & estimated dates | `order_id` |
| **Order Items** | `raw_order_items.csv` | Items per order, price, freight cost | `(order_id, order_item_id)` |
| **Payments** | `raw_order_payments.csv` | Payment method, installment count, amount paid | `(order_id, payment_sequential)` |
| **Reviews** | `raw_order_reviews.csv` | Customer satisfaction rating (1-5), comments | `review_id` |

---

## 3. Architecture and Data Flow

### 3.1 Data Flow Pipeline
```
+-------------------------------------------------------------------------+
|                        STAGE 1: DATA INGESTION                          |
|   Multi-Entity Transaction Sources (CSV / API Batch Generator)           |
|   Stores ~75,000 raw transactional records into data/raw/               |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                  STAGE 2A: QUALITY PROFILING (BEFORE)                   |
|   Detects Missing Values, Duplicates, Negative Prices, Outlier Weights  |
|   Outputs: data/processed/quality_report_before.json                    |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                   STAGE 3: TRANSFORMATION & ENRICHMENT                  |
|   • Deduplication (Unique primary keys)                                 |
|   • Missing Value Imputation (Zips, default product categories)         |
|   • Timestamp Standardisation (Mixed formats -> ISO-8601)               |
|   • Logistics SLA Feature Engineering (Delay days, sla_breached flag)   |
|   • Customer RFM Segmentation (Champions, Loyal, At Risk)               |
|   • Date Dimension Generation (731 continuous calendar days)            |
|   Stages cleaned analytical frames to data/processed/                   |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                  STAGE 2B: QUALITY PROFILING (AFTER)                    |
|   Verifies 100% Uniqueness, Validates Capping, Eliminates Outliers      |
|   Generates docs/DATA_QUALITY_REPORT.md                                 |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                   STAGE 4: STORAGE & STAR SCHEMA DW                     |
|   SQLite Relational Data Warehouse: data/warehouse/ecommerce_dw.db      |
|   • dim_customers, dim_products, dim_sellers, dim_date                  |
|   • fact_orders (Order item grain, surrogate keys, delivery metrics)    |
|   • 8 Performance B-tree Indexes & 5 Analytical SQL Views               |
|   • Export: data/warehouse/powerbi_export/*.csv for Power BI / Tableau  |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                     STAGE 6: BI VISUALIZATION LAYER                     |
|   Interactive Streamlit BI Web Dashboard (dashboard/app.py)             |
|   • Executive KPI Cards & Revenue Trends                                |
|   • Logistics & Delivery SLA Intelligence                               |
|   • Customer RFM Cohorts & Treemap                                      |
|   • Product Category Performance Scatter                                |
|   • Live SQL Query Studio with CSV Exporter                             |
+-------------------------------------------------------------------------+
```

---

## 4. Data Quality Findings & Remediation

Empirical Before-and-After Data Quality Audit Summary:

| Entity Table | Raw Records | Clean Records | Missing Cells (Before -> After) | Duplicates Purged | Health Improvement |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Customers** | 11,587 | 11,250 | 365 → 0 (imputed) | 337 | 98.6% → **100.0%** |
| **Products** | 800 | 800 | 34 → 0 (defaulted) | 0 | 99.5% → **100.0%** |
| **Sellers** | 150 | 150 | 0 → 0 | 0 | 100.0% → **100.0%** |
| **Orders** | 15,000 | 15,000 | Handled status-wise | 0 | 97.1% → **100.0%** |
| **Order Items** | 19,509 | 19,509 | 0 → 0 | 0 | 95.3% → **100.0%** |
| **Order Payments** | 15,225 | 15,000 | 0 → 0 | 225 | 94.2% → **100.0%** |
| **Order Reviews** | 12,727 | 12,727 | 0 → 0 | 0 | 100.0% → **100.0%** |
| **Total Pipeline** | **74,998** | **74,436** | **All Critical Cleaned**| **562 duplicates**| **100% Validated** |

### Key Cleaning Logic Applied:
1. **Deduplication:** Dropped 337 redundant customer rows and 225 duplicate payment records using distinct natural keys `customer_id` and `(order_id, payment_sequential)`.
2. **Missing Value Imputation:** Modal zip codes by city/state filled missing postal values; missing product categories filled with `'unclassified_general'`.
3. **Outlier Treatment:** Handled entry errors (e.g. 999,999g weights) by capping at the 99th percentile (IQR method).
4. **Validity Rules:** Inverted negative price anomalies using absolute value transformations.

---

## 5. Transformation Logic & Schema Design

### 5.1 Business Feature Engineering
- **Actual Delivery Days:** `(order_delivered_customer_date - order_purchase_timestamp).days`
- **Estimated Delivery Days:** `(order_estimated_delivery_date - order_purchase_timestamp).days`
- **Delivery Delay Days:** `(order_delivered_customer_date - order_estimated_delivery_date).days`
- **SLA Breached Flag:** `1` if `delivery_delay_days > 0`, else `0`
- **Customer RFM:** Recency, Order Frequency, and Total Spend mapped into 6 distinct behavioral tiers (`Champions`, `Loyal Customers`, `Promising New`, `Need Attention`, `At Risk`, `Hibernating / Lost`).

### 5.2 Star Schema Data Warehouse
The warehouse follows Ralph Kimball’s dimensional modeling methodology:
- **Central Fact Table (`fact_orders`):** Grain is one line item per order. Contains metrics: `price`, `freight_value`, `total_item_value`, `payment_value`, `actual_delivery_days`, `delivery_delay_days`, `sla_breached`, `review_score`.
- **Dimension Tables:**
  - `dim_customers`: Customer geography, RFM segmentation, lifetime order metrics.
  - `dim_products`: Product categories, physical specifications.
  - `dim_sellers`: Seller hub location.
  - `dim_date`: Complete calendar dimension spanning days, months, quarters, and weekdays.

---

## 6. Tools & Technologies Used (With Justification)

| Technology | Role in Architecture | Justification |
| :--- | :--- | :--- |
| **Python 3.13** | Core Pipeline Engine | Extensive data ecosystem, readability, rapid prototyping |
| **Pandas & NumPy** | Ingestion & ETL Processing | Vectorized data transformations, missing value imputation, robust string handling |
| **SQLite 3** | Relational Data Warehouse | Zero-configuration, serverless, atomic ACID compliance, embedded, perfectly suited for reproducible local grading |
| **Streamlit** | BI Dashboard Layer | Modern web interface, Python native, interactive reactive components, dynamic filtering |
| **Plotly** | Data Visualization | Interactive SVG/WebGL charts, hover tooltips, zoomable timelines |
| **Pytest** | Automated Testing | CI/CD test harness validating data integrity, deduplication, and schema constraints |
| **Apache Spark (PySpark)** | Distributed Scaling Blueprint | Horizontal scaling reference for multi-terabyte cluster deployments |

### Why Distributed Spark was Not Needed for the Default Execution:
- The mini-project dataset contains ~75,000 records (~15 MB in memory).
- SQLite and Pandas process the entire pipeline end-to-end in under 25 seconds on a standard laptop.
- Spinning up an Apache Spark cluster for < 100MB introduces unnecessary JVM initialization, network serialization, and cloud costs.
- The repository includes `src/distributed_spark_etl.py` to illustrate how the exact same business logic maps to PySpark for enterprise TB-scale workloads.

---

## 7. Challenges Faced & Solutions

| Challenge Encountered | Technical Solution Implemented |
| :--- | :--- |
| **Mixed Datetime Formats** (`YYYY-MM-DD` vs `DD/MM/YYYY`) causing date parsing errors | Utilized `pd.to_datetime(..., format='mixed', errors='coerce')` with explicit fallback handlers. |
| **Logistics Nulls in In-Flight Orders** (missing delivered date for active orders) | Preserved legitimate operational nulls while computing SLA flags only on delivered orders, avoiding data corruption. |
| **Foreign Key Orphan Risks** when loading dimensional tables | Created automated surrogate key lookup mapping in `src/storage.py` and implemented automated orphan checks in `test_pipeline.py`. |
| **Cross-Platform Compatibility** (Windows PowerShell & Linux) | Enforced standard `pathlib.Path` path handling across all modules. |

---

## 8. Pipeline Execution Results

- **Total Ingested Records:** 74,998 records across 7 entities.
- **Pipeline Execution Time:** ~23.5 seconds end-to-end (`run_pipeline.py`).
- **Data Quality Improvement:** Uniqueness increased to 100%; zero critical nulls in key analytical dimensions; 100% referential integrity (0 orphan keys).
- **Executive Metrics Computed:**
  - Total Orders: 15,000
  - Gross Merchandise Value (GMV): $5,165,641.29
  - Average Item Value: $264.78
  - On-Time Delivery Rate: 82.95%
  - Average Customer Review: 3.48 / 5.0
