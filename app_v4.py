import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import requests

# --- 1. THEME & UI CONFIG ---
st.set_page_config(layout="wide", page_title="Institutional Equity Station 2026", page_icon="🏦")

st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; color: #1C1C1C; }
    [data-testid="stMetric"] { background-color: #F8F9FB; border: 1px solid #E6E9EF; border-radius: 12px; }
    .benchmark-label { color: #007BFF; font-weight: bold; font-size: 0.95rem; }
    .def-box { background-color: #f1f3f5; padding: 10px; border-left: 5px solid #007BFF; border-radius: 4px; font-size: 0.85rem; margin-top: 10px; }
    div[data-testid="stSidebar"] { background-color: #F0F2F6 !important; }
    hr { margin: 10px 0; border-color: #E6E9EF; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATA & SEARCH UTILITIES ---
@st.cache_data(ttl=3600)
def fetch_search_suggestions(query):
    if not query or len(query) < 2:
        return []
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        data = response.json()
        return [f"{res['symbol']} | {res['shortname']}" for res in data.get('quotes', []) if 'symbol' in res]
    except:
        return []

def scale_val(val):
    if val is None or pd.isna(val): return "N/A"
    abs_v = abs(val)
    if abs_v >= 1e9: return f"{val/1e9:.1f}B"
    if abs_v >= 1e6: return f"{val/1e6:.1f}M"
    return f"{val:,.0f}"

RATIO_LIBRARY = {
    "P/E Ratio": {"ideal": "15.0x - 25.0x", "def": "Price-to-Earnings measures company valuation."},
    "Earnings Per Share (EPS)": {"ideal": "Growth", "def": "Net profit allocated to each outstanding share."},
    "Price-to-Book (P/B)": {"ideal": "< 3.0x", "def": "Market capitalization compared to its book value."},
    "Book Value Per Share": {"ideal": "Growth", "def": "Per-share value of the company's equity."},
    "Debt-to-Equity": {"ideal": "< 2.0", "def": "Total liabilities relative to shareholder equity. Measures leverage risk."},
    "Operating Margin": {"ideal": "> 15.0%", "def": "Profit from core business after variable costs. Core efficiency metric."},
    "Net Margin": {"ideal": "> 10.0%", "def": "Final profit percentage after all costs, taxes, and interest."},
    "Return on Assets (ROA)": {"ideal": "> 5.0%", "def": "Net Income generated per dollar of total assets."},
    "Return on Equity (ROE)": {"ideal": "> 15.0%", "def": "Net Income generated per dollar of shareholder equity."},
}

@st.cache_data(ttl=300)
def get_comprehensive_data(symbol):
    ticker = yf.Ticker(symbol)
    return {
        "info": ticker.info,
        "hist": ticker.history(period="2y"),
        "annual_fin": ticker.financials,
        "quart_fin": ticker.quarterly_financials,
        "annual_bs": ticker.balance_sheet,
        "quart_bs": ticker.quarterly_balance_sheet
    }

# --- 3. STATE CALLBACKS ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["AAPL", "MSFT", "NVDA"]
if 'active_ticker' not in st.session_state:
    st.session_state.active_ticker = "AAPL"

def update_from_search():
    choice = st.session_state.search_results
    if choice and choice != "--- Select to Load ---":
        new_ticker = choice.split(" | ")[0]
        st.session_state.active_ticker = new_ticker

def update_from_watchlist():
    choice = st.session_state.nav_pick
    if choice:
        st.session_state.active_ticker = choice

def add_to_watchlist():
    if st.session_state.active_ticker not in st.session_state.watchlist:
        st.session_state.watchlist.append(st.session_state.active_ticker)

def remove_from_watchlist():
    if len(st.session_state.watchlist) > 1 and st.session_state.active_ticker in st.session_state.watchlist:
        st.session_state.watchlist.remove(st.session_state.active_ticker)
        st.session_state.active_ticker = st.session_state.watchlist[0]

# --- 4. CONTROL CENTER ---
with st.sidebar:
    st.title("🏛️ Control Center")
    
    st.write("**🔍 Search Asset**")
    search_query = st.text_input("Enter Company Name or Ticker:", placeholder="e.g. Amazon...")
    
    if search_query:
        suggestions = fetch_search_suggestions(search_query)
        if suggestions:
            st.selectbox(
                "Search Results:", 
                ["--- Select to Load ---"] + suggestions, 
                key="search_results",
                on_change=update_from_search
            )

    st.divider()

    st.write("**📂 Watchlist Manager**")
    try:
        current_idx = st.session_state.watchlist.index(st.session_state.active_ticker)
    except ValueError:
        current_idx = 0
        
    st.selectbox(
        "Pinned Tickers:", 
        st.session_state.watchlist, 
        index=current_idx,
        key="nav_pick",
        on_change=update_from_watchlist
    )
    
    c1, c2 = st.columns(2)
    with c1:
        st.button("➕ Add", on_click=add_to_watchlist, use_container_width=True, disabled=(st.session_state.active_ticker in st.session_state.watchlist))
    with c2:
        st.button("➖ Remove", on_click=remove_from_watchlist, use_container_width=True, disabled=(st.session_state.active_ticker not in st.session_state.watchlist or len(st.session_state.watchlist) <= 1))

# --- 5. MAIN DASHBOARD ---
active_ticker = st.session_state.active_ticker

try:
    data = get_comprehensive_data(active_ticker)
    info = data["info"]
    
    st.title(f"{info.get('longName', active_ticker)} ({active_ticker})")
    st.caption(f"Status: Institutional Feed Connected | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} EDT")

    # SECTION 1: PRICE ACTION
    fig_p = go.Figure(data=[go.Candlestick(
        x=data['hist'].index, open=data['hist']['Open'], 
        high=data['hist']['High'], low=data['hist']['Low'], close=data['hist']['Close']
    )])
    fig_p.update_layout(template="plotly_white", xaxis_rangeslider_visible=True, height=450, margin=dict(l=0,r=0,t=0,b=0))
    st.plotly_chart(fig_p, use_container_width=True)

    # SECTION 2: FUNDAMENTALS (BAR CHARTS)
    st.divider()
    st.subheader("📊 Fundamental Performance")
    freq = st.radio("Frequency:", ["Annual", "Quarterly"], horizontal=True)
    
    raw_pl = data["annual_fin"] if freq == "Annual" else data["quart_fin"]
    raw_bs = data["annual_bs"] if freq == "Annual" else data["quart_bs"]
    
    tab1, tab2 = st.tabs(["Profit & Loss", "Balance Sheet"])
    
    with tab1:
        if not raw_pl.empty:
            target_rows = ['Total Revenue', 'Net Income']
            available = [r for r in target_rows if r in raw_pl.index]
            df_pl = raw_pl.loc[available].T
            df_pl.index = df_pl.index.strftime('%b %Y')
            
            fig_bar_pl = go.Figure()
            if 'Total Revenue' in available: fig_bar_pl.add_trace(go.Bar(x=df_pl.index, y=df_pl['Total Revenue'], name='Revenue', marker_color='#1f77b4'))
            if 'Net Income' in available: fig_bar_pl.add_trace(go.Bar(x=df_pl.index, y=df_pl['Net Income'], name='Net Income', marker_color='#2ca02c'))
            fig_bar_pl.update_layout(template="plotly_white", barmode='group', height=350, xaxis_type='category')
            st.plotly_chart(fig_bar_pl, use_container_width=True)
            
            with st.expander("View P&L Statistical Data"):
                st.dataframe(df_pl.map(scale_val), use_container_width=True)

    with tab2:
        if not raw_bs.empty:
            target_bs = ['Total Assets', 'Total Liabilities Net Minority Interest']
            avail_bs = [r for r in target_bs if r in raw_bs.index]
            df_bs = raw_bs.loc[avail_bs].T
            df_bs.index = df_bs.index.strftime('%b %Y')
            
            fig_bar_bs = go.Figure()
            if 'Total Assets' in avail_bs: fig_bar_bs.add_trace(go.Bar(x=df_bs.index, y=df_bs['Total Assets'], name='Total Assets', marker_color='#17becf'))
            if 'Total Liabilities Net Minority Interest' in avail_bs: fig_bar_bs.add_trace(go.Bar(x=df_bs.index, y=df_bs['Total Liabilities Net Minority Interest'], name='Total Liabilities', marker_color='#d62728'))
            fig_bar_bs.update_layout(template="plotly_white", barmode='group', height=350, xaxis_type='category')
            st.plotly_chart(fig_bar_bs, use_container_width=True)

    # SECTION 3: LIVE RATIO SNAPSHOT
    st.divider()
    st.subheader("⚡ Live Ratio Snapshot")
    
    pe = info.get('trailingPE', 0)
    eps = info.get('trailingEps', 0)
    pb = info.get('priceToBook', 0)
    debt_eq = (info.get('debtToEquity', 0) or 0) / 100
    net_margin = info.get('profitMargins', 0) * 100
    roe = info.get('returnOnEquity', 0) * 100

    col_r1, col_r2, col_r3, col_r4, col_r5 = st.columns(5)
    col_r1.metric("P/E Ratio", f"{pe:.1f}x" if pe else "N/A")
    col_r2.metric("EPS (TTM)", f"${eps:.1f}" if eps else "N/A")
    col_r3.metric("Net Margin", f"{net_margin:.1f}%" if net_margin else "N/A")
    col_r4.metric("ROE", f"{roe:.1f}%" if roe else "N/A")
    col_r5.metric("Debt/Equity", f"{debt_eq:.1f}" if debt_eq else "N/A")

    # SECTION 4: HISTORICAL RATIO TRENDS (WITH METRICS RESTORED)
    st.divider()
    st.subheader("⏳ Historical Ratio Trends")
    st.info("Visualizing the quarterly progression of core metrics next to their latest live values.")
    
    q_fin = data["quart_fin"].T.sort_index(ascending=True)
    q_bs = data["quart_bs"].T.sort_index(ascending=True)
    
    trend_metrics = ["Earnings Per Share (EPS)", "Book Value Per Share", "Net Margin", "Operating Margin", "Return on Assets (ROA)", "Return on Equity (ROE)", "Debt-to-Equity"]

    for label in trend_metrics:
        meta = RATIO_LIBRARY[label]
        trend = []
        y_label = "Value"
        latest_str = "N/A"
        
        try:
            if label == "Net Margin":
                trend = (q_fin['Net Income'] / q_fin['Total Revenue']) * 100
                latest = info.get('profitMargins', 0) * 100
                latest_str = f"{latest:.1f}%"
                y_label = "Margin %"
            elif label == "Operating Margin":
                trend = (q_fin['Operating Income'] / q_fin['Total Revenue']) * 100
                latest = info.get('operatingMargins', 0) * 100
                latest_str = f"{latest:.1f}%"
                y_label = "Margin %"
            elif label == "Return on Assets (ROA)":
                if 'Net Income' in q_fin.columns and 'Total Assets' in q_bs.columns:
                    trend = (q_fin['Net Income'] / q_bs['Total Assets']) * 100
                latest = info.get('returnOnAssets', 0) * 100
                latest_str = f"{latest:.1f}%"
                y_label = "ROA %"
            elif label == "Return on Equity (ROE)":
                if 'Net Income' in q_fin.columns and 'Stockholders Equity' in q_bs.columns:
                    trend = (q_fin['Net Income'] / q_bs['Stockholders Equity']) * 100
                latest = info.get('returnOnEquity', 0) * 100
                latest_str = f"{latest:.1f}%"
                y_label = "ROE %"
            elif label == "Debt-to-Equity":
                if 'Total Debt' in q_bs.columns and 'Stockholders Equity' in q_bs.columns:
                    trend = q_bs['Total Debt'] / q_bs['Stockholders Equity']
                latest = (info.get('debtToEquity', 0) or 0) / 100
                latest_str = f"{latest:.1f}"
            elif label == "Earnings Per Share (EPS)":
                if 'Basic EPS' in q_fin.columns: trend = q_fin['Basic EPS']
                elif 'Diluted EPS' in q_fin.columns: trend = q_fin['Diluted EPS']
                latest = info.get('trailingEps', 0)
                latest_str = f"${latest:.1f}" if latest else "N/A"
            elif label == "Book Value Per Share":
                if 'Stockholders Equity' in q_bs.columns and 'Ordinary Shares Number' in q_bs.columns:
                    trend = q_bs['Stockholders Equity'] / q_bs['Ordinary Shares Number']
                latest = info.get('bookValue', 0)
                latest_str = f"${latest:.1f}" if latest else "N/A"
        except Exception:
            continue 
        
        if len(trend) > 0:
            with st.container():
                m_col1, m_col2 = st.columns([1, 3])
                
                # Restored the latest metric box into the left column
                with m_col1:
                    st.markdown(f"#### {label}")
                    st.metric("Latest Live", latest_str)
                    st.markdown(f"Industry Ideal: <span class='benchmark-label'>{meta['ideal']}</span>", unsafe_allow_html=True)
                    st.markdown(f"<div class='def-box'><b>Concept:</b> {meta['def']}</div>", unsafe_allow_html=True)
                
                with m_col2:
                    fig_trend = go.Figure(go.Scatter(
                        x=q_fin.index.strftime('%b %Y'), y=trend, 
                        mode='lines+markers+text', 
                        text=[f"{v:.1f}" for v in trend], 
                        textposition="top center",
                        line=dict(color='#007BFF', width=3)
                    ))
                    fig_trend.update_layout(
                        template="plotly_white", height=220, 
                        margin=dict(l=10, r=10, t=30, b=10), xaxis_type='category', yaxis_title=y_label
                    )
                    st.plotly_chart(fig_trend, use_container_width=True)
                st.markdown("<hr>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Application Sync Error: {e}")
