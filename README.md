# Hype Cycle, Quantified — Data & Code Package

**Paper:** *The Hype Cycle, Quantified: Star–Download Divergence as a Leading Indicator of Technology Adoption in the AI Tool Ecosystem*
**Data fetched:** 2026-10-07 (GitHub REST API + PyPI JSON API)
**Package version:** v1.0 (2026-10-08)

This package contains **every dataset and every script** needed to reproduce all
numbers, statistics, and figures in the paper, from raw data to the quoted
values. It is self-contained: running the two verification commands below
regenerates every statistic and proves the paper's numbers are reproducible.

---

## 1. Quick start (reproduce everything)

Requirements: Python ≥ 3.9 and SciPy (for `analyze_final.py`; the independent
verifier needs only the standard library).

```bash
cd hypecycle-data

# 1) Regenerate every statistic from raw data + regression gate vs frozen artifacts
python3 analyze_final.py
#   Expected: REGRESSION f1_revised: PASS · f2_final: PASS · f2_lead: PASS
#             REGRESSION GATE: PASS · golden_numbers.json written (346 keys)

# 2) Independent reproduction (no scipy, no shared code paths — hand-written stats)
python3 verify_independent.py
#   Expected: PASS 36 | FAIL 0 → INDEPENDENT VERIFICATION: PASS
```

`analyze_final.py` also regenerates the frozen analysis artifacts
(`data/f1_revised.json`, `f2_final.json`, `f2_lead.json`, `f3_sync.json`,
`f4_autogen.json`) and compares them field-by-field against the packaged
versions (the regression gate). It writes `golden_numbers.json`
(the single source of truth for every number the paper quotes) to
`writing/.workflow/golden_numbers.json`.

---

## 2. Data dictionary

### 2.1 Repository star histories — `data/{owner}__{repo}.json` (25 files)

| Field | Type | Meaning |
|---|---|---|
| `repo` | string | GitHub `owner/name` |
| `created_at` | ISO datetime | repository creation timestamp |
| `stars_now` | int | stargazers count at fetch time |
| `forks_now` / `open_issues` / `language` | mixed | repository snapshot at fetch time |
| `fetched_at` | ISO datetime | data-collection timestamp (2026-10-07T20:26Z) |
| `weeks` | array | weekly star **additions**; each `{week: unix_seconds, total: int}` |
| `weeks[].week` | int | Sunday-ending week timestamp (GitHub native) |
| `weeks[].total` | int | stars added that week (may be 0) |

Note: `weeks` is stored newest-first; every script sorts ascending before use.

### 2.2 PyPI download series — `data/downloads/{pkg}.json` (20 files)

| Field | Type | Meaning |
|---|---|---|
| `package` | string | PyPI project name |
| `fetched_at` | ISO datetime | collection time (2026-10-07T19:16Z) |
| `series` | array | daily `{date: YYYY-MM-DD, downloads: int}` |
| `series` range | — | 2026-04-08 → 2026-10-06 (182 days, complete, no gaps) |

### 2.3 Frozen analysis artifacts (regression baselines)

`data/f1_revised.json` (25 repos, Table 1 fields), `data/f2_final.json`
(13 packages, three-phase detection), `data/f2_lead.json` (13 packages,
divergence vs inflection), `data/f3_sync.json` (21 event–repo pairs),
`data/f4_autogen.json` (AutoGen monthly aggregates). These are what the
regression gate compares against.

---

## 3. Conventions (must read — three label conventions)

1. **Star-history weeks** (F1, Table 1, F4): **Sunday-ending** labels, native
   GitHub timestamps.
2. **Download-window weeks** (F2, F2-lead): **Monday-start** labels, native
   PyPI weekly aggregation.
3. **F4 months**: calendar months of the star timestamps (e.g. 2025-09 = 1,003;
   2025-10 = 899) — **not** Monday-normalized months.

These conventions are stated in the paper's Section 3 (data provenance) and are
hard-coded in `analyze_final.py` with comments forbidding re-derivation.

---

## 4. What each script is

| Script | Role | Dependencies |
|---|---|---|
| `analyze_final.py` | **Single authoritative statistics implementation.** Computes every quoted number from raw data; regenerates artifacts + golden; regression gate. | scipy (Mann–Whitney) |
| `verify_independent.py` | **Independent reproduction.** Re-implements every statistic by hand (no scipy, no shared code); checks golden vs raw data; positive control. | standard library only |
| `collect_stars.py` | GitHub star-history collector (resumable; API snapshot protocol) | requests |
| `collect_downloads.py` | PyPI daily-downloads collector (resumable) | requests |

The paper's manuscript-side number gate (`verify_numbers.py`, comparing every
number in the manuscript text against `golden_numbers.json`) is part of the
paper's internal workflow and is documented there; the package-level
reproducibility contract is commands in §1.

---

## 5. Licensing & provenance

- **Data:** dedicated to the public domain under **CC0 1.0**. The data are
  metadata retrieved from public APIs (GitHub REST API; PyPI JSON API); no
  private, personal, or proprietary information is included. GitHub and PyPI
  remain the owners of their platforms and marks; this package is an
  independently collected snapshot.
- **Code:** MIT License.
- Collection scripts reproduce the exact acquisition protocol (API endpoints,
  parameters, resume logic) so the snapshot can be re-collected and diffed.

## 6. How to cite

```bibtex
@misc{hypecycle_data2026,
  title        = {Hype Cycle, Quantified — Data and Code Package},
  author       = {Zhang, Shuren},
  year         = {2026},
  howpublished = {Zenodo, DOI: [to be assigned]},
  note         = {Fetched 2026-10-07; CC0}
}
```

## 7. Limitations (mirrors paper Section 6.4)

- PyPI window is 182 days (2026-04-08 → 2026-10-06); F2 is restricted to the
  2026 window.
- 20 packages / 25 repositories is a curated, ecosystem-representative sample,
  not a census.
- Star counts can include manipulated accounts; the paper mitigates via
  growth-rate differentials (D_t), not levels (see He et al. 2026, ICSE).
- SHA-256 manifest: see `MANIFEST.md` (verify with `sha256sum -c`).
