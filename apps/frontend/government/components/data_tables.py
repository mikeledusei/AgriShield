"""Data tables for government dashboard."""
import streamlit as st
import pandas as pd


def render_data_tables(df_data, columns=None, title: str = "Data Table"):
    """Render a styled data table with optional filters."""
    st.subheader(title)

    if df_data is None or df_data.empty:
        st.info("No data available.")
        return

    df = pd.DataFrame(df_data) if not isinstance(df_data, pd.DataFrame) else df_data

    col1, col2 = st.columns([2, 1])
    with col1:
        page_size = st.selectbox("Rows per page", [10, 25, 50, 100], index=1)
    with col2:
        search = st.text_input("Search", placeholder="Filter rows...")

    if search:
        mask = df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)
        df = df[mask]
        st.caption(f"Showing {len(df)} of {len(df_data)} rows")

    st.dataframe(df.head(page_size), use_container_width=True)
    st.caption(f"Total rows: {len(df)}")
