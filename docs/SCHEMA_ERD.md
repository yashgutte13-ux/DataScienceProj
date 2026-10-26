# Star Schema Entity-Relationship (ER) Diagram & Data Dictionary

## 1. Star Schema Entity Relationship Diagram

```mermaid
erDiagram
    FACT_ORDERS }|--|| DIM_CUSTOMERS : "customer_key"
    FACT_ORDERS }|--|| DIM_PRODUCTS : "product_key"
    FACT_ORDERS }|--|| DIM_SELLERS : "seller_key"
    FACT_ORDERS }|--|| DIM_DATE : "order_date_key"
    FACT_ORDERS }|--o| DIM_DATE : "delivery_date_key"

    DIM_CUSTOMERS {
        INTEGER customer_key PK
        TEXT customer_id UK
        TEXT customer_city
        TEXT customer_state
        TEXT customer_zip_code_prefix
        INTEGER recency_days
        INTEGER order_frequency
        REAL monetary_spend
        TEXT rfm_segment
    }

    DIM_PRODUCTS {
        INTEGER product_key PK
        TEXT product_id UK
        TEXT product_category_name
        REAL product_weight_g
        REAL product_length_cm
        REAL product_height_cm
        REAL product_width_cm
    }

    DIM_SELLERS {
        INTEGER seller_key PK
        TEXT seller_id UK
        TEXT seller_city
        TEXT seller_state
        TEXT seller_zip_code_prefix
    }

    DIM_DATE {
        INTEGER date_key PK
        TEXT full_date
        INTEGER year
        INTEGER quarter
        INTEGER month
        TEXT month_name
        TEXT month_year
        INTEGER day
        INTEGER day_of_week
        TEXT day_name
        INTEGER is_weekend
        TEXT fiscal_quarter
    }

    FACT_ORDERS {
        INTEGER order_item_key PK
        TEXT order_id
        INTEGER order_item_id
        INTEGER customer_key FK
        INTEGER product_key FK
        INTEGER seller_key FK
        INTEGER order_date_key FK
        INTEGER delivery_date_key FK
        TEXT order_status
        REAL price
        REAL freight_value
        REAL total_item_value
        TEXT payment_type
        INTEGER payment_installments
        REAL payment_value
        REAL actual_delivery_days
        REAL estimated_delivery_days
        REAL delivery_delay_days
        INTEGER sla_breached
        TEXT delivery_performance_status
        INTEGER review_score
    }
```

---

## 2. Table Specifications & Grain Definitions

### Fact Table: `fact_orders`
- **Grain:** One row per individual item purchased in an order.
- **Surrogate Key:** `order_item_key` (INTEGER AUTOINCREMENT).
- **Business Keys:** `(order_id, order_item_id)`.
- **Measures / Metrics:**
  - `price`: Unit price of the item.
  - `freight_value`: Shipping and handling fee charged.
  - `total_item_value`: `price + freight_value`.
  - `actual_delivery_days`: Total duration from purchase to customer doorstep.
  - `estimated_delivery_days`: Estimated promised transit duration.
  - `delivery_delay_days`: Delay beyond estimated promise date.
  - `sla_breached`: Binary indicator (`1` if delayed, `0` if on-time).
  - `review_score`: Satisfaction rating (1 to 5).

### Dimension Table: `dim_customers`
- **Grain:** One row per registered customer.
- **Surrogate Key:** `customer_key` (INTEGER AUTOINCREMENT).
- **Attributes:** City, State, Zip Prefix, RFM Metrics (`recency_days`, `order_frequency`, `monetary_spend`, `rfm_segment`).

### Dimension Table: `dim_products`
- **Grain:** One row per unique catalog product.
- **Surrogate Key:** `product_key` (INTEGER AUTOINCREMENT).
- **Attributes:** Normalized category name, physical dimensions (weight, length, height, width).

### Dimension Table: `dim_sellers`
- **Grain:** One row per marketplace merchant/seller.
- **Surrogate Key:** `seller_key` (INTEGER AUTOINCREMENT).
- **Attributes:** Seller ID, Hub City, State, Postal prefix.

### Dimension Table: `dim_date`
- **Grain:** One row per calendar day.
- **Key:** `date_key` in format `YYYYMMDD` (e.g., `20230514`).
- **Attributes:** Year, Quarter, Month, Day, Day of Week, Is Weekend, Fiscal Quarter.

---

## 3. Pre-Built SQL Analytical Views

1. `vw_executive_kpis`: High-level executive aggregates (GMV, order volume, on-time delivery SLA %, avg review).
2. `vw_monthly_revenue_trend`: Time-series revenue, freight income, and satisfaction trends by month.
3. `vw_delivery_sla_performance`: Regional delivery performance and SLA breach counts by state.
4. `vw_customer_rfm_summary`: Customer count, CLV, and spend breakdown by RFM segment.
5. `vw_product_category_performance`: Sales volume, unit economics, and satisfaction by category.
