import streamlit as st
import pandas as pd
import plotly.express as px
import os
import requests 
from io import StringIO

# --- Configuration and Constants ---

# GOOGLE SHEET CONFIGURATION 
SHEET_ID = '16z_vMVAmUfQz6rta9Xk62gqlTdUqKVAtjp1HDQmC-x4'
# GID for the "Sheet4 (2)" tab
GID = '34645063' 

# Construct the public CSV export URL using the GViz Query endpoint
DATA_URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={GID}'

# Column Mapping from Original Sheet Headers to Clean Names
# UPDATED MAPPING BASED ON NEW KPI/FILTER REQUIREMENTS
CLEAN_COLUMN_NAMES = {
    'SNo': 'SNo',
    'Investigator': 'Investigator',
    'Institute Name-1': 'Institute_Name',
    'Division-1': 'Division',
    'Programme/Scheme': 'Programme_Scheme',
    'Umbrella Scheme': 'Umbrella_Scheme',
    
    # NEW KPI & FILTER COLUMNS
    'Sanction File No.-1': 'Sanction_File_No',
    'Budget Head-1': 'Budget_Head',
    'Diary No.(General/Capital/Salary)-1': 'Diary_No',
    'DSO-1': 'DSO',
    'Project Type': 'Project_Type',
    'Budget Type': 'Budget', # Renamed from 'Budget Type' to 'Budget' for consistency with request
    
    # Key Financial Columns (Retained)
    'Vetting Amount (in INR)': 'Vetting_Amount_INR',
    'Credite Amout': 'Released_Amount_INR'
}

# Key columns used for filtering and visualization
FINANCIAL_COLS = ['Vetting_Amount_INR', 'Released_Amount_INR']
KPI_COUNT_COLS = ['Sanction_File_No', 'Budget_Head', 'Diary_No'] # Columns to count

# Currency and Scaling Constants (Crore = 10,000,000)
CRORE_FACTOR = 10000000 
CURRENCY_LABEL = "INR (Cr)" 

# Define Status Colors (Used in KPIs and Charts)
COLOR_VETTING = '#ffc72c'  # Yellow (Vetting/KPI Header)
COLOR_RELEASED = '#1f77b4' # Blue (Released by PFMS)
COLOR_PENDING = '#ff0000'  # Red (Pending for PFMS)
COLOR_COUNT = '#6C757D'    # Gray/Count Color


# --- Data Loading and Preprocessing ---

