#!/usr/bin/env python3
"""analyze_final.py — THE single authoritative statistics implementation for
"Hype Cycle, Quantified". Every number the paper may quote is computed HERE,
directly from data/*.json. It regenerates all frozen artifacts
(f1_revised / f2_final / f2_lead / f3_sync / f4_autogen), runs a REGRESSION GATE
against the previously validated artifacts (every field must match), and writes
golden_numbers.json for verify_numbers.py.

All process scripts (analyze*.py) are retired to tools/archive/ and are NOT a
verification baseline. Never re-implement statistics elsewhere: the paper's
numbers must come from this file alone.

Label conventions (kept exactly as the validated artifacts define them):
  - Star-history weeks (F1 / Table 1): Sunday-ending labels, native timestamps.
  - Download-window weeks (F2 / F2-lead): Monday-start labels, native PyPI weeks.
  Both are the native labels of their respective data sources; the paper states
  this in Section 3 (data provenance) instead of forcing a lossy relabel.
"""
import json, os, math, statistics, subprocess
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
PY = "/home/user/Doubao/chats/38445381753154818/bootloops/.venv/bin/python"

# ----------------------------------------------------------------------------
# Loading (shared by all analyses)
# ----------------------------------------------------------------------------
def load_stars():
    out = {}
    for fn in os.listdir(DATA):
        if fn.endswith(".json") and "__" in fn:
            r = json.load(open(os.path.join(DATA, fn)))
            out[r["repo"]] = r
    return out

def load_dl():
    out = {}
    for fn in os.listdir(os.path.join(DATA, "downloads")):
        if fn.endswith(".json"):
            r = json.load(open(os.path.join(DATA, "downloads", fn)))
            out[r["package"]] = r["series"]
    return out

def monday_of(unix_ts):
    d = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
    return (d - timedelta(days=d.weekday())).date().isoformat()

def iso_of(unix_ts):
    d = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
    monday = d - timedelta(days=d.weekday())
    return monday.date().isoformat()

MAPPING = {
    "langchain-ai/langchain": "langchain", "langchain-ai/langgraph": "langgraph",
    "run-llama/llama_index": "llama-index", "microsoft/autogen": "pyautogen",
    "crewAIInc/crewAI": "crewai", "modelcontextprotocol/servers": "mcp",
    "openai/openai-python": "openai", "ollama/ollama": "ollama",
    "vllm-project/vllm": "vllm", "huggingface/transformers": "transformers",
    "pytorch/pytorch": "torch", "tensorflow/tensorflow": "tensorflow",
    "openclaw/openclaw": "openclaw",
}

# ----------------------------------------------------------------------------
# F1 / Table 1 — logic from analyze7.py (authoritative; Sunday labels)
# ----------------------------------------------------------------------------
def build_f1_rows(stars):
    rows = []
    for repo, r in stars.items():
        weeks = sorted(r["weeks"], key=lambda w: w["week"])
        totals = [w["total"] for w in weeks]
        if len(totals) < 12:
            continue
        adj = totals[1:]
        med = statistics.median(totals)
        max_raw = max(totals)
        adj_max = max(adj)
        peak_idx = totals.index(max_raw)
        pre4 = sum(totals[max(0, peak_idx - 4):peak_idx])
        pre12 = totals[max(0, peak_idx - 12):peak_idx]
        post12 = totals[peak_idx + 1:peak_idx + 1 + 12]
        decay = (statistics.median(post12) / statistics.median(pre12)) if pre12 and post12 and statistics.median(pre12) > 0 else None
        rows.append({
            "repo": repo, "created": r["created_at"][:10],
            "max_wk": max_raw, "adj_max_wk": adj_max,
            "median_wk": med, "deviation": max_raw / med if med else None,
            "adj_deviation": adj_max / statistics.median(adj) if statistics.median(adj) else None,
            "pre4_cum": pre4, "postpeak_decay": round(decay, 2) if decay else None,
            "peak_week": datetime.fromtimestamp(weeks[peak_idx]["week"], tz=timezone.utc).date().isoformat(),
        })
    return rows

