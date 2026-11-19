"""
Nationwide job search via JobSpy (free, open source): Indeed, LinkedIn, ZipRecruiter, Google Jobs.
Unlike the company boards, this sees jobs from EVERY company posting in the US.

Each hourly run grabs the last few hours of postings; the first run backfills 24 hours.
"""

from datetime import date

from sources import platform

COMPANY_PLATFORMS = {"workday": "Workday", "greenhouse": "Greenhouse", "lever": "Lever", "ashby": "Ashby"}

SEARCH_TERMS = ["data analyst", "data scientist", "data engineer", "machine learning engineer",
                "analytics engineer", "business intelligence analyst"]

# site -> results per search term (keep LinkedIn small: it rate-limits quickly)
SITES = {"indeed": 100, "linkedin": 30, "zip_recruiter": 30, "google": 30}
LABEL = {"indeed": "Indeed", "linkedin": "LinkedIn", "zip_recruiter": "ZipRecruiter", "google": "Google Jobs"}


def _newest_first():
    """JobSpy asks Indeed and LinkedIn for the most RELEVANT jobs in the time window, so with a
    per-search cap, brand-new postings can be cut off. Switch both to newest-first."""
    notes = []
    try:
        import jobspy.indeed as ji
        if "sort: RELEVANCE" in ji.job_search_query:
            ji.job_search_query = ji.job_search_query.replace("sort: RELEVANCE", "sort: DATE")
        notes.append("Indeed")
    except Exception:
        pass
    try:
        from jobspy.linkedin import LinkedIn
        if not getattr(LinkedIn, "_newest_patch", False):
            orig = LinkedIn._search_params
            def _params(self):
                p = orig(self)
                p["sortBy"] = "DD"  # date descending
                return p
            LinkedIn._search_params = _params
            LinkedIn._newest_patch = True
        notes.append("LinkedIn")
    except Exception:
        pass
    return notes


def _ok(v):
    """True for a real value (pandas fills missing cells with NaN, which is truthy)."""
    return v is not None and str(v).strip().lower() not in ("", "nan", "none", "nat")


def _location(loc, remote):
    """JobSpy gives a dict {city, state, country} (or a string in some versions)."""
    if isinstance(loc, dict):
        loc = {k: v for k, v in loc.items() if _ok(v)}
        parts = [loc.get("city"), loc.get("state")]
        text = ", ".join(str(p) for p in parts if p)
        country = str(loc.get("country") or "")
        if not text and country:
            text = country
    else:
        text = str(loc or "")
    if remote and "remote" not in text.lower():
        text = f"{text} (Remote - US)".strip() if text else "Remote - US"
    return text


def _posted(d):
    if not d:
        return "", 0
    try:
        days = (date.today() - (d if isinstance(d, date) else date.fromisoformat(str(d)[:10]))).days
    except Exception:
        return "", 0
    return ("Posted Today" if days <= 0 else "Posted Yesterday" if days == 1 else f"Posted {days} Days Ago"), days


def fetch_aggregators(keep_title, max_days, hours_old, log=print):
    """Returns candidate jobs (title + date filtered) from all aggregator sites."""
    try:
        from jobspy import scrape_jobs
    except ImportError:
        log("JobSpy not installed (pip install python-jobspy): skipping Indeed/LinkedIn/ZipRecruiter/Google")
        return [], {}

    sorted_sites = _newest_first()
    out, stats = {}, {}
    dropped = {"title": 0, "older than window": 0}
    for site, per_term in SITES.items():
        got = 0
        for term in SEARCH_TERMS:
            try:
                kw = dict(site_name=[site], search_term=term, location="United States", results_wanted=per_term,
                          hours_old=hours_old, country_indeed="USA", verbose=0, description_format="markdown")
                if site == "linkedin":
                    kw["linkedin_fetch_description"] = True
                if site == "google":
                    when = "since yesterday" if hours_old <= 24 else "in the last 3 days"
                    kw["google_search_term"] = f"{term} jobs in United States {when}"
                df = scrape_jobs(**kw)
            except Exception as e:
                stats[LABEL[site]] = f"failed: {type(e).__name__}: {str(e)[:80]}"
                break  # this site is blocking us this run; move on to the next site
            for r in df.to_dict("records"):
                title = str(r.get("title")) if _ok(r.get("title")) else ""
                company = str(r.get("company")) if _ok(r.get("company")) else ""
                if not title or not company:
                    continue
                if not keep_title(title):
                    dropped["title"] += 1
                    continue
                posted, days = _posted(r.get("date_posted"))
                if days > max_days:
                    dropped["older than window"] += 1
                    continue
                url = next((str(u) for u in (r.get("job_url_direct"), r.get("job_url")) if _ok(u)), "")
                if not url:
                    continue
                desc = r.get("description") if _ok(r.get("description")) else ""
                # apply link goes to a company career site -> it's a company-site job, not a job-board one
                plat = COMPANY_PLATFORMS.get(platform(url) or "")
                out.setdefault(str(url), {
                    "source": plat or LABEL[site], "found_via": LABEL[site] if plat else "",
                    "company": company, "title": title,
                    "location": _location(r.get("location"), r.get("is_remote") is True),
                    "posted": posted or "Posted Today", "url": str(url),
                    "description": str(desc),
                    "extra_locs": [], "country": "",
                })
                got += 1
        stats.setdefault(LABEL[site], f"{got} candidates")
    stats["newest-first"] = "+".join(sorted_sites) or "off"
    stats["skipped (senior/intern/other title)"] = dropped["title"]
    stats["skipped (too old)"] = dropped["older than window"]
    return list(out.values()), stats
