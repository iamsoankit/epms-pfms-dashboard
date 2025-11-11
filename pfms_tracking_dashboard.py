import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# --- Configuration ---
# You need to ensure the CSV files are in the same directory as this script.
RELEASED_FILE = "book1.xlsx - Released by pfms .csv"
PENDING_FILE = "book1.xlsx - Pending by PFMS.csv"

# Columns identified for the dashboard
RELEASED_COL = 'Credited Amount'
PENDING_COL = 'Vetting Amount (in INR)'
GROUPING_COL = 'Division-1'

st.set_page_config(layout="wide", page_title="PFMS Release vs. Pending Analysis")

# --- Data Loading and Cleaning Function ---
@st.cache_data
def load_data():
    """Loads and cleans the Released and Pending data."""
    try:
        df_released = pd.read_csv(RELEASED_FILE)
        df_pending = pd.read_csv(PENDING_FILE)

        # 1. Clean and standardize amount columns
        for df, col in [(df_released, RELEASED_COL), (df_pending, PENDING_COL)]:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # 2. Add a status column for merging
        df_released['Status'] = 'Released'
        df_pending['Status'] = 'Pending'

        # 3. Rename pending column to match released for consolidation
        df_pending = df_pending.rename(columns={PENDING_COL: RELEASED_COL})

        # 4. Consolidate into a single DataFrame for charting
        df_all = pd.concat([
            df_released[[GROUPING_COL, RELEASED_COL, 'Status']],
            df_pending[[GROUPING_COL, RELEASED_COL, 'Status']]
        ], ignore_index=True)

        return df_released, df_pending, df_all

    except FileNotFoundError as e:
        st.error(f"Error: Required file not found. Please ensure both CSV files are in the current folder. Missing file: {e.filename}")
        st.stop()
    except Exception as e:
        st.error(f"An error occurred during data processing: {e}")
        st.stop()


df_released, df_pending, df_all = load_data()


# --- Dashboard Layout ---

st.title("💰 PFMS Financial Status Dashboard")
st.markdown("Comparing the financial distribution of projects based on their **Released** and **Pending** status.")


# 1. KPI Section
col1, col2 = st.columns(2)

total_released = df_released[RELEASED_COL].sum()
total_pending = df_pending[RELEASED_COL].sum() # Using the renamed column

col1.metric(
    label="Total Released Amount",
    value=f"₹ {total_released:,.2f}",
    help="Sum of 'Credited Amount' in the Released file."
)

col2.metric(
    label="Total Pending Amount",
    value=f"₹ {total_pending:,.2f}",
    help="Sum of 'Vetting Amount (in INR)' in the Pending file."
)

st.markdown("---")

# 2. Comparative Analysis Chart
st.header("Comparative Analysis by Division")
st.markdown(f"**Released vs. Pending Amounts broken down by {GROUPING_COL}.**")

# Calculate the combined total for sorting
df_agg_total = df_all.groupby(GROUPING_COL)[RELEASED_COL].sum().sort_values(ascending=False)

# Get top 10 divisions
top_10_divisions = df_agg_total.head(10).index.tolist()
df_top_10 = df_all[df_all[GROUPING_COL].isin(top_10_divisions)]

# Aggregate for the plot
df_chart_data = df_top_10.groupby([GROUPING_COL, 'Status'])[RELEASED_COL].sum().reset_index()

# Plotting with Plotly
fig = px.bar(
    df_chart_data,
    x=GROUPING_COL,
    y=RELEASED_COL,
    color='Status',
    title=f"Top 10 Divisions: Released vs. Pending Amount",
    labels={
        RELEASED_COL: "Amount (in INR)",
        GROUPING_COL: GROUPING_COL
    },
    barmode='group'
)

# Sort the x-axis by the total aggregated amount
order_map = {div: i for i, div in enumerate(top_10_divisions)}
fig.update_xaxes(categoryorder='array', categoryarray=top_10_divisions)

fig.update_layout(hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# 3. Raw Data Tables
st.header("Raw Data View")

# Create tabs for switching between the raw dataframes
tab1, tab2 = st.tabs(["Released by PFMS", "Pending by PFMS"])

with tab1:
    st.subheader("Released Data (`Credited Amount`)")
    st.dataframe(df_released)

with tab2:
    st.subheader("Pending Data (`Vetting Amount in INR`)")
    st.dataframe(df_pending)
