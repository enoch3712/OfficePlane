import os
import time
import concurrent.futures
import requests

URL = os.getenv("OFFICEPLANE_URL", "http://localhost:8001/render")
FILE_PATH = os.getenv("OFFICEPLANE_INPUT", "./tests/fixtures/sample.pptx")

def one():
    t0 = time.time()
    with open(FILE_PATH, "rb") as f:
        r = requests.post(URL, files={"file": f}, params={"dpi": 120, "output": "images", "inline": False})
    dt = time.time() - t0
    return r.status_code, dt

def main(n=10):
    if not os.path.exists(FILE_PATH):
        raise SystemExit(f"Missing file: {FILE_PATH}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as ex:
        futs = [ex.submit(one) for _ in range(n)]
        res = [f.result() for f in futs]

    ok = [t for s, t in res if s == 200]
    print("ok:", len(ok), "/", n)
    if ok:
        ok_sorted = sorted(ok)
        print("p50:", ok_sorted[len(ok_sorted)//2], "max:", max(ok_sorted), "min:", min(ok_sorted))

if __name__ == "__main__":
    main()
