"""
Guards — the checks that catch THIS project's failure modes.

A guard earns its place only if it can fail on a realistic regression. Each one
below exists because the corresponding mistake was actually made during the
build, not because it sounded prudent.

  figures        v1 shipped hardcoded numbers in prose that drifted from the
                 engine. Every financial figure in docs/ must now be present in
                 the generated FIGURES.json.
  pinch_api      v1 documented `POST /merchants`. The real endpoint is
                 `POST /merchants/managed`. Wrong endpoints in docs become wrong
                 endpoints in code.
  money_type     Pinch is cents-integer. Float money silently loses precision
                 and reconciliation breaks days later.
  no_secrets     API keys and webhook secrets must never be committed.
  claims         Any yield or return figure asserted in docs must appear beside
                 a downside figure. Single-number yields are how this product
                 becomes misleading.
  skills         Skill files need valid front matter to load.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
ENGINE = ROOT / "engine"
SKILLS = ROOT / ".agents" / "skills"
FIGURES = ROOT / "engine" / "FIGURES.json"


class Failure(Exception):
    pass


def _md_files():
    files = list(DOCS.glob("*.md"))
    for extra in ("CLAUDE.md", "README.md"):
        f = ROOT / extra
        if f.exists():
            files.append(f)
    return files


# ---------------------------------------------------------------------------

def guard_figures():
    """Every $ figure and % figure in docs must be traceable to FIGURES.json
    or to an explicitly sourced market datum."""
    if not FIGURES.exists():
        raise Failure("FIGURES.json missing — run `python3 tools/check.py figures` first")
    known = set(json.loads(FIGURES.read_text())["all_strings"])

    # market data from external sources is allowed but must be on a SOURCED line
    sourced = re.compile(r"\[(src|source):", re.I)
    money = re.compile(r"\$\d[\d,]*(?:\.\d+)?(?<![,.])")
    pct = re.compile(r"\b\d+(?:\.\d+)?%")

    bad = []
    for f in _md_files():
        lines = f.read_text().splitlines()
        for i, line in enumerate(lines, 1):
            # a source tag anywhere in the surrounding two lines covers the claim
            window = "\n".join(lines[max(0, i - 3): i + 2])
            if sourced.search(window) or line.lstrip().startswith((">", "|", "```")):
                continue
            # a figure explicitly identified as wrong is the point of the sentence
            if re.search(r"(?i)\bnot\b|\bwrong\b|overstat|\berror\b|instead of|"
                         r"rather than|v1 ", line):
                continue
            for m in list(money.findall(line)) + list(pct.findall(line)):
                if m not in known:
                    bad.append(f"{f.relative_to(ROOT)}:{i}  {m}")
    if bad:
        raise Failure(
            "figures not traceable to the engine or to a [source:] line:\n  "
            + "\n  ".join(bad[:25])
            + (f"\n  ...and {len(bad)-25} more" if len(bad) > 25 else "")
        )


def guard_pinch_api():
    """Catch the endpoint and header mistakes that cost real debugging time."""
    wrong = {
        r"POST\s+/merchants(?!/managed)":
            "use POST /merchants/managed (create-managed-merchant)",
        r"POST\s+/plans/calculate":
            "use GET /plans/{id}/calculated-payments",
        r"GET\s+/payments/processed\b(?!.*paged)":
            "list-processed-payments is paged — say so",
        r"Current-Merchant:\s*mch_x\b":
            "use a realistic mch_ id, not a placeholder that looks like a header value",
    }
    bad = []
    for f in _md_files() + list(ENGINE.glob("*.py")):
        text = f.read_text()
        lines = text.splitlines()
        for pat, msg in wrong.items():
            for m in re.finditer(pat, text):
                ln = text[:m.start()].count("\n")
                line = lines[ln] if ln < len(lines) else ""
                # documenting a wrong pattern is allowed when the correction is
                # on the same line, or the line is flagged as the wrong column
                if re.search(r"(?i)\bnot\b|\bwrong\b|instead of|corrections?", line):
                    continue
                if "/merchants/managed" in line or "calculated-payments" in line:
                    continue
                if "paged" in line.lower():
                    continue
                bad.append(f"{f.relative_to(ROOT)}:{ln+1}  {m.group(0)!r} — {msg}")
    if bad:
        raise Failure("incorrect Pinch API usage:\n  " + "\n  ".join(bad))


def guard_money_type():
    """Money must be integer cents at every API boundary."""
    bad = []
    suspicious = re.compile(r"(amount|price|fee|principal)\s*(:|=)\s*\d+\.\d+")
    for f in list(ENGINE.glob("*.py")) + list((ROOT/"integration").glob("*.py")):
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if suspicious.search(line):
                bad.append(f"{f.relative_to(ROOT)}:{i}  {line.strip()}")
    if bad:
        raise Failure("float money found — Pinch amounts are integer cents:\n  "
                      + "\n  ".join(bad))


def guard_no_secrets():
    pats = {
        "Pinch secret key": r"\bsk_(live|test)_[A-Za-z0-9]{8,}",
        "webhook secret": r"\bwhsec_[A-Za-z0-9]{8,}",
        "bearer token": r"Authorization:\s*Bearer\s+[A-Za-z0-9._-]{20,}",
    }
    bad = []
    for f in list(ROOT.rglob("*.py")) + list(ROOT.rglob("*.md")) + list(ROOT.rglob("*.html")):
        if ".git" in f.parts:
            continue
        text = f.read_text(errors="ignore")
        for label, pat in pats.items():
            if re.search(pat, text):
                bad.append(f"{f.relative_to(ROOT)} — possible {label}")
    if bad:
        raise Failure("possible committed secret:\n  " + "\n  ".join(bad))


def guard_claims():
    """A yield figure without a downside figure nearby is how this product
    becomes misleading. Enforce that mechanically."""
    yield_words = re.compile(r"(net yield|investor (net|return)|p\.a\.)", re.I)
    downside_words = re.compile(
        r"(p1\b|p5\b|percentile|downside|worst|negativ|loss|lose|stress|tail|"
        r"at risk|scenario|distribution|risk|default|drag|fail)", re.I)
    bad = []
    for f in _md_files():
        lines = f.read_text().splitlines()
        for i, line in enumerate(lines):
            if not yield_words.search(line):
                continue
            window = "\n".join(lines[max(0, i - 12): i + 13])
            if not downside_words.search(window):
                bad.append(f"{f.relative_to(ROOT)}:{i+1}  yield claim with no downside within 12 lines")
    if bad:
        raise Failure("unbalanced return claims:\n  " + "\n  ".join(bad))


def guard_skills():
    bad = []
    for skill in sorted(SKILLS.iterdir()) if SKILLS.exists() else []:
        if not skill.is_dir() or skill.name.startswith("."):
            continue
        md = skill / "SKILL.md"
        if not md.exists():
            bad.append(f"{skill.name}: no SKILL.md")
            continue
        text = md.read_text()
        if not text.startswith("---"):
            bad.append(f"{skill.name}: missing front matter")
            continue
        fm = text.split("---")[1]
        for key in ("name:", "description:"):
            if key not in fm:
                bad.append(f"{skill.name}: front matter missing {key}")
        m = re.search(r"^name:\s*(\S+)", fm, re.M)
        if m and m.group(1) != skill.name:
            bad.append(f"{skill.name}: front-matter name is {m.group(1)!r}")
    if bad:
        raise Failure("skill registry invalid:\n  " + "\n  ".join(bad))


GUARDS = {
    "figures": guard_figures,
    "pinch_api": guard_pinch_api,
    "money_type": guard_money_type,
    "no_secrets": guard_no_secrets,
    "claims": guard_claims,
    "skills": guard_skills,
}


def run_all(only=None):
    failures = []
    for name, fn in GUARDS.items():
        if only and name not in only:
            continue
        try:
            fn()
            print(f"  ok    {name}")
        except Failure as e:
            print(f"  FAIL  {name}")
            failures.append(f"[{name}] {e}")
    if failures:
        print()
        for f in failures:
            print(f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(run_all(sys.argv[1:] or None))
