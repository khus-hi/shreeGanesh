"""
Job scanner (whole US): Workday + Greenhouse + Lever + Ashby -> Excel + email alert.

Every run (e.g. hourly):
  1. Once a day: Google (SerpAPI) finds new Workday companies posting US data jobs
     and adds them to companies.txt -> the list grows by itself.
  2. Scans every company in companies.txt for new US data roles.
  3. For each NEW job: reads the description, scores it against your resumes
     (resume_profiles.json), flags sponsorship + years required.
  4. Adds them to jobs.xlsx (best matches first) and emails you.

Run:  python workday_jobs.py
"""

import json
import os
import re
import smtplib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import urlparse

import requests

from enrich import clean_html, h1b_history, score, sponsorship
from places import HUB_SEARCH_CITIES, STATE_NAMES, metro_of
from tailor import tailor_resume
from sources import board_from_link, fetch_board, greenhouse_detail, platform, site_key
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

# ================= CONFIG =================
HERE = Path(__file__).parent
COMPANIES_FILE = HERE / "companies.txt"
EXCEL_FILE = HERE / "jobs.xlsx"
DASHBOARD_DATA = HERE / "docs" / "jobs.json"
DASHBOARD_URL = "https://khus-hi.github.io/shreeGanesh/"
DASHBOARD_MAX_JOBS = 4000  # keep the page fast
STATE_FILE = HERE / ".scanner_state.json"

MAX_DAYS_OLD = 1          # Workday shows "Posted Today/Yesterday"; dedupe stops repeats
MAX_PAGES_PER_SEARCH = 3  # 20 jobs per page
WORKERS = 8               # companies scanned in parallel
DISABLE_AFTER_FAILURES = 3  # broken board links get switched off automatically

# Workday's search matches titles + descriptions, so a few broad terms are enough
SEARCH_TERMS = ["data", "analytics", "machine learning"]

TITLE_INCLUDE = re.compile(
    r"\bdata\b|analyst|analytics|scientist|machine learning|\bml\b|\bai\b|business intelligence|\bbi\b",
    re.I,
)
# remove words here if you want those roles too
TITLE_EXCLUDE = re.compile(
    r"senior|\bsr\b|staff|principal|lead|manager|director|head of|\bvp\b|architect|"
    r"intern|co-op|data center|technician|clinical data|data entry",
    re.I,
)

INCLUDE_REMOTE = True

# --- Scoring / alerts ---
MIN_MATCH_FOR_ALERT = 60     # jobs at/above this go in the "Top matches" part of the email
SKIP_NO_SPONSORSHIP = False  # True = drop jobs that say they won't sponsor visas
MAX_TAILORED_PER_RUN = 10    # Claude-tailored resumes per run (top matches first); needs ANTHROPIC_API_KEY

# --- Discovery (needs SERPAPI_KEY env var) ---
# Each search = one place x one platform, with all data roles OR-ed together.
# Places rotate: every tech-hub city (places.py) + every US state + nationwide + remote.
# Tech hubs are searched twice as often as states.
DISCOVER_EVERY_HOURS = 24      # how often to look for new companies
DISCOVERY_QUERIES_PER_RUN = 10  # SerpAPI searches each time (10/day ~ 300/month; lower it on a free plan)
DISCOVERY_PLATFORMS = ["myworkdayjobs.com", "boards.greenhouse.io", "jobs.lever.co",
                       "jobs.ashbyhq.com", "job-boards.greenhouse.io"]
DISCOVERY_ROLES = ['"data analyst"', '"data scientist"', '"data engineer"', '"machine learning engineer"',
                   '"analytics engineer"', '"business intelligence"']

# Email alert (optional): ALERT_EMAIL_TO, GMAIL_USER, GMAIL_APP_PASSWORD env vars
# ==========================================

STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}
# names longest-first so "West Virginia" wins over "Virginia"
STATE_NAME_RE = re.compile(r"\b(" + "|".join(sorted(STATES.values(), key=len, reverse=True)) + r")\b", re.I)
# abbreviations must be uppercase and look like ", MA" / "US-MA" / "MA,"
STATE_ABBR_RE = re.compile(r"(?:^|[,\-\s(])(" + "|".join(STATES) + r")(?=$|[,\-\s)])")
US_RE = re.compile(r"united states|\busa\b|\bu\.s\.(a\.)?|\bus\b", re.I)
REMOTE_RE = re.compile(r"remote|virtual|work from home", re.I)
NAME_TO_ABBR = {v.lower(): k for k, v in STATES.items()}

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Accept-Language": "en-US",
    "User-Agent": "Mozilla/5.0",
}
SITE_RE = re.compile(r"https://([\w-]+\.wd\d+\.myworkdayjobs\.com)/(?:[a-z]{2}-[A-Z]{2}/)?([\w-]+)")


# ---------------- helpers ----------------
def parse_site(url):
    u = urlparse(url.strip())
    tenant = u.netloc.split(".")[0]
    parts = [p for p in u.path.split("/") if p]
    if parts and re.fullmatch(r"[a-z]{2}-[A-Z]{2}", parts[0]):
        parts = parts[1:]
    return f"{u.scheme}://{u.netloc}", tenant, parts[0]


def days_old(posted_on):
    s = (posted_on or "").lower()
    if "today" in s:
        return 0
    if "yesterday" in s:
        return 1
    m = re.search(r"(\d+)\+?\s*day", s)
    if m:
        return 99 if "+" in s else int(m.group(1))
    return 99


NON_US_RE = re.compile(
    r"\b(india|canada|united kingdom|uk|england|ireland|germany|france|spain|italy|portugal|"
    r"netherlands|belgium|switzerland|sweden|poland|romania|czech republic|czechia|hungary|"
    r"mexico|brazil|argentina|colombia|chile|costa rica|china|japan|korea|taiwan|singapore|"
    r"malaysia|philippines|vietnam|indonesia|thailand|australia|israel|uae|dubai|"
    r"south africa|egypt|bengaluru|bangalore|hyderabad|chennai|pune|mumbai|noida|gurgaon|gurugram)\b",
    re.I,
)
# Workday codes like "US-MA-Boston" / "IN-KA-Bangalore" / "CA-ON-Toronto"
CODE_PREFIX_RE = re.compile(r"^\s*([A-Z]{2,3})\s*-\s*([A-Z]{2})\s*-")


def us_state(location):
    """Returns 'MA', 'Remote', 'US', or None if not US."""
    loc = location or ""
    m = CODE_PREFIX_RE.match(loc)
    if m:
        if m.group(1) in ("US", "USA") and m.group(2) in STATES:
            return m.group(2)
        return None
    if NON_US_RE.search(loc):
        return None
    m = STATE_NAME_RE.search(loc)
    if m:
        return NAME_TO_ABBR[m.group(1).lower()]
    m = STATE_ABBR_RE.search(loc)
    if m:
        return m.group(1)
    if US_RE.search(loc):
        return "Remote" if REMOTE_RE.search(loc) else "US"
    return None


def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {"last_discovery": 0, "query_index": 0}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state))


# ---------------- discovery ----------------
def discovery_queries():
    """Hub cities appear twice per cycle, states once."""
    roles = "(" + " OR ".join(DISCOVERY_ROLES) + ")"
    places = [""] + HUB_SEARCH_CITIES
    mixed, states = [], list(STATE_NAMES) + ["Remote"]
    for i, place in enumerate(places * 2):  # hubs twice, states spread in between
        mixed.append(place)
        if i % 2 == 1 and states:
            mixed.append(states.pop(0))
    mixed += states
    return [(f'site:{plat} {roles}' + (f' "{p}"' if p else ""), p or "US") for p in mixed for plat in DISCOVERY_PLATFORMS]


def discover_sites(state):
    key = os.getenv("SERPAPI_KEY")
    if not key or time.time() - state["last_discovery"] < DISCOVER_EVERY_HOURS * 3600:
        return []
    queries = discovery_queries()
    sites = set()
    for _ in range(DISCOVERY_QUERIES_PER_RUN):
        q, place = queries[state["query_index"] % len(queries)]
        state["query_index"] += 1
        try:
            r = requests.get(
                "https://serpapi.com/search.json",
                params={"q": q, "num": 100, "tbs": "qdr:w", "api_key": key},
                timeout=30,
            )
            for res in r.json().get("organic_results", []):
                link = res.get("link", "")
                m = SITE_RE.match(link)
                if m and m.group(2) not in ("wday", "job"):
                    sites.add(f"https://{m.group(1)}/{m.group(2)}")
                elif board_from_link(link):
                    sites.add(board_from_link(link))
        except Exception as e:
            print(f"Discovery failed for {place}: {e}")
    state["last_discovery"] = time.time()
    cycle = len(queries) / max(DISCOVERY_QUERIES_PER_RUN, 1) * DISCOVER_EVERY_HOURS / 24
    print(f"Discovery: searched {DISCOVERY_QUERIES_PER_RUN} place/platform combos "
          f"(full cycle of {len(queries)} every ~{cycle:.0f} days)")
    return sorted(sites)


