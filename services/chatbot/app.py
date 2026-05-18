import json
import os

import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Maintainer's Copilot", layout="wide")


def _headers() -> dict:
    if token := st.session_state.get("token"):
        return {"Authorization": f"Bearer {token}"}
    return {}


# ── Auth ──────────────────────────────────────────────────────────────────────
if "token" not in st.session_state:
    st.title("Maintainer's Copilot — Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    col1, col2 = st.columns(2)
    if col1.button("Login"):
        r = requests.post(f"{API_URL}/auth/login", json={"email": email, "password": password}, timeout=10)
        if r.ok:
            st.session_state["token"] = r.json()["access_token"]
            st.rerun()
        else:
            st.error(r.json().get("message", "Login failed"))
    if col2.button("Register"):
        r = requests.post(f"{API_URL}/auth/register", json={"email": email, "password": password}, timeout=10)
        if r.ok:
            st.session_state["token"] = r.json()["access_token"]
            st.rerun()
        else:
            st.error(r.json().get("message", "Registration failed"))
    st.stop()

# ── Chat UI ───────────────────────────────────────────────────────────────────
st.title("Maintainer's Copilot")

if "conversation_id" not in st.session_state:
    st.session_state["conversation_id"] = None
if "messages" not in st.session_state:
    st.session_state["messages"] = []

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask about an issue, paste a thread, or search docs…"):
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_text = ""
        with requests.post(
            f"{API_URL}/chat/stream",
            json={"message": prompt, "conversation_id": st.session_state["conversation_id"]},
            headers=_headers(),
            stream=True,
            timeout=60,
        ) as r:
            for line in r.iter_lines():
                if line and line.startswith(b"data: "):
                    data = json.loads(line[6:])
                    if data.get("type") == "text":
                        full_text += data["text"]
                        placeholder.markdown(full_text + "▌")
                    elif data.get("type") == "start" and "conversation_id" in data:
                        st.session_state["conversation_id"] = data["conversation_id"]
        placeholder.markdown(full_text)
        st.session_state["messages"].append({"role": "assistant", "content": full_text})

with st.sidebar:
    st.page_link("app.py", label="Chat", icon="💬")
    st.page_link("pages/1_memory.py", label="Memory", icon="🧠")
    st.page_link("pages/2_widgets.py", label="Widgets", icon="🔧")
    st.page_link("pages/3_audit.py", label="Audit Log", icon="📋")
    if st.button("Logout"):
        del st.session_state["token"]
        st.rerun()
