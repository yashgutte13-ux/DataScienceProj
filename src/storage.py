"""
Module: src.storage
Stage 4: Storage & Star Schema Dimensional Data Warehouse

Loads cleaned staged data into an OLAP Star Schema relational warehouse:
- Initializes database tables, surrogate keys, and referential constraints
- Builds performance B-tree indexes
- Maps natural business keys to dimensional surrogate keys
- Populates analytical views
- Performs referential integrity audits
- Exports clean dimensional tables for external BI tools (Power BI / Tableau)
"""

import sqlite3
import pandas as pd
from pathlib import Path
from src.utils import get_logger, PROCESSED_DATA_DIR, WAREHOUSE_DIR, POWERBI_EXPORT_DIR, time_it

logger = get_logger("WarehouseStorage")

DB_FILE = WAREHOUSE_DIR / "ecommerce_dw.db"
SQL_DDL_FILE = Path(__file__).resolve().parent / "models.sql"

def get_connection(db_path: Path = DB_FILE) -> sqlite3.Connection:
    """Establish connection to SQLite data warehouse with foreign keys enabled."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def initialize_warehouse_schema(conn: sqlite3.Connection):
    """Execute DDL scripts to create star schema tables, indexes, and views."""
    logger.info("Initializing Star Schema tables, indexes, and views from models.sql...")
    cursor = conn.cursor()
    
    # Drop existing tables in reverse order to respect foreign key constraints
    tables = ["fact_orders", "dim_customers", "dim_products", "dim_sellers", "dim_date"]
    for t in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {t};")
    
    # Drop existing views
    views = [
        "vw_executive_kpis", "vw_monthly_revenue_trend",
        "vw_delivery_sla_performance", "vw_customer_rfm_summary",
        "vw_product_category_performance"
    ]
    for v in views:
        cursor.execute(f"DROP VIEW IF EXISTS {v};")
        
    # Read and execute DDL
    with open(SQL_DDL_FILE, "r", encoding="utf-8") as f:
        ddl_script = f.read()
        
    cursor.executescript(ddl_script)
    conn.commit()
    logger.info("Schema initialization successful.")

def load_dimensions(conn: sqlite3.Connection) -> dict[str, pd.DataFrame]:
    """Load cleaned dimension data and return mapped lookup frames."""
    logger.info("Loading Dimension Tables into Warehouse...")
    
    # 1. Dim Customers
    df_cust = pd.read_csv(PROCESSED_DATA_DIR / "clean_customers.csv", low_memory=False)
    cust_dim = df_cust[[
        "customer_id", "customer_city", "customer_state", "customer_zip_code_prefix",
        "recency", "frequency", "monetary", "rfm_segment"
    ]].rename(columns={
        "recency": "recency_days",
        "frequency": "order_frequency",
        "monetary": "monetary_spend"
    })
    cust_dim.to_sql("dim_customers", conn, if_exists="append", index=False)
    
    # 2. Dim Products
    df_prod = pd.read_csv(PROCESSED_DATA_DIR / "clean_products.csv", low_memory=False)
    prod_dim = df_prod[[
        "product_id", "product_category_name", "product_weight_g",
        "product_length_cm", "product_height_cm", "product_width_cm"
    ]]
    prod_dim.to_sql("dim_products", conn, if_exists="append", index=False)
    
    # 3. Dim Sellers
    df_sell = pd.read_csv(PROCESSED_DATA_DIR / "clean_sellers.csv", low_memory=False)
    sell_dim = df_sell[[
        "seller_id", "seller_city", "seller_state", "seller_zip_code_prefix"
    ]]
    sell_dim.to_sql("dim_sellers", conn, if_exists="append", index=False)
    
    # 4. Dim Date
    df_date = pd.read_csv(PROCESSED_DATA_DIR / "clean_dim_date.csv", low_memory=False)
    df_date.to_sql("dim_date", conn, if_exists="append", index=False)
    
    # Query back generated surrogate keys for fact table lookup
    cust_keys = pd.read_sql("SELECT customer_key, customer_id FROM dim_customers;", conn)
    prod_keys = pd.read_sql("SELECT product_key, product_id FROM dim_products;", conn)
    sell_keys = pd.read_sql("SELECT seller_key, seller_id FROM dim_sellers;", conn)
    
    logger.info(f"  --> Loaded dim_customers: {len(cust_dim):6d} rows")
    logger.info(f"  --> Loaded dim_products : {len(prod_dim):6d} rows")
    logger.info(f"  --> Loaded dim_sellers  : {len(sell_dim):6d} rows")
    logger.info(f"  --> Loaded dim_date     : {len(df_date):6d} rows")
    
    return {
        "cust_keys": cust_keys,
        "prod_keys": prod_keys,
        "sell_keys": sell_keys
    }

def load_fact_orders(conn: sqlite3.Connection, lookups: dict[str, pd.DataFrame]):
    """Assemble and load fact_orders with dimensional surrogate keys."""
    logger.info("Assembling and loading Fact Table (fact_orders)...")
    
    # Load staged datasets
    df_ord = pd.read_csv(PROCESSED_DATA_DIR / "clean_orders.csv", low_memory=False)
    df_items = pd.read_csv(PROCESSED_DATA_DIR / "clean_order_items.csv", low_memory=False)
    df_pay = pd.read_csv(PROCESSED_DATA_DIR / "clean_order_payments.csv", low_memory=False)
    df_rev = pd.read_csv(PROCESSED_DATA_DIR / "clean_order_reviews.csv", low_memory=False)
    
    # Merge order items with order header
    fact = df_items.merge(df_ord, on="order_id", how="inner")
    
    # Merge first payment details
    pay_dedup = df_pay.sort_values(["order_id", "payment_sequential"]).drop_duplicates(subset=["order_id"])
    fact = fact.merge(
        pay_dedup[["order_id", "payment_type", "payment_installments", "payment_value"]],
        on="order_id",
        how="left"
    )
    
    # Merge review details
    rev_dedup = df_rev.drop_duplicates(subset=["order_id"])
    fact = fact.merge(
        rev_dedup[["order_id", "review_score"]],
        on="order_id",
        how="left"
    )
    
    # Merge dimensional surrogate keys
    fact = fact.merge(lookups["cust_keys"], on="customer_id", how="inner")
    fact = fact.merge(lookups["prod_keys"], on="product_id", how="inner")
    fact = fact.merge(lookups["sell_keys"], on="seller_id", how="inner")
    
    # Derive Date Keys (YYYYMMDD integer format)
    fact["order_date_key"] = pd.to_datetime(fact["order_purchase_timestamp"]).dt.strftime("%Y%m%d").astype(int)
    
    def parse_deliv_key(x):
        if pd.notnull(x) and str(x).lower() != "nan":
            return int(pd.to_datetime(x).strftime("%Y%m%d"))
        return None
        
    fact["delivery_date_key"] = fact["order_delivered_customer_date"].apply(parse_deliv_key)
    
    # Select columns matching fact_orders DDL
    fact_columns = [
        "order_id", "order_item_id", "customer_key", "product_key", "seller_key",
        "order_date_key", "delivery_date_key", "order_status", "price", "freight_value",
        "total_item_value", "payment_type", "payment_installments", "payment_value",
        "actual_delivery_days", "estimated_delivery_days", "delivery_delay_days",
        "sla_breached", "delivery_performance_status", "review_score"
    ]
    fact_table = fact[fact_columns].copy()
    
    fact_table.to_sql("fact_orders", conn, if_exists="append", index=False)
    logger.info(f"  --> Loaded fact_orders: {len(fact_table):6d} rows")

def verify_warehouse_integrity(conn: sqlite3.Connection):
    """Run data integrity and referential checks on warehouse tables."""
    logger.info("Verifying warehouse referential integrity & analytical views...")
    cursor = conn.cursor()
    
    # 1. Check orphan records
    orphan_query = """
    SELECT COUNT(*) FROM fact_orders f
    LEFT JOIN dim_customers c ON f.customer_key = c.customer_key
    WHERE c.customer_key IS NULL;
    """
    cursor.execute(orphan_query)
    orphans = cursor.fetchone()[0]
    if orphans > 0:
        logger.error(f"CRITICAL: Found {orphans} orphaned records in fact_orders!")
    else:
        logger.info("  --> Referential Integrity Check: 100% Pass (0 orphans)")
        
    # 2. Check Executive KPI View
    cursor.execute("SELECT total_orders, total_gross_merchandise_value, on_time_delivery_rate_pct, average_review_score FROM vw_executive_kpis;")
    kpis = cursor.fetchone()
    logger.info(f"  --> Executive View Validated: Orders={kpis[0]:,}, GMV=${kpis[1]:,.2f}, On-Time SLA={kpis[2]}%, Avg Review={kpis[3]}/5.0")

def export_for_powerbi_tableau(conn: sqlite3.Connection, export_dir: Path = POWERBI_EXPORT_DIR):
    """Export warehouse tables and views as clean CSVs for external BI tool ingestion."""
    export_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Exporting curated analytical tables for Power BI / Tableau to {export_dir}...")
    
    tables_to_export = [
        "dim_customers", "dim_products", "dim_sellers", "dim_date",
        "fact_orders", "vw_monthly_revenue_trend", "vw_delivery_sla_performance",
        "vw_customer_rfm_summary", "vw_product_category_performance"
    ]
    
    for tbl in tables_to_export:
        df = pd.read_sql(f"SELECT * FROM {tbl};", conn)
        out_file = export_dir / f"{tbl}.csv"
        df.to_csv(out_file, index=False)
        logger.info(f"  --> Exported {tbl:30s} ({len(df):6d} rows) -> {out_file.name}")
        
    logger.info("Power BI / Tableau analytical export completed.")

@time_it("Warehouse Storage & Dimensional Modeling Pipeline")
def run_storage_pipeline(db_file: Path = DB_FILE) -> sqlite3.Connection:
    """Execute complete storage stage pipeline."""
    conn = get_connection(db_file)
    try:
        initialize_warehouse_schema(conn)
        lookups = load_dimensions(conn)
        load_fact_orders(conn, lookups)
        verify_warehouse_integrity(conn)
        export_for_powerbi_tableau(conn)
        return conn
    except Exception as e:
        logger.error(f"Storage pipeline encountered error: {e}", exc_info=True)
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    run_storage_pipeline()
