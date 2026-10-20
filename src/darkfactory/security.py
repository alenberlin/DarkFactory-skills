"""Redact credential-shaped values before untrusted text reaches persistent records."""

import re

_SENSITIVE_NAME = re.compile(
    r"(?i)^(?:authorization|api[_-]?key|x-api-key|password|secret|(?:access|auth|refresh)[_-]?token|token)$"
)


def redact(text: str) -> str:
    """Remove common credential/header/URL/private-key forms without reading secret files.

    Args:
        text: Untrusted diagnostic or report text from a process, provider or operator.

    Returns:
        Text with recognizable sensitive values replaced. This is defense in depth;
        credential isolation and avoiding collection remain the primary controls.
    """
    text = re.sub(
        r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----[\s\S]*?"
        r"-----END (?:[A-Z]+ )*PRIVATE KEY-----",
        "[REDACTED PRIVATE KEY]",
        text,
    )
    text = re.sub(
        r"(?i)(authorization[\"']?\s*:\s*[\"']?(?:bearer|basic)\s+)[^\s\"',;]+",
        r"\1[REDACTED]",
        text,
    )
    names = r"(?:api[_-]?key|x-api-key|password|secret|(?:access|auth|refresh)[_-]?token|token)"
    text = re.sub(
        rf"(?i)([\"']?{names}[\"']?\s*[=:]\s*)([\"'])(.*?)\2",
        lambda match: match[1] + match[2] + "[REDACTED]" + match[2],
        text,
    )
    text = re.sub(
        rf"(?i)({names}\s*[=:]\s*)[^\s,;\"']+",
        r"\1[REDACTED]",
        text,
    )
    text = re.sub(r"(https?://)[^/\s:@]+:[^/\s@]+@", r"\1[REDACTED]@", text)
    return re.sub(r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,})\b", "[REDACTED]", text)


def redact_value(value: object) -> object:
    """Redact JSON-shaped values before encoding, preserving valid JSON and numeric accounting.

    Args:
        value: A nested report, list, primitive or diagnostic string.

    Returns:
        A separately constructed value with sensitive named fields and text redacted.
    """
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if _SENSITIVE_NAME.fullmatch(str(key)) else redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    return redact(value) if isinstance(value, str) else value
