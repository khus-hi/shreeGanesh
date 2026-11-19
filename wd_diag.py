"""Temporary: test different ways of calling Workday from GitHub's servers."""
import requests, time, json
SITES = [("nvidia","wd5","NVIDIAExternalCareerSite"),("capitalone","wd12","Capital_One"),("cigna","wd5","cignacareers")]
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
BODY = {"appliedFacets":{},"limit":20,"offset":0,"searchText":"data"}
def show(name, r):
    try: n = len(r.json().get("jobPostings", []))
    except Exception: n = "-"
    print(f"  {name:38} HTTP {r.status_code}  jobs={n}  server={r.headers.get('server','')}  retry-after={r.headers.get('retry-after','')}  body={r.text[:90]!r}")
ip = requests.get("https://api.ipify.org").text; print("runner IP:", ip)
for t, wd, s in SITES:
    base = f"https://{t}.{wd}.myworkdayjobs.com"; api = f"{base}/wday/cxs/{t}/{s}/jobs"
    print(t)
    show("plain POST (no headers)", requests.post(api, json=BODY, timeout=25)); time.sleep(3)
    show("POST + browser headers", requests.post(api, json=BODY, timeout=25, headers={"User-Agent":UA,"Accept":"application/json","Content-Type":"application/json","Accept-Language":"en-US","Origin":base,"Referer":f"{base}/en-US/{s}"})); time.sleep(3)
    ses = requests.Session(); ses.headers["User-Agent"] = UA
    g = ses.get(f"{base}/en-US/{s}", timeout=25); show("GET career page (HTML)", g); time.sleep(3)
    show("POST after page visit (cookies)", ses.post(api, json=BODY, timeout=25, headers={"Accept":"application/json","Content-Type":"application/json","Origin":base,"Referer":f"{base}/en-US/{s}"})); time.sleep(3)
    show("GET sitemap/rss alt", requests.get(f"{base}/wday/cxs/{t}/{s}/jobs?limit=5", headers={"User-Agent":UA}, timeout=25)); time.sleep(5)
