from pathlib import Path

import anthropic
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()

PROMPT_PATH = Path(__file__).parent.parent.parent.parent / "prompts" / "summarize_issue.txt"


class SummarizeRequest(BaseModel):
    title: str
    body: str
    comments: list[str] = []


class SummarizeResponse(BaseModel):
    summary: str


def _render_prompt(title: str, body: str, comments: list[str]) -> str:
    template = PROMPT_PATH.read_text()
    comments_block = "\n".join(f"- {c}" for c in comments[:10]) if comments else ""
    return (
        template
        .replace("{{title}}", title)
        .replace("{{body}}", body[:1200])
        .replace("{{comments}}", comments_block)
        .replace("{% if comments %}", "")
        .replace("{% endif %}", "")
    )


@router.post("/summarize", response_model=SummarizeResponse)
def summarize(req: SummarizeRequest, request: Request):
    api_key = request.app.state.llm_api_key
    client = anthropic.Anthropic(api_key=api_key)

    prompt = _render_prompt(req.title, req.body, req.comments)

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return SummarizeResponse(summary=msg.content[0].text.strip())
