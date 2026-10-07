#!/usr/bin/env python3
"""Collect recent daily download series from PyPI (pypistats.org public API).
- GET https://pypistats.org/api/packages/{pkg}/overall  -> ~364 days daily series
- Saves hypecycle/data/downloads/{pkg}.json  (resumable)
"""
import json, os, time, urllib.request, urllib.error

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "downloads")
os.makedirs(DATA_DIR, exist_ok=True)

PKGS = [
    # AI tool ecosystem (Python SDKs / frameworks)
    "langchain", "langgraph", "llama-index", "pyautogen", "crewai", "mcp",
    "anthropic", "openai", "ollama", "vllm", "llmfactory", "openai-whisper",
    # classic controls (mature, long-adoption packages)
    "torch", "tensorflow", "numpy", "pandas", "requests", "flask",
    "transformers", "scikit-learn",
]

def fetch(pkg):
    url = f"https://pypistats.org/api/packages/{pkg}/overall"
    req = urllib.request.Request(url, headers={"User-Agent": "research-data-collection/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

for pkg in PKGS:
    out = os.path.join(DATA_DIR, pkg + ".json")
    if os.path.exists(out):
        print(f"SKIP {pkg}")
        continue
    try:
        d = fetch(pkg)
        # keep without_mirrors only (cleaner measure of actual installs)
        pts = [p for p in d.get("data", []) if p.get("category") == "without_mirrors"]
        rec = {"package": pkg, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
               "series": [{"date": p["date"], "downloads": p["downloads"]} for p in pts]}
        with open(out, "w") as f:
            json.dump(rec, f)
        print(f"OK {pkg}: {len(pts)} days")
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} {pkg}: {e.read()[:100]}")
    except Exception as e:
        print(f"FAIL {pkg}: {e}")
    time.sleep(1.5)
print("DOWNLOADS DONE")
