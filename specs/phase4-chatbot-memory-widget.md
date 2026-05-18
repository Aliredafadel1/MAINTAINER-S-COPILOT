# Phase 4 — Chatbot + Memory + Embeddable Widget
**Day:** Thursday  
**Goal:** A fully authenticated tool-calling chatbot with short- and long-term memory, a Streamlit admin UI, a standalone React widget bundle, and a working demo host app. Both eval suites wired into CI.

---

## Deliverables

### 1. Authentication (`api`)
Using `fastapi-users` with JWT:
- `POST /auth/register` — email + password
- `POST /auth/login` — returns JWT
- JWT signing key resolved from Vault at startup (never from `.env`)
- Two roles: `user` and `admin`
  - `admin` can: invite users, configure widgets, view audit log
  - `user` can: chat, write memories, view own conversations
- Role stored in JWT claims and in `users` table
- `POST /auth/invite` (admin only) — generates a one-time registration token

### 2. Tool-Calling Chatbot (`api`)
A **single LLM** that picks tools — not a workflow, not a multi-agent system.

**Tools available to the LLM:**
| Tool | Calls | Description |
|---|---|---|
| `classify_issue` | `POST modelserver/classify` | Classify an issue text |
| `extract_entities` | `POST modelserver/ner` | Extract code entities from text |
| `summarize_thread` | `POST modelserver/summarize` | Summarize an issue thread |
| `search_docs` | `retrieval.py` | RAG search over docs + resolved issues |
| `write_memory` | `memories` table | Explicit long-term memory write (no auto-writes) |

- Prompts as files in `prompts/`:
  - `prompts/system.txt` — main system prompt
  - `prompts/tool_descriptions.txt` — tool descriptions injected at runtime
- Every tool call emits a span: tool name, inputs (after redaction), outputs (after redaction), latency
- Tool failures are caught: if `modelserver` is down, the chatbot responds with a graceful degradation message — never a 500

### 3. Short-Term Memory (Redis)
In `app/services/memory_short.py`:
- Stores conversation message history keyed by `conversation_id`
- TTL: choose a value (e.g., 2 hours for active sessions), justify in `DECISIONS.md`
- On TTL expiry: conversation history is gone from Redis; long-term memories persist in Postgres
- `GET /conversations/{id}/messages` reads from Redis first, falls back to Postgres

### 4. Long-Term Memory (Postgres + pgvector)
In `app/services/memory_long.py`:
- Memory type: choose one of `episodic | semantic | procedural`; defend the choice in `DECISIONS.md`
  - **Episodic:** stores specific past interactions ("User reported a bug with pandas 2.0 on 2026-05-15")
  - **Semantic:** stores extracted facts ("User is a maintainer of repo X", "User prefers concise answers")
  - **Procedural:** stores how-to patterns ("When user asks about CI failures, always check the classifier eval first")
- Every `write_memory` tool call:
  - Embeds the memory content
  - Upserts into `memories` table with `user_id`, `memory_type`, `content`, `embedding`, `created_at`
  - Writes an audit log row: `{actor: user_id, action: "write_memory", target: memory_id, timestamp}`
- Memory retrieval: semantic search over `memories` for the current user, injected into system prompt context
- Cross-conversation recall: memories from past conversations surface in new ones (demo this on Friday)

### 5. Streamlit App (`chatbot`)
Pages:
1. **Login / Register** — calls `api` auth endpoints
2. **Chat** — full chat UI, shows tool calls in an expander, streams responses
3. **Memory Inspector** — lists current user's long-term memories; admin can view any user's memories
4. **Widget Config** (admin only) — create/edit widget configs, shows generated embed snippet
5. **Audit Log** (admin only) — paginated view of the audit log table

### 6. Widget Configuration (Postgres)
`widgets` table (already scaffolded in Phase 1 migration), extended:
- `widget_id`: public UUID (used in the loader script)
- `allowed_origins`: `text[]` — CORS and CSP allowlist
- `theme`: `jsonb` — `{primary_color, position}`
- `greeting`: `text`
- `enabled_tools`: `text[]` — subset of available tools
- Admin creates/edits via the Streamlit config page
- `GET /api/widgets/{widget_id}/config` — public endpoint returning theme, greeting, enabled tools (no secrets)

