#!/usr/bin/env bash
# Maintainer's Copilot — 10-minute Friday demo script
# Run from the repo root: bash demo/demo.sh
set -euo pipefail

API="http://localhost:8000"
MODELSERVER="http://localhost:8001"

# Colors
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
step() { echo -e "\n${GREEN}[STEP $1]${NC} $2"; }
note() { echo -e "${YELLOW}  ▶ $1${NC}"; }

# ─────────────────────────────────────────────────────────────
step 1 "Stack startup — docker compose up (should all be healthy)"
note "Run: docker compose up --build"
note "Wait for api log: startup_complete"
echo "  Verify: curl -s $API/health | jq ."
curl -sf "$API/health" | python3 -m json.tool || { echo "API not healthy — is the stack up?"; exit 1; }
echo ""
echo "All services healthy. Open Jaeger UI: http://localhost:16686"

# ─────────────────────────────────────────────────────────────
step 2 "Classify an issue — show trace tree in Jaeger"
note "Classifying a real issue via modelserver..."
CLASSIFY_RESULT=$(curl -sf -X POST "$MODELSERVER/classify" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Pipeline crashes on MPS device with batch_size > 1",
    "body": "On Apple Silicon with device=mps, text-classification raises RuntimeError on any batch > 1. Works fine on CPU."
  }')
echo "  Result: $CLASSIFY_RESULT"
note "Now open Jaeger UI → search service: api → find /classify span → show parent/child tree"

# ─────────────────────────────────────────────────────────────
step 3 "RAG question — show retrieved chunks"
note "Registering user and asking a RAG question..."

# Register (first user → admin)
TOKEN=$(curl -sf -X POST "$API/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "demo@example.com", "password": "demopass123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "  Token: ${TOKEN:0:30}..."

RAG_RESULT=$(curl -sf -X POST "$API/rag/search" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "How do I load a model in 8-bit on CPU?", "top_k": 3}')
echo "  Top chunks:"
echo "$RAG_RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for r in data['results']:
    print(f\"  [{r['source_type']}:{r['source_id']}] score={r['score']:.3f}\")
    print(f\"  {r['content'][:120]}...\")
    print()
"

# ─────────────────────────────────────────────────────────────
step 4 "Chat + write_memory — show cross-session recall"
note "Starting a chat conversation and writing a memory..."
CHAT_RESULT=$(curl -sf -X POST "$API/chat/stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Remember that this project uses a monorepo structure with api/ and modelserver/ as separate services."}' \
  --no-buffer | grep '"type":"text"' | python3 -c "
import sys, json
text = ''
for line in sys.stdin:
    line = line.strip()
    if line.startswith('data: '):
        try:
            d = json.loads(line[6:])
            if d.get('type') == 'text':
                text += d['text']
        except: pass
print(text[:300])
" 2>/dev/null || echo "  (stream response — check Streamlit UI for full output)")

note "Check long-term memory was saved:"
curl -sf "$API/memory" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -20

# ─────────────────────────────────────────────────────────────
step 5 "Widget loading on allowed origin"
note "Create a widget with localhost:3000 as allowed origin..."
WIDGET=$(curl -sf -X POST "$API/widgets" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Demo Widget", "allowed_origins": ["http://localhost:3000"]}')
WIDGET_ID=$(echo "$WIDGET" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "  Widget ID: $WIDGET_ID"

# Update demo host with real widget ID
sed -i "s/YOUR_WIDGET_ID/$WIDGET_ID/g" demo/host/index.html 2>/dev/null || true
echo "  Open http://localhost:3000 — widget should load (CSP allows localhost:3000)"

# ─────────────────────────────────────────────────────────────
step 6 "Widget blocked on disallowed origin"
note "Widget config sets CSP frame-ancestors http://localhost:3000"
note "Opening demo/host/index.html from file:// or a different port will show:"
note "  Refused to frame '...' because an ancestor violates the following CSP directive"
echo "  Config endpoint: curl $API/widgets/$WIDGET_ID/config"
curl -sf "$API/widgets/$WIDGET_ID/config" | python3 -m json.tool

# ─────────────────────────────────────────────────────────────
step 7 "Jaeger trace tree — full conversation"
note "Open http://localhost:16686"
note "Service: api → Operation: POST /chat/stream"
note "Show: rag.search span → retrieval.rewrite → retrieval.embed → retrieval.rerank"
note "Show: tool.classify_issue child span with model + latency attributes"

# ─────────────────────────────────────────────────────────────
step 8 "CI green + eval report diff"
note "Run classifier eval (requires modelserver):"
echo "  python evals/eval_classifier.py --skip-minio"
note "Run RAG eval (requires api + PG):"
echo "  python evals/eval_rag.py"
note "Last green build report:"
ls -la evals/results/ 2>/dev/null || echo "  (run evals first)"

# ─────────────────────────────────────────────────────────────
step 9 "Live architecture extension — add a new tool"
note "The grader will ask you to add a new tool. Here is the pattern:"
cat <<'EOF'
  # 1. Add to app/services/tools.py tool_definitions():
  {
    "name": "get_contributor_info",
    "description": "Look up a GitHub contributor's recent activity.",
    "input_schema": {"type": "object", "properties": {"username": {"type": "string"}}, "required": ["username"]}
  }

  # 2. Add to dispatch():
  if tool_name == "get_contributor_info":
      return json.dumps({"username": tool_input["username"], "recent_issues": 5})

  # 3. Restart api:
  docker compose restart api
  # New tool is live — chatbot will use it automatically.
EOF

echo -e "\n${GREEN}Demo complete.${NC}"
