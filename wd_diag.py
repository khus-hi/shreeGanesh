import ssl, sys, requests, time
print("python", sys.version.split()[0], "|", ssl.OPENSSL_VERSION, "| requests", requests.__version__)
B = {"appliedFacets":{},"limit":20,"offset":0,"searchText":"data"}
for t, wd, s in [("mastercard","wd1","CorporateCareers"),("freshfields","wd3","fbd_101"),("nvidia","wd5","NVIDIAExternalCareerSite"),("walmart","wd5","WalmartExternal")]:
    r = requests.post(f"https://{t}.{wd}.myworkdayjobs.com/wday/cxs/{t}/{s}/jobs", json=B, timeout=25)
    print(f"  {t:12} HTTP {r.status_code}"); time.sleep(2)