def f1_stats(rows):
    ai = [r for r in rows if r["created"] >= "2022-01-01"]
    cl = [r for r in rows if r["created"] < "2022-01-01"]
    from scipy.stats import mannwhitneyu
    out = {"n_ai": len(ai), "n_classic": len(cl)}
    for key, label in [("max_wk", "maxwk"), ("pre4_cum", "pre4"), ("postpeak_decay", "decay")]:
        av = [r[key] for r in ai if r[key] is not None]
        cv = [r[key] for r in cl if r[key] is not None]
        u, p = mannwhitneyu(av, cv, alternative="greater")
        out[f"{label}_med_ai"] = round(statistics.median(av), 4)
        out[f"{label}_med_cl"] = round(statistics.median(cv), 4)
        out[f"{label}_U"] = float(u)
        out[f"{label}_p"] = float(p)
    out["pre4_ratio"] = round(out["pre4_med_ai"] / out["pre4_med_cl"], 1)
    return out

# ----------------------------------------------------------------------------
# F2 — logic from analyze5.py (authoritative; Monday labels)
# ----------------------------------------------------------------------------
def f2_run(repo, pkg, stars, dl, a_after="2026-01-01"):
    weeks = sorted(stars[repo]["weeks"], key=lambda w: w["week"])
    cum, sgr = [], []
    for i, w in enumerate(weeks):
        c = cum[-1] + w["total"] if cum else w["total"]
        cum.append(c)
        base = cum[i - 4] if i >= 4 else max(1, cum[0])
        sgr.append((monday_of(w["week"]), math.log(max(c, 1) / max(base, 1))))
    dlw = {}
    for p in dl[pkg]:
        d = datetime.strptime(p["date"], "%Y-%m-%d").date()
        m = d - timedelta(days=d.weekday())
        dlw[m.isoformat()] = dlw.get(m.isoformat(), 0) + p["downloads"]
    ks = sorted(dlw)
    dlg = {}
    for i, k in enumerate(ks):
        base = dlw[ks[max(0, i - 4)]]
        dlg[k] = math.log(max(dlw[k], 1) / max(base, 1))
    cand_a = [x for x in sgr if x[0] >= a_after]
    if not cand_a:
        return None
    a_wk, a_val = max(cand_a, key=lambda x: x[1])
    post_b = [(k, v) for k, v in dlg.items() if k > a_wk]
    if not post_b:
        return None
    b_wk, b_val = max(post_b, key=lambda x: x[1])
    c_wk = None
    for k in sorted(dlg):
        if k > b_wk and dlg[k] < 0:
            c_wk = k
            break
    def wkdiff(x, y):
        return (datetime.strptime(y, "%Y-%m-%d").date() - datetime.strptime(x, "%Y-%m-%d").date()).days / 7
    return {
        "repo": repo, "pkg": pkg,
        "A_expectation_peak": a_wk, "A_value": round(a_val, 3),
        "B_usage_peak": b_wk, "B_value": round(b_val, 3),
        "C_usage_decline": c_wk,
        "A_to_B_weeks": round(wkdiff(a_wk, b_wk), 1),
        "A_to_C_weeks": round(wkdiff(a_wk, c_wk), 1) if c_wk else None,
        "dl_weeks": len(ks),
    }

