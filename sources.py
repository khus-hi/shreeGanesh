"""
Greenhouse, Lever and Ashby job boards (free public JSON APIs).

companies.txt lines that use these platforms look like:
  https://boards.greenhouse.io/airbnb
  https://jobs.lever.co/palantir
  https://jobs.ashbyhq.com/openai
"""

import html
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

# discovery: link from Google -> canonical board URL
BOARD_PATTERNS = [
    (re.compile(r"https?://(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board\?for=)?([\w-]+)", re.I),
     "https://boards.greenhouse.io/{}"),
    (re.compile(r"https?://jobs\.lever\.co/([\w.-]+)", re.I), "https://jobs.lever.co/{}"),
    (re.compile(r"https?://jobs\.ashbyhq\.com/([\w.%-]+)", re.I), "https://jobs.ashbyhq.com/{}"),
]
SKIP_SLUGS = {"embed", "jobs", "api", "v1", "search"}


def board_from_link(link):
    for rx, fmt in BOARD_PATTERNS:
        m = rx.match(link or "")
        if m and m.group(1).lower() not in SKIP_SLUGS:
            return fmt.format(m.group(1))
    return None


def platform(url):
    host = urlparse(url).netloc.lower()
    if "myworkdayjobs.com" in host:
        return "workday"
    if "greenhouse.io" in host:
        return "greenhouse"
    if "lever.co" in host:
        return "lever"
    if "ashbyhq.com" in host:
        return "ashby"
    return None


def site_key(url):
    """Unique id for a company board (Workday = host, others = host + slug)."""
    u = urlparse(url.strip())
    if "myworkdayjobs.com" in u.netloc:
        return u.netloc.lower()
    slug = [p for p in u.path.split("/") if p][:1]
    return (u.netloc.lower() + "/" + (slug[0].lower() if slug else ""))


def _slug(url):
    return [p for p in urlparse(url).path.split("/") if p][0]


def _age_days(ts):
    """ISO string or epoch-ms -> days since posted."""
    if ts is None:
        return 99
    try:
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return 99


def _iso(ts):
    """ISO string or epoch-ms -> UTC ISO string ('' if unknown)."""
    if ts is None:
        return ""
    try:
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat(timespec="minutes").replace("+00:00", "Z")
    except Exception:
        return ""


def _posted_label(days):
    return "Posted Today" if days == 0 else "Posted Yesterday" if days == 1 else f"Posted {days} Days Ago"


def fetch_board(url, keep_title, max_days):
    """Returns candidate jobs (title + date already filtered)."""
    kind = platform(url)
    slug = _slug(url)
    out = []

    if kind == "greenhouse":
        r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", headers=UA, timeout=30)
        r.raise_for_status()
        for j in r.json().get("jobs", []):
            days = _age_days(j.get("first_published") or j.get("updated_at"))
            if days <= max_days and keep_title(j.get("title", "")):
                out.append({
                    "source": "Greenhouse", "company": slug, "title": j["title"],
                    "location": (j.get("location") or {}).get("name", ""),
                    "posted": _posted_label(days), "url": j.get("absolute_url"),
                    "posted_at": _iso(j.get("first_published")),
                    "detail_api": f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{j['id']}",
                })

    elif kind == "lever":
        r = requests.get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"}, headers=UA, timeout=30)
        r.raise_for_status()
        for j in r.json():
            days = _age_days(j.get("createdAt"))
            if days <= max_days and keep_title(j.get("text", "")):
                cats = j.get("categories") or {}
                lists = " ".join(f"{l.get('text', '')} {l.get('content', '')}" for l in j.get("lists") or [])
                out.append({
                    "source": "Lever", "company": slug, "title": j["text"],
                    "location": cats.get("location", ""),
                    "posted": _posted_label(days), "url": j.get("hostedUrl"),
                    "posted_at": _iso(j.get("createdAt")),
                    "description": " ".join([j.get("descriptionPlain", ""), lists, j.get("additionalPlain", "")]),
                    "extra_locs": cats.get("allLocations") or [],
                    "country": j.get("country", ""),
                })

    elif kind == "ashby":
        r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", headers=UA, timeout=30)
        r.raise_for_status()
        for j in r.json().get("jobs", []):
            if j.get("isListed") is False:
                continue
            days = _age_days(j.get("publishedAt"))
            if days <= max_days and keep_title(j.get("title", "")):
                addr = ((j.get("address") or {}).get("postalAddress") or {})
                loc = j.get("location", "")
                if j.get("isRemote") and "remote" not in loc.lower():
                    loc = f"{loc} (Remote)".strip()
                out.append({
                    "source": "Ashby", "company": slug, "title": j["title"],
                    "location": loc,
                    "posted": _posted_label(days), "url": j.get("jobUrl"),
                    "posted_at": _iso(j.get("publishedAt")),
                    "description": j.get("descriptionPlain") or j.get("descriptionHtml", ""),
                    "extra_locs": [s.get("location", "") for s in j.get("secondaryLocations") or []]
                                  + [addr.get("addressRegion", "")],
                    "country": addr.get("addressCountry", ""),
                })
    return out


def greenhouse_detail(job):
    """Returns (description_text_html, location strings) for a Greenhouse job."""
    d = requests.get(job["detail_api"], headers=UA, timeout=20).json()
    locs = [(d.get("location") or {}).get("name", "")]
    locs += [o.get("location") or o.get("name", "") for o in d.get("offices") or []]
    return html.unescape(d.get("content", "")), locs
