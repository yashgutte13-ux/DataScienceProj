"""
Module: src.quality_assessment
Stage 2: Data Quality Assessment & Profiling

Profiles tabular data across key data quality dimensions:
1. Completeness: Missing / Null values
2. Uniqueness: Exact duplicate rows and primary key uniqueness
3. Validity & Format Consistency: Unparseable date strings, negative numbers
4. Accuracy & Outliers: IQR (Interquartile Range) detection on numerical distributions
Generates Before-and-After audit reports to quantify data engineering quality improvements.
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from src.utils import get_logger, RAW_DATA_DIR, PROCESSED_DATA_DIR, DOCS_DIR, time_it

logger = get_logger("QualityAssessment")

def profile_dataframe(df: pd.DataFrame, table_name: str, key_columns: list[str] = None) -> dict:
    """
    Profile a single dataframe for missing values, duplicates, outliers, and format issues.
    """
    total_rows = len(df)
    total_cols = len(df.columns)
    
    # 1. Missing Values (Completeness)
    missing_counts = df.isnull().sum().to_dict()
    missing_pcts = {col: round((count / total_rows) * 100, 2) if total_rows > 0 else 0 for col, count in missing_counts.items()}
    total_missing_cells = int(df.isnull().sum().sum())
    total_possible_cells = total_rows * total_cols
    completeness_score = round(100.0 - (total_missing_cells / total_possible_cells * 100), 2) if total_possible_cells > 0 else 100.0
    
    # 2. Duplicates (Uniqueness)
    exact_duplicates = int(df.duplicated().sum())
    key_duplicates = 0
    if key_columns:
        valid_keys = [c for c in key_columns if c in df.columns]
        if valid_keys:
            key_duplicates = int(df.duplicated(subset=valid_keys).sum())
    uniqueness_score = round(100.0 - (max(exact_duplicates, key_duplicates) / total_rows * 100), 2) if total_rows > 0 else 100.0
    
    # 3. Outlier Analysis (IQR Method on numeric columns)
    outlier_summary = {}
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    total_outliers = 0
    
    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) > 10:
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            outlier_mask = (series < lower_bound) | (series > upper_bound)
            num_outliers = int(outlier_mask.sum())
            total_outliers += num_outliers
            outlier_summary[col] = {
                "q1": round(float(q1), 2),
                "q3": round(float(q3), 2),
                "iqr": round(float(iqr), 2),
                "lower_bound": round(float(lower_bound), 2),
                "upper_bound": round(float(upper_bound), 2),
                "outlier_count": num_outliers,
                "outlier_pct": round((num_outliers / len(series)) * 100, 2)
            }
            
    # 4. Validity & Format Issues (e.g., negative values in prices or weights)
    validity_issues = {}
    for col in numeric_cols:
        if col in ["price", "freight_value", "payment_value", "product_weight_g"]:
            negative_count = int((df[col] < 0).sum())
            if negative_count > 0:
                validity_issues[f"{col}_negative_values"] = negative_count
                
    # Calculate Overall Data Health Score (Weighted average)
    health_score = round(0.40 * completeness_score + 0.40 * uniqueness_score + 0.20 * max(0, 100 - (total_outliers / max(1, total_rows) * 100)), 2)
    
    return {
        "table_name": table_name,
        "total_rows": total_rows,
        "total_columns": total_cols,
        "total_missing_cells": total_missing_cells,
        "completeness_score": completeness_score,
        "missing_by_column": missing_counts,
        "missing_pct_by_column": missing_pcts,
        "exact_duplicates": exact_duplicates,
        "key_duplicates": key_duplicates,
        "uniqueness_score": uniqueness_score,
        "outlier_summary": outlier_summary,
        "total_outliers": total_outliers,
        "validity_issues": validity_issues,
        "health_score": health_score
    }

@time_it("Data Quality Profiling Audit")
def run_quality_assessment(data_dir: Path, report_tag: str = "before") -> dict:
    """
    Assess quality across all CSV files in target directory and output structured metrics.
    """
    logger.info(f"Running Data Quality Profiling [{report_tag.upper()}] on {data_dir}...")
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    
    key_mapping = {
        "customers": ["customer_id"],
        "raw_customers": ["customer_id"],
        "products": ["product_id"],
        "raw_products": ["product_id"],
        "sellers": ["seller_id"],
        "raw_sellers": ["seller_id"],
        "orders": ["order_id"],
        "raw_orders": ["order_id"],
        "order_items": ["order_id", "order_item_id"],
        "raw_order_items": ["order_id", "order_item_id"],
        "order_payments": ["order_id", "payment_sequential"],
        "raw_order_payments": ["order_id", "payment_sequential"],
        "order_reviews": ["review_id"],
        "raw_order_reviews": ["review_id"]
    }
    
    results = {}
    csv_files = list(data_dir.glob("*.csv"))
    
    if not csv_files:
        logger.warning(f"No CSV files found in {data_dir} to profile!")
        return {}
        
    for file_path in csv_files:
        clean_name = file_path.stem.replace("raw_", "").replace("clean_", "")
        df = pd.read_csv(file_path, low_memory=False)
        keys = key_mapping.get(file_path.stem, key_mapping.get(clean_name, None))
        profile = profile_dataframe(df, table_name=clean_name, key_columns=keys)
        results[clean_name] = profile
        logger.info(
            f"  --> {clean_name:15s} | Rows: {profile['total_rows']:6d} | "
            f"Completeness: {profile['completeness_score']:5.1f}% | "
            f"Uniqueness: {profile['uniqueness_score']:5.1f}% | "
            f"Duplicates: {profile['exact_duplicates']:4d} | "
            f"Health: {profile['health_score']:5.1f}%"
        )
        
    # Save structured JSON
    json_path = PROCESSED_DATA_DIR / f"quality_report_{report_tag}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Saved quality profile JSON to {json_path}")
    
    return results

def generate_quality_comparison_report(before_report: dict, after_report: dict) -> Path:
    """
    Generate markdown documentation comparing before-and-after data quality metrics.
    """
    report_file = DOCS_DIR / "DATA_QUALITY_REPORT.md"
    
    md = []
    md.append("# Data Quality Audit & Profiling Report")
    md.append("## Before-and-After Data Cleansing & Pipeline Improvement\n")
    md.append("This document provides empirical validation of the Data Engineering pipeline's data cleansing, anomaly handling, and standardization logic across all 7 operational entities.\n")
    
    md.append("### 1. Executive Summary Table")
    md.append("| Entity Table | Raw Records | Clean Records | Missing Cells (Before -> After) | Duplicates (Before -> After) | Health Score (Before -> After) |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    
    all_tables = sorted(list(set(before_report.keys()).union(set(after_report.keys()))))
    
    total_raw_rows = 0
    total_clean_rows = 0
    total_raw_missing = 0
    total_clean_missing = 0
    total_raw_dups = 0
    total_clean_dups = 0
    
    for tbl in all_tables:
        b = before_report.get(tbl, {})
        a = after_report.get(tbl, {})
        
        r_rows = b.get("total_rows", 0)
        c_rows = a.get("total_rows", 0)
        r_miss = b.get("total_missing_cells", 0)
        c_miss = a.get("total_missing_cells", 0)
        r_dups = b.get("exact_duplicates", 0) + b.get("key_duplicates", 0)
        c_dups = a.get("exact_duplicates", 0) + a.get("key_duplicates", 0)
        r_health = b.get("health_score", 0.0)
        c_health = a.get("health_score", 0.0)
        
        total_raw_rows += r_rows
        total_clean_rows += c_rows
        total_raw_missing += r_miss
        total_clean_missing += c_miss
        total_raw_dups += r_dups
        total_clean_dups += c_dups
        
        md.append(f"| **{tbl}** | {r_rows:,} | {c_rows:,} | {r_miss:,} → {c_miss:,} | {r_dups:,} → {c_dups:,} | {r_health:.1f}% → **{c_health:.1f}%** |")
        
    md.append(f"| **TOTAL PIPELINE** | **{total_raw_rows:,}** | **{total_clean_rows:,}** | **{total_raw_missing:,} → {total_clean_missing:,}** | **{total_raw_dups:,} → {total_clean_dups:,}** | **Average Health Improvement** |\n")
    
    md.append("### 2. Detailed Data Quality Dimensions Evaluated")
    md.append("#### A. Completeness (Missing Value Remediation)")
    md.append("- **Customer Zip Codes**: Imputed missing postal codes based on modal distribution per city/state.")
    md.append("- **Product Categories**: Missing category values filled with `'unclassified_general'` fallback.")
    md.append("- **Logistics Delivery Dates**: Missing customer delivery dates for non-delivered items (`shipped`, `processing`, `canceled`) appropriately flagged without schema truncation.\n")
    
    md.append("#### B. Uniqueness (Deduplication)")
    md.append("- Exact customer duplicates generated by repeated registrations were detected and eliminated based on `customer_id` primary key constraint.")
    md.append("- Double-processed payment records (duplicate `order_id` + `payment_sequential`) were purged prior to Star Schema loading.\n")
    
    md.append("#### C. Validity & Format Standardization")
    md.append("- **Date Formats**: Mixed datetime formatting (ISO `YYYY-MM-DD` vs European `DD/MM/YYYY`) parsed and converted into uniform ISO-8601 standard timestamps.")
    md.append("- **Casing Consistency**: City and state names standardized into canonical lowercase trimmed strings to enable accurate geographic joins.")
    md.append("- **Negative Price / Value Elimination**: Negative transactions filtered or corrected to protect accounting integrity.\n")
    
    md.append("#### D. Outlier Detection & Handling (IQR Method)")
    md.append("- Extreme product weight entry outliers (e.g. 999,999g entry error) identified using 1.5 × IQR thresholds and capped at the 99th percentile.")
    md.append("- Order price extremes validated against order payment aggregations to guarantee referential consistency.\n")
    
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
        
    logger.info(f"Generated comprehensive markdown quality report at: {report_file}")
    return report_file

if __name__ == "__main__":
    import sys
    tag = sys.argv[1] if len(sys.argv) > 1 else "before"
    target_dir = PROCESSED_DATA_DIR if tag == "after" else RAW_DATA_DIR
    res = run_quality_assessment(target_dir, report_tag=tag)
    
    # If both before and after reports exist, generate comparison
    before_json = PROCESSED_DATA_DIR / "quality_report_before.json"
    after_json = PROCESSED_DATA_DIR / "quality_report_after.json"
    if before_json.exists() and after_json.exists():
        with open(before_json, "r", encoding="utf-8") as f:
            b_rep = json.load(f)
        with open(after_json, "r", encoding="utf-8") as f:
            a_rep = json.load(f)
        generate_quality_comparison_report(b_rep, a_rep)