# ---------------- scanning ----------------
def search_site(url):
    base, tenant, site = parse_site(url)
    api = f"{base}/wday/cxs/{tenant}/{site}/jobs"
    found = {}
    for term in SEARCH_TERMS:
        for page in range(MAX_PAGES_PER_SEARCH):
            body = {"appliedFacets": {}, "limit": 20, "offset": page * 20, "searchText": term}
            r = requests.post(api, json=body, headers=HEADERS, timeout=20)
            r.raise_for_status()
            postings = r.json().get("jobPostings", [])
            if not postings:
                break
            for p in postings:
                path, title = p.get("externalPath", ""), p.get("title", "")
                if (
                    path
                    and path not in found
                    and days_old(p.get("postedOn")) <= MAX_DAYS_OLD
                    and TITLE_INCLUDE.search(title)
                    and not TITLE_EXCLUDE.search(title)
                ):
                    found[path] = {
                        "source": "Workday",
                        "company": tenant,
                        "title": title,
                        "location": p.get("locationsText", ""),
                        "posted": p.get("postedOn", ""),
                        "url": f"{base}/{site}{path}",
                        "detail_api": f"{base}/wday/cxs/{tenant}/{site}{path}",
                    }
            if all(days_old(p.get("postedOn")) > MAX_DAYS_OLD for p in postings):
                break
            time.sleep(0.3)
    return list(found.values())


def keep_title(title):
    return bool(TITLE_INCLUDE.search(title)) and not TITLE_EXCLUDE.search(title)


def scan_any(url):
    kind = platform(url)
    if kind == "workday":
        return search_site(url)
    if kind:
        return fetch_board(url, keep_title, MAX_DAYS_OLD)
    raise ValueError("unknown job board")


def get_details(job):
    """Returns (description text, org name, extra location strings, country)."""
    src = job.get("source")
    if src in ("Lever", "Ashby"):
        return clean_html(job.get("description", "")), "", job.get("extra_locs", []), job.get("country", "")
    if src == "Greenhouse":
        try:
            raw, locs = greenhouse_detail(job)
            return clean_html(raw), "", locs, ""
        except Exception:
            return "", "", [], ""
    try:  # Workday
        data = requests.get(job["detail_api"], headers=HEADERS, timeout=20).json()
    except Exception:
        data = {}
    info = data.get("jobPostingInfo", {}) or {}
    org = (data.get("hiringOrganization") or {}).get("name", "")
    locs = [info.get("location", "")] + (info.get("additionalLocations") or [])
    country = (info.get("country") or {}).get("descriptor", "")
    return clean_html(info.get("jobDescription", "")), org, locs, country


def enrich_job(job):
    """Fetch description, check US location, score. Returns job, or None if not US."""
    text, org, locs, country = get_details(job)

    # location
    st = us_state(job["location"])
    if st is None:
        us_locs = [(l, us_state(l)) for l in locs if l and us_state(l)]
        if us_locs:
            job["location"] = "; ".join(l for l, _ in us_locs)
            st = ", ".join(sorted({s for _, s in us_locs}))
        elif str(country).strip().lower() in ("united states", "united states of america", "us", "usa"):
            st = "Remote" if REMOTE_RE.search(job["location"]) else "US"
    if st is None or (st == "Remote" and not INCLUDE_REMOTE):
        return None
    job["state"] = st
    job["metro"] = metro_of(job["location"], st)

    # description-based fields
    job["company_name"] = org or job["company"]
    job["sponsor"], job["sponsor_text"] = sponsorship(text) if text else ("Unknown", "")
    job["h1b"] = h1b_history(org, job["company"])
    job.update(score(job["title"], text))
    job["jd_text"] = text
    if not text:
        job["missing"] = "(no description found)"
    return job


