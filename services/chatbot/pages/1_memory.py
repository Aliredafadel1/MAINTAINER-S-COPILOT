import os

import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Memory Inspector")
st.title("Long-Term Memory")

if "token" not in st.session_state:
    st.warning("Please log in from the Chat page.")
    st.stop()

headers = {"Authorization": f"Bearer {st.session_state['token']}"}

r = requests.get(f"{API_URL}/memory", headers=headers, timeout=10)
if not r.ok:
    st.error("Failed to load memories.")
    st.stop()

memories = r.json()
if not memories:
    st.info("No memories saved yet.")
else:
    for mem in memories:
        col1, col2 = st.columns([8, 1])
        col1.markdown(f"**[{mem['memory_type']}]** {mem['content']}")
        col1.caption(mem["created_at"])
        if col2.button("Delete", key=mem["id"]):
            dr = requests.delete(
                f"{API_URL}/memory/{mem['id']}", headers=headers, timeout=10
            )
            if dr.ok:
                st.rerun()
            else:
                st.error("Delete failed.")
