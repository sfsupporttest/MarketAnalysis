import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- 1. THEME & UI CONFIG ---
st.set_page_config(layout="wide", page_title="Market Analyst Elite 2026", page_icon="📈")

st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; color: #1C1C1C; }
    [data-testid="stMetric"] { background-color: #F8F9FB; border: 1px solid #E6E9EF; border-radius: 12px; }
    .ratio-info { font-size: 0.85rem; color: #666; margin-bottom: 5px; }
    .benchmark { color: #007BFF; font-weight: bold; font-size: 0.85rem; }
    div[data-testid="stSidebar"] { background-color: #F0F2F6 !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. ARCHITECTURAL UTILITIES ---
def scale_val(val):
    if val is None or pd.isna(val): return "N/A"
    abs_v = abs(val)
    if abs_v >= 1e9: return f"{val/1e9:.2f}B"
    if abs_v >= 1e6: return f"{val/1e6:.2f}M"
    return f"{val:,.0f}"

RATIO_MAP = {
    "Operating Margin": {"def": "Efficiency: Operating income / Revenue.", "ideal": "> 15%"},
    "Net Margin": {"def": "Profitability: Final profit / Revenue.", "ideal": "> 10%"},
    "ROE": {"def": "Return on Equity: Net Income / Shareholder Equity.", "ideal": "> 15%"},
    "Debt-to-Equity": {"def": "Leverage: Total Debt / Total Equity.", "ideal": "< 1.5"},
    "P/E Ratio": {"def": "Valuation: Price relative to earnings.", "ideal": "15-25x"}
}

# --- 3. DATA ENGINE ---
@st.cache_data(ttl=300)
def get_latest_market_data(symbol):
    ticker = yf.Ticker(symbol)
    return {
        "info": ticker.info,
        "hist": ticker.history(period="2y", interval="1d"),
        "annual_fin": ticker.financials,
        "quart_fin": ticker.quarterly_financials,
        "annual_bs": ticker.balance_sheet,
        "quart_bs": ticker.quarterly_balance_sheet
    }

# --- 4. SIDEBAR & WATCHLIST ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["AAPL", "MSFT", "NVDA", "TSLA"]

with st.sidebar:
    st.title("🏛️ Control Center")
    search = st.text_input("Search Ticker:").upper()
    if st.button("➕ Add to Watchlist") and search:
        if search not in st.session_state.watchlist:
            st.session_state.watchlist.append(search)
    active_ticker = st.selectbox("Active Analysis:", st.session_state.watchlist)

# --- 5. MAIN DASHBOARD ---
try:
    data = get_latest_market_data(active_ticker)
    info = data["info"]
    
    st.title(f"{info.get('longName', active_ticker)}")
    st.caption(f"Status: Live Data as of {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # SECTION 1: PRICE ACTION (CANDLESTICK)
    fig_p = go.Figure(data=[go.Candlestick(
        x=data['hist'].index, open=data['hist']['Open'], 
        high=data['hist']['High'], low=data['hist']['Low'], close=data['hist']['Close']
    )])
    fig_p.update_layout(template="plotly_white", xaxis_rangeslider_visible=True, height=450)
    st.plotly_chart(fig_p, use_container_width=True)

    # SECTION 2: TTM RATIOS
    st.divider()
    st.subheader("🧪 Trailing Twelve Months (TTM) Ratios")
    r1, r2, r3, r4 = st.columns(4)
    
    metrics_list = [
        ("P/E Ratio", info.get("trailingPE")),
        ("Debt-to-Equity", (info.get("debtToEquity", 0) or 0)/100),
        ("ROE", info.get("returnOnEquity")),
        ("Net Margin", info.get("profitMargins"))
    ]
    
    cols = [r1, r2, r3, r4]
    for i, (label, val) in enumerate(metrics_list):
        with cols[i]:
            val_str = f"{val:.2f}" if label in ["P/E Ratio", "Debt-to-Equity"] else f"{val*100:.2f}%"
            st.metric(label, val_str if val else "N/A")
            st.markdown(f"<p class='ratio-info'>{RATIO_MAP[label]['def']}</p>", unsafe_allow_html=True)
            st.markdown(f"<p class='benchmark'>Ideal: {RATIO_MAP[label]['ideal']}</p>", unsafe_allow_html=True)

    # SECTION 3: FUNDAMENTAL ANALYSIS (BAR CHARTS)
    st.divider()
    st.subheader("🏢 Financial Performance (Grouped Bars)")
    freq = st.radio("Frequency:", ["Annual", "Quarterly"], horizontal=True)
    view = st.radio("Mode:", ["Graphical Bar Chart", "Statistical Table"], horizontal=True)
    
    raw_pl = data["annual_fin"] if freq == "Annual" else data["quart_fin"]
    raw_bs = data["annual_bs"] if freq == "Annual" else data["quart_bs"]
    
    tab1, tab2 = st.tabs(["Profit & Loss", "Balance Sheet"])

    with tab1:
        if not raw_pl.empty:
            df_pl = raw_pl.loc[['Total Revenue', 'Net Income']].T
            # Force string index for clean X-axis
            df_pl.index = df_pl.index.strftime('%b %Y')
            
            if view == "Graphical Bar Chart":
                fig_pl = go.Figure()
                fig_pl.add_trace(go.Bar(x=df_pl.index, y=df_pl['Total Revenue'], name='Revenue', marker_color='#1f77b4'))
                fig_pl.add_trace(go.Bar(x=df_pl.index, y=df_pl['Net Income'], name='Net Income', marker_color='#2ca02c'))
                fig_pl.update_layout(template="plotly_white", barmode='group', xaxis_type='category', yaxis_title="USD")
                st.plotly_chart(fig_pl, use_container_width=True)
            else:
                st.dataframe(df_pl.map(scale_val), use_container_width=True)
        else:
            st.info("No P&L data available.")

    with tab2:
        if not raw_bs.empty:
            df_bs = raw_bs.loc[['Total Assets', 'Total Liabilities Net Minority Interest']].T
            df_bs.index = df_bs.index.strftime('%b %Y')
            
            if view == "Graphical Bar Chart":
                fig_bs = go.Figure()
                fig_bs.add_trace(go.Bar(x=df_bs.index, y=df_bs['Total Assets'], name='Assets', marker_color='#17becf'))
                fig_bs.add_trace(go.Bar(x=df_bs.index, y=df_bs['Total Liabilities Net Minority Interest'], name='Liabilities', marker_color='#d62728'))
                fig_bs.update_layout(template="plotly_white", barmode='group', xaxis_type='category', yaxis_title="USD")
                st.plotly_chart(fig_bs, use_container_width=True)
            else:
                st.dataframe(df_bs.map(scale_val), use_container_width=True)
        else:
            st.info("No Balance Sheet data available.")

    # SECTION 4: RATIO TRENDS
    st.divider()
    st.subheader("⏳ Historical Ratio Trends")
    target_trend = st.selectbox("Select Ratio to Analyze:", list(RATIO_MAP.keys()))
    
    # Using quarterly financials for trend density
    fin_t = data["quart_fin"].T
    if not fin_t.empty and 'Total Revenue' in fin_t.columns:
        if target_trend == "Net Margin":
            y_data = (fin_t['Net Income'] / fin_t['Total Revenue']) * 100
            label = "Margin %"
        else:
            y_data = fin_t['Total Revenue'].pct_change(periods=-1) * 100
            label = "Growth %"
        
        # Sort values so oldest is left, newest is right
        fin_t = fin_t.sort_index(ascending=True)
        x_dates = fin_t.index.strftime('%b %Y')
            
        fig_trend = go.Figure(go.Scatter(x=x_dates, y=y_data, mode='lines+markers', line=dict(color='#ff7f0e', width=4)))
        fig_trend.update_layout(template="plotly_white", title=f"{target_trend} Trend", yaxis_title=label, xaxis={'categoryorder':'trace'})
        st.plotly_chart(fig_trend, use_container_width=True)

except Exception as e:
    st.error(f"Execution Error: {e}")
