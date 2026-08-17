#!/usr/bin/env python3
"""Verify a generated scoping doc against the evidence it claims to come from.

With no scoping.docx to anchor against, citation discipline is the only thing
between a scoping doc and confident fiction. This checks the mechanical parts.

Usage:
  check_scoping.py <prospect folder> [scoping file]

Defaults to <folder>/scoping.generated.md, falling back to scoping.md.
Exit 0 when clean, 1 when anything is unsupported. Treat findings as blocking.
"""

import re
import sys
from pathlib import Path

SCOPE_HEADINGS = ("scope for this build", "use case", "data shape")
QUARANTINE = "mentioned on calls"
CITATION = re.compile(r"\((?:[^()]*\d{4}-\d{2}-\d{2}[^()]*|[^()]*\.(?:lkml|csv|json|yaml|yml|sql|md|txt)[^()]*)\)")
TABLE_TOKEN = re.compile(r"\b((?:dim|fct|fact|stg|ref|raw|agg)_[a-z0-9_]+)\b", re.I)
# "Firstname Lastname" — the shape a fabricated stakeholder takes.
PERSON = re.compile(r"\b([A-Z][a-z]{2,})\s+([A-Z][a-z]{2,})\b")

STOPWORDS = {
    "Data Review", "Open Questions", "Out Of", "Sigma Computing", "Deal Logistics",
    "Use Case", "Data Shape", "Prospect Console", "Input Table", "Row Level",
    "Google Cloud", "Power Bi", "Big Query", "Already Built", "First Pass",
}


def sections(text):
    """Split markdown into (heading, body) pairs."""
    out, heading, buf = [], "", []
    for line in text.splitlines():
        if line.startswith("## "):
            out.append((heading, "\n".join(buf)))
            heading, buf = line[3:].strip(), []
        else:
            buf.append(line)
    out.append((heading, "\n".join(buf)))
    return out


def join_wrapped(body):
    """Bullets, with hard-wrapped continuation lines folded back in.

    These docs are written at ~78 columns, so a citation routinely lands on the
    second physical line of a bullet. Checking line-by-line reports those as
    uncited — a false positive that sends the writer chasing ghosts.
    """
    bullets, current = [], None
    for line in body.splitlines():
        stripped = line.strip()
        if re.match(r"^[-*]\s|^\d+\.\s", stripped):
            if current:
                bullets.append(current)
            current = stripped
        elif current is not None:
            if not stripped or stripped.startswith("#"):
                bullets.append(current)
                current = None
            else:
                current += " " + stripped
    if current:
        bullets.append(current)
    return bullets


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    folder = Path(sys.argv[1])
    if len(sys.argv) > 2:
        doc = Path(sys.argv[2])
    else:
        doc = folder / "scoping.generated.md"
        if not doc.exists():
            doc = folder / "scoping.md"

    if not doc.exists():
        print(f"error: no scoping doc at {doc}")
        return 2

    text = doc.read_text(encoding="utf-8")

    # The evidence: transcripts plus every artifact in the folder.
    evidence = []
    for pattern in ("context_*.txt", "**/*.lkml", "**/*.csv", "**/*.json",
                    "**/*.yaml", "**/*.yml", "**/*.sql", "reference/**/*"):
        for path in folder.glob(pattern):
            if path.is_file() and path.name != doc.name and not path.name.startswith(".env"):
                try:
                    evidence.append(path.read_text(encoding="utf-8", errors="ignore"))
                except OSError:
                    pass
    corpus = "\n".join(evidence)
    # Match case-insensitively: transcripts are conversational, so a doc's
    # "National Debt Relief" appears there as "national debt relief".
    corpus_low = corpus.lower()

    if not corpus.strip():
        print(f"warn: no evidence files found under {folder} — nothing to verify against")

    findings = []

    # 1. Every load-bearing section is sourced — either per bullet, or at the
    #    section level via a "(from X)" heading or a source line in the body.
    #    Both existing docs use section-level sourcing, which is a legitimate
    #    discipline; what matters is that a reader can trace the claims.
    has_provenance = bool(re.search(r"^>\s*Source:", text, re.M))
    for heading, body in sections(text):
        low = heading.lower()
        if not any(low.startswith(h) for h in SCOPE_HEADINGS):
            continue

        sourced_heading = bool(re.search(r"\((?:from|per|source:)\s", heading, re.I))
        sourced_body = bool(re.search(r"^\s*[>*_-]?\s*(source|from|per)\b.*:", body, re.M | re.I))
        bullets = [b for b in join_wrapped(body) if len(b) >= 25]
        cited = sum(1 for b in bullets if CITATION.search(b))

        if sourced_heading or sourced_body or not bullets:
            continue
        # Provenance header alone covers a section only if nothing in it is
        # traceable; a section with some cited bullets should cite them all.
        if cited == 0 and has_provenance:
            continue
        if cited < len(bullets):
            for b in bullets:
                if not CITATION.search(b):
                    findings.append(f"uncited in '{heading}': {b[:88]}")

    # 2. Every person named appears in the evidence.
    quarantined = "\n".join(b for h, b in sections(text) if QUARANTINE in h.lower())
    for first, last in set(PERSON.findall(text)):
        name = f"{first} {last}"
        if name in STOPWORDS or name in quarantined:
            continue
        if first.lower() not in corpus_low and last.lower() not in corpus_low:
            findings.append(f"person not found in any transcript or artifact: {name}")

    # 3. Every table-looking token appears in the evidence.
    for table in sorted(set(m.lower() for m in TABLE_TOKEN.findall(text))):
        if table not in corpus_low:
            findings.append(f"table not found in any transcript or artifact: {table}")

    # 4. Provenance header present.
    if not re.search(r"^>\s*[*_]*\s*Source\b", text, re.M | re.I):
        findings.append("missing '> Source:' provenance header")

    print(f"checked {doc}  ({len(text.splitlines())} lines, {len(evidence)} evidence files)")
    if not findings:
        print("clean — every claim is supported")
        return 0

    print(f"\n{len(findings)} finding(s):")
    for f in findings:
        print(f"  - {f}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
