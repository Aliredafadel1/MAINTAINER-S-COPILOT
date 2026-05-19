import time

import torch
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()

LABELS = ["bug", "feature", "docs", "question"]

_LLM_SYSTEM = (
    "Classify the GitHub issue into exactly one of: bug, feature, docs, question.\n"
    "Reply with only the label — nothing else."
)


class ClassifyRequest(BaseModel):
    text: str


class ClassifyResponse(BaseModel):
    label: str
    confidence: float
    probabilities: dict[str, float]
    latency_ms: float


@router.post("/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest, request: Request):
    state = request.app.state

    if state.model is None:
        try:
            return classify_llm(req, request)
        except Exception:
            return ClassifyResponse(
                label="other",
                confidence=0.0,
                probabilities={lbl: 0.0 for lbl in LABELS},
                latency_ms=0.0,
            )

    with state.tracer.start_as_current_span(
        "classify", attributes={"model": state.model_name, "input_chars": len(req.text)}
    ):
        inputs = state.tokenizer(
            req.text, return_tensors="pt", truncation=True, max_length=512, padding=True
        )
        t0 = time.perf_counter()
        with torch.no_grad():
            logits = state.model(**inputs).logits
        latency_ms = (time.perf_counter() - t0) * 1000

        probs = torch.softmax(logits, dim=-1)[0].tolist()
        label_idx = int(torch.argmax(logits, dim=-1).item())
        return ClassifyResponse(
            label=LABELS[label_idx],
            confidence=round(probs[label_idx], 4),
            probabilities={lbl: round(p, 4) for lbl, p in zip(LABELS, probs)},
            latency_ms=round(latency_ms, 2),
        )


@router.post("/classify/classical", response_model=ClassifyResponse)
def classify_classical(req: ClassifyRequest, request: Request):
    pipeline = request.app.state.classical_pipeline
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Classical model not loaded")

    t0 = time.perf_counter()
    label = pipeline.predict([req.text])[0]
    latency_ms = (time.perf_counter() - t0) * 1000
    probs_arr = pipeline.predict_proba([req.text])[0]
    class_labels = pipeline.classes_
    probs = {lbl: round(float(p), 4) for lbl, p in zip(class_labels, probs_arr)}
    confidence = probs.get(label, 0.0)
    return ClassifyResponse(
        label=label,
        confidence=confidence,
        probabilities=probs,
        latency_ms=round(latency_ms, 2),
    )


@router.post("/classify/llm", response_model=ClassifyResponse)
def classify_llm(req: ClassifyRequest, request: Request):
    import anthropic
    api_key = request.app.state.llm_api_key
    client = anthropic.Anthropic(api_key=api_key)

    t0 = time.perf_counter()
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        system=_LLM_SYSTEM,
        messages=[{"role": "user", "content": req.text[:1000]}],
    )
    latency_ms = (time.perf_counter() - t0) * 1000
    raw = msg.content[0].text.strip().lower()
    label = raw if raw in LABELS else "other"
    return ClassifyResponse(
        label=label,
        confidence=1.0,
        probabilities={lbl: (1.0 if lbl == label else 0.0) for lbl in LABELS},
        latency_ms=round(latency_ms, 2),
    )
