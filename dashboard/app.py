"""
OmniCart Analytics | Enterprise Data Engineering BI Dashboard
Streamlit-based Interactive Analytical Application
Connects directly to the Star Schema Data Warehouse (SQLite)
"""

import sqlite3
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "warehouse" / "ecommerce_dw.db"
QUALITY_BEFORE_PATH = PROJECT_ROOT / "data" / "processed" / "quality_report_before.json"
QUALITY_AFTER_PATH = PROJECT_ROOT / "data" / "processed" / "quality_report_after.json"

# Page configuration
st.set_page_config(
    page_title="OmniCart Analytics | Data Warehouse BI",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern styling
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        color: white;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .metric-val {
        font-size: 28px;
        font-weight: 700;
        color: #38bdf8;
    }
    .metric-lbl {
        font-size: 13px;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-sub {
        font-size: 12px;
        color: #10b981;
        margin-top: 4px;
    }
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        background-color: #064e3b;
        color: #6ee7b7;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_db_connection():
    """Cache connection to local SQLite Data Warehouse, auto-building if running on cloud."""
    if not DB_PATH.exists():
        with st.spinner("🚀 First-time Setup: Building Star Schema Data Warehouse on Streamlit Cloud..."):
            import sys
            if str(PROJECT_ROOT) not in sys.path:
                sys.path.insert(0, str(PROJECT_ROOT))
            from run_pipeline import execute_full_pipeline
            execute_full_pipeline(num_orders=10000)
    return sqlite3.connect(DB_PATH, check_same_thread=False)

conn = get_db_connection()

# Sidebar: Global Filters
st.sidebar.title("🎛️ Warehouse Filters")
st.sidebar.markdown("<span class='status-badge'>● Warehouse Live</span>", unsafe_allow_html=True)
st.sidebar.write("")

# Query filter metadata
all_states = [row[0] for row in conn.execute("SELECT DISTINCT customer_state FROM dim_customers ORDER BY 1;").fetchall()]
all_segments = [row[0] for row in conn.execute("SELECT DISTINCT rfm_segment FROM dim_customers ORDER BY 1;").fetchall()]
all_categories = [row[0] for row in conn.execute("SELECT DISTINCT product_category_name FROM dim_products ORDER BY 1;").fetchall()]

selected_states = st.sidebar.multiselect("Filter by State", options=all_states, default=all_states[:5])
selected_segments = st.sidebar.multiselect("Filter by Customer Segment", options=all_segments, default=all_segments)
selected_categories = st.sidebar.multiselect("Filter by Product Category", options=all_categories, default=all_categories[:6])

# Build dynamic SQL WHERE clause
where_clauses = ["1=1"]
if selected_states:
    state_str = "', '".join(selected_states)
    where_clauses.append(f"c.customer_state IN ('{state_str}')")
if selected_segments:
    seg_str = "', '".join(selected_segments)
    where_clauses.append(f"c.rfm_segment IN ('{seg_str}')")
if selected_categories:
    cat_str = "', '".join(selected_categories)
    where_clauses.append(f"p.product_category_name IN ('{cat_str}')")

filter_sql = " AND ".join(where_clauses)

# Header
st.title("📦 OmniCart Enterprise Data Warehouse & BI")
st.caption("End-to-End Data Engineering Solution | Star Schema Dimensional Model & Analytical Intelligence")

# Main Navigation Tabs
tab_kpi, tab_logistics, tab_rfm, tab_products, tab_sql, tab_quality = st.tabs([
    "🌟 Executive Overview",
    "🚚 Logistics & Delivery SLA",
    "👥 Customer RFM Segments",
    "📦 Product Category Matrix",
    "🔍 SQL Query Studio",
    "🛡️ Data Quality & Architecture"
])

# -------------------------------------------------------------------
# TAB 1: EXECUTIVE OVERVIEW
# -------------------------------------------------------------------
with tab_kpi:
    # Query filtered KPIs
    kpi_query = f"""
    SELECT
        COUNT(DISTINCT f.order_id) as total_orders,
        COUNT(f.order_item_key) as total_items,
        COALESCE(SUM(f.total_item_value), 0) as total_gmv,
        COALESCE(AVG(f.total_item_value), 0) as avg_item_val,
        COALESCE(AVG(CASE WHEN f.order_status = 'delivered' THEN f.actual_delivery_days END), 0) as avg_delivery,
        COALESCE(100.0 * SUM(CASE WHEN f.order_status = 'delivered' AND f.sla_breached = 0 THEN 1 ELSE 0 END) / 
                 NULLIF(SUM(CASE WHEN f.order_status = 'delivered' THEN 1 ELSE 0 END), 0), 0) as on_time_sla,
        COALESCE(AVG(f.review_score), 0) as avg_review
    FROM fact_orders f
    JOIN dim_customers c ON f.customer_key = c.customer_key
    JOIN dim_products p ON f.product_key = p.product_key
    WHERE {filter_sql};
    """
    kpis = pd.read_sql(kpi_query, conn).iloc[0]
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-lbl">Total Gross Revenue</div>
            <div class="metric-val">${kpis['total_gmv']:,.2f}</div>
            <div class="metric-sub">▲ Filtered GMV</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-lbl">Orders Placed</div>
            <div class="metric-val">{int(kpis['total_orders']):,}</div>
            <div class="metric-sub">▲ {int(kpis['total_items']):,} items sold</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-lbl">Average Item Value</div>
            <div class="metric-val">${kpis['avg_item_val']:.2f}</div>
            <div class="metric-sub">Across all categories</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-lbl">On-Time Delivery SLA</div>
            <div class="metric-val">{kpis['on_time_sla']:.1f}%</div>
            <div class="metric-sub">Avg {kpis['avg_delivery']:.1f} days to door</div>
        </div>
        """, unsafe_allow_html=True)
    with col5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-lbl">Avg Review Rating</div>
            <div class="metric-val">{kpis['avg_review']:.2f} ★</div>
            <div class="metric-sub">Out of 5.0 rating scale</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.write("")
    
    # Revenue Trend Chart
    trend_query = f"""
    SELECT
        d.year,
        d.month,
        d.month_year,
        ROUND(SUM(f.total_item_value), 2) as revenue,
        COUNT(DISTINCT f.order_id) as order_count
    FROM fact_orders f
    JOIN dim_date d ON f.order_date_key = d.date_key
    JOIN dim_customers c ON f.customer_key = c.customer_key
    JOIN dim_products p ON f.product_key = p.product_key
    WHERE {filter_sql}
    GROUP BY d.year, d.month, d.month_year
    ORDER BY d.year, d.month;
    """
    df_trend = pd.read_sql(trend_query, conn)
    
    c_left, c_right = st.columns([2, 1])
    with c_left:
        st.subheader("📈 Monthly Revenue & Order Volume Trajectory")
        fig_trend = go.Figure()
        fig_trend.add_trace(go.Bar(
            x=df_trend["month_year"],
            y=df_trend["revenue"],
            name="Gross Revenue ($)",
            marker_color="#38bdf8"
        ))
        fig_trend.add_trace(go.Scatter(
            x=df_trend["month_year"],
            y=df_trend["order_count"],
            name="Order Count",
            yaxis="y2",
            line=dict(color="#f59e0b", width=3)
        ))
        fig_trend.update_layout(
            yaxis=dict(title="Gross Revenue ($)"),
            yaxis2=dict(title="Order Count", overlaying="y", side="right"),
            legend=dict(x=0.01, y=0.99),
            margin=dict(l=20, r=20, t=30, b=20),
            height=380
        )
        st.plotly_chart(fig_trend, use_container_width=True)
        
    with c_right:
        st.subheader("💳 Payment Type Share")
        pay_query = f"""
        SELECT f.payment_type, COUNT(DISTINCT f.order_id) as orders, ROUND(SUM(f.total_item_value), 2) as sales
        FROM fact_orders f
        JOIN dim_customers c ON f.customer_key = c.customer_key
        JOIN dim_products p ON f.product_key = p.product_key
        WHERE {filter_sql} AND f.payment_type IS NOT NULL
        GROUP BY f.payment_type;
        """
        df_pay = pd.read_sql(pay_query, conn)
        fig_pay = px.pie(
            df_pay,
            names="payment_type",
            values="sales",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Prism
        )
        fig_pay.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=380)
        st.plotly_chart(fig_pay, use_container_width=True)

# -------------------------------------------------------------------
# TAB 2: LOGISTICS & DELIVERY SLA
# -------------------------------------------------------------------
with tab_logistics:
    st.subheader("🚚 Fulfillment Performance & Carrier SLA Analytics")
    st.markdown("Monitor order fulfillment speed, regional carrier delays, and SLA breach rates across states.")
    
    sla_query = f"""
    SELECT
        c.customer_state,
        COUNT(DISTINCT f.order_id) as total_orders,
        ROUND(AVG(f.actual_delivery_days), 1) as avg_actual_days,
        ROUND(AVG(f.estimated_delivery_days), 1) as avg_estimated_days,
        ROUND(AVG(f.delivery_delay_days), 1) as avg_delay_days,
        SUM(f.sla_breached) as breaches,
        ROUND(100.0 * (COUNT(f.order_item_key) - SUM(f.sla_breached)) / COUNT(f.order_item_key), 1) as on_time_rate
    FROM fact_orders f
    JOIN dim_customers c ON f.customer_key = c.customer_key
    JOIN dim_products p ON f.product_key = p.product_key
    WHERE {filter_sql} AND f.order_status = 'delivered'
    GROUP BY c.customer_state
    ORDER BY breaches DESC;
    """
    df_sla = pd.read_sql(sla_query, conn)
    
    col_sla1, col_sla2 = st.columns([3, 2])
    with col_sla1:
        fig_sla = px.bar(
            df_sla,
            x="customer_state",
            y="on_time_rate",
            color="on_time_rate",
            color_continuous_scale="RdYlGn",
            labels={"on_time_rate": "On-Time SLA %", "customer_state": "State"},
            title="State-by-State On-Time Delivery Rate (%)"
        )
        fig_sla.add_hline(y=85.0, line_dash="dash", line_color="red", annotation_text="Target SLA (85%)")
        fig_sla.update_layout(height=400)
        st.plotly_chart(fig_sla, use_container_width=True)
        
    with col_sla2:
        # Delivery delay breakdown
        delay_dist_query = f"""
        SELECT f.delivery_performance_status, COUNT(*) as count
        FROM fact_orders f
        JOIN dim_customers c ON f.customer_key = c.customer_key
        JOIN dim_products p ON f.product_key = p.product_key
        WHERE {filter_sql}
        GROUP BY f.delivery_performance_status;
        """
        df_dist = pd.read_sql(delay_dist_query, conn)
        fig_dist = px.pie(
            df_dist,
            names="delivery_performance_status",
            values="count",
            title="Delivery SLA Status Breakdown",
            color_discrete_sequence=["#10b981", "#3b82f6", "#f59e0b", "#ef4444"]
        )
        fig_dist.update_layout(height=400)
        st.plotly_chart(fig_dist, use_container_width=True)
        
    st.dataframe(
        df_sla.rename(columns={
            "customer_state": "State",
            "total_orders": "Total Orders",
            "avg_actual_days": "Avg Actual Days",
            "avg_estimated_days": "Avg Promised Days",
            "avg_delay_days": "Avg Delay (Days)",
            "breaches": "SLA Breaches",
            "on_time_rate": "On-Time Rate %"
        }),
        use_container_width=True
    )

# -------------------------------------------------------------------
# TAB 3: CUSTOMER RFM SEGMENTS
# -------------------------------------------------------------------
with tab_rfm:
    st.subheader("👥 Customer RFM (Recency, Frequency, Monetary) Intelligence")
    st.markdown("Segments customer base into behavioral cohorts for retention, upsell, and reactivation campaigns.")
    
    rfm_query = f"""
    SELECT
        c.rfm_segment,
        COUNT(DISTINCT c.customer_key) as customers,
        ROUND(AVG(c.recency_days), 1) as avg_recency,
        ROUND(AVG(c.order_frequency), 2) as avg_frequency,
        ROUND(SUM(c.monetary_spend), 2) as total_spend,
        ROUND(AVG(c.monetary_spend), 2) as avg_clv
    FROM dim_customers c
    WHERE c.rfm_segment IN ('{"', '".join(selected_segments)}')
    GROUP BY c.rfm_segment
    ORDER BY total_spend DESC;
    """
    df_rfm = pd.read_sql(rfm_query, conn)
    
    col_rfm1, col_rfm2 = st.columns([1, 1])
    with col_rfm1:
        fig_rfm_tree = px.treemap(
            df_rfm,
            path=["rfm_segment"],
            values="total_spend",
            color="customers",
            color_continuous_scale="Viridis",
            title="Customer Segments by Total Spend ($GMV)"
        )
        fig_rfm_tree.update_layout(height=420)
        st.plotly_chart(fig_rfm_tree, use_container_width=True)
        
    with col_rfm2:
        fig_rfm_scatter = px.scatter(
            df_rfm,
            x="avg_recency",
            y="avg_clv",
            size="customers",
            color="rfm_segment",
            labels={"avg_recency": "Avg Recency (Days Ago)", "avg_clv": "Avg Customer Lifetime Spend ($)"},
            title="Customer Segment Positioning (Recency vs CLV)"
        )
        fig_rfm_scatter.update_layout(height=420)
        st.plotly_chart(fig_rfm_scatter, use_container_width=True)
        
    st.dataframe(
        df_rfm.rename(columns={
            "rfm_segment": "Segment",
            "customers": "Customer Count",
            "avg_recency": "Avg Recency (Days)",
            "avg_frequency": "Avg Frequency (Orders)",
            "total_spend": "Total Revenue ($)",
            "avg_clv": "Avg Spend per Customer ($)"
        }),
        use_container_width=True
    )

# -------------------------------------------------------------------
# TAB 4: PRODUCT CATEGORY MATRIX
# -------------------------------------------------------------------
with tab_products:
    st.subheader("📦 Product Category Performance & Quality Matrix")
    
    cat_query = f"""
    SELECT
        p.product_category_name,
        COUNT(f.order_item_key) as units_sold,
        ROUND(SUM(f.total_item_value), 2) as total_sales,
        ROUND(AVG(f.price), 2) as avg_price,
        ROUND(AVG(f.review_score), 2) as avg_review,
        ROUND(100.0 * SUM(f.sla_breached) / COUNT(f.order_item_key), 1) as delay_rate
    FROM fact_orders f
    JOIN dim_products p ON f.product_key = p.product_key
    JOIN dim_customers c ON f.customer_key = c.customer_key
    WHERE {filter_sql}
    GROUP BY p.product_category_name
    ORDER BY total_sales DESC;
    """
    df_cat = pd.read_sql(cat_query, conn)
    
    col_cat1, col_cat2 = st.columns(2)
    with col_cat1:
        fig_cat_sales = px.bar(
            df_cat.head(10),
            x="total_sales",
            y="product_category_name",
            orientation="h",
            color="avg_review",
            color_continuous_scale="Blues",
            title="Top 10 Categories by Total Sales ($)",
            labels={"total_sales": "Gross Revenue ($)", "product_category_name": "Category"}
        )
        fig_cat_sales.update_layout(yaxis=dict(autorange="reversed"), height=420)
        st.plotly_chart(fig_cat_sales, use_container_width=True)
        
    with col_cat2:
        fig_cat_bubble = px.scatter(
            df_cat,
            x="avg_price",
            y="avg_review",
            size="units_sold",
            color="delay_rate",
            color_continuous_scale="Reds",
            hover_name="product_category_name",
            title="Price vs Review Score (Color = Delay Rate %)",
            labels={"avg_price": "Avg Unit Price ($)", "avg_review": "Avg Review Score (1-5)"}
        )
        fig_cat_bubble.update_layout(height=420)
        st.plotly_chart(fig_cat_bubble, use_container_width=True)
        
    st.dataframe(df_cat, use_container_width=True)

# -------------------------------------------------------------------
# TAB 5: INTERACTIVE SQL QUERY STUDIO
# -------------------------------------------------------------------
with tab_sql:
    st.subheader("🔍 Star Schema SQL Query Studio")
    st.markdown("Execute custom ad-hoc analytical SQL queries directly against `ecommerce_dw.db`.")
    
    sample_queries = {
        "Executive KPI View": "SELECT * FROM vw_executive_kpis;",
        "Top 10 Revenue Generating Customers": """
            SELECT c.customer_id, c.customer_city, c.customer_state, c.rfm_segment,
                   c.order_frequency, c.monetary_spend
            FROM dim_customers c
            ORDER BY c.monetary_spend DESC
            LIMIT 10;
        """,
        "Monthly Order & Revenue Growth": """
            SELECT year, month_year, total_orders, gross_revenue, avg_review_score, on_time_pct
            FROM vw_monthly_revenue_trend
            ORDER BY year, month;
        """,
        "Worst Delivery Delay Records": """
            SELECT f.order_id, c.customer_state, p.product_category_name,
                   f.actual_delivery_days, f.estimated_delivery_days, f.delivery_delay_days, f.review_score
            FROM fact_orders f
            JOIN dim_customers c ON f.customer_key = c.customer_key
            JOIN dim_products p ON f.product_key = p.product_key
            WHERE f.sla_breached = 1
            ORDER BY f.delivery_delay_days DESC
            LIMIT 15;
        """
    }
    
    selected_sample = st.selectbox("Load Sample Analytical Query:", list(sample_queries.keys()))
    user_query = st.text_area("SQL Editor:", value=sample_queries[selected_sample].strip(), height=150)
    
    if st.button("▶ Run SQL Query"):
        try:
            import time
            start = time.time()
            df_custom = pd.read_sql(user_query, conn)
            latency = (time.time() - start) * 1000
            st.success(f"Query returned {len(df_custom):,} rows in {latency:.1f} ms")
            st.dataframe(df_custom, use_container_width=True)
            
            # Download CSV
            csv_data = df_custom.to_csv(index=False).encode("utf-8")
            st.download_button("⬇ Download Result as CSV", data=csv_data, file_name="query_results.csv", mime="text/csv")
        except Exception as err:
            st.error(f"SQL Execution Error: {err}")

# -------------------------------------------------------------------
# TAB 6: DATA QUALITY & ARCHITECTURE
# -------------------------------------------------------------------
with tab_quality:
    st.subheader("🛡️ Data Pipeline Lineage & Before-vs-After Quality Audit")
    
    # Architecture Diagram
    st.markdown("### 🏗️ End-to-End Pipeline Architecture Diagram")
    st.code("""
    [ Raw Data Sources: CSVs / API Batch ]
                   │
                   ▼ (Stage 1: Automated Ingestion)
    [ Raw Data Lake / data/raw/ ]
                   │
                   ▼ (Stage 2: Automated Data Quality Profiler)
    [ Quality Assessment Engine ] ──► [ quality_report_before.json ]
                   │
                   ▼ (Stage 3: Pandas / Python ETL Pipeline)
    • Deduplication (Customers, Payments)
    • Missing Value Imputation (Zips, Categories)
    • Datetime Standardisation (ISO-8601)
    • Logistics SLA & Delay Calculation
    • Customer RFM Segmentation
                   │
                   ▼ (Stage 4: Relational Star Schema Loading)
    [ SQLite Data Warehouse: data/warehouse/ecommerce_dw.db ]
         ├── dim_customers  (Surrogate Keys, Geography, RFM)
         ├── dim_products   (Dimensions, Clean Categories)
         ├── dim_sellers    (Location, Seller Key)
         ├── dim_date       (Full Calendar Hierarchy)
         └── fact_orders    (Grain: Order Item, Revenue, Logistics Metrics)
                   │
                   ├──► [ Power BI / Tableau Curated CSV Exports ]
                   └──► [ Stage 6: Interactive Streamlit BI Dashboard ]
    """, language="text")
    
    # Quality comparison
    if QUALITY_BEFORE_PATH.exists() and QUALITY_AFTER_PATH.exists():
        import json
        with open(QUALITY_BEFORE_PATH, "r") as fb, open(QUALITY_AFTER_PATH, "r") as fa:
            b_data = json.load(fb)
            a_data = json.load(fa)
            
        st.markdown("### 📊 Empirical Data Quality Improvements (Before vs After)")
        comp_rows = []
        for tbl in sorted(list(set(b_data.keys()).union(set(a_data.keys())))):
            b = b_data.get(tbl, {})
            a = a_data.get(tbl, {})
            comp_rows.append({
                "Table": tbl,
                "Raw Records": b.get("total_rows", 0),
                "Clean Records": a.get("total_rows", 0),
                "Duplicates Purged": (b.get("exact_duplicates", 0) + b.get("key_duplicates", 0)) - (a.get("exact_duplicates", 0) + a.get("key_duplicates", 0)),
                "Health Score (Before)": f"{b.get('health_score', 0):.1f}%",
                "Health Score (After)": f"{a.get('health_score', 0):.1f}%"
            })
        st.dataframe(pd.DataFrame(comp_rows), use_container_width=True)
    else:
        st.info("Run `python run_pipeline.py` to view live Before/After quality benchmarks.")
