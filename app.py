# app.py
from __future__ import annotations

import re
from pathlib import Path
import pandas as pd
import streamlit as st

OUTPUT_DIR = Path("output")
DATE_SUFFIX_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\.csv$", re.IGNORECASE)

st.set_page_config(page_title="CSV Viewer", layout="wide")
st.title("Output CSV Viewer")

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

# Optional: basic options
with st.expander("Display options", expanded=False):
    show_rows = st.slider("Max rows to show", 10, 500, 100)
    show_all_cols = st.checkbox("Show all columns", value=True)

if not show_all_cols:
    # If you ever want to restrict columns later, adjust here
    df_to_show = df
else:
    df_to_show = df

st.dataframe(df_to_show.head(show_rows), width='stretch')

# Optional: download
st.download_button(
    label="Download selected CSV",
    data=selected_file.read_bytes(),
    file_name=selected_file.name,
    mime="text/csv",
)
