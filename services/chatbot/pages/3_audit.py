import os

import pandas as pd
import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Audit Log")
st.title("Audit Log")

if "token" not in st.session_state:
    st.warning("Please log in from the Chat page.")
    st.stop()

headers = {"Authorization": f"Bearer {st.session_state['token']}"}

r = requests.get(f"{API_URL}/audit", headers=headers, timeout=10)
if r.status_code == 403:
    st.error("Admin access required.")
    st.stop()
if not r.ok:
    st.error("Failed to load audit log.")
    st.stop()

entries = r.json()
if not entries:
    st.info("No audit entries yet.")
else:
    df = pd.DataFrame(entries)
    st.dataframe(df, use_container_width=True)
