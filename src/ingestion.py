"""
Module: src.ingestion
Stage 1: Automated Data Ingestion Pipeline

Collects, validates, and stages raw e-commerce transaction data.
Generates realistic multi-table relational data containing real-world dirty data
phenomena (missing values, formatting differences, outliers, duplicates)
to test and validate subsequent profiling, cleaning, and ETL pipelines.
"""

import os
import random
import datetime
import numpy as np
import pandas as pd
from pathlib import Path
from src.utils import get_logger, RAW_DATA_DIR, time_it

logger = get_logger("DataIngestion")

# Set random seed for determinism
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# Reference data dictionaries for realistic e-commerce simulation
CITIES_STATES = [
    ("sao paulo", "SP", "01001"),
    ("rio de janeiro", "RJ", "20000"),
    ("belo horizonte", "MG", "30000"),
    ("brasilia", "DF", "70000"),
    ("curitiba", "PR", "80000"),
    ("porto alegre", "RS", "90000"),
    ("salvador", "BA", "40000"),
    ("fortaleza", "CE", "60000"),
    ("recife", "PE", "50000"),
    ("campinas", "SP", "13000"),
    ("florianopolis", "SC", "88000"),
    ("goiania", "GO", "74000"),
    ("manaus", "AM", "69000"),
    ("vitoria", "ES", "29000"),
    ("natal", "RN", "59000"),
]

PRODUCT_CATEGORIES = [
    "electronics", "computers_accessories", "telephony", "bed_bath_table",
    "sports_leisure", "furniture_decor", "health_beauty", "toys",
    "watches_gifts", "auto", "garden_tools", "housewares",
    "stationery", "perfumery", "baby"
]

PAYMENT_TYPES = ["credit_card", "boleto", "voucher", "debit_card"]
ORDER_STATUSES = ["delivered", "delivered", "delivered", "delivered", "shipped", "processing", "canceled"]

