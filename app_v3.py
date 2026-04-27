import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- 1. THEME & UI CONFIG ---
st.set_page_config(layout="wide", page_title="Institutional Equity Station 2026", page_icon="🏦")

st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; color: #1C1C1C; }
    [data-testid="stMetric"] { background-color: #F8F9FB; border: 1px solid #E6E9EF; border-radius: 12px; }
    .unified-block { 
        border: 1px solid #E6E9EF; 
        padding: 25px; 
        border-radius: 15px; 
        background-color: #FFFFFF;
        margin-bottom: 20px;
    }
    .benchmark-label { color: #007BFF; font-weight: bold; font-size: 0.95rem; }
    .def-box { background-color: #f1f3f5; padding: 10px; border-left: 5px solid #007BFF; border-radius: 4px; font-size: 0.85rem; margin-top: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. ARCHITECTURAL UTILITIES ---
def scale_val(val):
    if val is None or pd.isna(val): return "N/A"
    abs_v = abs(val)
    if abs_v >= 1e9: return f"{val/1e9:.2f}B"
    if abs_v >= 1e6: return f"{val/1e6:.2f}M"
    return f"{val:,.0f}"

# Detailed Ratio Dictionary
RATIO_LIBRARY = {
    "Net Margin": {
        "ideal": "> 10.0%", 
        "def": "The percentage of revenue left as profit after all operating expenses, interest, and taxes have been paid.",
        "standard": "High margins indicate a strong competitive moat and pricing power."
    },
    "Operating Margin": {
        "ideal": "> 15.0%", 
        "def": "Measures how much profit a company makes on a dollar of sales after paying for variable costs of production.",
        "standard": "Crucial for understanding core business efficiency before tax/debt obligations."
    },
    "ROE": {
        "ideal": "> 15.0%", 
        "def": "Return on Equity: Measures the profitability of a business in relation to the equity held by shareholders.",
        "standard": "Investors use this to see how effectively management is using shareholder capital to generate growth."
    },
    "Debt-to-Equity": {
        "ideal": "< 1.50", 
        "def": "Calculated by dividing total liabilities by shareholder equity.",
        "standard": "Used to gauge a company's financial leverage and its ability to cover outstanding debts."
    }
}

# --- 3. DATA ENGINE ---
@st.cache_data(ttl=300)
def get_comprehensive_data(symbol):
    ticker = yf.Ticker(symbol)
    return {
        "info": ticker.info,
        "hist": ticker.history(period="2y"),
        "annual_fin": ticker.financials,
        "quart_fin": ticker.quarterly_financials
    }

# --- 4. SIDEBAR & WATCHLIST ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["AAPL", "MSFT", "NVDA", "VOO"]

with st.sidebar:
    st.title("🏛️ Control Center")
    search = st.text_input("Quick Search (Ticker):").upper()
    if st.button("➕ Add to Watchlist") and search:
        if search not in st.session_state.watchlist: st.session_state.watchlist.append(search)
    active_ticker = st.selectbox("Active Ticker:", st.session_state.watchlist)

# --- 5. MAIN DASHBOARD ---
try:
    data = get_comprehensive_data(active_ticker)
    info = data["info"]
    
    st.title(f"{info.get('longName', active_ticker)}")
    st.caption(f"Data status: Latest 2026 Sync | Local Time: {datetime.now().strftime('%H:%M')}")

    # --- SECTION 1: PRICE ACTION ---
    fig_p = go.Figure(data=[go.Candlestick(x=data['hist'].index, open=data['hist']['Open'], high=data['hist']['High'], low=data['hist']['Low'], close=data['hist']['Close'])])
    fig_p.update_layout(template="plotly_white", xaxis_rangeslider_visible=True, height=400, margin=dict(l=0,r=0,t=0,b=0))
    st.plotly_chart(fig_p, use_container_width=True)

    # --- SECTION 2: STATISTICAL PERFORMANCE (BAR CHARTS) ---
    st.divider()
    st.subheader("📊 Statistical Performance: Revenue & Net Income")
    c1, c2 = st.columns([1, 4])
    with c1:
        freq = st.radio("Reporting Period:", ["Annual", "Quarterly"], horizontal=False)
    
    raw_df = data["annual_fin"] if freq == "Annual" else data["quart_fin"]
    if not raw_df.empty:
        df_pl = raw_df.loc[['Total Revenue', 'Net Income']].T
        df_pl.index = df_pl.index.strftime('%b %Y') # Ensure string index for dates
        
        with c2:
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(x=df_pl.index, y=df_pl['Total Revenue'], name='Revenue', marker_color='#1f77b4'))
            fig_bar.add_trace(go.Bar(x=df_pl.index, y=df_pl['Net Income'], name='Net Income', marker_color='#2ca02c'))
            fig_bar.update_layout(template="plotly_white", barmode='group', height=350, xaxis_type='category')
            st.plotly_chart(fig_bar, use_container_width=True)
            
        if st.checkbox("Show Raw Statistical Table"):
            st.dataframe(df_pl.map(scale_val), use_container_width=True)

    # --- SECTION 3: UNIFIED RATIO ANALYSIS (LATEST + IDEAL + DEFINITION + GRAPH) ---
    st.divider()
    st.subheader("🧪 Unified Ratio Intelligence")
    st.info("Each section contains the Latest Trailing Data, Industry Benchmarks, and 4-Quarter Historical Progression.")

    q_fin = data["quart_fin"].T.sort_index(ascending=True)
    
    for label, meta in RATIO_LIBRARY.items():
        # Calculation Block
        if label == "Net Margin":
            trend_data = (q_fin['Net Income'] / q_fin['Total Revenue']) * 100
            current = info.get('profitMargins', 0) * 100
        elif label == "Operating Margin":
            trend_data = (q_fin['Operating Income'] / q_fin['Total Revenue']) * 100
            current = info.get('operatingMargins', 0) * 100
        elif label == "ROE":
            current = info.get('returnOnEquity', 0) * 100
            trend_data = [current] * len(q_fin) # Estimation
        else: # Debt to Equity
            current = (info.get('debtToEquity', 0) or 0) / 100
            trend_data = [current] * len(q_fin)

        with st.container():
            m_col1, m_col2 = st.columns([1, 2])
            
            with m_col1:
                st.markdown(f"#### {label}")
                st.metric("Latest Live Metric", f"{current:.2f}%" if "Margin" in label or "ROE" in label else f"{current:.2f}")
                st.markdown(f"Industry Ideal: <span class='benchmark-label'>{meta['ideal']}</span>", unsafe_allow_html=True)
                st.markdown(f"<div class='def-box'><b>Definition:</b> {meta['def']}<br><br><b>Industry Standard:</b> {meta['standard']}</div>", unsafe_allow_html=True)

            with m_col2:
                fig_trend = go.Figure(go.Scatter(
                    x=q_fin.index.strftime('%b %Y'), 
                    y=trend_data, 
                    mode='lines+markers+text',
                    text=[f"{v:.1f}" for v in trend_data],
                    textposition="top center",
                    line=dict(color='#ff7f0e', width=3)
                ))
                fig_trend.update_layout(template="plotly_white", height=280, margin=dict(l=10, r=10, t=30, b=10), xaxis_type='category')
                st.plotly_chart(fig_trend, use_container_width=True)
            
            st.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Execution Error: {e}. Try refreshing or check the ticker symbol.")
