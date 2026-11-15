"""Pattern-based redaction, not a general data-loss-prevention guarantee."""
import re

PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "credential": re.compile(r"(?i)\b(?:api[_ -]?key|access[_ -]?token|password|client[_ -]?secret)\s*[:=]\s*[\"']?[^\s\"',;}{]{8,}"),
    "bearer_token": re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{16,}"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
}


def redact(text):
    counts = {}
    for name, pattern in PATTERNS.items():
        text, count = pattern.subn(f"[REDACTED_{name.upper()}]", text)
        if count:
            counts[name] = count
    return text, counts