# ---------------- excel ----------------
COLUMNS = ["Found On", "Match %", "Best Resume", "Company", "Title", "State", "Metro", "Location",
           "Sponsorship", "H-1B History", "Years Req", "Matched Skills", "Missing Skills",
           "Posted", "Source", "URL", "Tailored Resume", "Status"]
WIDTHS = [17, 9, 8, 18, 45, 8, 16, 28, 13, 13, 9, 40, 30, 16, 11, 50, 28, 12]


def load_sheet():
    if EXCEL_FILE.exists():
        wb = load_workbook(EXCEL_FILE)
        ws = wb.active
        header = [c.value for c in ws[1]]
        if header == COLUMNS:
            return wb, ws
        old = EXCEL_FILE.with_name("jobs_old.xlsx")
        EXCEL_FILE.rename(old)
        print(f"Column layout changed -> old file kept as {old.name}")
    wb = Workbook()
    ws = wb.active
    ws.title = "Jobs"
    ws.append(COLUMNS)
    for c in ws[1]:
        c.font = Font(bold=True)
    for i, w in enumerate(WIDTHS):
        ws.column_dimensions[chr(65 + i)].width = w
    ws.freeze_panes = "A2"
    return wb, ws


def seen_urls():
    if not EXCEL_FILE.exists():
        return set()
    ws = load_workbook(EXCEL_FILE, read_only=True).active
    rows = ws.iter_rows(values_only=True)
    header = list(next(rows, []))
    if "URL" not in header:
        return set()
    i = header.index("URL")
    return {r[i] for r in rows if r[i]}


def job_row(j, now):
    repo = os.getenv("GITHUB_REPOSITORY")
    tailored = j.get("tailored") or ""
    tailored_link = (f"https://github.com/{repo}/blob/main/{tailored}" if repo and tailored else Path(tailored).name)
    return [
        now, j["match"], j["best_resume"], j["company_name"], j["title"], j["state"], j.get("metro", ""), j["location"],
        j["sponsor"], j["h1b"], j["years"] if j["years"] is not None else "", j["matched"],
        j["missing"], j["posted"], j["source"], j["url"], tailored_link, "",
    ]


def push_to_sheet(rows):
    """Sends rows to the Google Sheet web app (google_sheets_script.gs). Needs SHEETS_WEBHOOK_URL."""
    url = os.getenv("SHEETS_WEBHOOK_URL")
    if not url or not rows:
        return True
    clean = [["" if v is None else v for v in r] for r in rows]
    try:
        for i in range(0, len(clean), 500):
            r = requests.post(url, data=json.dumps({"columns": COLUMNS, "rows": clean[i:i + 500]}),
                              headers={"Content-Type": "application/json"}, timeout=120)
            r.raise_for_status()
            print(f"Google Sheet: {r.json().get('added', '?')} row(s) added")
        return True
    except Exception as e:
        print(f"Google Sheet update failed: {e}")
        return False


def sync_sheet(state, new):
    """First time: send everything already in jobs.xlsx. After that: only new jobs."""
    if not os.getenv("SHEETS_WEBHOOK_URL"):
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    if not state.get("sheet_backfilled") and EXCEL_FILE.exists():
        ws = load_workbook(EXCEL_FILE, read_only=True).active
        rows = [list(r) for r in ws.iter_rows(min_row=2, values_only=True)]
        rows.sort(key=lambda r: -(r[1] or 0))
        if push_to_sheet(rows):
            state["sheet_backfilled"] = True
        return
    if push_to_sheet([job_row(j, now) for j in sorted(new, key=lambda j: -j["match"])]):
        state["sheet_backfilled"] = True