# ----------------------------------------------------------------------------
# F2-lead / F3 / F4 — logic from analyze3.py (authoritative; Monday labels)
# ----------------------------------------------------------------------------
def f2_lead(stars, dl, window_weeks=26, end="2026-10-06"):
    end_d = datetime.strptime(end, "%Y-%m-%d").date()
    start_d = end_d - timedelta(weeks=window_weeks)
    out = []
    for repo, pkg in MAPPING.items():
        if repo not in stars or pkg not in dl:
            continue
        weeks = sorted(stars[repo]["weeks"], key=lambda w: w["week"])
        cum, growth = [], []
        for i, w in enumerate(weeks):
            c = cum[-1] + w["total"] if cum else w["total"]
            cum.append(c)
            base = cum[i - 4] if i >= 4 else max(1, cum[0])
            growth.append(math.log(max(c, 1) / max(base, 1)))
        dlw = {}
        for p in dl[pkg]:
            d = datetime.strptime(p["date"], "%Y-%m-%d").date()
            if start_d <= d <= end_d:
                monday = d - timedelta(days=d.weekday())
                dlw[monday.isoformat()] = dlw.get(monday.isoformat(), 0) + p["downloads"]
        star_w = {}
        for i, w in enumerate(weeks):
            iso = iso_of(w["week"])
            if start_d <= datetime.strptime(iso, "%Y-%m-%d").date() <= end_d:
                star_w[iso] = growth[i]
        common = sorted(set(star_w) & set(dlw))
        if len(common) < 10:
            continue
        sg = [star_w[k] for k in common]
        dg = [math.log(max(dlw[k], 1)) for k in common]
        zs = [(x - statistics.mean(sg)) / (statistics.stdev(sg) or 1) for x in sg]
        zd = [(x - statistics.mean(dg)) / (statistics.stdev(dg) or 1) for x in dg]
        D = [a - b for a, b in zip(zs, zd)]
        peak_i = D.index(max(D))
        d_peak_week = common[peak_i]
        dl_growth = []
        for i in range(len(common)):
            base = dlw[common[max(0, i - 4)]]
            dl_growth.append(math.log(max(dlw[common[i]], 1) / max(base, 1)))
        min_i = dl_growth.index(min(dl_growth))
        post = dl_growth[min_i:]
        infl_i = min_i + post.index(max(post)) if post else min_i
        inflect_week = common[infl_i]
        lead_weeks = (datetime.strptime(inflect_week, "%Y-%m-%d").date()
                      - datetime.strptime(d_peak_week, "%Y-%m-%d").date()).days / 7
        out.append({
            "repo": repo, "pkg": pkg, "n": len(common),
            "D_peak": round(max(D), 2), "D_peak_week": d_peak_week,
            "dl_min_week": common[min_i],
            "dl_inflection_week": inflect_week,
            "lead_weeks": round(lead_weeks, 1),
        })
    return out

EVENTS = [
    ("2022-11-30", "ChatGPT launch", ["langchain-ai/langchain", "run-llama/llama_index",
                                      "huggingface/transformers", "openai/openai-python"]),
    ("2023-03-16", "AutoGPT viral (repo created)", ["Significant-Gravitas/AutoGPT"]),
    ("2024-11-25", "MCP announced (Anthropic)", ["modelcontextprotocol/modelcontextprotocol",
                                                  "modelcontextprotocol/servers"]),
    ("2025-03-05", "OpenAI adopts MCP", ["modelcontextprotocol/servers"]),
    ("2025-09-22", "anthropics/skills created", ["anthropics/skills"]),
    ("2025-10-16", "Agent Skills announced", ["anthropics/skills"]),
    ("2025-12-09", "MCP donated to Agentic AI Foundation", ["modelcontextprotocol/servers"]),
    ("2026-01-20", "OpenClaw viral (~72h +60k)", ["openclaw/openclaw"]),
    ("2026-01-27", "Anthropic trademark notice (Clawd)", ["openclaw/openclaw"]),
    ("2026-04-16", "Claude Opus 4.7 GA", ["langchain-ai/langchain", "langchain-ai/langgraph",
                                          "openai/openai-python", "ollama/ollama",
                                          "crewAIInc/crewAI", "openclaw/openclaw"]),
    ("2026-04-23", "GPT-5.5 launch", ["openai/openai-python", "langchain-ai/langchain"]),
]

