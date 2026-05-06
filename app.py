# app.py
from __future__ import annotations

import json
import re
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

OUTPUT_DIR = Path("output")
CHART_DATA_DIR = OUTPUT_DIR / "chart-data" / "tickers"
DATE_SUFFIX_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\.csv$", re.IGNORECASE)

st.set_page_config(page_title="Trender Stock List Viewer", layout="wide")
st.title("Trender Stock List Viewer")

if not OUTPUT_DIR.exists() or not OUTPUT_DIR.is_dir():
    st.error(f"Folder not found: {OUTPUT_DIR.resolve()}")
    st.stop()

# Gather files that end with YYYY-MM-DD.csv
csv_paths = sorted([p for p in OUTPUT_DIR.glob("*.csv") if DATE_SUFFIX_RE.search(p.name)])

if not csv_paths:
    st.warning("No files found that end with YYYY-MM-DD.csv in the output/ folder.")
    st.stop()

# Build: date -> list of files
date_to_files: dict[str, list[Path]] = {}
for p in csv_paths:
    m = DATE_SUFFIX_RE.search(p.name)
    if not m:
        continue
    date_str = m.group(1)
    date_to_files.setdefault(date_str, []).append(p)

available_dates = sorted(date_to_files.keys(), reverse=True)

# --- UI controls (top of page)
col1, col2 = st.columns([1, 2])

with col1:
    selected_date = st.selectbox("Date", available_dates, index=0)

files_for_date = sorted(date_to_files[selected_date], key=lambda x: x.name.lower())

with col2:
    # Show file names, but keep full Path in the selection
    selected_file = st.selectbox(
        "File",
        options=files_for_date,
        format_func=lambda p: p.name,
        index=0,
    )

st.divider()

# Display file info + dataframe
st.caption(f"Showing: `{selected_file}`")

try:
    df = pd.read_csv(selected_file)
except Exception as e:
    st.error(f"Failed to read CSV: {e}")
    st.stop()

# Check if this is a 'stock' file (starts with 'stock')
is_stock_file = selected_file.name.lower().startswith("stock")

# Optional: basic options
with st.expander("Display options", expanded=False):
    show_rows = st.slider("Max rows to show", 10, 500, 100)
    if not is_stock_file:
        show_all_cols = st.checkbox("Show all columns", value=False)

column_config = {}

# For 'stock' files, display all content without filtering
if is_stock_file:
    df_to_show = df.copy()
else:
    # For non-stock files, apply preferred columns logic
    preferred_columns = [
        "ticker",
        "current_up_trend",
        "current_trend_length",
        "current_price",
        "1D",
        "1W",
        "1M",
        "3M",
        "6M",
        "1Y",
    ]

    performance_column_labels = {
        "1D": "1D Performance",
        "1W": "1W Performance",
        "1M": "1M Performance",
        "3M": "3M Performance",
        "6M": "6M Performance",
        "1Y": "1Y Performance",
    }

    if show_all_cols:
        df_to_show = df.copy()
    else:
        available_columns = [c for c in preferred_columns if c in df.columns]
        missing_columns = [c for c in preferred_columns if c not in df.columns]
        if missing_columns:
            st.info(
                "Missing columns in file: " + ", ".join(missing_columns)
            )
        df_to_show = df[available_columns].copy()

    rename_map = {c: performance_column_labels[c] for c in df_to_show.columns if c in performance_column_labels}
    if rename_map:
        df_to_show = df_to_show.rename(columns=rename_map)

    performance_cols = []
    for raw_col, display_col in performance_column_labels.items():
        if display_col in df_to_show.columns:
            col_series = df_to_show[display_col]
            if col_series.dtype == object:
                col_series = (
                    col_series.astype(str)
                    .str.replace("%", "", regex=False)
                    .str.replace(",", "", regex=False)
                )
            df_to_show[display_col] = pd.to_numeric(col_series, errors="coerce")
            performance_cols.append(display_col)

    for col in performance_cols:
        column_config[col] = st.column_config.NumberColumn(
            format="%.2f",
            help="Percent value",
        )

