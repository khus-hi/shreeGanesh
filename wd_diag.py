import sys, time
B = {"appliedFacets":{},"limit":20,"offset":0,"searchText":"data"}
SITES = [("mastercard","wd1","CorporateCareers"),("freshfields","wd3","fbd_101"),("nvidia","wd5","NVIDIAExternalCareerSite"),("cigna","wd5","cignacareers"),("capitalone","wd12","Capital_One"),("adobe","wd5","external_experienced")]
mode = sys.argv[1]
if mode == "cffi":
    from curl_cffi import requests as R
    post = lambda u: R.post(u, json=B, timeout=25, impersonate="chrome")
else:
    import requests as R
    post = lambda u: R.post(u, json=B, timeout=25)
print("mode", mode, sys.version.split()[0])
ok = 0
for t, wd, s in SITES:
    r = post(f"https://{t}.{wd}.myworkdayjobs.com/wday/cxs/{t}/{s}/jobs"); ok += r.status_code == 200
    print(f"  {t:12} HTTP {r.status_code}"); time.sleep(2)
print(f"RESULT {mode}: {ok}/{len(SITES)} ok")
