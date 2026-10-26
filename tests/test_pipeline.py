"""
Pipeline Test Suite: tests/test_pipeline.py
Automated validation of Ingestion, Cleaning, RFM, Star Schema, and Referential Integrity
"""

import sqlite3
import pytest
import pandas as pd
from pathlib import Path
from src.utils import PROJECT_ROOT, RAW_DATA_DIR, PROCESSED_DATA_DIR, WAREHOUSE_DIR
from src.transformation import clean_customers, clean_orders, calculate_customer_rfm, generate_date_dimension

DB_PATH = WAREHOUSE_DIR / "ecommerce_dw.db"

def test_raw_files_exist():
    """Verify raw datasets were generated and stored."""
    expected_files = [
        "raw_customers.csv", "raw_products.csv", "raw_sellers.csv",
        "raw_orders.csv", "raw_order_items.csv", "raw_order_payments.csv",
        "raw_order_reviews.csv"
    ]
    for filename in expected_files:
        p = RAW_DATA_DIR / filename
        assert p.exists(), f"Missing raw file: {filename}"
        assert p.stat().st_size > 0, f"Raw file {filename} is empty"

def test_customer_deduplication():
    """Ensure customer transformation purges duplicates and normalizes city/state."""
    dummy_cust = pd.DataFrame([
        {"customer_id": "c1", "customer_city": "Sao Paulo", "customer_state": "sp", "customer_zip_code_prefix": "01001"},
        {"customer_id": "c1", "customer_city": "SAO PAULO", "customer_state": "SP", "customer_zip_code_prefix": "01001"},
        {"customer_id": "c2", "customer_city": "Rio De Janeiro", "customer_state": "rj", "customer_zip_code_prefix": None}
    ])
    cleaned = clean_customers(dummy_cust)
    assert len(cleaned) == 2, "Customer deduplication failed"
    assert cleaned.loc[cleaned["customer_id"] == "c1", "customer_city"].iloc[0] == "sao paulo"
    assert cleaned.loc[cleaned["customer_id"] == "c1", "customer_state"].iloc[0] == "SP"

def test_sla_breach_calculation():
    """Verify delivery delay and SLA breach binary flags."""
    dummy_orders = pd.DataFrame([
        {
            "order_id": "o1", "customer_id": "c1", "order_status": "delivered",
            "order_purchase_timestamp": "2023-01-01 10:00:00",
            "order_approved_at": "2023-01-01 12:00:00",
            "order_delivered_carrier_date": "2023-01-02 10:00:00",
            "order_delivered_customer_date": "2023-01-05 10:00:00",
            "order_estimated_delivery_date": "2023-01-10 10:00:00"  # On time (5 days early)
        },
        {
            "order_id": "o2", "customer_id": "c2", "order_status": "delivered",
            "order_purchase_timestamp": "2023-01-01 10:00:00",
            "order_approved_at": "2023-01-01 12:00:00",
            "order_delivered_carrier_date": "2023-01-02 10:00:00",
            "order_delivered_customer_date": "2023-01-15 10:00:00",
            "order_estimated_delivery_date": "2023-01-10 10:00:00"  # Delayed by 5 days (SLA breached)
        }
    ])
    cleaned = clean_orders(dummy_orders)
    assert cleaned.loc[cleaned["order_id"] == "o1", "sla_breached"].iloc[0] == 0
    assert cleaned.loc[cleaned["order_id"] == "o2", "sla_breached"].iloc[0] == 1
    assert cleaned.loc[cleaned["order_id"] == "o2", "delivery_delay_days"].iloc[0] == 5.0

def test_warehouse_referential_integrity():
    """Ensure SQLite data warehouse exists and foreign keys resolve with zero orphans."""
    assert DB_PATH.exists(), f"Warehouse database {DB_PATH} not found"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check fact table row count
    cursor.execute("SELECT COUNT(*) FROM fact_orders;")
    fact_count = cursor.fetchone()[0]
    assert fact_count > 0, "fact_orders table is empty"
    
    # Check customer orphan foreign keys
    cursor.execute("""
        SELECT COUNT(*) FROM fact_orders f
        LEFT JOIN dim_customers c ON f.customer_key = c.customer_key
        WHERE c.customer_key IS NULL;
    """)
    assert cursor.fetchone()[0] == 0, "Found orphaned customer_keys in fact_orders"
    
    # Check product orphan foreign keys
    cursor.execute("""
        SELECT COUNT(*) FROM fact_orders f
        LEFT JOIN dim_products p ON f.product_key = p.product_key
        WHERE p.product_key IS NULL;
    """)
    assert cursor.fetchone()[0] == 0, "Found orphaned product_keys in fact_orders"
    
    # Check seller orphan foreign keys
    cursor.execute("""
        SELECT COUNT(*) FROM fact_orders f
        LEFT JOIN dim_sellers s ON f.seller_key = s.seller_key
        WHERE s.seller_key IS NULL;
    """)
    assert cursor.fetchone()[0] == 0, "Found orphaned seller_keys in fact_orders"
    
    # Check date dimension joins
    cursor.execute("""
        SELECT COUNT(*) FROM fact_orders f
        LEFT JOIN dim_date d ON f.order_date_key = d.date_key
        WHERE d.date_key IS NULL;
    """)
    assert cursor.fetchone()[0] == 0, "Found invalid date_keys in fact_orders"
    
    conn.close()

def test_analytical_views_queryable():
    """Verify that all core analytical views execute and return valid metrics."""
    conn = sqlite3.connect(DB_PATH)
    views = [
        "vw_executive_kpis", "vw_monthly_revenue_trend",
        "vw_delivery_sla_performance", "vw_customer_rfm_summary",
        "vw_product_category_performance"
    ]
    for v in views:
        df = pd.read_sql(f"SELECT * FROM {v};", conn)
        assert len(df) > 0, f"Analytical view {v} returned 0 rows"
    conn.close()
