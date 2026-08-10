# astroph-weekday-citations

Reproducible pipeline to test whether astro-ph papers posted to arXiv on different days of the week end up with different citation counts.

**Research question:** Do MNRAS (or ApJ) refereed articles whose arXiv preprint was submitted on a particular weekday accumulate systematically more or fewer citations?

Methodology follows Desai (arXiv:2410.03342). Results are compared against Tsantilas et al. (arXiv:2509.09601), who found ~6–7 fewer mean citations for weekend submissions in hep/nucl (>10σ).

---

## Setup

**Requirements:** Python 3.10+, Anaconda recommended.

```bash
pip install -r requirements.txt
```

### Get a NASA ADS token

1. Create a free account at <https://ui.adsabs.harvard.edu>
2. Go to **Account → Settings → API Token** and generate a token
3. Export it in your shell (or add to `.env`):

```bash
export ADS_API_TOKEN=<your-token>
```

---

## Run

```bash
# Full pipeline for MNRAS (2020–2023)
python run_pipeline.py --journal MNRAS

# Re-run for ApJ (shares the arXiv metadata cache)
python run_pipeline.py --journal ApJ
```

First run fetches ~14,000 arXiv records in batches of 100 with a mandatory 3-second sleep between batches (arXiv rate limit). **Expect ~10–15 minutes** for the arXiv stage. All raw API responses are cached to `data/raw/`; subsequent runs are fully offline and complete in seconds.

---

## Outputs

All outputs land in `results/<journal>/`:

| File | Description |
|---|---|
| `fig1_median_submission_day.(png\|pdf)` | Median citations ± 95% bootstrap CI by submission day |
| `fig2_median_announcement_day.(png\|pdf)` | Same, by announcement day |
| `fig3_mean_sem_submission_day.(png\|pdf)` | Mean ± SEM by submission day |
| `fig4_mean_sem_announcement_day.(png\|pdf)` | Mean ± SEM by announcement day |
| `fig5_paper_counts.(png\|pdf)` | Paper counts per bin (both binnings) |
| `fig6–7_year_stratified_*.(png\|pdf)` | Year-stratified medians (robustness check) |
| `fig8–9_survival_*.(png\|pdf)` | Log-scale empirical survival functions per day |
| `fig10_listing_size_proxy.(png\|pdf)` | Median citations vs average listing size |
| `table_submission_day.(csv\|md)` | N / mean / SEM / median / 95% CI per bin |
| `table_announcement_day.(csv\|md)` | Same for announcement-day binning |
| `pairwise_*.csv / .md` | Pairwise Mann-Whitney U + Holm-corrected p-values |
| `year_stratified_*.csv` | Median per (year, day) |
| `year_normalized_*.csv` | Stats on year-normalized citation counts |
| `listing_size_proxy.csv / .md` | Dietrich-motivated listing-size analysis |
| `RESULTS.md` | Auto-generated narrative summary with all statistics |

---

## Day-of-week binnings

Two independent analyses are run:

**`submission_day` (7 bins: Mon–Sun)**  
Weekday of the arXiv v1 `<published>` timestamp, converted to `America/New_York` using `zoneinfo` (DST-aware).

**`announcement_day` (5 bins: Mon–Fri)**  
arXiv's effective listing day, computed by:
1. Convert UTC timestamp to `America/New_York`.
2. If local time ≥ 14:00, advance the date by one day (submission missed that day's deadline).
3. Roll Saturday (+2 days) or Sunday (+1 day) forward to Monday.

This correctly maps the Friday-14:00-to-Monday-14:00 window to Monday's listing.  
*Known limitation:* US federal holidays occasionally delay announcements by one business day; not modelled.

---

## Tests

```bash
# Run all tests
pytest tests/ -v

# Run only the schedule unit tests
pytest tests/test_schedule.py -v
```

The schedule tests cover: Fri 13:59 vs 14:01, Sat, Sun, Mon 13:59 vs 14:01, and DST transitions (spring 2022-03-13, fall 2022-11-06), including a check that a fixed UTC offset would give the wrong answer.

---

## Project structure

```
config.py              — API URLs, journal presets, paths, statistical constants
run_pipeline.py        — CLI entry point (--journal MNRAS | ApJ)
src/
  ads_client.py        — NASA ADS pagination + arXiv ID extraction + caching
  arxiv_client.py      — arXiv Atom API, batch fetching, incremental JSONL cache
  schedule.py          — submission_day / announcement_day / announcement_date
  stats.py             — bootstrap CI, Kruskal-Wallis, Mann-Whitney, Holm correction
  plots.py             — all figures (matplotlib, 300 dpi PNG + PDF)
tests/
  test_schedule.py     — pytest unit tests for announcement_day DST logic
data/raw/              — cached API responses (not committed)
results/<journal>/     — all outputs
```

---

## Key references

- Desai, S. (2024). *Citation statistics of MNRAS papers*. arXiv:2410.03342
- Tsantilas et al. (2025). *Weekend submission effect in hep/nucl*. arXiv:2509.09601
- Dietrich, J. (2007). *Listing position and citation counts in astro-ph*. arXiv:0712.1037
