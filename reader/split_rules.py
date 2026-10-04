"""Split a trial's eligibility prose into one rule per bullet.

Registry text is inconsistent. Some trials have a heading on its own
line, some bury the words in a paragraph, some have no heading.
Measure the miss rather than assuming a clean split.

The system does not say a patient qualifies.
"""

from __future__ import annotations

import re

from reader.schema import Rule

INCLUSION_HEADER = re.compile(
    r"(?im)^[ \t]*(?:key[ \t]+)?inclusion[ \t]+criteria[ \t]*:?[ \t]*$"
)
EXCLUSION_HEADER = re.compile(
    r"(?im)^[ \t]*(?:key[ \t]+)?exclusion[ \t]+criteria[ \t]*:?[ \t]*$"
)
INCLUSION_LOOSE = re.compile(r"(?i)inclusion[ \t]+criteria")
EXCLUSION_LOOSE = re.compile(r"(?i)exclusion[ \t]+criteria")
HEADER_ONLY = re.compile(
    r"(?i)^(key\s+)?(inclusion|exclusion)\s+criteria:?$|^eligibility\s+criteria:?$"
)
BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.*)$")


def split_sections(text: str) -> dict[str, str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    exclusion = EXCLUSION_HEADER.search(text)
    inclusion = INCLUSION_HEADER.search(text)
    if exclusion:
        cut = exclusion.start()
        return {"mode": "line_header", "inclusion": text[:cut], "exclusion": text[cut:]}
    loose_ex = EXCLUSION_LOOSE.search(text)
    if loose_ex:
        cut = loose_ex.start()
        return {"mode": "loose_header", "inclusion": text[:cut], "exclusion": text[cut:]}
    return {"mode": "no_header", "inclusion": text, "exclusion": ""}


def _unwrap(text: str) -> str:
    """Join soft-wrapped registry lines. Keep blank lines as paragraph breaks."""
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n")]
    out: list[str] = []
    buf = ""
    for ln in lines:
        if not ln:
            if buf:
                out.append(buf)
                buf = ""
            out.append("")
            continue
        if BULLET.match(ln) or HEADER_ONLY.match(ln):
            if buf:
                out.append(buf)
            buf = ln
            continue
        if not buf:
            buf = ln
        elif BULLET.match(buf) or buf.endswith(("-", "—")):
            buf = buf.rstrip("-— ") + " " + ln
        else:
            buf = buf + " " + ln
    if buf:
        out.append(buf)
    return "\n".join(out)


def _bullets(text: str, section: str, prefix: str) -> list[Rule]:
    text = _unwrap(text)
    chunks: list[str] = []
    current = ""
    for ln in text.split("\n"):
        stripped = ln.strip()
        if HEADER_ONLY.match(stripped):
            continue
        m = BULLET.match(stripped)
        if m:
            if current.strip():
                chunks.append(current.strip())
            current = m.group(1).strip()
            continue
        if not stripped:
            if current.strip():
                chunks.append(current.strip())
                current = ""
            continue
        current = (current + " " + stripped).strip() if current else stripped
    if current.strip():
        chunks.append(current.strip())

    rules = []
    n = 0
    for chunk in chunks:
        chunk = re.sub(r"\s+", " ", chunk).strip(" -")
        if len(chunk) < 12:
            continue
        if HEADER_ONLY.match(chunk):
            continue
        n += 1
        rules.append(Rule(rule_id=f"{prefix}_{n:02d}", section=section, text=chunk))
    return rules


def split_rules(eligibility: str) -> list[Rule]:
    """Return inclusion rules then exclusion rules. Empty input is empty."""
    if not (eligibility or "").strip():
        return []
    parts = split_sections(eligibility)
    if parts["mode"] == "no_header":
        return _bullets(parts["inclusion"], "unsplit", "u")
    inc = _bullets(parts["inclusion"], "inclusion", "inc")
    exc = _bullets(parts["exclusion"], "exclusion", "exc")
    return inc + exc
