import os

import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Widget Config")
st.title("Embedded Widgets")

if "token" not in st.session_state:
    st.warning("Please log in from the Chat page.")
    st.stop()

headers = {"Authorization": f"Bearer {st.session_state['token']}"}

# ── Existing widgets ──────────────────────────────────────────────────────────
r = requests.get(f"{API_URL}/widgets", headers=headers, timeout=10)
widgets = r.json() if r.ok else []

for w in widgets:
    with st.expander(f"{w['name']} ({'active' if w['is_active'] else 'inactive'})"):
        st.code(w["id"], language=None)
        st.write("Allowed origins:", w["allowed_origins"])
        loader = f'<script src="{API_URL}/static/widget.js" data-widget-id="{w["id"]}"></script>'
        st.code(loader, language="html")

# ── Create new widget ─────────────────────────────────────────────────────────
st.divider()
st.subheader("Create new widget")
name = st.text_input("Name")
origins_raw = st.text_input("Allowed origins (comma-separated)", placeholder="https://myproject.com")

if st.button("Create"):
    origins = [o.strip() for o in origins_raw.split(",") if o.strip()]
    cr = requests.post(
        f"{API_URL}/widgets",
        json={"name": name, "allowed_origins": origins},
        headers=headers,
        timeout=10,
    )
    if cr.ok:
        st.success(f"Widget created: {cr.json()['id']}")
        st.rerun()
    else:
        st.error(cr.json().get("message", "Creation failed"))
