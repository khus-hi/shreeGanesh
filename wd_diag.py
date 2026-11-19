"""Temporary: run the scanner's own Workday code on GitHub, with/without jobspy loaded."""
import sys, subprocess
CODE_A = r'''
import time, requests
import workday_jobs as w
print("A) full scanner imports; jobspy loaded:", "jobspy" in __import__("sys").modules)
for u in ["https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite","https://mastercard.wd1.myworkdayjobs.com/CorporateCareers","https://freshfields.wd3.myworkdayjobs.com/fbd_101"]:
    try: print("  ", u.split("//")[1].split(".")[0], "jobs:", len(w.search_site(u)))
    except Exception as e: print("  ", u, "ERR", e)
'''
CODE_B = r'''
import sys, requests, time
sys.modules["jobspy"] = None  # block jobspy import
import types; fake = types.ModuleType("aggregators"); fake.fetch_aggregators = lambda *a, **k: ([], {}); sys.modules["aggregators"] = fake
import workday_jobs as w
print("B) without jobspy")
for u in ["https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite","https://mastercard.wd1.myworkdayjobs.com/CorporateCareers","https://freshfields.wd3.myworkdayjobs.com/fbd_101"]:
    try: print("  ", u.split("//")[1].split(".")[0], "jobs:", len(w.search_site(u)))
    except Exception as e: print("  ", u, "ERR", e)
'''
CODE_C = r'''
import requests
r = requests.post("https://freshfields.wd3.myworkdayjobs.com/wday/cxs/freshfields/fbd_101/jobs", json={"appliedFacets":{},"limit":20,"offset":0,"searchText":"data"}, timeout=25)
print("C) freshfields plain:", r.status_code, r.text[:150])
r = requests.post("https://mastercard.wd1.myworkdayjobs.com/wday/cxs/mastercard/CorporateCareers/jobs", json={"appliedFacets":{},"limit":20,"offset":0,"searchText":"data"}, timeout=25)
print("C) mastercard plain:", r.status_code, r.text[:150])
'''
for c in (CODE_C, CODE_B, CODE_A):
    subprocess.run([sys.executable, "-c", c]); sys.stdout.flush()