def export_dashboard():
    """Writes docs/jobs.json (all jobs found so far) for the dashboard website."""
    if not EXCEL_FILE.exists():
        return
    ws = load_workbook(EXCEL_FILE, read_only=True).active
    rows = ws.iter_rows(values_only=True)
    header = list(next(rows, []))
    keys = {"Found On": "found", "Match %": "match", "Best Resume": "resume", "Company": "company",
            "Title": "title", "State": "state", "Metro": "metro", "Location": "location",
            "Sponsorship": "sponsor", "H-1B History": "h1b", "Years Req": "years",
            "Matched Skills": "matched", "Missing Skills": "missing", "Posted": "posted",
            "Source": "source", "URL": "url", "Tailored Resume": "tailored"}
    repo = os.getenv("GITHUB_REPOSITORY")
    jobs = []
    for r in rows:
        d = {keys[h]: ("" if v is None else v) for h, v in zip(header, r) if h in keys}
        if not d.get("url"):
            continue
        if d.get("tailored") and repo and not str(d["tailored"]).startswith("http"):
            d["tailored"] = ""  # older rows stored only a file name
        jobs.append(d)
    jobs.sort(key=lambda d: str(d.get("found", "")), reverse=True)
    DASHBOARD_DATA.parent.mkdir(exist_ok=True)
    DASHBOARD_DATA.write_text(json.dumps({
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "top_match": MIN_MATCH_FOR_ALERT,
        "jobs": jobs[:DASHBOARD_MAX_JOBS],
    }, ensure_ascii=False, separators=(",", ":")))


def save_new(new):
    if not new:
        return
    wb, ws = load_sheet()
    for row in ws.iter_rows(min_row=2):  # un-highlight the previous batch
        for c in row:
            c.fill = PatternFill()
    yellow = PatternFill("solid", fgColor="FFF2CC")
    green = PatternFill("solid", fgColor="C6EFCE")
    red_font = Font(color="C00000", bold=True)
    url_col = COLUMNS.index("URL") + 1
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    for j in sorted(new, key=lambda j: -j["match"]):
        ws.append(job_row(j, now))
        r = ws.max_row
        for c in ws[r]:
            c.fill = yellow
        if j["match"] >= MIN_MATCH_FOR_ALERT:
            ws.cell(row=r, column=2).fill = green
        if j["sponsor"] == "No":
            ws.cell(row=r, column=COLUMNS.index("Sponsorship") + 1).font = red_font
        link = ws.cell(row=r, column=url_col)
        link.hyperlink = j["url"]
        link.font = Font(color="0563C1", underline="single")
        if j.get("tailored"):
            repo = os.getenv("GITHUB_REPOSITORY")
            cell = ws.cell(row=r, column=COLUMNS.index("Tailored Resume") + 1)
            cell.hyperlink = (f"https://github.com/{repo}/blob/main/{j['tailored']}" if repo else j["tailored"])
            cell.font = Font(color="0563C1", underline="single")
    ws.auto_filter.ref = f"A1:{chr(64 + len(COLUMNS))}{ws.max_row}"
    wb.save(EXCEL_FILE)


def send_email(new):
    to, user, pw = (os.getenv(k) for k in ("ALERT_EMAIL_TO", "GMAIL_USER", "GMAIL_APP_PASSWORD"))
    if not (to and user and pw and new):
        return
    new = sorted(new, key=lambda j: -j["match"])
    top = [j for j in new if j["match"] >= MIN_MATCH_FOR_ALERT and j["sponsor"] != "No"]
    rest = [j for j in new if j not in top]

    def line(j):
        yrs = f"{j['years']}+ yrs" if j["years"] is not None else "yrs n/a"
        res = f"\n  resume: {Path(j['tailored']).name} (attached)" if j.get("tailored") else ""
        where = f"{j['state']} ({j['metro']})" if j.get("metro") else j["state"]
        return (f"{j['match']}% [{j['best_resume']}] {j['company_name']} | {j['title']} | {where} | "
                f"{yrs} | sponsorship: {j['sponsor']}\n{j['url']}{res}\n")

    body = ""
    if top:
        body += f"TOP MATCHES - apply today ({len(top)})\n\n" + "\n".join(map(line, top)) + "\n"
    if rest:
        body += f"\nOTHER NEW JOBS ({len(rest)})\n\n" + "\n".join(map(line, rest))
    msg = MIMEMultipart()
    msg.attach(MIMEText(f"Open your job dashboard: {DASHBOARD_URL}\n\n" + body))
    for j in new:
        if j.get("tailored") and (HERE / j["tailored"]).exists():
            pdf = HERE / j["tailored"]
            part = MIMEApplication(pdf.read_bytes(), Name=pdf.name)
            part["Content-Disposition"] = f'attachment; filename="{pdf.name}"'
            msg.attach(part)
    msg["Subject"] = f"{len(top)} top matches / {len(new)} new data jobs"
    msg["From"], msg["To"] = user, to
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, pw)
        s.send_message(msg)
    print(f"Emailed {to}")


