import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- 1. THEME & UI CONFIG (LIGHT MODE) ---
st.set_page_config(layout="wide", page_title="Market Analyst Elite", page_icon="📈")

st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; color: #1C1C1C; }
    [data-testid="stMetric"] { 
        background-color: #F8F9FB; 
        border: 1px solid #E6E9EF; 
        border-radius: 12px; 
    }
    div[data-testid="stSidebar"] { background-color: #F0F2F6 !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATA LAYER & CACHING ---
@st.cache_data
def get_ticker_db():
    return ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "BRK-B", "VOO", "SPY", "QQQ", "AMD", "NFLX", "DIS"]

@st.cache_resource
def get_ticker_obj(symbol):
    return yf.Ticker(symbol)

@st.cache_data
def get_ticker_info(symbol):
    return yf.Ticker(symbol).info

# --- 3. SIDEBAR NAVIGATION ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["AAPL", "VOO", "NVDA"]

with st.sidebar:
    st.title("🏛️ Control Center")
    search_input = st.text_input("Search Ticker:", placeholder="e.g. NVD").upper()
    
    suggestions = [t for t in get_ticker_db() if t.startswith(search_input)] if len(search_input) >= 3 else []
    
    if suggestions:
        selected_search = st.selectbox("Suggestions Found:", suggestions)
    else:
        selected_search = search_input if len(search_input) >= 3 else None

    if st.button("➕ Add to Watchlist") and selected_search:
        if selected_search not in st.session_state.watchlist:
            st.session_state.watchlist.append(selected_search)
    
    st.divider()
    active_ticker = st.selectbox("Active Analysis:", st.session_state.watchlist)

# --- 4. MAIN DASHBOARD ---
try:
    ticker_obj = get_ticker_obj(active_ticker)
    info = get_ticker_info(active_ticker)
    
    st.title(f"{info.get('longName', active_ticker)}")
    
    # --- WIDGET A: INTERACTIVE CANDLESTICK (TIME SCALING) ---
    st.subheader("Price Action")
    hist = ticker_obj.history(period="2y") # Fetch 2 years to allow narrowing
    
    fig_price = go.Figure(data=[go.Candlestick(
        x=hist.index,
        open=hist['Open'],
        high=hist['High'],
        low=hist['Low'],
        close=hist['Close'],
        name="Price"
    )])
    
    fig_price.update_layout(
        template="plotly_white",
        xaxis_rangeslider_visible=True, # Allows expanding/narrowing timeline
        height=500,
        margin=dict(l=0, r=0, t=0, b=0)
    )
    st.plotly_chart(fig_price, use_container_width=True)

    # --- WIDGET B: RATIOS ---
    st.divider()
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("P/E Ratio", f"{info.get('trailingPE', 'N/A')}")
    r2.metric("PEG Ratio", f"{info.get('pegRatio', 'N/A')}")
    r3.metric("Current Ratio", f"{info.get('currentRatio', 'N/A')}")
    r4.metric("ROE", f"{info.get('returnOnEquity', 'N/A')}")

    # --- WIDGET C: FINANCIALS (ANNUAL vs QUARTERLY) ---
    st.divider()
    st.subheader("🏢 Financial Deep-Dive")
    
    col_ctrl1, col_ctrl2 = st.columns([1, 1])
    with col_ctrl1:
        freq = st.segmented_control("Report Frequency:", ["Annual", "Quarterly"], default="Annual")
    with col_ctrl2:
        view_mode = st.radio("Display Type:", ["Graphical Mode", "Statistical Mode"], horizontal=True)

    tab1, tab2 = st.tabs(["Profit & Loss", "Balance Sheet"])

    with tab1:
        # Toggle logic for frequency
        pl = ticker_obj.financials if freq == "Annual" else ticker_obj.quarterly_financials
        
        if not pl.empty:
            pl_data = pl.loc[['Total Revenue', 'Net Income']].T
            # Format index to show Date/Year clearly
            pl_data.index = pl_data.index.strftime('%Y-%m-%d') if freq == "Quarterly" else pl_data.index.year

            if view_mode == "Graphical Mode":
                fig_pl = go.Figure()
                fig_pl.add_trace(go.Bar(x=pl_data.index, y=pl_data['Total Revenue'], name='Revenue', marker_color='#1f77b4'))
                fig_pl.add_trace(go.Bar(x=pl_data.index, y=pl_data['Net Income'], name='Net Income', marker_color='#2ca02c'))
                fig_pl.update_layout(template="plotly_white", barmode='group', height=400)
                st.plotly_chart(fig_pl, use_container_width=True)
            else:
                st.dataframe(pl_data.style.format("{:,.0f}"), use_container_width=True)
        else:
            st.info("Income Statement not available for this frequency.")

    with tab2:
        bs = ticker_obj.balance_sheet if freq == "Annual" else ticker_obj.quarterly_balance_sheet
        
        if not bs.empty:
            bs_data = bs.loc[['Total Assets', 'Total Liabilities Net Minority Interest']].T
            bs_data.index = bs_data.index.strftime('%Y-%m-%d') if freq == "Quarterly" else bs_data.index.year

            if view_mode == "Graphical Mode":
                fig_bs = go.Figure()
                fig_bs.add_trace(go.Bar(x=bs_data.index, y=bs_data['Total Assets'], name='Assets', marker_color='#17becf'))
                fig_bs.add_trace(go.Bar(x=bs_data.index, y=bs_data['Total Liabilities Net Minority Interest'], name='Liabilities', marker_color='#d62728'))
                fig_bs.update_layout(template="plotly_white", barmode='group', height=400)
                st.plotly_chart(fig_bs, use_container_width=True)
            else:
                st.dataframe(bs_data.style.format("{:,.0f}"), use_container_width=True)
        else:
            st.info("Balance Sheet data not found for this frequency.")

except Exception as e:
    st.error(f"Dashboard Load Error: {e}")