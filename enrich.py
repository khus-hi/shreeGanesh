"""
Scores a job description against your resumes, flags sponsorship language,
reads years of experience required, and (optionally) looks up H-1B history.
"""

import csv
import html
import json
import re
from pathlib import Path

from make_profiles import refresh_profiles
from skills import find_skills, weight

HERE = Path(__file__).parent
refresh_profiles()  # rebuilds from resumes/*.pdf when they change
PROFILES = json.loads((HERE / "resume_profiles.json").read_text())["resumes"]
ALL_MY_SKILLS = set().union(*map(set, PROFILES.values()))

TITLE_FIT = {
    "DA": re.compile(r"analyst|analytics|business intelligence|\bbi\b|insights|reporting", re.I),
    "DE": re.compile(r"data engineer|analytics engineer|etl|pipeline|data platform|data infrastructure|data integration", re.I),
    "DS": re.compile(r"scientist|machine learning|\bml\b|\bai\b|modeling|modeler|quantitative|research", re.I),
}


def clean_html(raw):
    text = re.sub(r"<(br|/p|/li|/div|/h\d)\s*/?>", "\n", raw or "", flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[ \t]+", " ", html.unescape(text))


# ---------------- years of experience ----------------
YEARS_RE = re.compile(
    r"(?:minimum of |at least |min\.? )?(\d{1,2})\s*(?:\+|plus)?\s*(?:(?:-|–|to)\s*\d{1,2}\s*\+?\s*)?(?:or more\s+)?years?",
    re.I,
)


def years_required(text):
    """Smallest 'N years ... experience' found (most lenient requirement), or None."""
    found = []
    for m in YEARS_RE.finditer(text):
        window = text[max(0, m.start() - 40): m.end() + 80].lower()
        n = int(m.group(1))
        if "experience" in window and 0 <= n <= 15:
            found.append(n)
    return min(found) if found else None


# ---------------- sponsorship ----------------
NO_SPONSOR = re.compile(
    r"(?:unable|not able|cannot|can ?not|will not|won'?t|does not|do not|is not able|are not able|not in a position)"
    r"\s+(?:\w+\s+){0,4}sponsor"
    r"|without\s+(?:\w+\s+){0,6}sponsorship"
    r"|no\s+(?:visa\s+|immigration\s+)?sponsorship"
    r"|not eligible for\s+(?:\w+\s+){0,2}sponsorship"
    r"|sponsorship\s+(?:is\s+)?not\s+(?:available|offered|provided)"
    r"|(?:must|required to)\s+be\s+(?:a\s+)?u\.?s\.?\s+citizens?"
    r"|u\.?s\.?\s+citizenship\s+(?:is\s+)?required"
    r"|green card holders?"
    r"|(?:secret|top secret|ts/sci|security)\s+clearance",
    re.I,
)
YES_SPONSOR = re.compile(
    r"(?:visa|h-?1b|immigration)\s+sponsorship\s+(?:is\s+)?(?:available|offered|provided)"
    r"|sponsorship\s+(?:is\s+)?available"
    r"|(?<!not )(?<!\w)(?:will|can|able to|happy to|open to)\s+sponsor"
    r"|consider(?:s|ed)?\s+(?:\w+\s+){0,2}sponsor",
    re.I,
)


def sponsorship(text):
    no, yes = NO_SPONSOR.search(text), YES_SPONSOR.search(text)
    if no and not yes:
        return "No", no.group(0)
    if yes and not no:
        return "Yes", yes.group(0)
    if yes and no:
        return "Check", no.group(0)
    return "Not mentioned", ""


# ---------------- H-1B history (optional) ----------------
_H1B = None
SUFFIX_RE = re.compile(r"\b(inc|llc|l\.l\.c|corp|corporation|co|company|ltd|lp|llp|plc|na|n\.a|the|holdings?|group)\b\.?", re.I)


def _norm(name):
    return re.sub(r"[^a-z0-9]", "", SUFFIX_RE.sub("", (name or "").lower()))


def _load_h1b():
    """Reads h1b_employers.csv (USCIS H-1B Employer Data Hub export) if present."""
    global _H1B
    if _H1B is not None:
        return _H1B
    _H1B = {}
    for f in sorted(HERE.glob("h1b*.csv")):
        with open(f, newline="", encoding="utf-8-sig", errors="ignore") as fh:
            reader = csv.DictReader(fh)
            cols = reader.fieldnames or []
            emp = next((c for c in cols if "employer" in c.lower()), None)
            appr = [c for c in cols if "approval" in c.lower()]
            if not emp:
                continue
            for row in reader:
                key = _norm(row.get(emp))
                if len(key) < 4:
                    continue
                n = sum(int(re.sub(r"\D", "", row.get(c) or "0") or 0) for c in appr)
                _H1B[key] = _H1B.get(key, 0) + n
    return _H1B


def h1b_history(*names):
    data = _load_h1b()
    if not data:
        return ""
    for name in names:
        n = _norm(name)
        if len(n) < 4:
            continue
        if n in data:
            return f"Yes ({data[n]:,})"
        hits = [v for k, v in data.items() if k.startswith(n) or n.startswith(k)]
        if hits:
            return f"Yes ({sum(hits):,})"
    return "Not found"


# ---------------- scoring ----------------
def score(title, text):
    jd_skills = find_skills(text)
    yrs = years_required(text)
    total = sum(weight(s) for s in jd_skills)
    results = {}
    for label, mine in PROFILES.items():
        mine = set(mine)
        coverage = (sum(weight(s) for s in jd_skills & mine) / total) if total else 0.5
        fit = 1.0 if TITLE_FIT.get(label, re.compile("$^")).search(title) else 0.0
        pct = 100 * (0.8 * coverage + 0.2 * fit)
        if yrs is not None and yrs >= 5:
            pct -= 20
        elif yrs is not None and yrs >= 3:
            pct -= 10
        results[label] = max(0, min(100, round(pct)))
    best = max(results, key=results.get)
    matched = sorted(jd_skills & set(PROFILES[best]), key=lambda s: -weight(s))
    missing = sorted(jd_skills - ALL_MY_SKILLS, key=lambda s: -weight(s))
    return {
        "match": results[best],
        "best_resume": best,
        "years": yrs,
        "matched": ", ".join(matched),
        "missing": ", ".join(missing),
    }