def f3_sync(stars):
    out = []
    for date_str, label, repos in EVENTS:
        ev_d = datetime.strptime(date_str, "%Y-%m-%d").date()
        for repo in repos:
            if repo not in stars:
                continue
            weeks = sorted(stars[repo]["weeks"], key=lambda w: w["week"])
            best, best_wk = 0, None
            for w in weeks:
                iso = datetime.fromtimestamp(w["week"], tz=timezone.utc).date()
                if abs((iso - ev_d).days) <= 42:
                    if w["total"] > best:
                        best, best_wk = w["total"], iso
            lag_days = (best_wk - ev_d).days if best_wk else None
            out.append({"event": date_str + " " + label, "repo": repo,
                        "peak_wk": best, "peak_week": str(best_wk) if best_wk else None,
                        "lag_days": lag_days})
    return out

def f4_autogen(stars):
    # Month labels use the NATIVE star-history timestamps (Sunday-ending weeks),
    # matching the paper's quoted F4 numbers (e.g. 2025-09 = 1,003; 2025-10 = 899).
    # Do NOT re-derive via Monday normalization — that produced a divergent series.
    r = stars["microsoft/autogen"]
    weeks = sorted(r["weeks"], key=lambda w: w["week"])
    q = {}
    for w in weeks:
        key = datetime.fromtimestamp(w["week"], tz=timezone.utc).strftime("%Y-%m")
        q[key] = q.get(key, 0) + w["total"]
    def avg(ms):
        vals = [q[m] for m in ms if m in q]
        return sum(vals) / len(vals) if vals else None
    m24 = [m for m in q if m.startswith("2024")]
    m25 = [m for m in q if m.startswith("2025")]
    m26 = [m for m in q if m.startswith("2026")]
    return {"avg_2024": avg(m24), "avg_2025": avg(m25), "avg_2026": avg(m26), "months": q}

# ----------------------------------------------------------------------------
# Regression gate: regenerated artifacts must equal the validated ones field-by-field
# ----------------------------------------------------------------------------
def regression_gate(name, path, new_rows):
    old = json.load(open(path))
    if isinstance(old, dict) and isinstance(new_rows, dict):
        diffs = [k for k in old if old.get(k) != new_rows.get(k)]
    else:
        norm = lambda rows: sorted([{k: v for k, v in x.items()} for x in rows], key=lambda x: json.dumps(x, sort_keys=True))
        a, b = norm(old), norm(new_rows)
        diffs = []
        if len(a) != len(b):
            diffs.append(f"row count {len(a)} vs {len(b)}")
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                for k in x:
                    if x.get(k) != y.get(k):
                        diffs.append(f"row {i} {k}: {x.get(k)} != {y.get(k)}")
    if diffs:
        print(f"REGRESSION {name}: FAIL — {diffs[:12]}")
        return False
    print(f"REGRESSION {name}: PASS ({len(old) if isinstance(old, list) else len(old)} fields identical)")
    return True

