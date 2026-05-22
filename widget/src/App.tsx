import React, { useEffect, useRef, useState } from "react";

interface Props { widgetId: string; apiUrl: string; }
interface Msg { role: "user" | "assistant"; content: string; }

const BASE_Z = 2147483647;

const S = {
  bubble: (c: string): React.CSSProperties => ({
    position: "fixed", top: "20px", right: "20px",
    width: "60px", height: "60px", borderRadius: "50%",
    background: c, color: "#fff", border: "none", cursor: "pointer",
    fontSize: "26px", boxShadow: "0 4px 20px rgba(0,0,0,.5)",
    display: "flex", alignItems: "center", justifyContent: "center",
    padding: "0", margin: "0", zIndex: BASE_Z,
    fontFamily: "Arial, sans-serif",
  }),

  panel: {
    position: "fixed", top: "92px", right: "20px",
    width: "360px", height: "500px", background: "#ffffff",
    borderRadius: "12px", boxShadow: "0 8px 32px rgba(0,0,0,.3)",
    border: "1px solid #e5e7eb", display: "flex", flexDirection: "column",
    overflow: "hidden", zIndex: BASE_Z,
    fontFamily: "-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif",
    fontSize: "14px", lineHeight: "1.5", color: "#111111",
  } as React.CSSProperties,

  header: (c: string): React.CSSProperties => ({
    background: c, color: "#fff", padding: "12px 16px",
    fontWeight: "700", fontSize: "15px", flexShrink: 0,
    display: "flex", alignItems: "center", justifyContent: "space-between",
  }),

  closeBtn: {
    background: "none", border: "none", color: "#fff",
    cursor: "pointer", fontSize: "20px", lineHeight: "1",
    padding: "0", margin: "0",
  } as React.CSSProperties,

  body: {
    flex: 1, padding: "20px", display: "flex",
    flexDirection: "column", gap: "12px", background: "#fff",
    overflowY: "auto",
  } as React.CSSProperties,

  label: {
    margin: "0 0 2px 0", fontSize: "12px",
    color: "#555", fontWeight: "500",
  } as React.CSSProperties,

  input: {
    padding: "9px 12px", border: "1px solid #d1d5db",
    borderRadius: "8px", fontSize: "14px", color: "#111",
    background: "#fff", outline: "none", width: "100%",
    boxSizing: "border-box", display: "block",
  } as React.CSSProperties,

  btn: (c: string, disabled = false): React.CSSProperties => ({
    padding: "10px", background: disabled ? "#9ca3af" : c,
    color: "#fff", border: "none", borderRadius: "8px",
    fontSize: "14px", fontWeight: "600",
    cursor: disabled ? "not-allowed" : "pointer",
    width: "100%", display: "block", textAlign: "center",
  }),

  messages: {
    flex: 1, overflowY: "auto", padding: "12px",
    display: "flex", flexDirection: "column", gap: "8px",
    background: "#f9fafb",
  } as React.CSSProperties,

  userBub: (c: string): React.CSSProperties => ({
    alignSelf: "flex-end", background: c, color: "#fff",
    padding: "8px 12px", borderRadius: "12px 12px 2px 12px",
    maxWidth: "82%", fontSize: "14px", lineHeight: "1.5",
    wordBreak: "break-word", whiteSpace: "pre-wrap",
  }),

  asstBub: {
    alignSelf: "flex-start", background: "#fff", color: "#111",
    padding: "8px 12px", borderRadius: "12px 12px 12px 2px",
    maxWidth: "82%", fontSize: "14px", lineHeight: "1.5",
    border: "1px solid #e5e7eb", wordBreak: "break-word",
    whiteSpace: "pre-wrap",
  } as React.CSSProperties,

  inputRow: {
    display: "flex", padding: "10px", gap: "8px",
    borderTop: "1px solid #e5e7eb", background: "#fff", flexShrink: 0,
  } as React.CSSProperties,

  chatInput: {
    flex: 1, padding: "8px 12px", border: "1px solid #d1d5db",
    borderRadius: "8px", fontSize: "14px", color: "#111",
    background: "#fff", outline: "none", boxSizing: "border-box",
  } as React.CSSProperties,

  sendBtn: (c: string, disabled: boolean): React.CSSProperties => ({
    padding: "8px 16px", background: disabled ? "#9ca3af" : c,
    color: "#fff", border: "none", borderRadius: "8px",
    fontSize: "14px", fontWeight: "600",
    cursor: disabled ? "not-allowed" : "pointer", flexShrink: 0,
  }),

  hint: {
    color: "#888", fontSize: "13px", textAlign: "center" as const,
    margin: "20px 0 0 0",
  },
};

