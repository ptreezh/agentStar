#!/usr/bin/env python3
"""Collect per-week star history for a fixed repo list via GitHub REST API.
- Endpoint: GET /repos/{owner}/{repo}/stargazers/history?per_page=30&page=N
  (privacy-safe, public data, works without auth at 60 req/h per IP)
- Resumes: skips repos already saved to hypecycle/data/{repo}.json
- Rate control: honours X-RateLimit-Remaining; sleeps ~60s between calls.
"""
import json, os, sys, time, urllib.request, urllib.error

BASE = "https://api.github.com"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

REPOS = [
    # --- AI tool ecosystem (expectation/growth objects) ---
    "langchain-ai/langchain", "langchain-ai/langgraph", "run-llama/llama_index",
    "microsoft/autogen", "crewAIInc/crewAI", "Significant-Gravitas/AutoGPT",
    "modelcontextprotocol/modelcontextprotocol", "modelcontextprotocol/servers",
    "anthropics/skills", "openai/openai-python", "ollama/ollama",
    "vllm-project/vllm", "hiyouga/LLaMA-Factory", "AUTOMATIC1111/stable-diffusion-webui",
    # --- classic software controls (long, saturated series) ---
    "react/react", "vuejs/vue", "moby/moby", "kubernetes/kubernetes",
    "tensorflow/tensorflow", "pytorch/pytorch", "huggingface/transformers",
    "golang/go", "microsoft/vscode", "vercel/next.js",
]

TOKEN = os.environ.get("GITHUB_TOKEN", "")

def api_get(path, retries=3):
    for attempt in range(retries):
        hdrs = {
            "User-Agent": "research-data-collection/1.0",
            "Accept": "application/vnd.github+json",
        }
        if TOKEN:
            hdrs["Authorization"] = f"Bearer {TOKEN}"
        req = urllib.request.Request(BASE + path, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                rem = int(r.headers.get("X-RateLimit-Remaining", "60"))
                return json.load(r), rem
        except urllib.error.HTTPError as e:
            if e.code == 403:
                reset = e.headers.get("X-RateLimit-Reset")
                wait = (int(reset) - int(time.time()) + 10) if reset else 3600
                wait = max(wait, 60)
                print(f"  [rate-limited] sleeping {wait}s", flush=True)
                time.sleep(wait)
                continue
            if e.code == 404:
                return None, 60
            if e.code in (502, 503):
                print(f"  [retry {attempt+1}] HTTP {e.code}", flush=True)
                time.sleep(30)
                continue
            raise
    return None, 60

def collect_repo(repo):
    out_path = os.path.join(DATA_DIR, repo.replace("/", "__") + ".json")
    if os.path.exists(out_path):
        print(f"SKIP {repo} (exists)", flush=True)
        return
    print(f"== {repo} ==", flush=True)
    meta, rem = api_get("/repos/" + repo)
    if meta is None:
        print(f"  !! repo not found", flush=True)
        return
    weeks = []
    page = 1
    while True:
        path = f"/repos/{repo}/stargazers/history?per_page=30&page={page}"
        data, rem = api_get(path)
        if not data:
            break
        weeks.extend(data)
        if len(data) < 30:
            break
        page += 1
        if not TOKEN:
            time.sleep(61)  # anonymous: stay within 60 req/h
    rec = {
        "repo": repo,
        "created_at": meta.get("created_at"),
        "stars_now": meta.get("stargazers_count"),
        "forks_now": meta.get("forks_count"),
        "open_issues": meta.get("open_issues_count"),
        "language": meta.get("language"),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "weeks": [{"week": w["week"], "total": w["total"]} for w in weeks],
    }
    with open(out_path, "w") as f:
        json.dump(rec, f)
    print(f"  saved {len(weeks)} weeks (latest stars {meta.get('stargazers_count')})", flush=True)

def main():
    done = 0
    for repo in REPOS:
        out_path = os.path.join(DATA_DIR, repo.replace("/", "__") + ".json")
        if os.path.exists(out_path):
            done += 1
    print(f"Resume: {done}/{len(REPOS)} already collected", flush=True)
    for repo in REPOS:
        collect_repo(repo)
        if not TOKEN:
            time.sleep(61)  # global pacing for anonymous mode
    print("ALL DONE", flush=True)

if __name__ == "__main__":
    main()