### 7. React Widget (`widget` service)
Built with Vite, output to a single `widget.bundle.js`:
- **UI:** collapsed bubble → expanded chat panel, input box, streamed message rendering
- **Styling:** Tailwind CSS or vanilla CSS; theme (primary color, position) applied at runtime from widget config
- Calls `POST /api/chat` with the JWT (obtained via a widget-specific auth flow or anonymous session token)
- One `postMessage` channel to the host: at minimum for iframe height resize
- Bundle served from MinIO (or the `widget` static server) with `Cache-Control: public, max-age=86400`
- **Bundle size target:** ≤ 150KB gzipped; report actual size in the submission block

### 8. Loader Script (`/widget.js`)
Served from `api` or the `widget` static server:
```js
// Host pastes:
// <script src="https://your-api/widget.js" data-widget-id="abc-123"></script>
```
- Reads `data-widget-id` from the script tag
- Injects an `<iframe>` pointing at the React widget bundle URL
- Passes `widget_id` as a query param so the widget fetches its own config

### 9. Origin Allowlisting (CORS + CSP)
- `api` CORS middleware reads `allowed_origins` from the `widgets` table, **not** from a hardcoded env var
- The embed route (`GET /embed`) sets `Content-Security-Policy: frame-ancestors <allowed_origins>`
- Unallowed host origins are blocked by the browser (no API change needed — the browser enforces CSP)
- Friday demo: show widget loading on allowed host → show it blocked on a disallowed host (use browser DevTools)

### 10. Demo Host App (`demo/host/`)
- A single `index.html` page that embeds the widget via the loader script
- Served by the `host` nginx container
- This is what runs on Friday for the live demo

### 11. CI — Both Eval Suites
`.github/workflows/ci.yml` (or equivalent):
```
on: push
jobs:
  ci:
    steps:
      - lint (ruff / eslint)
      - type-check (mypy / tsc)
      - build images
      - docker-compose up (smoke test)
      - pytest evals/eval_classifier.py   # exits non-zero on regression
      - pytest evals/eval_rag.py          # exits non-zero on regression
      - pytest tests/test_redaction.py    # exits non-zero if redaction broken
      - store eval_report.json to MinIO
      - diff eval_report.json vs previous green build; fail if any metric regressed below threshold
```
- Thresholds in `eval_thresholds.yaml` — committed to the repo, never zero
- `eval_report.json` written every run, stored in MinIO `ci-reports/`

---

## Acceptance Criteria
- [ ] `POST /auth/register` + `POST /auth/login` returns a valid JWT
- [ ] Chatbot uses the JWT signing key from Vault (not `.env`)
- [ ] At least 3 tools callable from the chat (classify, search_docs, write_memory)
- [ ] `write_memory` creates an audit log row in Postgres
- [ ] Long-term memory surfaces in a new conversation (cross-conversation recall demo)
- [ ] Streamlit memory inspector shows stored memories for logged-in user
- [ ] Admin can create a widget config in the Streamlit UI and get a valid embed snippet
- [ ] Widget loads in `demo/host/index.html` and sends/receives a chat message
- [ ] Widget is blocked on a host not in `allowed_origins` (CSP enforced)
- [ ] Both `evals/eval_classifier.py` and `evals/eval_rag.py` run in CI on push
- [ ] Widget bundle size reported (target ≤ 150KB gzipped)

---

## Dependencies
- Phase 1: auth scaffold, Vault, Redis, Postgres, audit log table
- Phase 2: `modelserver` running with `/classify`, `/ner`, `/summarize`
- Phase 3: `retrieval.py`, redaction layer, pgvector embeddings

---

## Key Files to Create
- `app/api/routes/auth.py`, `chat.py`, `widgets.py`, `memory.py`
- `app/services/chatbot.py` (tool-calling loop)
- `app/services/memory_short.py`, `app/services/memory_long.py`
- `app/services/tools.py` (tool registry)
- `chatbot/app.py` (Streamlit entry point)
- `chatbot/pages/` (login, chat, memory inspector, widget config, audit log)
- `widget/src/` (React app)
- `widget/vite.config.ts`
- `demo/host/index.html`
- `services/widget/` (static server or nginx config)
- `public/widget.js` (loader script)
- `.github/workflows/ci.yml`
- `eval_thresholds.yaml` (finalize thresholds)
- `prompts/system.txt`, `prompts/tool_descriptions.txt`
- New Alembic migration: any schema additions from this phase
