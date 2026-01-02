import os
import time
import base64
import requests

URL = os.getenv("OFFICEPLANE_URL", "http://localhost:8001/render")
OUT = os.getenv("OFFICEPLANE_OUT", "./demo_out")

def main():
    os.makedirs(OUT, exist_ok=True)

    path = os.getenv("OFFICEPLANE_INPUT", "./tests/fixtures/sample.pptx")
    if not os.path.exists(path):
        raise SystemExit(f"Missing input file: {path} (add one, or set OFFICEPLANE_INPUT)")

    t0 = time.time()
    with open(path, "rb") as f:
        r = requests.post(URL, files={"file": f}, params={"dpi": 120, "output": "both", "inline": True})
    dt = time.time() - t0

    print("status:", r.status_code, "time:", f"{dt:.2f}s")
    r.raise_for_status()
    data = r.json()

    pdf_bytes = base64.b64decode(data["pdf"]["base64"])
    with open(os.path.join(OUT, "out.pdf"), "wb") as f:
        f.write(pdf_bytes)

    for p in data["pages"]:
        img = base64.b64decode(p["base64"])
        with open(os.path.join(OUT, f"page_{p['page']}.png"), "wb") as f:
            f.write(img)

    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        import json
        json.dump(data["manifest"], f, indent=2)

    print("wrote:", OUT)

if __name__ == "__main__":
    main()
