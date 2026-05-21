import json
import os
import time

import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")
_API_RETRIES = 5
_API_DELAY = 3


def _headers() -> dict:
    if token := st.session_state.get("token"):
        return {"Authorization": f"Bearer {token}"}
    return {}


def _api_ready() -> bool:
    """Return True if the API health endpoint responds."""
    try:
        r = requests.get(f"{API_URL}/health", timeout=3)
        return r.ok
    except Exception:
        return False


def _wait_for_api() -> bool:
    """Spin up to _API_RETRIES×_API_DELAY seconds waiting for the API."""
    for _ in range(_API_RETRIES):
        if _api_ready():
            return True
        time.sleep(_API_DELAY)
    return False


def _post(path: str, **kwargs) -> requests.Response | None:
    """POST with connection-error handling. Returns None on network failure."""
    try:
        return requests.post(f"{API_URL}{path}", timeout=15, **kwargs)
    except requests.exceptions.ConnectionError:
        return None


# ── Auth ──────────────────────────────────────────────────────────────────────
if "token" not in st.session_state:
    st.title("Maintainer's Copilot — Login")

    # Show a spinner while API warms up instead of crashing
    if not _api_ready():
        with st.spinner("API is starting up, please wait…"):
            ready = _wait_for_api()
        if not ready:
            st.error(
                "Cannot reach the API. Make sure the stack is running:\n\n"
                "```\ndocker compose up\n```"
            )
            st.stop()

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    col1, col2 = st.columns(2)

    if col1.button("Login"):
        r = _post("/auth/login", json={"email": email, "password": password})
        if r is None:
            st.error("Cannot reach the API — it may still be starting. Please try again in a few seconds.")
        elif r.ok:
            st.session_state["token"] = r.json()["access_token"]
            st.rerun()
        else:
            st.error(r.json().get("message", "Login failed"))

    if col2.button("Register"):
        r = _post("/auth/register", json={"email": email, "password": password})
        if r is None:
            st.error("Cannot reach the API — it may still be starting. Please try again in a few seconds.")
        elif r.ok:
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
        try:
            with requests.post(
                f"{API_URL}/chat/stream",
                json={
                    "message": prompt,
                    "conversation_id": st.session_state["conversation_id"],
                },
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
        except requests.exceptions.ConnectionError:
            placeholder.error("Lost connection to the API. Please refresh and try again.")
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
