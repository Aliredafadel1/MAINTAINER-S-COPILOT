import re

# Patterns are documented and justified in SECURITY.md.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "api_key",
        re.compile(r"(sk|gh[ps]|ghs|ghp|xox[bpoa])[-_][A-Za-z0-9\-_]{10,}", re.I),
    ),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+")),
    ("email", re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z0-9]+")),
    ("basic_auth", re.compile(r"(?i)authorization:\s*basic\s+[A-Za-z0-9+/=]+")),
    ("db_url", re.compile(r"(?i)postgresql://[^@\s]+:[^@\s]+@")),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
]

_PLACEHOLDER = "[REDACTED]"


def redact(text: str) -> str:
    for _, pattern in _PATTERNS:
        text = pattern.sub(_PLACEHOLDER, text)
    return text


def redact_dict(data: dict) -> dict:
    """Redact string values in a flat dict (for span attributes, log fields)."""
    return {k: redact(v) if isinstance(v, str) else v for k, v in data.items()}
