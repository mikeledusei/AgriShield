import streamlit as st

st.set_page_config(page_title="AgriShield", page_icon="🌾", layout="wide")

st.title("🌾 AgriShield Platform")
st.markdown("""
Welcome to the AgriShield Agricultural Risk Intelligence System. 

Select a tool from the sidebar on the left to get started:
* **Dashboard**: Input county data and run risk predictions.
* **Map View**: Visualize regional risk heatmaps.
* **Reports**: Generate and download PDF risk assessments.
""")