export default function App({ widgetId, apiUrl }: Props) {
  const [open, setOpen] = useState(false);
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginErr, setLoginErr] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [convId, setConvId] = useState<string | null>(null);
  const [color, setColor] = useState("#6366f1");
  const [greeting, setGreeting] = useState("Maintainer's Copilot");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(`${apiUrl}/widgets/${widgetId}/config`)
      .then(r => r.json())
      .then(d => {
        if (d.config?.primary_color) setColor(d.config.primary_color);
        if (d.config?.greeting) setGreeting(d.config.greeting);
      })
      .catch(() => {});
  }, [widgetId, apiUrl]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs]);

  async function login() {
    setLoginErr("");
    try {
      const r = await fetch(`${apiUrl}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const d = await r.json();
      if (!r.ok) { setLoginErr(d.message || "Login failed"); return; }
      setToken(d.access_token);
    } catch {
      setLoginErr("Cannot reach API");
    }
  }

  async function send() {
    if (!input.trim() || !token || loading) return;
    const msg = input.trim();
    setInput("");
    setMsgs(p => [...p, { role: "user", content: msg }]);
    setLoading(true);
    setMsgs(p => [...p, { role: "assistant", content: "" }]);

    try {
      const r = await fetch(`${apiUrl}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ message: msg, conversation_id: convId }),
      });
      let text = "";
      const reader = r.body!.getReader();
      const dec = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        for (const line of dec.decode(value).split("\n")) {
          if (!line.startsWith("data: ")) continue;
          try {
            const d = JSON.parse(line.slice(6));
            if (d.type === "text") {
              text += d.text;
              setMsgs(p => { const u = [...p]; u[u.length - 1] = { role: "assistant", content: text }; return u; });
            }
            if (d.type === "start" && d.conversation_id) setConvId(d.conversation_id);
          } catch { }
        }
      }
    } catch {
      setMsgs(p => { const u = [...p]; u[u.length - 1] = { role: "assistant", content: "⚠️ Error reaching API." }; return u; });
    }
    setLoading(false);
  }

  return (
    <>
      {open && (
        <div style={S.panel}>
          <div style={S.header(color)}>
            <span>{greeting}</span>
            <button style={S.closeBtn} onClick={() => setOpen(false)}>×</button>
          </div>

          {!token ? (
            <div style={S.body}>
              <p style={{ margin: "0 0 8px 0", color: "#555", fontSize: "13px" }}>
                Sign in to use the Maintainer's Copilot.
              </p>
              <div>
                <p style={S.label}>Email</p>
                <input
                  style={S.input}
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                />
              </div>
              <div>
                <p style={S.label}>Password</p>
                <input
                  style={S.input}
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && login()}
                />
              </div>
              {loginErr && (
                <p style={{ margin: 0, color: "#ef4444", fontSize: "13px" }}>{loginErr}</p>
              )}
              <button style={S.btn(color)} onClick={login}>Sign in</button>
            </div>
          ) : (
            <>
              <div style={S.messages}>
                {msgs.length === 0 && (
                  <p style={S.hint}>Ask me about an issue, bug, or feature request.</p>
                )}
                {msgs.map((m, i) => (
                  <div key={i} style={m.role === "user" ? S.userBub(color) : S.asstBub}>
                    {m.content || (loading && i === msgs.length - 1 ? "…" : "")}
                  </div>
                ))}
                <div ref={bottomRef} />
              </div>
              <div style={S.inputRow}>
                <input
                  style={S.chatInput}
                  type="text"
                  placeholder="Ask about an issue…"
                  value={input}
                  disabled={loading}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && !e.shiftKey && send()}
                />
                <button style={S.sendBtn(color, loading)} onClick={send} disabled={loading}>
                  {loading ? "…" : "Send"}
                </button>
              </div>
            </>
          )}
        </div>
      )}

      <button style={S.bubble(color)} onClick={() => setOpen(o => !o)}>
        {open ? "✕" : "💬"}
      </button>
    </>
  );
}