@st.cache_data(ttl=60)
def load_and_clean_data(url):
    """
    Loads data directly from the robust Google Sheets GViz endpoint, ensuring clean CSV output.
    """
    try:
        # 1. Use requests to get the content
        response = requests.get(url)
        response.raise_for_status() 
        
        # 2. Read the content string into pandas as a CSV
        df = pd.read_csv(StringIO(response.text))
        
        # Rename columns using the mapping
        df = df.rename(columns=CLEAN_COLUMN_NAMES, errors='ignore')
        
        # Select only the necessary columns for the dashboard
        required_cols = list(CLEAN_COLUMN_NAMES.values())
        df = df.filter(items=required_cols)

        # Clean numeric columns (Remove non-digits and convert)
        for col in FINANCIAL_COLS:
            if col in df.columns:
                # Remove non-digits and convert to numeric
                df[col] = df[col].astype(str).str.replace(r'[^\d.]', '', regex=True)
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Calculate the derived "Pending" amount
        if 'Vetting_Amount_INR' in df.columns and 'Released_Amount_INR' in df.columns:
            df['Pending_Amount_INR'] = df['Vetting_Amount_INR'] - df['Released_Amount_INR']
        else:
            st.error("Financial columns (Vetting/Released) not found after renaming. Please check the `CLEAN_COLUMN_NAMES` map.")
            return pd.DataFrame()
            
        # Ensure count columns are strings for consistent filtering/counting
        for col in KPI_COUNT_COLS + ['DSO', 'Project_Type', 'Budget']:
             if col in df.columns:
                df[col] = df[col].astype(str)

        st.sidebar.success("Data loaded successfully from Google Sheet URL (Refreshed every 60s).")
        return df

    except requests.exceptions.RequestException as e:
        # Specifically handle request errors
        st.error(f"Failed to fetch data from Google Sheet. Please double-check the sheet URL/GID and ensure it is shared publicly. Error: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"An unexpected error occurred during data processing. Error: {e}")
        return pd.DataFrame()


# --- Load Data and Handle Failure ---
df = load_and_clean_data(DATA_URL)

if df.empty:
    st.stop() 


# --- Page Configuration and Layout ---
st.set_page_config(layout="wide", initial_sidebar_state="expanded", page_title="PFMS Release & Pending Status")
st.title("💸 EPMS vs PFMS Release & Pending Status Dashboard")
st.markdown("---")


# --- Sidebar Filters (Cascading Filters - UPDATED) ---
st.sidebar.header("Filter Data")
st.sidebar.info("Use the filters below to narrow down the data scope.")

df_filtered = df.copy()

# 1. DSO Filter (Highest level of grouping)
selected_dso = st.sidebar.selectbox("Select DSO:", 
    options=['All DSO'] + sorted(df_filtered['DSO'].astype(str).unique().tolist())
)
if selected_dso != 'All DSO':
    df_filtered = df_filtered[df_filtered['DSO'] == selected_dso]

# 2. Project Type Filter (Depends on DSO)
df_for_project = df_filtered.copy()
selected_project_type = st.sidebar.selectbox("Select Project Type:", 
    options=['All Project Types'] + sorted(df_for_project['Project_Type'].astype(str).unique().tolist())
)
if selected_project_type != 'All Project Types':
    df_filtered = df_filtered[df_filtered['Project_Type'] == selected_project_type]

# 3. Budget Filter (Depends on Project Type)
df_for_budget = df_filtered.copy()
selected_budget = st.sidebar.selectbox("Select Budget:", 
    options=['All Budgets'] + sorted(df_for_budget['Budget'].astype(str).unique().tolist())
)
if selected_budget != 'All Budgets':
    df_filtered = df_filtered[df_filtered['Budget'] == selected_budget]

# --- Calculation of New KPIs on Filtered Data ---
total_vetting = df_filtered['Vetting_Amount_INR'].sum()
total_released = df_filtered['Released_Amount_INR'].sum()
total_pending = df_filtered['Pending_Amount_INR'].sum()

# New Count KPIs (Unique non-empty values)
count_sanction_file = df_filtered['Sanction_File_No'].nunique()
count_budget_head = df_filtered['Budget_Head'].nunique()
count_diary_no = df_filtered['Diary_No'].nunique()

# Scale to Crores
vetting_cr = total_vetting / CRORE_FACTOR
released_cr = total_released / CRORE_FACTOR
pending_cr = total_pending / CRORE_FACTOR

# Calculate Rates
release_rate = (total_released / total_vetting) * 100 if total_vetting != 0 else 0
pending_rate = (total_pending / total_vetting) * 100 if total_vetting != 0 else 0


# --- KPI Row (Custom styling for Yellow, Blue, Red indicators - UPDATED) ---
st.header("Key Performance Indicators (KPIs)")
st.markdown("The amounts below reflect the total for the selected filters, scaled to Crores INR.")

# Split into 3 columns for Financial/Rate KPIs and 3 for Count KPIs
col1, col2, col3 = st.columns(3)

# FINANCIAL KPIs (Your Primary Metrics)
col1.markdown(f"""
    <div style="background-color: {COLOR_VETTING}; padding: 10px; border-radius: 8px; text-align: center; color: black; font-weight: bold; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);">
        <p style='margin: 0; font-size: 14px;'>Total Vetting Amount</p>
        <p style='margin: 0; font-size: 24px;'>₹{vetting_cr:,.2f} {CURRENCY_LABEL}</p>
    </div>
    """, unsafe_allow_html=True)

col2.markdown(f"""
    <div style="background-color: {COLOR_RELEASED}; padding: 10px; border-radius: 8px; text-align: center; color: white; font-weight: bold; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);">
        <p style='margin: 0; font-size: 14px;'>Released by PFMS (Blue)</p>
        <p style='margin: 0; font-size: 24px;'>₹{released_cr:,.2f} {CURRENCY_LABEL}</p>
    </div>
    """, unsafe_allow_html=True)

col3.markdown(f"""
    <div style="background-color: {COLOR_PENDING}; padding: 10px; border-radius: 8px; text-align: center; color: white; font-weight: bold; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);">
        <p style='margin: 0; font-size: 14px;'>Pending for PFMS (Red)</p>
        <p style='margin: 0; font-size: 24px;'>₹{pending_cr:,.2f} {CURRENCY_LABEL}</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# COUNT KPIs (The remaining 3 metrics)
st.subheader("Document Counts (Unique Items)")
col4, col5, col6 = st.columns(3)

col4.metric(
    "Sanction File No. Count",
    f"{count_sanction_file:,}",
    delta_color="off"
)
col5.metric(
    "Budget Head Count",
    f"{count_budget_head:,}",
    delta_color="off"
)
col6.metric(
    "Diary No. Count",
    f"{count_diary_no:,}",
    delta_color="off"
)

st.markdown("---")


# --- Main Visualizations (Retaining Division and Scheme charts) ---
col_vis1, col_vis2 = st.columns(2)

if df_filtered.empty:
    st.info("No data available for the selected filters to display charts.")
else:
    # --- Visualization 1: Release vs Pending by Division ---
    with col_vis1:
        st.subheader("1. Release & Pending Status by Division")
        
        # Aggregate by Division and scale
        div_summary = df_filtered.groupby('Division').agg(
            Released=('Released_Amount_INR', 'sum'),
            Pending=('Pending_Amount_INR', 'sum')
        ).reset_index()
        
        div_summary['Released'] /= CRORE_FACTOR
        div_summary['Pending'] /= CRORE_FACTOR

        # Melt the data for Plotly stacking
        div_melted = div_summary.melt(id_vars='Division', 
                                      value_vars=['Released', 'Pending'],
                                      var_name='Status',
                                      value_name=f'Amount ({CURRENCY_LABEL})')
        
        fig1 = px.bar(
            div_melted,
            x=f'Amount ({CURRENCY_LABEL})',
            y='Division',
            color='Status',
            orientation='h',
            title=f"Released vs. Pending Amounts by Division",
            color_discrete_map={'Released': COLOR_RELEASED, 'Pending': COLOR_PENDING},
            template="plotly_white",
            height=500
        )
        
        fig1.update_layout(
            barmode='stack', 
            yaxis={'categoryorder':'total ascending', 'title': {'text': 'Division', 'font': {'size': 14, 'weight': 'bold'}}},
            xaxis={'title': {'text': f'Amount ({CURRENCY_LABEL})', 'font': {'size': 14, 'weight': 'bold'}}},
            title_font={'size': 16, 'weight': 'bold'},
            font={'size': 12}
        )
        st.plotly_chart(fig1, use_container_width=True)


    # --- Visualization 2: Vetting Amount Distribution by Programme/Scheme (Pie Chart) ---
    with col_vis2:
        st.subheader("2. Vetting Amount Distribution by Scheme")
        
        scheme_summary = df_filtered.groupby('Programme_Scheme')['Vetting_Amount_INR'].sum().reset_index()
        scheme_summary['Vetting_Amount_INR'] /= CRORE_FACTOR
        
        fig2 = px.pie(
            scheme_summary,
            names='Programme_Scheme',
            values='Vetting_Amount_INR',
            title='Percentage of Total Vetting Amount by Programme/Scheme',
            hole=0.4, # Donut chart style
            template="plotly_white",
            color_discrete_sequence=px.colors.sequential.Plasma,
            labels={'Vetting_Amount_INR': f'Vetting Amount ({CURRENCY_LABEL})'}
        )
        fig2.update_traces(hovertemplate='%{label}<br>Amount: %{value:,.2f} Cr<br>Share: %{percent}<extra></extra>')
        fig2.update_layout(
            height=500, 
            showlegend=True, 
            margin=dict(t=50, b=0, l=0, r=0),
            title_font={'size': 16, 'weight': 'bold'},
            font={'size': 12}
        )
        st.plotly_chart(fig2, use_container_width=True)


# --- Detailed Data Table ---
st.markdown("---")
with st.expander("📋 Click to View Detailed Filtered Data", expanded=False):
    st.subheader("Filtered Transaction Data")
    
    df_display = df_filtered.copy()
    
    # Scale and rename financial columns for display
    df_display[f'Vetting Amount ({CURRENCY_LABEL})'] = df_display['Vetting_Amount_INR'] / CRORE_FACTOR
    df_display[f'Released Amount (BLUE, {CURRENCY_LABEL})'] = df_display['Released_Amount_INR'] / CRORE_FACTOR
    df_display[f'Pending Amount (RED, {CURRENCY_LABEL})'] = df_display['Pending_Amount_INR'] / CRORE_FACTOR

    # Drop the original unscaled columns
    df_display = df_display.drop(columns=FINANCIAL_COLS + ['Pending_Amount_INR'], errors='ignore')

    st.dataframe(df_display, use_container_width=True)