st.dataframe(df_to_show.head(show_rows), width='stretch', column_config=column_config)

# Optional: download
st.download_button(
    label="Download selected CSV",
    data=df_to_show.to_csv(index=False).encode("utf-8"),
    file_name=selected_file.name,
    mime="text/csv",
)

# --- Price Charts Section ---
st.divider()
st.subheader("Price Charts")

# Check if 'ticker' column exists in the dataframe
if 'ticker' in df.columns:
    # Get unique tickers from the dataframe
    tickers = df['ticker'].dropna().unique().tolist()
    
    # Filter tickers that have chart data available
    available_tickers = []
    for ticker in tickers:
        ticker_file = CHART_DATA_DIR / f"{ticker}.json"
        if ticker_file.exists():
            available_tickers.append(ticker)
    
    if available_tickers:
        st.info(f"Found chart data for {len(available_tickers)} out of {len(tickers)} tickers.")
        
        # Allow user to select which tickers to display
        with st.expander("Chart Display Options", expanded=True):
            # Only show slider if there's more than 1 chart
            if len(available_tickers) > 1:
                display_limit = st.slider("Number of charts to display", 1, min(20, len(available_tickers)), min(5, len(available_tickers)))
            else:
                display_limit = 1
            
            selected_tickers = st.multiselect(
                "Select specific tickers (optional)",
                options=available_tickers,
                default=None,
                help="Leave empty to show the first N tickers based on the slider above"
            )
        
        # Determine which tickers to display
        if selected_tickers:
            tickers_to_display = selected_tickers[:display_limit]
        else:
            tickers_to_display = available_tickers[:display_limit]
        
        # Display charts
        for ticker in tickers_to_display:
            ticker_file = CHART_DATA_DIR / f"{ticker}.json"
            
            try:
                with open(ticker_file, 'r') as f:
                    data = json.load(f)
                
                candles = data.get('candles', [])
                if not candles:
                    st.warning(f"No candle data found for {ticker}")
                    continue
                
                # Convert candles to dataframe for easier plotting
                df_candles = pd.DataFrame(candles)
                df_candles['date'] = pd.to_datetime(df_candles['date'])
                
                # Create candlestick chart
                fig = go.Figure(data=[go.Candlestick(
                    x=df_candles['date'],
                    open=df_candles['open'],
                    high=df_candles['high'],
                    low=df_candles['low'],
                    close=df_candles['close'],
                    name=ticker
                )])
                
                # Update layout
                fig.update_layout(
                    title=f"{ticker} Price Chart",
                    xaxis_title="Date",
                    yaxis_title="Price ($)",
                    height=500,
                    xaxis_rangeslider_visible=False,
                    hovermode='x unified'
                )
                
                # Display the chart
                st.plotly_chart(fig, use_container_width=True)
                
            except Exception as e:
                st.error(f"Failed to load chart for {ticker}: {e}")
    else:
        st.warning(f"No chart data available for any of the {len(tickers)} tickers in this file.")
else:
    st.info("No 'ticker' column found in the selected file. Charts require a 'ticker' column.")

st.markdown(
    """
    <style>
      .bottom-left-link {
        position: fixed;
        left: 1rem;
        bottom: 1rem;
        z-index: 9999;
      }
      .bottom-left-link a {
        display: inline-block;
        padding: 0.45rem 0.75rem;
        border-radius: 0.5rem;
        text-decoration: none;
        font-weight: 600;

        color: var(--text-color, #262730);
        background: var(--secondary-background-color, #ffffff);
        border: 1px solid rgba(49, 51, 63, 0.2);
      }
      .bottom-left-link a:hover {
        border-color: rgba(49, 51, 63, 0.35);
      }
    </style>

    <div class="bottom-left-link">
      <a href="https://topstocksmonitor.streamlit.app/" target="_blank" rel="noopener noreferrer">
        Top Stocks Monitor
      </a>
    </div>
    """,
    unsafe_allow_html=True,
)
