"""Temporary: run the full scanner exactly like the schedule does (results are not saved)."""
import time, workday_jobs as w
t0 = time.time()
_orig = w.requests.request
def logged(method, url, **kw):
    r = _orig(method, url, **kw)
    if "myworkdayjobs" in url:
        print(f"    t+{time.time()-t0:5.1f}s {method} {url[:90]} -> {r.status_code}", flush=True)
    return r
w.requests.request = logged
w.main()