def generate_raw_dataset(num_orders: int = 15000) -> dict[str, pd.DataFrame]:
    """
    Generate realistic raw multi-entity e-commerce transactional data with
    synthetic real-world anomalies (duplicates, nulls, outliers, unstandardized dates).
    """
    logger.info(f"Generating realistic raw e-commerce dataset (~{num_orders} orders)...")
    
    # 1. Customers
    num_customers = int(num_orders * 0.75)
    customer_ids = [f"cust_{i:06d}" for i in range(1, num_customers + 1)]
    
    customers_data = []
    for cid in customer_ids:
        city, state, zip_prefix = random.choice(CITIES_STATES)
        # Introduce casing variations
        if random.random() < 0.15:
            city = city.upper()
        elif random.random() < 0.15:
            city = city.title()
        
        # Introduce occasional missing or corrupted zip code
        zip_val = zip_prefix if random.random() > 0.03 else None
        
        customers_data.append({
            "customer_id": cid,
            "customer_unique_id": f"uniq_{cid}",
            "customer_zip_code_prefix": zip_val,
            "customer_city": city,
            "customer_state": state
        })
    df_customers = pd.DataFrame(customers_data)
    
    # Add intentional duplicate customer rows (data quality check)
    duplicates_cust = df_customers.sample(n=int(num_customers * 0.03), random_state=RANDOM_SEED)
    df_customers = pd.concat([df_customers, duplicates_cust], ignore_index=True)
    
    # 2. Products
    num_products = 800
    products_data = []
    for i in range(1, num_products + 1):
        pid = f"prod_{i:04d}"
        category = random.choice(PRODUCT_CATEGORIES) if random.random() > 0.04 else None  # 4% nulls
        weight_g = round(random.uniform(100, 15000), 1)
        length_cm = round(random.uniform(10, 80), 1)
        height_cm = round(random.uniform(5, 50), 1)
        width_cm = round(random.uniform(10, 60), 1)
        
        # Anomaly: outlier weight
        if random.random() < 0.01:
            weight_g = 999999.0  # Erroneous sensor / manual entry outlier
            
        products_data.append({
            "product_id": pid,
            "product_category_name": category,
            "product_weight_g": weight_g,
            "product_length_cm": length_cm,
            "product_height_cm": height_cm,
            "product_width_cm": width_cm
        })
    df_products = pd.DataFrame(products_data)
    
    # 3. Sellers
    num_sellers = 150
    sellers_data = []
    for i in range(1, num_sellers + 1):
        sid = f"seller_{i:04d}"
        city, state, zip_prefix = random.choice(CITIES_STATES)
        sellers_data.append({
            "seller_id": sid,
            "seller_zip_code_prefix": zip_prefix,
            "seller_city": city,
            "seller_state": state
        })
    df_sellers = pd.DataFrame(sellers_data)
    
    # 4. Orders & Associated Details
    start_date = datetime.datetime(2023, 1, 1)
    orders_data = []
    items_data = []
    payments_data = []
    reviews_data = []
    
    for i in range(1, num_orders + 1):
        oid = f"ord_{i:06d}"
        cid = random.choice(customer_ids)
        status = random.choice(ORDER_STATUSES)
        
        # Purchase timestamp between 2023-01-01 and 2024-06-30
        delta_days = random.randint(0, 545)
        purchase_time = start_date + datetime.timedelta(
            days=delta_days,
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59)
        )
        
        # Approval time typically 1-24 hours after purchase
        approved_time = purchase_time + datetime.timedelta(hours=random.randint(1, 24))
        
        # Shipping and Delivery
        carrier_time = approved_time + datetime.timedelta(days=random.randint(1, 3))
        
        # Estimated delivery usually 10-25 days out
        estimated_delivery = purchase_time + datetime.timedelta(days=random.randint(10, 25))
        
        # Actual delivery date depends on status and real-world variance
        if status == "delivered":
            # Realistic transit duration with occasional delay
            transit_days = random.choices([random.randint(3, 9), random.randint(10, 18), random.randint(19, 35)], weights=[0.6, 0.3, 0.1])[0]
            delivered_customer = purchase_time + datetime.timedelta(days=transit_days)
        elif status in ["shipped", "processing"]:
            delivered_customer = None
        else: # canceled
            carrier_time = None
            delivered_customer = None
            
        # Format dates with occasional formatting inconsistencies
        fmt_normal = "%Y-%m-%d %H:%M:%S"
        fmt_alt = "%d/%m/%Y %H:%M:%S"
        
        purchase_str = purchase_time.strftime(fmt_alt if random.random() < 0.05 else fmt_normal)
        approved_str = approved_time.strftime(fmt_normal) if approved_time else None
        carrier_str = carrier_time.strftime(fmt_normal) if carrier_time else None
        delivered_str = delivered_customer.strftime(fmt_normal) if delivered_customer else None
        estimated_str = estimated_delivery.strftime(fmt_normal)
        
        orders_data.append({
            "order_id": oid,
            "customer_id": cid,
            "order_status": status,
            "order_purchase_timestamp": purchase_str,
            "order_approved_at": approved_str,
            "order_delivered_carrier_date": carrier_str,
            "order_delivered_customer_date": delivered_str,
            "order_estimated_delivery_date": estimated_str
        })
        
        # Order items (1 to 3 items per order)
        num_items = random.choices([1, 2, 3], weights=[0.75, 0.2, 0.05])[0]
        order_total_price = 0.0
        
        for item_seq in range(1, num_items + 1):
            pid = random.choice(df_products["product_id"].tolist())
            sid = random.choice(df_sellers["seller_id"].tolist())
            
            # Base price
            base_price = round(random.uniform(15.0, 450.0), 2)
            # Anomaly: 0.2% negative price (corrupted entry)
            if random.random() < 0.002:
                base_price = -abs(base_price)
            # Anomaly: 0.1% extreme price outlier
            elif random.random() < 0.001:
                base_price = 9999.99
                
            freight = round(random.uniform(8.0, 55.0), 2)
            order_total_price += max(0, base_price) + freight
            
            items_data.append({
                "order_id": oid,
                "order_item_id": item_seq,
                "product_id": pid,
                "seller_id": sid,
                "shipping_limit_date": (purchase_time + datetime.timedelta(days=7)).strftime(fmt_normal),
                "price": base_price,
                "freight_value": freight
            })
            
        # Order payment
        pay_type = random.choice(PAYMENT_TYPES)
        installments = random.randint(1, 10) if pay_type == "credit_card" else 1
        payments_data.append({
            "order_id": oid,
            "payment_sequential": 1,
            "payment_type": pay_type,
            "payment_installments": installments,
            "payment_value": round(order_total_price, 2)
        })
        
        # Order reviews (approx 85% review rate)
        if random.random() < 0.85:
            # Reviews correlate slightly with on-time delivery
            if status == "delivered" and delivered_customer and delivered_customer <= estimated_delivery:
                score = random.choices([5, 4, 3, 2, 1], weights=[0.60, 0.25, 0.08, 0.04, 0.03])[0]
            else:
                score = random.choices([5, 4, 3, 2, 1], weights=[0.15, 0.15, 0.20, 0.25, 0.25])[0]
                
            reviews_data.append({
                "review_id": f"rev_{i:06d}",
                "order_id": oid,
                "review_score": score,
                "review_comment_title": "Good" if score >= 4 else "Late Delivery" if score <= 2 else "Neutral",
                "review_creation_date": (purchase_time + datetime.timedelta(days=15)).strftime(fmt_normal)
            })
            
    df_orders = pd.DataFrame(orders_data)
    df_items = pd.DataFrame(items_data)
    df_payments = pd.DataFrame(payments_data)
    df_reviews = pd.DataFrame(reviews_data)
    
    # Add duplicate payment records (anomalous double processing)
    duplicate_payments = df_payments.sample(n=int(len(df_payments) * 0.015), random_state=RANDOM_SEED)
    df_payments = pd.concat([df_payments, duplicate_payments], ignore_index=True)
    
    return {
        "customers": df_customers,
        "products": df_products,
        "sellers": df_sellers,
        "orders": df_orders,
        "order_items": df_items,
        "order_payments": df_payments,
        "order_reviews": df_reviews
    }

@time_it("Data Ingestion Pipeline")
def run_ingestion(num_orders: int = 15000, target_dir: Path = RAW_DATA_DIR) -> dict[str, Path]:
    """
    Automated ingestion execution: writes generated raw multi-table files to CSV
    and returns file mapping dictionary with record metrics.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Target raw directory: {target_dir}")
    
    datasets = generate_raw_dataset(num_orders=num_orders)
    file_manifest = {}
    
    for name, df in datasets.items():
        file_path = target_dir / f"raw_{name}.csv"
        df.to_csv(file_path, index=False)
        file_manifest[name] = file_path
        logger.info(f"  --> Saved {name:15s}: {len(df):6d} records | {file_path.name}")
        
    logger.info("Raw data ingestion complete across all 7 entities.")
    return file_manifest

if __name__ == "__main__":
    run_ingestion()
