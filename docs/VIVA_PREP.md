# Mini Project Viva Voce & Presentation Preparation Guide

This guide is designed to prepare team members for the 10-12 minute final project presentation, live demonstration, and professor/examiner viva questions.

---

## 1. 10-12 Minute Presentation Structure

| Time | Slide / Topic | Key Points to Cover |
| :--- | :--- | :--- |
| **00:00 - 02:00** | **Problem Statement & Objectives** | E-commerce fragmentation across sales, logistics, and payments. Why unified dimensional data is needed for logistics SLA tracking and customer retention. |
| **02:00 - 04:00** | **Pipeline Architecture & Ingestion** | End-to-end data flow: Raw ingestion -> Pre-cleaning quality profiler -> Pandas transformation -> Post-cleaning profiler -> Star Schema warehouse loading. |
| **04:00 - 06:00** | **Data Quality Audit (Before vs After)** | Show the 4 dimensions: Completeness (imputation), Uniqueness (deduplication of customers/payments), Validity (casing/negative prices), and Outlier capping (IQR method). |
| **06:00 - 08:00** | **Dimensional Modeling (Star Schema)** | Explain Fact Table grain (`fact_orders` at order item level), 4 Dimension tables (`dim_customers`, `dim_products`, `dim_sellers`, `dim_date`), surrogate keys, and B-tree indexes. |
| **08:00 - 10:00** | **Live BI Dashboard Demo** | Demonstrate the Streamlit app: Executive KPIs, Delivery SLA state map, RFM treemap, and the interactive SQL Query Studio. |
| **10:00 - 12:00** | **Distributed Scalability & Conclusion** | Explain the single-node SQLite decision vs Apache Spark cluster scaling (`src/distributed_spark_etl.py`). Open for Q&A. |

---

## 2. Top Viva Voce Questions & Model Answers

### Category 1: Architecture & Data Engineering Fundamentals

**Q1: What is the difference between ETL and ELT, and which one did you implement?**  
*Answer:* In ETL (Extract, Transform, Load), raw data is extracted, transformed in memory/staging by an external compute engine (like Pandas or Spark), and then loaded into the target storage. In ELT (Extract, Load, Transform), raw data is loaded directly into a cloud data lake/warehouse (like Snowflake or BigQuery) and transformed using SQL engines. In this project, we implemented an **ETL pipeline**: we extracted raw data, applied deduplication and feature engineering in Python/Pandas, and loaded the curated records into our Star Schema Data Warehouse.

**Q2: What is the Kimball Dimensional Modeling methodology?**  
*Answer:* Ralph Kimball’s dimensional modeling is a bottom-up data warehousing technique focused on business process measurement. It separates data into **Fact tables** (numerical measurements, transaction events, and additive metrics) and **Dimension tables** (contextual descriptive attributes like who, what, where, and when), forming a Star or Snowflake schema optimized for fast analytical read queries.

**Q3: What is the grain of your Fact Table?**  
*Answer:* The grain of `fact_orders` is **one individual line item within an order**. This atomic grain ensures that orders containing multiple products or different sellers can be accurately analyzed without data loss or multi-value attribute violations.

---

### Category 2: Data Quality & Profiling

**Q4: What data quality dimensions did your pipeline profile, and what were the findings?**  
*Answer:* We evaluated four primary dimensions:
1. **Completeness:** Identified missing zip codes and product categories; resolved via modal imputation and default category fallbacks.
2. **Uniqueness:** Detected 337 duplicate customer registrations and 225 duplicate payment records; resolved via natural key deduplication.
3. **Validity:** Standardized inconsistent date strings (mixing ISO and European formats) and converted negative prices using absolute values.
4. **Outliers:** Identified extreme weight sensor anomalies (999,999g) using 1.5 × IQR thresholds and capped them at the 99th percentile.

**Q5: Why did you profile the data both Before and After transformation?**  
*Answer:* Before-and-after profiling provides empirical proof of data quality improvement. It guarantees that our transformation logic purged 100% of duplicates, resolved format discrepancies, and maintained referential integrity without accidentally dropping valid records.

---

### Category 3: Database & Schema Design

**Q6: Why did you use a Star Schema instead of 3rd Normal Form (3NF)?**  
*Answer:* 3NF is designed for Online Transaction Processing (OLTP) to minimize write redundancy and update anomalies through extensive normalization (many joined tables). Star Schema is designed for Online Analytical Processing (OLAP) to minimize table joins, simplify BI queries, and provide superior aggregation performance.

**Q7: Why do we use surrogate keys instead of natural business keys in dimension tables?**  
*Answer:* 
1. **Performance:** Integer surrogate keys (e.g. 4-byte INT) are much faster to index and join than variable-length string UUIDs.
2. **Slowly Changing Dimensions (SCD):** Surrogate keys allow tracking historical changes for the same entity over time (e.g. if a customer moves to another city).
3. **System Independence:** Shields the warehouse from upstream source system key changes or format shifts.

**Q8: What performance indexes did you create, and why?**  
*Answer:* We created B-tree indexes on:
1. Foreign key columns in `fact_orders` (`customer_key`, `product_key`, `seller_key`, `order_date_key`) to accelerate dimension joins.
2. High-cardinality filter columns (`order_status`, `sla_breached`, `rfm_segment`) to speed up WHERE clause filtering in BI queries.

---

### Category 4: Distributed Computing & Scalability

**Q9: Why didn't you use Apache Spark as the primary database for this project?**  
*Answer:* Apache Spark is a distributed cluster computing framework built for multi-terabyte datasets that cannot fit in the RAM of a single server. Our dataset is ~75,000 records (~15 MB). Running Spark locally would incur high JVM startup latency, CPU overhead, and cluster management complexity without performance gain. However, to prove production readiness, we created `src/distributed_spark_etl.py` which demonstrates the exact same logic using PySpark dataframes, Catalyst optimization, and partitioned Parquet storage.

**Q10: How would you scale this pipeline if data volume grew from 75,000 to 100 million records daily?**  
*Answer:*
1. **Ingestion:** Transition to Apache Kafka or AWS Kinesis for streaming ingestion, writing raw JSON/Avro into an Amazon S3 or Google Cloud Storage Data Lake.
2. **Compute:** Deploy the PySpark pipeline on AWS EMR or Databricks, using Delta Lake for ACID transactions and partition pruning on `(year, month)`.
3. **Warehouse:** Load into a cloud data warehouse like Snowflake or Google BigQuery.
4. **Orchestration:** Use Apache Airflow or Prefect to schedule and monitor daily DAG execution.

---

### Category 5: Business Intelligence & Feature Engineering

**Q11: How is the Logistics SLA Breach metric calculated?**  
*Answer:*
- `delivery_delay_days = (order_delivered_customer_date - order_estimated_delivery_date).days`
- If `delivery_delay_days > 0`, `sla_breached = 1` (Late delivery); otherwise `0` (On-time).

**Q12: How does Customer RFM Segmentation work?**  
*Answer:*
- **Recency (R):** Days since the customer's last order.
- **Frequency (F):** Total number of distinct orders placed.
- **Monetary (M):** Total lifetime spend across all purchases.  
Customers are scored into quartile tiers and segmented into cohorts like *Champions*, *Loyal Customers*, *At Risk*, and *Lost*, allowing targeted retention and marketing strategies.