def disable_broken(state, sites, failed):
    """Counts consecutive failures per board; comments out boards that keep failing."""
    fails = state.setdefault("failures", {})
    for u in sites:
        fails[u] = fails.get(u, 0) + 1 if u in failed else 0
    dead = {u for u, n in fails.items() if n >= DISABLE_AFTER_FAILURES}
    if not dead:
        return
    lines = COMPANIES_FILE.read_text().splitlines()
    out = [f"# disabled (failed {DISABLE_AFTER_FAILURES} runs): {l.strip()}" if l.strip() in dead else l for l in lines]
    COMPANIES_FILE.write_text("\n".join(out) + "\n")
    for u in dead:
        fails.pop(u, None)
    print(f"Disabled {len(dead)} broken board(s):", *sorted(dead), sep="\n  ")


# ---------------- main ----------------
def main():
    start = time.time()
    if not COMPANIES_FILE.exists():
        COMPANIES_FILE.write_text("# Workday career sites (auto-filled; add your own too)\n")
    sites = [l.strip() for l in COMPANIES_FILE.read_text().splitlines() if l.strip() and not l.startswith("#")]

    state = load_state()
    known = {site_key(s) for s in sites}
    found = list({site_key(s): s for s in discover_sites(state) if site_key(s) not in known}.values())
    if found:
        with COMPANIES_FILE.open("a") as f:
            f.write("\n".join(found) + "\n")
        sites += found
        print(f"Discovered {len(found)} new companies")

    # 1. scan all sites
    print(f"Scanning {len(sites)} job boards...")
    candidates, failed = [], []
    with ThreadPoolExecutor(WORKERS) as pool:
        futures = {pool.submit(scan_any, u): u for u in sites}
        for f in as_completed(futures):
            try:
                candidates += f.result()
            except Exception:
                failed.append(futures[f])

    disable_broken(state, sites, failed)

    # 2. only look closer at jobs we haven't seen before
    skip = seen_urls() | set(state.get("rejected", []))
    fresh = list({j["url"]: j for j in candidates if j["url"] not in skip}.values())

    # 3. read descriptions + score
    new, rejected = [], []
    with ThreadPoolExecutor(WORKERS) as pool:
        for job, res in zip(fresh, pool.map(enrich_job, fresh)):
            if res is None or (SKIP_NO_SPONSORSHIP and res["sponsor"] == "No"):
                rejected.append(job["url"])
            else:
                new.append(res)
    # 4. Claude-tailored resumes for the best matches
    if os.getenv("ANTHROPIC_API_KEY"):
        picks = sorted((j for j in new if j["match"] >= MIN_MATCH_FOR_ALERT and j["sponsor"] != "No"),
                       key=lambda j: -j["match"])[:MAX_TAILORED_PER_RUN]
        if picks:
            print(f"Tailoring {len(picks)} resume(s) with Claude...")
        day = datetime.now().strftime("%Y-%m-%d")
        with ThreadPoolExecutor(3) as pool:
            for j, path in zip(picks, pool.map(lambda j: tailor_resume(j, j["jd_text"], day), picks)):
                j["tailored"] = path

    state["rejected"] = (state.get("rejected", []) + rejected)[-5000:]
    save_state(state)

    save_new(new)
    export_dashboard()
    sync_sheet(state, new)
    save_state(state)
    top = sum(j["match"] >= MIN_MATCH_FOR_ALERT for j in new)
    print(f"{len(new)} new jobs added, {top} top matches "
          f"({len(failed)} sites failed, {time.time() - start:.0f}s)")
    for j in sorted(new, key=lambda j: -j["match"]):
        print(f"  {j['match']:>3}% [{j['best_resume']}] [{j['state']}] {j['company_name']}: "
              f"{j['title']} | {j['source']} | sponsorship: {j['sponsor']}")
    if failed:
        print("Failed sites:", *failed, sep="\n  ")
    send_email(new)


if __name__ == "__main__":
    main()
