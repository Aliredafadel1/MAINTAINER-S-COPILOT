"""Anthropic tool definitions and dispatch for the chatbot loop."""

import json
import os
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import memory_long, retrieval


def tool_definitions() -> list[dict]:
    return [
        {
            "name": "classify_issue",
            "description": "Classify a GitHub issue into a label (bug, feature, docs, question, other).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["title", "body"],
            },
        },
        {
            "name": "extract_entities",
            "description": "Extract structured entities from issue text (versions, file paths, error codes, GitHub refs).",
            "input_schema": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
        {
            "name": "summarize_thread",
            "description": "Summarize a long GitHub issue or PR thread into a concise paragraph.",
            "input_schema": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
        {
            "name": "search_docs",
            "description": "Semantic search over the project's documentation and issue corpus.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
        {
            "name": "write_memory",
            "description": "Persist a piece of information to long-term memory for future sessions.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "memory_type": {"type": "string", "default": "semantic"},
                },
                "required": ["content"],
            },
        },
    ]


def _modelserver_url() -> str:
    return os.environ.get("MODELSERVER_URL", "http://modelserver:8001")


async def dispatch(
    tool_name: str,
    tool_input: dict,
    session: AsyncSession,
    user_id: UUID,
) -> str:
    from app.infra.redaction import redact
    from app.infra.tracing import span

    base = _modelserver_url()

    if tool_name == "classify_issue":
        text = f"{tool_input.get('title', '')}\n{tool_input.get('body', '')}"
        with span(
            "tool.classify_issue", title=redact(tool_input.get("title", "")[:100])
        ):
            try:
                async with httpx.AsyncClient(timeout=10) as http:
                    resp = await http.post(f"{base}/classify", json={"text": text})
                    resp.raise_for_status()
                    data = resp.json()
            except Exception as exc:
                return json.dumps({"error": f"Classifier unavailable: {exc}"})
        return json.dumps(data)

    if tool_name == "extract_entities":
        with span("tool.extract_entities"):
            try:
                async with httpx.AsyncClient(timeout=10) as http:
                    resp = await http.post(
                        f"{base}/ner", json={"text": tool_input["text"]}
                    )
                    resp.raise_for_status()
                    data = resp.json()
            except Exception as exc:
                return json.dumps({"error": f"NER unavailable: {exc}"})
        return json.dumps(data)

    if tool_name == "summarize_thread":
        with span("tool.summarize_thread", text_len=len(tool_input.get("text", ""))):
            try:
                async with httpx.AsyncClient(timeout=30) as http:
                    resp = await http.post(
                        f"{base}/summarize",
                        json={"title": "", "body": tool_input["text"], "comments": []},
                    )
                    resp.raise_for_status()
                    data = resp.json()
            except Exception as exc:
                return f"Summarizer unavailable: {exc}"
        return data.get("summary", "")

    if tool_name == "search_docs":
        query = tool_input["query"]
        top_k = tool_input.get("top_k", 5)
        with span("tool.search_docs", query=redact(query[:200]), top_k=top_k) as s:
            try:
                chunks = await retrieval.search(session, query=query, top_k=top_k)
            except Exception as exc:
                return f"Search unavailable: {exc}"
            s.set_attribute("tool.search_docs.results", len(chunks))
        snippets = [
            f"[{c.source_type}:{c.source_id}] {c.content[:300]}" for c in chunks
        ]
        return "\n\n".join(snippets) if snippets else "No results found."

    if tool_name == "write_memory":
        with span(
            "tool.write_memory", memory_type=tool_input.get("memory_type", "semantic")
        ):
            try:
                await memory_long.save(
                    session,
                    user_id=user_id,
                    content=tool_input["content"],
                    memory_type=tool_input.get("memory_type", "semantic"),
                )
            except Exception:
                return "Memory save failed (embedding service unavailable)."
        return "Memory saved."

    return f"Unknown tool: {tool_name}"
