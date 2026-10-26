"""
Master Pipeline Orchestrator: run_pipeline.py
End-to-End Data Engineering Pipeline Execution

Orchestrates all 5 stages of the data engineering lifecycle:
1. Ingestion: Raw multi-entity data generation and ingestion
2. Quality Assessment (Before): Initial data profiling and anomaly detection
3. Transformation: Deduplication, missing value imputation, SLA and RFM feature engineering
4. Quality Assessment (After): Cleaned data profiling and improvement report generation
5. Storage & Star Schema Loading: Relational Data Warehouse population, indexes, views, and Power BI export
"""

import sys
import time
import json
from pathlib import Path

# Force UTF-8 on Windows stdout/stderr
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.utils import get_logger, RAW_DATA_DIR, PROCESSED_DATA_DIR, WAREHOUSE_DIR
from src.ingestion import run_ingestion
from src.quality_assessment import run_quality_assessment, generate_quality_comparison_report
from src.transformation import run_transformation
from src.storage import run_storage_pipeline

logger = get_logger("PipelineOrchestrator")

def execute_full_pipeline(num_orders: int = 15000):
    """Run full data engineering pipeline end-to-end with timing and audit metrics."""
    print("=" * 80)
    print(">>> LAUNCHING END-TO-END DATA ENGINEERING SOLUTION PIPELINE <<<")
    print("=" * 80)
    
    total_start = time.time()
    
    # Stage 1: Ingestion
    print("\n--- STAGE 1: RAW DATA INGESTION ---")
    raw_files = run_ingestion(num_orders=num_orders)
    
    # Stage 2: Quality Assessment Before Cleaning
    print("\n--- STAGE 2A: DATA QUALITY PROFILING (BEFORE) ---")
    report_before = run_quality_assessment(RAW_DATA_DIR, report_tag="before")
    
    # Stage 3: Transformation & Enrichment
    print("\n--- STAGE 3: DATA TRANSFORMATION & ENRICHMENT ---")
    transformed_dfs = run_transformation()
    
    # Stage 4: Quality Assessment After Cleaning
    print("\n--- STAGE 2B: DATA QUALITY PROFILING (AFTER) ---")
    report_after = run_quality_assessment(PROCESSED_DATA_DIR, report_tag="after")
    
    # Generate Comparison Report
    print("\n--- STAGE 2C: GENERATING QUALITY COMPARISON AUDIT ---")
    quality_md = generate_quality_comparison_report(report_before, report_after)
    
    # Stage 5: Storage & Star Schema Loading
    print("\n--- STAGE 4: STORAGE & STAR SCHEMA WAREHOUSE LOADING ---")
    run_storage_pipeline()
    
    total_duration = time.time() - total_start
    
    print("\n" + "=" * 80)
    print(f"[SUCCESS] PIPELINE COMPLETED SUCCESSFULLY IN {total_duration:.2f} SECONDS")
    print("=" * 80)
    print(f"Raw Data Stored In        : {RAW_DATA_DIR}")
    print(f"Clean Data Staged In      : {PROCESSED_DATA_DIR}")
    print(f"Data Warehouse Location   : {WAREHOUSE_DIR / 'ecommerce_dw.db'}")
    print(f"Power BI / Tableau Export : {WAREHOUSE_DIR / 'powerbi_export'}")
    print(f"Audit Report Generated    : {quality_md}")
    print("=" * 80)
    print("To launch the interactive BI Dashboard, run:")
    print("   streamlit run dashboard/app.py")
    print("=" * 80)

if __name__ == "__main__":
    execute_full_pipeline()
