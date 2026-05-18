import re

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

# Loaded once at startup via app.state.nlp
_VERSION_RE = re.compile(r"\bv?\d+\.\d+(?:\.\d+)*(?:[-+]\w+)?\b")
_GH_REF_RE = re.compile(r"#\d+|PR\s*#\d+|issue\s*#\d+", re.IGNORECASE)
_FILE_PATH_RE = re.compile(r"(?:[a-zA-Z]:[\\/]|\.{0,2}[/\\])[\w/\\.\-]+\.\w{1,6}")
_ERROR_CODE_RE = re.compile(r"\b[A-Z][A-Z_0-9]{2,}(?:Error|Exception|Warning)\b|\bE\d{3,4}\b")


class NERRequest(BaseModel):
    text: str


class Entity(BaseModel):
    text: str
    label: str
    start: int
    end: int


class NERResponse(BaseModel):
    entities: list[Entity]


@router.post("/ner", response_model=NERResponse)
def extract_entities(req: NERRequest):
    entities: list[Entity] = []
    seen: set[tuple[int, int]] = set()

    def add(text: str, label: str, start: int, end: int) -> None:
        if (start, end) not in seen:
            seen.add((start, end))
            entities.append(Entity(text=text, label=label, start=start, end=end))

    for m in _VERSION_RE.finditer(req.text):
        add(m.group(), "VERSION", m.start(), m.end())

    for m in _GH_REF_RE.finditer(req.text):
        add(m.group(), "GH_REF", m.start(), m.end())

    for m in _FILE_PATH_RE.finditer(req.text):
        add(m.group(), "FILE_PATH", m.start(), m.end())

    for m in _ERROR_CODE_RE.finditer(req.text):
        add(m.group(), "ERROR_CODE", m.start(), m.end())

    entities.sort(key=lambda e: e.start)
    return NERResponse(entities=entities)
