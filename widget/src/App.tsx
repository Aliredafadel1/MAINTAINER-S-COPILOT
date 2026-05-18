import React, { useEffect, useRef, useState } from "react";

interface Props {
  widgetId: string;
  apiUrl: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function App({ widgetId, apiUrl }: Props) {
  const [open, setOpen] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function login() {
    const r = await fetch(`${apiUrl}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (r.ok) {
      const data = await r.json();
      setToken(data.access_token);
    } else {
      alert("Login failed");
    }
  }

  async function send() {
    if (!input.trim() || !token) return;
    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);

    const resp = await fetch(`${apiUrl}/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ message: userMsg, conversation_id: conversationId }),
    });

    let assistantText = "";
    const reader = resp.body!.getReader();
    const decoder = new TextDecoder();

    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      for (const line of chunk.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        try {
          const data = JSON.parse(line.slice(6));
          if (data.type === "text") {
            assistantText += data.text;
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = { role: "assistant", content: assistantText };
              return updated;
            });
          }
          if (data.type === "start" && data.conversation_id) {
            setConversationId(data.conversation_id);
          }
        } catch {}
      }
    }
    setLoading(false);
  }

  const styles: Record<string, React.CSSProperties> = {
    bubble: {
      position: "fixed", bottom: 24, right: 24, width: 56, height: 56,
      borderRadius: "50%", background: "#6366f1", color: "#fff",
      fontSize: 24, cursor: "pointer", border: "none",
      boxShadow: "0 4px 12px rgba(0,0,0,.25)", zIndex: 9999,
    },
    panel: {
      position: "fixed", bottom: 96, right: 24, width: 360, height: 520,
      background: "#fff", borderRadius: 12, boxShadow: "0 8px 32px rgba(0,0,0,.2)",
      display: "flex", flexDirection: "column", zIndex: 9998, overflow: "hidden",
    },
    header: { background: "#6366f1", color: "#fff", padding: "12px 16px", fontWeight: 600 },
    messages: { flex: 1, overflowY: "auto", padding: 12, display: "flex", flexDirection: "column", gap: 8 },
    userBubble: { alignSelf: "flex-end", background: "#6366f1", color: "#fff", padding: "8px 12px", borderRadius: "12px 12px 2px 12px", maxWidth: "80%", fontSize: 14 },
    asstBubble: { alignSelf: "flex-start", background: "#f3f4f6", color: "#111", padding: "8px 12px", borderRadius: "12px 12px 12px 2px", maxWidth: "80%", fontSize: 14 },
    inputRow: { display: "flex", borderTop: "1px solid #e5e7eb", padding: 8, gap: 8 },
    inputField: { flex: 1, border: "1px solid #d1d5db", borderRadius: 8, padding: "6px 10px", fontSize: 14, outline: "none" },
    sendBtn: { background: "#6366f1", color: "#fff", border: "none", borderRadius: 8, padding: "6px 12px", cursor: "pointer", fontSize: 14 },
  };

  return (
    <>
      <button style={styles.bubble} onClick={() => setOpen((o) => !o)} aria-label="Open chat">
        {open ? "✕" : "💬"}
      </button>

      {open && (
        <div style={styles.panel}>
          <div style={styles.header}>Maintainer's Copilot</div>

          {!token ? (
            <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 8 }}>
              <input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} style={styles.inputField} />
              <input placeholder="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} style={styles.inputField} />
              <button onClick={login} style={styles.sendBtn}>Login</button>
            </div>
          ) : (
            <>
              <div style={styles.messages}>
                {messages.map((m, i) => (
                  <div key={i} style={m.role === "user" ? styles.userBubble : styles.asstBubble}>
                    {m.content || (loading && i === messages.length - 1 ? "…" : "")}
                  </div>
                ))}
                <div ref={bottomRef} />
              </div>
              <div style={styles.inputRow}>
                <input
                  style={styles.inputField}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
                  placeholder="Ask about an issue…"
                  disabled={loading}
                />
                <button style={styles.sendBtn} onClick={send} disabled={loading}>
                  {loading ? "…" : "Send"}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}
