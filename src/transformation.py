"""
Module: src.transformation
Stage 3: Data Transformation, Cleansing & Business Enrichment (ETL)

Performs comprehensive data cleansing, standardizations, outlier remediation,
and business metric enrichments:
- Deduplication of primary entities
- Imputation of missing values
- Datetime standardisation into ISO format
- Logistics SLA calculation (actual vs estimated delivery, SLA breach flags)
- Customer RFM (Recency, Frequency, Monetary) segmentation
- Dimension Date calendar generation
- Staging of cleaned analytical files to data/processed/
"""

import numpy as np
import pandas as pd
from pathlib import Path
from src.utils import get_logger, RAW_DATA_DIR, PROCESSED_DATA_DIR, time_it

logger = get_logger("Transformation")

def parse_dates_robust(series: pd.Series) -> pd.Series:
    """Parse dates robustly handling mixed formats and NaNs."""
    return pd.to_datetime(series, errors="coerce", format="mixed")

def clean_customers(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate, normalize casing, and impute missing postal codes."""
    logger.info("Transforming customers data...")
    df = df_raw.copy()
    
    # Deduplicate
    df = df.drop_duplicates(subset=["customer_id"]).reset_index(drop=True)
    
    # Standardize casing
    df["customer_city"] = df["customer_city"].astype(str).str.lower().str.strip()
    df["customer_state"] = df["customer_state"].astype(str).str.upper().str.strip()
    
    # Fill missing zip codes with modal zip per city/state
    mode_zips = df.groupby(["customer_state", "customer_city"])["customer_zip_code_prefix"].agg(
        lambda s: s.dropna().mode().iloc[0] if not s.dropna().empty else "01001"
    ).to_dict()
    
    def fill_zip(row):
        if pd.isna(row["customer_zip_code_prefix"]) or str(row["customer_zip_code_prefix"]).lower() == "nan":
            return mode_zips.get((row["customer_state"], row["customer_city"]), "01001")
        return str(row["customer_zip_code_prefix"]).split(".")[0].zfill(5)
        
    df["customer_zip_code_prefix"] = df.apply(fill_zip, axis=1)
    return df

def clean_products(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Impute missing categories and treat extreme weight outliers."""
    logger.info("Transforming products data...")
    df = df_raw.copy()
    
    # Impute missing categories
    df["product_category_name"] = df["product_category_name"].fillna("unclassified_general").str.lower().str.strip()
    
    # Treat weight outliers (IQR / 99th percentile cap)
    p99_weight = df["product_weight_g"][df["product_weight_g"] < 50000].quantile(0.99)
    df.loc[df["product_weight_g"] > 50000, "product_weight_g"] = p99_weight
    
    # Ensure all dimensions are positive non-zero
    for dim_col in ["product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"]:
        df[dim_col] = df[dim_col].abs()
        df[dim_col] = df[dim_col].replace(0, df[dim_col].median())
        
    return df

def clean_sellers(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Normalize casing and format zip codes."""
    logger.info("Transforming sellers data...")
    df = df_raw.copy()
    df = df.drop_duplicates(subset=["seller_id"]).reset_index(drop=True)
    df["seller_city"] = df["seller_city"].astype(str).str.lower().str.strip()
    df["seller_state"] = df["seller_state"].astype(str).str.upper().str.strip()
    df["seller_zip_code_prefix"] = df["seller_zip_code_prefix"].astype(str).str.split(".").str[0].str.zfill(5)
    return df

def clean_orders(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Standardize datetimes and compute delivery performance & SLA breach metrics."""
    logger.info("Transforming orders data & computing delivery SLA metrics...")
    df = df_raw.copy()
    df = df.drop_duplicates(subset=["order_id"]).reset_index(drop=True)
    
    # Standardize dates
    date_cols = [
        "order_purchase_timestamp", "order_approved_at",
        "order_delivered_carrier_date", "order_delivered_customer_date",
        "order_estimated_delivery_date"
    ]
    for col in date_cols:
        df[col] = parse_dates_robust(df[col])
        
    # SLA Metrics & Delivery Durations
    # 1. actual delivery days from purchase
    df["actual_delivery_days"] = (df["order_delivered_customer_date"] - df["order_purchase_timestamp"]).dt.total_seconds() / (24 * 3600)
    df["actual_delivery_days"] = df["actual_delivery_days"].apply(lambda x: round(max(0, x), 1) if pd.notnull(x) else None)
    
    # 2. estimated delivery days from purchase
    df["estimated_delivery_days"] = (df["order_estimated_delivery_date"] - df["order_purchase_timestamp"]).dt.total_seconds() / (24 * 3600)
    df["estimated_delivery_days"] = df["estimated_delivery_days"].apply(lambda x: round(max(0, x), 1) if pd.notnull(x) else None)
    
    # 3. delivery delay vs estimate (positive = delayed / SLA breached)
    df["delivery_delay_days"] = (df["order_delivered_customer_date"] - df["order_estimated_delivery_date"]).dt.total_seconds() / (24 * 3600)
    df["delivery_delay_days"] = df["delivery_delay_days"].apply(lambda x: round(x, 1) if pd.notnull(x) else None)
    
    # 4. Binary SLA Breach flag
    df["sla_breached"] = df.apply(
        lambda r: 1 if pd.notnull(r["delivery_delay_days"]) and r["delivery_delay_days"] > 0 else 0,
        axis=1
    )
    
    # 5. Delivery status classification
    def classify_delivery(row):
        if row["order_status"] != "delivered":
            return row["order_status"].title()
        if pd.isna(row["delivery_delay_days"]):
            return "Unknown"
        if row["delivery_delay_days"] <= 0:
            return "On-Time"
        elif row["delivery_delay_days"] <= 3:
            return "Slight Delay (1-3d)"
        else:
            return "Critical Delay (>3d)"
            
    df["delivery_performance_status"] = df.apply(classify_delivery, axis=1)
    return df

def clean_order_items(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Normalize prices, freight, and compute item gross value."""
    logger.info("Transforming order_items data...")
    df = df_raw.copy()
    
    # Fix negative values and cap erroneous extreme price spikes
    df["price"] = df["price"].abs()
    p99_price = df["price"][df["price"] < 5000].quantile(0.99)
    df.loc[df["price"] > 5000, "price"] = p99_price
    
    df["freight_value"] = df["freight_value"].abs()
    df["total_item_value"] = (df["price"] + df["freight_value"]).round(2)
    df["shipping_limit_date"] = parse_dates_robust(df["shipping_limit_date"])
    
    return df

def clean_order_payments(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate payments and ensure positive values."""
    logger.info("Transforming order_payments data...")
    df = df_raw.copy()
    df = df.drop_duplicates(subset=["order_id", "payment_sequential"]).reset_index(drop=True)
    df["payment_value"] = df["payment_value"].abs().round(2)
    return df

def clean_order_reviews(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Clean review scores and parse review dates."""
    logger.info("Transforming order_reviews data...")
    df = df_raw.copy()
    df = df.drop_duplicates(subset=["review_id"]).reset_index(drop=True)
    df["review_score"] = df["review_score"].clip(lower=1, upper=5).astype(int)
    df["review_creation_date"] = parse_dates_robust(df["review_creation_date"])
    return df

def calculate_customer_rfm(df_orders: pd.DataFrame, df_items: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Customer Recency, Frequency, and Monetary (RFM) segmentation.
    """
    logger.info("Computing customer RFM segmentation metrics...")
    # Merge order items with orders to get customer spend and purchase dates
    df_merged = df_items.merge(df_orders[["order_id", "customer_id", "order_purchase_timestamp", "order_status"]], on="order_id", how="inner")
    df_delivered = df_merged[df_merged["order_status"] == "delivered"].copy()
    
    ref_date = df_delivered["order_purchase_timestamp"].max() + pd.Timedelta(days=1)
    
    rfm = df_delivered.groupby("customer_id").agg(
        recency=("order_purchase_timestamp", lambda x: (ref_date - x.max()).days),
        frequency=("order_id", "nunique"),
        monetary=("total_item_value", "sum")
    ).reset_index()
    
    rfm["monetary"] = rfm["monetary"].round(2)
    
    # Assign quartile/score bins (1 to 4)
    rfm["r_score"] = pd.qcut(rfm["recency"].rank(method="first"), q=4, labels=[4, 3, 2, 1]).astype(int)
    rfm["f_score"] = pd.qcut(rfm["frequency"].rank(method="first"), q=4, labels=[1, 2, 3, 4]).astype(int)
    rfm["m_score"] = pd.qcut(rfm["monetary"].rank(method="first"), q=4, labels=[1, 2, 3, 4]).astype(int)
    rfm["rfm_composite"] = rfm["r_score"] * 100 + rfm["f_score"] * 10 + rfm["m_score"]
    
    # Segment naming rule
    def assign_segment(row):
        r, f, m = row["r_score"], row["f_score"], row["m_score"]
        if r >= 3 and f >= 3 and m >= 3:
            return "Champions"
        elif r >= 3 and f >= 2:
            return "Loyal Customers"
        elif r >= 3 and f == 1:
            return "Promising New"
        elif r == 2 and f >= 2:
            return "Need Attention"
        elif r == 1 and f >= 3:
            return "At Risk"
        else:
            return "Hibernating / Lost"
            
    rfm["rfm_segment"] = rfm.apply(assign_segment, axis=1)
    return rfm

def generate_date_dimension(start_date: str = "2023-01-01", end_date: str = "2024-12-31") -> pd.DataFrame:
    """
    Generate complete date dimension table with calendar attributes for Star Schema.
    """
    logger.info(f"Generating date dimension calendar from {start_date} to {end_date}...")
    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    df_date = pd.DataFrame({"full_date": dates})
    
    df_date["date_key"] = df_date["full_date"].dt.strftime("%Y%m%d").astype(int)
    df_date["year"] = df_date["full_date"].dt.year
    df_date["quarter"] = df_date["full_date"].dt.quarter
    df_date["month"] = df_date["full_date"].dt.month
    df_date["month_name"] = df_date["full_date"].dt.strftime("%B")
    df_date["month_year"] = df_date["full_date"].dt.strftime("%b %Y")
    df_date["day"] = df_date["full_date"].dt.day
    df_date["day_of_week"] = df_date["full_date"].dt.dayofweek + 1
    df_date["day_name"] = df_date["full_date"].dt.strftime("%A")
    df_date["is_weekend"] = df_date["day_of_week"].apply(lambda d: 1 if d in [6, 7] else 0)
    df_date["fiscal_quarter"] = "Q" + df_date["quarter"].astype(str)
    
    return df_date

@time_it("Data Transformation & Enrichment Pipeline")
def run_transformation(raw_dir: Path = RAW_DATA_DIR, output_dir: Path = PROCESSED_DATA_DIR) -> dict[str, pd.DataFrame]:
    """
    Execute end-to-end transformation, save clean datasets, and return cleaned dictionary.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Loading raw datasets from {raw_dir}...")
    
    # Read raw files
    df_cust = pd.read_csv(raw_dir / "raw_customers.csv", low_memory=False)
    df_prod = pd.read_csv(raw_dir / "raw_products.csv", low_memory=False)
    df_sell = pd.read_csv(raw_dir / "raw_sellers.csv", low_memory=False)
    df_ord = pd.read_csv(raw_dir / "raw_orders.csv", low_memory=False)
    df_items = pd.read_csv(raw_dir / "raw_order_items.csv", low_memory=False)
    df_pay = pd.read_csv(raw_dir / "raw_order_payments.csv", low_memory=False)
    df_rev = pd.read_csv(raw_dir / "raw_order_reviews.csv", low_memory=False)
    
    # Transform entities
    clean_cust = clean_customers(df_cust)
    clean_prod = clean_products(df_prod)
    clean_sell = clean_sellers(df_sell)
    clean_ord = clean_orders(df_ord)
    clean_items = clean_order_items(df_items)
    clean_pay = clean_order_payments(df_pay)
    clean_rev = clean_order_reviews(df_rev)
    
    # Enrich Customers with RFM
    rfm_df = calculate_customer_rfm(clean_ord, clean_items)
    clean_cust = clean_cust.merge(
        rfm_df[["customer_id", "recency", "frequency", "monetary", "rfm_segment"]],
        on="customer_id",
        how="left"
    )
    clean_cust["rfm_segment"] = clean_cust["rfm_segment"].fillna("New / Prospect")
    
    # Generate Date Dimension
    dim_date = generate_date_dimension()
    
    transformed_dict = {
        "customers": clean_cust,
        "products": clean_prod,
        "sellers": clean_sell,
        "orders": clean_ord,
        "order_items": clean_items,
        "order_payments": clean_pay,
        "order_reviews": clean_rev,
        "dim_date": dim_date
    }
    
    # Save staged cleaned CSVs
    for name, df in transformed_dict.items():
        out_path = output_dir / f"clean_{name}.csv"
        df.to_csv(out_path, index=False)
        logger.info(f"  --> Saved cleaned {name:15s}: {len(df):6d} records | {out_path.name}")
        
    logger.info("Data transformation, enrichment, and staging successfully completed.")
    return transformed_dict

if __name__ == "__main__":
    run_transformation()
