# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

Bibliometrics pipeline (collaboration with Prof. Shantanu Desai, IIT Hyderabad) testing whether astro-ph arXiv papers submitted on different days of the week end up with different citation counts. Sample: refereed articles in MNRAS, ApJ, ApJL, ApJS, A&A, JCAP, AJ, PASJ with an astro-ph.* primary category; main period 2020–2023 (`config.DEFAULT_YEARS`), appendix period 2015–2020 via `--years`. Two independent day-of-week analyses: `submission_day` (7 bins) and `announcement_day` (5 bins, applying arXiv's 14:00 ET deadline rule).

## Common commands

```bash
# Install dependencies (Python 3.10+ required for zoneinfo + newer type hints)
pip install -r requirements.txt

# Run full pipeline
python run_pipeline.py --journal MNRAS
python run_pipeline.py --journal ApJ   # shares the arXiv metadata cache
python run_pipeline.py --journal AJ --years 2015-2020   # appendix period
python summarize.py [--years 2015-2020]                # cross-journal table

# Run tests
pytest tests/ -v
pytest tests/test_schedule.py -v       # schedule unit tests only
```

Set `ADS_API_TOKEN` before running. The pipeline fails loudly if the token is missing.

## Architecture

```
config.py          — single source of truth: API URLs, journal queries, file paths
run_pipeline.py    — 8-stage CLI orchestrator; imports from src/
summarize.py       — collects results/[<period>/]<journal>/weekend_weekday.csv into one table
src/
  ads_client.py    — ADS pagination (rows=2000), arXiv ID regex extraction, JSON cache
  arxiv_client.py  — arXiv Atom XML parsing, incremental JSONL cache, 3s rate-limit sleep
  schedule.py      — submission_day / announcement_day / announcement_date
  stats.py         — bootstrap_median_ci, bin_stats, kruskal_wallis,
                     pairwise_mannwhitney_holm, weekend_vs_weekday_mwu,
                     year_stratified, year_normalized_bin_stats, listing_size_proxy
  plots.py         — 10 figures, matplotlib only, 300 dpi PNG+PDF
```

## Critical methodology

**`announcement_day` rule** (in `src/schedule.py`):
1. Convert UTC → `America/New_York` via `zoneinfo` (never a fixed UTC offset).
2. If local hour ≥ 14, advance date by one day.
3. Roll Saturday (+2) or Sunday (+1) → Monday.

This is tested in `tests/test_schedule.py`, including two DST transition tests that prove a fixed UTC-5 offset gives the wrong answer.

## Caching design

- ADS: full results cached as `data/raw/{journal}_ads_raw.json` (default period) or `data/raw/{journal}_{START-END}_ads_raw.json`. Delete to re-fetch. Non-default periods write results to `results/{START-END}/{journal}/`.
- arXiv: incremental JSONL at `data/raw/arxiv_meta.jsonl`. New IDs are appended; existing records are never re-fetched. Safe to interrupt and resume.
- Analysis stage runs fully offline from cache.

## Adding a new journal

Add an entry to `JOURNALS` in `config.py`:
```python
"XYZ": {
    "bibstem": "XYZ",
    "ads_query": "bibstem:XYZ year:{years} property:refereed doctype:article",
},
```
`{years}` is filled from `--years`. The `--journal` choices are read from `JOURNALS` automatically.

## Statistical conventions

- Primary statistic: median + 95% percentile bootstrap CI (10,000 resamples, seed=42) — follows Desai arXiv:2410.03342.
- Mean ± SEM also reported for comparison with Tsantilas et al. arXiv:2509.09601 (hep/nucl found ~6–7 fewer mean citations for weekend submissions, >10σ).
- Holm-Bonferroni correction for pairwise Mann-Whitney tests.
- Environment: run in the `weekday` conda env — `scipy.stats` fails to import (DLL error) in `base`.
- `listing_size_proxy` requires an `ann_date` column; `run_pipeline.py` adds it before calling `run_analysis`.
