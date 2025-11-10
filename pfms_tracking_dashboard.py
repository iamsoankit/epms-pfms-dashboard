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
# This method is more stable for handling sheets with complex formatting/merged cells.
DATA_URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={GID}'

# Column Mapping from Original Sheet Headers to Clean Names
# NOTE: This mapping must exactly match the headers in your Google Sheet (Row 1).
CLEAN_COLUMN_NAMES = {
    'SNo': 'SNo',
    'Investigator': 'Investigator',
    'Institute Name-1': 'Institute_Name',
    'Division-1': 'Division',
    'Programme/Scheme': 'Programme_Scheme',
    'Project Type': 'Project_Type',
    'Umbrella Scheme': 'Umbrella_Scheme',
    'Budget Type': 'Budget_Type',
    'DSO-1': 'DSO',
    # Key Financial Columns
    'Vetting Amount (in INR)': 'Vetting_Amount_INR',
    'Credite Amout': 'Released_Amount_INR'
}

# Key columns used for filtering and visualization
FINANCIAL_COLS = ['Vetting_Amount_INR', 'Released_Amount_INR']

# Currency and Scaling Constants (Crore = 10,000,000)
CRORE_FACTOR = 10000000 
CURRENCY_LABEL = "INR (Cr)" 

# Define Status Colors (Used in KPIs and Charts)
COLOR_VETTING = '#ffc72c'  # Yellow (KPI Header/Vetting)
COLOR_RELEASED = '#1f77b4' # Blue (Released by PFMS)
COLOR_PENDING = '#ff0000'  # Red (Pending for PFMS)


# --- Data Loading and Preprocessing ---

@st.cache_data(ttl=60)
def load_and_clean_data(url):
    """
    Loads data directly from the robust Google Sheets GViz endpoint, ensuring clean CSV output.
    """
    try:
        # 1. Use requests to get the content
        # The GViz endpoint is very reliable for public CSV output.
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


# --- Sidebar Filters (Cascading Filters) ---
st.sidebar.header("Filter Data")
st.sidebar.info("Use the filters below to narrow down the data scope.")

df_filtered = df.copy()

# 1. DSO Filter (Highest level of grouping)
selected_dso = st.sidebar.selectbox("Select DSO:", 
    options=['All DSO'] + sorted(df_filtered['DSO'].astype(str).unique().tolist())
)
if selected_dso != 'All DSO':
    df_filtered = df_filtered[df_filtered['DSO'] == selected_dso]

# 2. Division Filter (Depends on DSO)
df_for_div = df_filtered.copy()
selected_division = st.sidebar.selectbox("Select Division:", 
    options=['All Divisions'] + sorted(df_for_div['Division'].astype(str).unique().tolist())
)
if selected_division != 'All Divisions':
    df_filtered = df_filtered[df_filtered['Division'] == selected_division]

# 3. Programme/Scheme Filter (Depends on Division)
df_for_scheme = df_filtered.copy()
selected_scheme = st.sidebar.selectbox("Select Programme/Scheme:", 
    options=['All Schemes'] + sorted(df_for_scheme['Programme_Scheme'].astype(str).unique().tolist())
)
if selected_scheme != 'All Schemes':
    df_filtered = df_filtered[df_filtered['Programme_Scheme'] == selected_scheme]


# --- Calculate Main KPIs on Filtered Data ---
total_vetting = df_filtered['Vetting_Amount_INR'].sum()
total_released = df_filtered['Released_Amount_INR'].sum()
total_pending = df_filtered['Pending_Amount_INR'].sum()

# Scale to Crores
vetting_cr = total_vetting / CRORE_FACTOR
released_cr = total_released / CRORE_FACTOR
pending_cr = total_pending / CRORE_FACTOR

# Calculate Rates
release_rate = (total_released / total_vetting) * 100 if total_vetting != 0 else 0
pending_rate = (total_pending / total_vetting) * 100 if total_vetting != 0 else 0


# --- KPI Row (Custom styling for Yellow, Blue, Red indicators) ---
st.header("Key Performance Indicators (KPIs)")
st.markdown("The amounts below reflect the total for the selected filters, scaled to Crores INR.")

col1, col2, col3, col4 = st.columns(4)

# KPI 1: Total Vetting Amount (Yellow)
col1.markdown(f"""
    <div style="background-color: {COLOR_VETTING}; padding: 10px; border-radius: 8px; text-align: center; color: black; font-weight: bold; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);">
        <p style='margin: 0; font-size: 14px;'>Total Vetting Amount</p>
        <p style='margin: 0; font-size: 24px;'>₹{vetting_cr:,.2f} {CURRENCY_LABEL}</p>
    </div>
    """, unsafe_allow_html=True)

# KPI 2: Released by PFMS (Blue)
col2.markdown(f"""
    <div style="background-color: {COLOR_RELEASED}; padding: 10px; border-radius: 8px; text-align: center; color: white; font-weight: bold; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);">
        <p style='margin: 0; font-size: 14px;'>Released by PFMS (Blue Filter)</p>
        <p style='margin: 0; font-size: 24px;'>₹{released_cr:,.2f} {CURRENCY_LABEL}</p>
    </div>
    """, unsafe_allow_html=True)

# KPI 3: Pending for PFMS (Red)
col3.markdown(f"""
    <div style="background-color: {COLOR_PENDING}; padding: 10px; border-radius: 8px; text-align: center; color: white; font-weight: bold; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);">
        <p style='margin: 0; font-size: 14px;'>Pending for PFMS (Red Filter)</p>
        <p style='margin: 0; font-size: 24px;'>₹{pending_cr:,.2f} {CURRENCY_LABEL}</p>
    </div>
    """, unsafe_allow_html=True)

# KPI 4: Release Rate (Uses Streamlit's built-in metric component for comparison)
col4.metric("PFMS Release Rate", f"{release_rate:,.2f}%", delta=f"Pending: {pending_rate:,.2f}%")


st.markdown("---")


# --- Main Visualizations ---
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
            color_discrete_map={'Released': COLOR_RELEASEED, 'Pending': COLOR_PENDING},
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
