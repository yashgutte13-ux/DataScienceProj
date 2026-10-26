# Technical Architecture & Data Flow Specification

## 1. High-Level Architecture Diagram

```mermaid
graph TD
    subgraph Data Sources & Ingestion
        A[Customer Transactions CSV / API] --> B[Raw Data Staging: data/raw/]
        A1[Product Catalog] --> B
        A2[Logistics Events] --> B
        A3[Payment Gateways] --> B
    end

    subgraph Data Quality Profiling Engine
        B --> C[Initial Quality Profiler]
        C --> D[(quality_report_before.json)]
    end

    subgraph Transformation & Business Logic ETL
        B --> E[Pandas / Python ETL Pipeline]
        E --> E1[Deduplication & Primary Key Validation]
        E --> E2[Datetime Standardisation to ISO-8601]
        E --> E3[Delivery SLA & Delay Feature Engineering]
        E --> E4[Customer RFM Behavioral Segmentation]
        E --> E5[Calendar Date Dimension Generation]
        E --> F[Processed Data Staging: data/processed/]
        F --> G[Post-Cleansing Quality Profiler]
        G --> H[(quality_report_after.json & DATA_QUALITY_REPORT.md)]
    end

    subgraph Relational Star Schema Data Warehouse
        F --> I[Storage Loader: src/storage.py]
        I --> J[(SQLite DW: ecommerce_dw.db)]
        J --> J1[dim_customers]
        J --> J2[dim_products]
        J --> J3[dim_sellers]
        J --> J4[dim_date]
        J --> J5[fact_orders]
        J --> K[B-tree Indexes & SQL Analytical Views]
    end

    subgraph Presentation & BI Layer
        J --> L[Streamlit Interactive BI Web App]
        K --> L
        J --> M[Power BI / Tableau CSV Export: powerbi_export/]
    end
```

---

## 2. Pipeline Layers & Lifecycle

### Layer 1: Ingestion Layer (`src/ingestion.py`)
- **Responsibility:** Automated collection, extraction, and staging of transactional data.
- **Input:** External feeds (CSV files, REST API batch simulations, database extracts).
- **Output:** Staged raw files in `data/raw/` preserving raw input fidelity without premature filtering.

### Layer 2: Data Quality Assessment Layer (`src/quality_assessment.py`)
- **Responsibility:** Objective profiling across Completeness, Uniqueness, Validity, and Outlier distributions.
- **Workflow:** Runs before and after transformations, outputting comparative JSON profiles and generating `docs/DATA_QUALITY_REPORT.md`.

### Layer 3: Transformation & Enrichment Layer (`src/transformation.py`)
- **Responsibility:** Cleansing anomalies, imputing missing values, enforcing casing consistency, and feature-engineering analytical metrics (Delivery SLA, RFM customer tiers).
- **Output:** Staged analytical tables in `data/processed/`.

### Layer 4: Storage & Data Warehouse Layer (`src/storage.py` & `src/models.sql`)
- **Responsibility:** Kimball Star Schema modeling. Generates surrogate primary keys, enforces foreign key referential integrity, builds query indexes, and encapsulates common analytics into SQL Views.
- **Output:** SQLite database (`data/warehouse/ecommerce_dw.db`) and CSV dumps for external BI tools (`data/warehouse/powerbi_export/`).

### Layer 5: BI & Visualization Layer (`dashboard/app.py`)
- **Responsibility:** Self-service interactive analytics, KPI tracking, cohort heatmaps, and ad-hoc SQL querying.

---

## 3. Distributed Scaling Blueprint (PySpark / Cloud)

For production enterprise workloads handling petabyte-scale data:
```
[ Kafka / Kinesis Streaming Ingestion ]
                  │
                  ▼
[ Raw Data Lake (Amazon S3 / Google Cloud Storage - Parquet format) ]
                  │
                  ▼
[ Apache Spark / Databricks Distributed Cluster (PySpark Catalyst Optimizer) ]
                  │
                  ├── Distributed Window Partitioning (RFM & Delivery Durations)
                  ├── Distributed Shuffling & Deduplication
                  └── Predicate Pushdown & Columnar Pruning
                  │
                  ▼
[ Cloud Data Warehouse: Snowflake / Databricks Delta Lake / Google BigQuery ]
                  │
                  ▼
[ Power BI / Tableau / Metabase Enterprise BI Dashboards ]
```
The blueprint is fully coded and documented in `src/distributed_spark_etl.py`.
