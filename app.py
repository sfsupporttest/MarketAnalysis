import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# --- 1. THEME & UI CONFIG ---
st.set_page_config(layout="wide", page_title="Institutional Equity Station 2026", page_icon="🏦")

st.markdown("""
    <style>
    /* Main app styling */
    .stApp { background-color: #FFFFFF; color: #1C1C1C; }
    
    /* Metric cards - better alignment */
    [data-testid="stMetric"] { 
        background-color: #F8F9FB; 
        border: 1px solid #E6E9EF; 
        border-radius: 12px; 
        padding: 12px 8px;
    }
    [data-testid="stMetricLabel"] { font-size: 0.75rem; color: #6c757d; }
    [data-testid="stMetricValue"] { font-size: 1.1rem; font-weight: 600; }
    
    /* Sidebar */
    div[data-testid="stSidebar"] { background-color: #F0F2F6 !important; }
    div[data-testid="stSidebar"] .stMarkdown { padding: 0 10px; }
    
    /* Headings */
    h1 { font-size: 2rem; font-weight: 700; margin-bottom: 0.5rem; }
    h2 { font-size: 1.5rem; font-weight: 600; margin-top: 1rem; }
    h3 { font-size: 1.2rem; font-weight: 600; }
    h4 { font-size: 1rem; font-weight: 600; }
    
    /* Dividers */
    hr { margin: 15px 0; border-color: #E6E9EF; }
    .block-container { padding-top: 1.5rem; padding-bottom: 1.5rem; }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { 
        padding: 8px 16px; 
        border-radius: 8px 8px 0 0;
    }
    
    /* Buttons */
    .stButton > button { border-radius: 8px; }
    
    /* Scanner section cards */
    .scanner-card {
        background-color: #f8f9fa;
        border-radius: 12px;
        padding: 20px;
        margin: 15px 0;
        border: 1px solid #e9ecef;
    }
    
    /* Recommendation boxes */
    .rec-box {
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
    
    /* DataFrame styling */
    [data-testid="stDataFrame"] { border-radius: 8px; }
    
    /* Expander */
    .streamlit-expanderHeader { 
        background-color: #f8f9fa; 
        border-radius: 8px;
    }
    
    /* Columns spacing */
    div[data-testid="column"] { padding: 0 5px; }
    
    /* Progress bar */
    .stProgress > div > div > div { background-color: #007BFF; }
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

# S&P 500 Top 50 Tickers (by market cap - representative sample for scanning)
SP500_TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "BRK.B", "UNH", "JNJ",
    "V", "XOM", "JPM", "WMT", "MA", "PG", "HD", "CVX", "MRK", "ABBV",
    "LLY", "PEP", "KO", "COST", "AVGO", "TMO", "MCD", "CSCO", "ACN", "ABT",
    "DHR", "CRM", "ADBE", "WFC", "TXN", "NKE", "PM", "NEE", "BMY", "UNP",
    "RTX", "ORCL", "HON", "LOW", "INTC", "IBM", "AMD", "QCOM", "SBUX", "CAT"
]

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

# --- OPTION SCANNER FUNCTIONS ---
def calculate_rsi(prices, period=14):
    """Calculate RSI indicator"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if len(rsi) > 0 else 50

def calculate_volatility(prices, period=20):
    """Calculate historical volatility (annualized)"""
    returns = prices.pct_change().dropna()
    if len(returns) < period:
        return 0
    vol = returns.rolling(window=period).std().iloc[-1] * np.sqrt(252) * 100
    return vol

def analyze_stock_for_options(symbol):
    """Analyze a single stock for option-selling suitability"""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        hist = ticker.history(period="6mo")
        
        if hist.empty or len(hist) < 30:
            return None
        
        close_prices = hist['Close']
        current_price = close_prices.iloc[-1]
        
        # Technical Analysis
        rsi = calculate_rsi(close_prices)
        volatility = calculate_volatility(hist['Close'])
        
        # Trend analysis (50-day vs 200-day SMA)
        sma_50 = close_prices.rolling(50).mean().iloc[-1]
        sma_200 = close_prices.rolling(200).mean().iloc[-1] if len(close_prices) >= 200 else sma_50
        trend = "bullish" if sma_50 > sma_200 else "bearish" if sma_50 < sma_200 * 0.95 else "sideways"
        
        # Price momentum (20-day return)
        momentum_20d = ((close_prices.iloc[-1] - close_prices.iloc[-20]) / close_prices.iloc[-20] * 100) if len(close_prices) >= 20 else 0
        
        # Fundamental Analysis
        market_cap = info.get('marketCap', 0)
        pe_ratio = info.get('trailingPE', 0) or 0
        dividend_yield = info.get('dividendYield', 0) or 0
        beta = info.get('beta', 1)
        
        # Get options data (if available)
        try:
            opt = ticker.option_chain()
            calls = opt.calls if hasattr(opt, 'calls') else pd.DataFrame()
            puts = opt.puts if hasattr(opt, 'puts') else pd.DataFrame()
            
            # Calculate average implied volatility from ATM options
            if not calls.empty:
                atm_calls = calls[(calls['strike'] >= current_price * 0.95) & (calls['strike'] <= current_price * 1.05)]
                iv = atm_calls['impliedVolatility'].mean() * 100 if not atm_calls.empty and 'impliedVolatility' in atm_calls.columns else volatility
            else:
                iv = volatility
        except:
            iv = volatility
        
        # Earnings date (next earnings)
        try:
            earnings_date = info.get('earningsDate')
            if earnings_date is not None:
                if isinstance(earnings_date, (list, tuple)):
                    next_earnings = earnings_date[0]
                else:
                    next_earnings = earnings_date
                # Handle pandas Timestamp
                if hasattr(next_earnings, 'days'):
                    days_to_earnings = (next_earnings - datetime.now()).days
                elif isinstance(next_earnings, str):
                    days_to_earnings = 30  # Default if string
                else:
                    days_to_earnings = 30
            else:
                days_to_earnings = 30
        except:
            days_to_earnings = 30
        
        # Score for option selling (higher = better)
        # Ideal: moderate IV (20-40%), RSI 40-60, stable/bullish trend, >30 days to earnings
        score = 0
        reasons = []
        
        # IV scoring (prefer moderate-high IV for premium)
        if 20 <= iv <= 40:
            score += 30
            reasons.append(f"Moderate IV ({iv:.1f}%) - good premium")
        elif iv > 40:
            score += 15
            reasons.append(f"High IV ({iv:.1f}%) - high risk premium")
        else:
            score += 5
            reasons.append(f"Low IV ({iv:.1f}%) - minimal premium")
        
        # RSI scoring (prefer not overbought)
        if 35 <= rsi <= 65:
            score += 25
            reasons.append(f"Neutral RSI ({rsi:.1f})")
        elif rsi < 35:
            score += 20
            reasons.append(f"Oversold RSI ({rsi:.1f}) - potential bounce")
        else:
            score += 10
            reasons.append(f"Overbought RSI ({rsi:.1f})")
        
        # Trend scoring
        if trend == "sideways":
            score += 25
            reasons.append("Sideways trend - stable price")
        elif trend == "bullish":
            score += 20
            reasons.append("Bullish trend - upward momentum")
        else:
            score += 5
            reasons.append("Bearish trend - caution")
        
        # Earnings avoidance (prefer >21 days)
        if days_to_earnings > 21:
            score += 15
            reasons.append(f"{days_to_earnings}d to earnings - safe window")
        elif days_to_earnings > 7:
            score += 5
            reasons.append(f"{days_to_earnings}d to earnings - elevated risk")
        else:
            score -= 20
            reasons.append(f"Earnings in {days_to_earnings}d - AVOID")
        
        # Market cap scoring (liquidity)
        if market_cap > 100e9:
            score += 5
        
        return {
            'symbol': symbol,
            'name': info.get('shortName', symbol),
            'price': current_price,
            'rsi': rsi,
            'iv': iv,
            'volatility': volatility,
            'trend': trend,
            'momentum_20d': momentum_20d,
            'pe_ratio': pe_ratio,
            'dividend_yield': dividend_yield * 100,
            'beta': beta,
            'market_cap': market_cap,
            'days_to_earnings': days_to_earnings,
            'score': score,
            'reasons': reasons
        }
    except Exception as e:
        return None

@st.cache_data(ttl=3600)
def scan_sp500_for_options():
    """Scan S&P 500 stocks for option-selling opportunities"""
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total = len(SP500_TICKERS)
    
    for i, symbol in enumerate(SP500_TICKERS):
        status_text.text(f"Analyzing {symbol} ({i+1}/{total})...")
        result = analyze_stock_for_options(symbol)
        if result:
            results.append(result)
        progress_bar.progress((i + 1) / total)
        time.sleep(0.1)  # Rate limiting
    
    progress_bar.empty()
    status_text.empty()
    
    # Sort by score (highest first)
    results.sort(key=lambda x: x['score'], reverse=True)
    return results

def generate_option_recommendation(stock_data, strategy_type="covered_call"):
    """Generate option selling recommendation"""
    price = stock_data['price']
    iv = stock_data['iv']
    
    if strategy_type == "covered_call":
        # Sell OTM call at 5-10% above current price
        strike = price * 1.05
        premium_estimate = price * (iv / 100) * 0.3  # Rough premium estimate
        duration = "30-45 DTE" if iv > 25 else "45-60 DTE"
        exit_strategy = "Buy back if stock drops >5% or at 50% of max profit"
    else:  # cash-secured put
        # Sell OTM put at 5-10% below current price
        strike = price * 0.95
        premium_estimate = price * (iv / 100) * 0.3
        duration = "30-45 DTE" if iv > 25 else "45-60 DTE"
        exit_strategy = "Roll if assigned or at 50% of max profit"
    
    return {
        'strike': strike,
        'premium_estimate': premium_estimate,
        'duration': duration,
        'exit_strategy': exit_strategy,
        'risk_level': 'Low' if iv < 30 else 'Medium' if iv < 45 else 'High'
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
    st.markdown("---")
    
    st.markdown("**🔍 Search Asset**")
    search_query = st.text_input("Enter Company Name or Ticker:", placeholder="e.g. Amazon...", label_visibility="collapsed")
    
    if search_query:
        suggestions = fetch_search_suggestions(search_query)
        if suggestions:
            st.selectbox(
                "Search Results:", 
                ["--- Select to Load ---"] + suggestions, 
                key="search_results",
                on_change=update_from_search
            )

    st.markdown("---")

    st.markdown("**📂 Watchlist Manager**")
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
        st.button("➕ Add", on_click=add_to_watchlist, use_container_width=True)
    with c2:
        st.button("➖ Remove", on_click=remove_from_watchlist, use_container_width=True, disabled=(st.session_state.active_ticker not in st.session_state.watchlist or len(st.session_state.watchlist) <= 1))

# --- 5. MAIN DASHBOARD ---
active_ticker = st.session_state.active_ticker

try:
    data = get_comprehensive_data(active_ticker)
    info = data["info"]
    
    # Header with better styling
    col_title, col_time = st.columns([3, 1])
    with col_title:
        st.title(f"{info.get('longName', active_ticker)} ({active_ticker})")
    with col_time:
        st.caption(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} EDT")

    # SECTION 1: PRICE ACTION
    fig_p = go.Figure(data=[go.Candlestick(
        x=data['hist'].index, open=data['hist']['Open'], 
        high=data['hist']['High'], low=data['hist']['Low'], close=data['hist']['Close']
    )])
    fig_p.update_layout(template="plotly_white", xaxis_rangeslider_visible=True, height=450, margin=dict(l=0,r=0,t=0,b=0))
    st.plotly_chart(fig_p, use_container_width=True)

    # SECTION 2: FUNDAMENTALS (BAR CHARTS)
    st.markdown("---")
    st.subheader("📊 Fundamental Performance")
    freq = st.radio("Frequency:", ["Annual", "Quarterly"], horizontal=True, label_visibility="collapsed")
    
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
    st.markdown("---")
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
    st.markdown("---")
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

    # --- SECTION 5: OPTION SELLING SCANNER ---
    st.markdown("---")
    st.subheader("🎯 S&P 500 Option Selling Scanner")
    st.markdown("**AI-Powered Analysis:** Scanning top 50 S&P 500 stocks for optimal option-selling opportunities based on technical & fundamental factors.")
    
    # Control row with better alignment
    scan_col1, scan_col2 = st.columns([1, 3])
    with scan_col1:
        scan_button = st.button("🔄 Run Scanner", type="primary", use_container_width=True)
    with scan_col2:
        strategy_choice = st.selectbox("Select Strategy:", ["Covered Call", "Cash-Secured Put"], index=0, label_visibility="collapsed")
    
    if scan_button or 'scanner_results' in st.session_state:
        if scan_button:
            with st.spinner("Scanning S&P 500 stocks... This may take 2-3 minutes."):
                results = scan_sp500_for_options()
                st.session_state.scanner_results = results
        else:
            results = st.session_state.get('scanner_results', [])
        
        if results:
            # Determine strategy type
            strategy_type = "covered_call" if strategy_choice == "Covered Call" else "cash_secured_put"
            strategy_icon = "📈" if strategy_choice == "Covered Call" else "📉"
            
            # Show top 3 recommendations
            st.markdown(f"### 🏆 Top 3 {strategy_choice} Candidates")
            
            top_3 = results[:3]
            
            for rank, stock in enumerate(top_3, 1):
                with st.container():
                    st.markdown(f"**{rank}. {stock['symbol']}** — {stock['name']}")
                    
                    # Key metrics - reduced columns for better fit
                    m1, m2, m3, m4, m5 = st.columns(5)
                    m1.metric("Price", f"${stock['price']:.2f}")
                    m2.metric("IV", f"{stock['iv']:.1f}%")
                    m3.metric("RSI", f"{stock['rsi']:.1f}")
                    m4.metric("Trend", stock['trend'].title())
                    m5.metric("Score", f"{stock['score']}")
                    
                    # Generate recommendation based on selected strategy
                    rec = generate_option_recommendation(stock, strategy_type)
                    
                    # Calculate collateral required for CSP
                    collateral = rec['strike'] * 100 if strategy_type == "cash_secured_put" else stock['price'] * 100
                    
                    # Recommendation boxes - side by side
                    rec_col1, rec_col2 = st.columns([1, 1])
                    with rec_col1:
                        if strategy_type == "covered_call":
                            st.markdown(f"""
                            <div class="rec-box" style="background-color: #e8f5e9; border-left: 4px solid #4caf50;">
                                <strong style="color: #2e7d32;">📋 {strategy_icon} {strategy_choice}</strong>
                                <div style="margin-top: 8px; font-size: 0.9rem;">
                                    <div><strong>Strike:</strong> ${rec['strike']:.2f} (5% OTM)</div>
                                    <div><strong>Premium:</strong> ${rec['premium_estimate']:.2f}/share</div>
                                    <div><strong>Duration:</strong> {rec['duration']}</div>
                                    <div><strong>Risk:</strong> {rec['risk_level']}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div class="rec-box" style="background-color: #e3f2fd; border-left: 4px solid #2196f3;">
                                <strong style="color: #1565c0;">📋 {strategy_icon} {strategy_choice}</strong>
                                <div style="margin-top: 8px; font-size: 0.9rem;">
                                    <div><strong>Strike:</strong> ${rec['strike']:.2f} (5% OTM)</div>
                                    <div><strong>Premium:</strong> ${rec['premium_estimate']:.2f}/share</div>
                                    <div><strong>Collateral:</strong> ${collateral:,.0f}</div>
                                    <div><strong>Duration:</strong> {rec['duration']}</div>
                                    <div><strong>Risk:</strong> {rec['risk_level']}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    with rec_col2:
                        reasons_list = "<br>".join([f"• {r}" for r in stock['reasons'][:3]])
                        st.markdown(f"""
                        <div class="rec-box" style="background-color: #fff8e1; border-left: 4px solid #ff9800;">
                            <strong style="color: #e65100;">🚪 Exit Strategy</strong>
                            <div style="margin-top: 8px; font-size: 0.9rem;">
                                {reasons_list}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    st.markdown("<hr>", unsafe_allow_html=True)
            
            # Show full rankings table
            with st.expander("📊 View Full Rankings (All Scanned Stocks)"):
                df_results = pd.DataFrame(results)
                if not df_results.empty:
                    display_cols = ['symbol', 'name', 'price', 'iv', 'rsi', 'trend', 'score', 'days_to_earnings', 'dividend_yield']
                    df_display = df_results[display_cols].copy()
                    df_display.columns = ['Symbol', 'Name', 'Price', 'IV%', 'RSI', 'Trend', 'Score', 'Days to Earnings', 'Div Yield%']
                    st.dataframe(df_display, use_container_width=True)

except Exception as e:
    st.error(f"Application Sync Error: {e}")