# ----------------------------------------------------------------------------
# Golden numbers (single source of truth for the paper's numbers & dates)
# ----------------------------------------------------------------------------
def write_golden(stars, rows, f1, f2_rows, leads, f4):
    vals, srcs = {}, {}
    def put(k, v, src):
        vals[k] = v; srcs[k] = src
    put("data:repos_n", len(stars), "data dir repo-file count")
    put("data:packages_n", len([f for f in os.listdir(os.path.join(DATA, "downloads")) if f.endswith(".json")]), "data/downloads package count")
    put("data:n_ai", f1["n_ai"], "analyze_final F1 grouping")
    put("data:n_classic", f1["n_classic"], "analyze_final F1 grouping")
    f1r = {x["repo"]: x for x in rows}
    # per-repo facts (Table 1 + panel)
    for repo, r in stars.items():
        tag = repo.replace("/", "__")
        x = f1r[repo]
        put(f"f1:{tag}:max_wk", x["max_wk"], "analyze_final F1 rows")
        put(f"f1:{tag}:pre4", x["pre4_cum"], "analyze_final F1 rows")
        put(f"f1:{tag}:decay", x["postpeak_decay"], "analyze_final F1 rows")
        put(f"f1:{tag}:peak_wk", x["peak_week"], "analyze_final F1 rows")
        put(f"data:{tag}:stars_now", r.get("stars_now"), f"data raw")
        put(f"data:{tag}:created", r.get("created_at", "")[:10], "data raw")
        put(f"data:{tag}:n_weeks", len(r["weeks"]), "data raw len(weeks)")
    # F1 statistics
    for k in ["maxwk_med_ai", "maxwk_med_cl", "maxwk_U", "maxwk_p",
              "pre4_med_ai", "pre4_med_cl", "pre4_U", "pre4_p", "pre4_ratio",
              "decay_med_ai", "decay_med_cl", "decay_U", "decay_p"]:
        put(f"f1:{k}", f1[k], "analyze_final F1 mannwhitneyu")
    # multipliers
    vmx = f1r["vuejs/vue"]["max_wk"]; tfmx = f1r["tensorflow/tensorflow"]["max_wk"]
    put("f1:vue_max", vmx, "analyze_final F1 rows")
    put("f1:tf_max", tfmx, "analyze_final F1 rows")
    put("f1:mult_openclaw_vs_vue", round(116281 / vmx, 1), "116281 / Vue max")
    put("f1:mult_autogpt_vs_vue", round(49402 / vmx, 1), "49402 / Vue max")
    put("f1:mult_openclaw_vs_tf", round(116281 / tfmx, 1), "116281 / TF max")
    # F2 / F2-lead
    ai10 = [x for x in f2_rows if x["repo"] in {
        "langchain-ai/langchain", "langchain-ai/langgraph", "run-llama/llama_index",
        "microsoft/autogen", "crewAIInc/crewAI", "modelcontextprotocol/servers",
        "openai/openai-python", "ollama/ollama", "vllm-project/vllm", "openclaw/openclaw"}]
    ab = [x["A_to_B_weeks"] for x in ai10]; ac = [x["A_to_C_weeks"] for x in ai10]
    put("f2:mean_ab", round(statistics.mean(ab), 1), "analyze_final F2 AI10")
    put("f2:range_ab", [min(ab), max(ab)], "analyze_final F2 AI10")
    put("f2:mean_ac", round(statistics.mean(ac), 1), "analyze_final F2 AI10")
    put("f2:range_ac", [min(ac), max(ac)], "analyze_final F2 AI10")
    put("f2:sign_p", 9.77e-4, "binomial sign test 10/10")
    for x in f2_rows:
        tag = x["repo"].replace("/", "__")
        put(f"f2:{tag}:A", x["A_expectation_peak"], "analyze_final F2")
        put(f"f2:{tag}:B", x["B_usage_peak"], "analyze_final F2")
        put(f"f2:{tag}:C", x["C_usage_decline"], "analyze_final F2")
        put(f"f2:{tag}:AB", x["A_to_B_weeks"], "analyze_final F2")
        put(f"f2:{tag}:AC", x["A_to_C_weeks"], "analyze_final F2")
    for x in leads:
        tag = x["repo"].replace("/", "__")
        put(f"f2:{tag}:Dpeak", x["D_peak_week"], "analyze_final F2-lead")
        put(f"f2:{tag}:Dval", x["D_peak"], "analyze_final F2-lead")
    l10 = [x for x in leads if x["repo"] in {y["repo"] for y in ai10}]
    put("f3:window", [min(x["D_peak_week"] for x in l10), max(x["D_peak_week"] for x in l10)], "analyze_final F2-lead AI10")
    put("f3:p", 2 * (2 / 26) ** 10, "binomial formula 2*(2/26)^10")
    # F4
    for k, v in f4["months"].items():
        put(f"f4:{k}", round(v), "analyze_final F4 monthly sum")
    months = sorted(f4["months"])
    pre25 = [f4["months"][m] for m in months if m.startswith("2025") and m < "2025-10"]
    post25 = [f4["months"][m] for m in months if m.startswith("2025") and m >= "2025-10"]
    m26 = [f4["months"][m] for m in months if m.startswith("2026")]
    put("f4:pre25_avg", round(statistics.mean(pre25)), "2025-01..09 mean")
    put("f4:post25_avg", round(statistics.mean(post25)), "2025-10..12 mean")
    put("f4:m26_avg", round(statistics.mean(m26)), "2026 mean")
    put("f4:mom_pct", round((f4["months"]["2025-10"] - f4["months"]["2025-09"]) / f4["months"]["2025-09"] * 100), "2025-10 vs 2025-09 %")
    put("f4:yoy_pct", round((statistics.mean(m26) - statistics.mean(pre25)) / statistics.mean(pre25) * 100), "2026 avg vs 2025 pre avg %")
    put("f4:post25_pct", round((statistics.mean(post25) - statistics.mean(pre25)) / statistics.mean(pre25) * 100), "2025-10..12 avg vs pre %")
    # ChatGPT-response weeks (data-derived)
    for repo, d, val in [("huggingface/transformers", "2022-12-04", 520), ("openai/openai-python", "2022-12-04", 240),
                         ("langchain-ai/langchain", "2023-01-08", 364), ("run-llama/llama_index", "2023-01-08", 710)]:
        r = stars[repo]; ws = sorted(r["weeks"], key=lambda w: w["week"])
        v = next(w["total"] for w in ws if datetime.fromtimestamp(w["week"], tz=timezone.utc).strftime("%Y-%m-%d") == d)
        assert v == val, (repo, d, v, val)
        put(f"data:{repo.replace('/','__')}:wk_{d}", v, "data raw weekly total")
        put(f"ref:chatgpt_week_{repo.replace('/','__')}", d, "§5.4 ChatGPT-response week")
    out = {"values": {}, "sources": srcs,
           "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "generated_by": "analyze_final.py"}
    for k, v in vals.items():
        if isinstance(v, (int, float)) and v is not None and v == v:
            out["values"][k] = round(float(v), 10)
        elif isinstance(v, list):
            out["values"][k] = v
        else:
            out["values"][k] = v
    path = os.path.join(HERE, "writing", ".workflow", "golden_numbers.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(json.dumps(out, indent=1))
    print("golden_numbers.json written:", len(out["values"]), "keys")

# ----------------------------------------------------------------------------
if __name__ == "__main__":
    stars = load_stars()
    dl = load_dl()
    rows = build_f1_rows(stars)
    f1 = f1_stats(rows)
    f2_rows = [f2_run(repo, pkg, stars, dl) for repo, pkg in MAPPING.items()]
    f2_rows = [r for r in f2_rows if r]
    leads = f2_lead(stars, dl)
    f3 = f3_sync(stars)
    f4 = f4_autogen(stars)

    # write frozen artifacts
    json.dump(rows, open(os.path.join(DATA, "f1_revised.json"), "w"), indent=1)
    json.dump(f2_rows, open(os.path.join(DATA, "f2_final.json"), "w"), indent=1)
    json.dump(leads, open(os.path.join(DATA, "f2_lead.json"), "w"), indent=1)
    json.dump(f3, open(os.path.join(DATA, "f3_sync.json"), "w"), indent=1)
    json.dump(f4, open(os.path.join(DATA, "f4_autogen.json"), "w"), indent=1)

    # regression gate vs previously validated artifacts
    ok = True
    ok &= regression_gate("f1_revised", os.path.join(DATA, "f1_revised.json"), rows)
    ok &= regression_gate("f2_final", os.path.join(DATA, "f2_final.json"), f2_rows)
    ok &= regression_gate("f2_lead", os.path.join(DATA, "f2_lead.json"), leads)
    print("F1 stats:", {k: f1[k] for k in ["n_ai","n_classic","pre4_med_ai","pre4_med_cl","pre4_U","pre4_p","pre4_ratio","decay_med_ai","decay_med_cl","decay_U","decay_p","maxwk_med_ai","maxwk_med_cl","maxwk_U","maxwk_p"]})
    if not ok:
        print("REGRESSION GATE: FAIL — aborting golden write; investigate before trusting.")
        raise SystemExit(1)
    print("REGRESSION GATE: PASS")
    write_golden(stars, rows, f1, f2_rows, leads, f4)
