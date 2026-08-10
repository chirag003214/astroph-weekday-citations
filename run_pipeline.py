#!/usr/bin/env python3
"""
Entry point: python run_pipeline.py --journal MNRAS

Stages:
  1. Fetch ADS records (cached to data/raw/)
  2. Fetch arXiv metadata (incrementally cached to data/raw/arxiv_meta.jsonl)
  3. Merge & filter to astro-ph.* primary category
  4. Compute submission_day and announcement_day columns
  5. Statistical analysis
  6. Figures (results/<journal>/fig*.png + .pdf)
  7. Tables (results/<journal>/table_*.csv + .md)
  8. RESULTS.md (results/<journal>/RESULTS.md)
"""
import argparse
import logging
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

_SEP = "═" * 62


def main() -> None:
    parser = argparse.ArgumentParser(
        description="arXiv day-of-week citation pipeline (Desai et al. methodology)"
    )
    parser.add_argument(
        "--journal", required=True,
        choices=["MNRAS", "ApJ", "ApJL", "ApJS", "A&A", "JCAP"],
        help="Journal bibstem to analyse.",
    )
    args = parser.parse_args()
    journal: str = args.journal

    # ── Validate token before any network call ───────────────────────────────
    token = os.environ.get("ADS_API_TOKEN", "").strip()
    if not token:
        sys.exit(
            "\nERROR: ADS_API_TOKEN is not set.\n"
            "  1. Get a free token at https://ui.adsabs.harvard.edu/user/settings/token\n"
            "  2. export ADS_API_TOKEN=<your-token>\n"
            "  The analysis stage can run fully offline once the cache is populated.\n"
        )

    import config
    results_dir = config.get_results_dir(journal)
    results_dir.mkdir(parents=True, exist_ok=True)

    # ── Stage 1: ADS records ─────────────────────────────────────────────────
    log.info(_SEP)
    log.info("STAGE 1  Fetching ADS records for %s", journal)
    from src.ads_client import fetch_ads_records, build_dataframe
    raw_records = fetch_ads_records(journal, token)
    n_ads = len(raw_records)
    log.info("  ADS total records : %d", n_ads)

    df_ads, n_no_arxiv = build_dataframe(raw_records)
    n_with_arxiv = len(df_ads)
    log.info("  With arXiv ID     : %d", n_with_arxiv)
    log.info("  Dropped (no ID)   : %d  (%.1f%%)", n_no_arxiv,
             100 * n_no_arxiv / n_ads if n_ads else 0)

    # ── Stage 2: arXiv metadata ──────────────────────────────────────────────
    log.info(_SEP)
    log.info("STAGE 2  Fetching arXiv metadata for %d papers", n_with_arxiv)
    log.info("  Expected duration: ~10–15 min (arXiv rate limit: 3 s between batches)")
    from src.arxiv_client import fetch_arxiv_metadata
    arxiv_meta = fetch_arxiv_metadata(df_ads["arxiv_id"].tolist(), journal=journal)
    df_arxiv = pd.DataFrame(arxiv_meta)
    log.info("  arXiv metadata retrieved: %d records", len(df_arxiv))

    # ── Stage 3: Merge & filter to astro-ph ──────────────────────────────────
    log.info(_SEP)
    log.info("STAGE 3  Merging and filtering to astro-ph primary category")
    df = df_ads.merge(df_arxiv, on="arxiv_id", how="inner")
    n_after_merge = len(df)
    df = df[df["primary_category"].str.startswith("astro-ph", na=False)].copy()
    n_non_astroph = n_after_merge - len(df)
    n_final = len(df)
    log.info("  After merge                  : %d", n_after_merge)
    log.info("  Excluded (non astro-ph prim) : %d", n_non_astroph)
    log.info("  Final analysis sample        : %d", n_final)

    if n_final == 0:
        sys.exit("ERROR: No papers remain after filtering. Check cache and API responses.")

    # ── Stage 4: Day-of-week columns ─────────────────────────────────────────
    log.info(_SEP)
    log.info("STAGE 4  Computing day-of-week columns (America/New_York, DST-aware)")
    from src.schedule import submission_day, announcement_day, announcement_date
    df["v1_utc"] = pd.to_datetime(df["v1_published"], utc=True)
    df["submission_day"] = df["v1_utc"].apply(
        lambda dt: submission_day(dt.to_pydatetime())
    )
    df["announcement_day"] = df["v1_utc"].apply(
        lambda dt: announcement_day(dt.to_pydatetime())
    )
    df["ann_date"] = df["v1_utc"].apply(
        lambda dt: announcement_date(dt.to_pydatetime())
    )
    log.info("  submission_day distribution:\n%s",
             df["submission_day"].value_counts().to_string())
    log.info("  announcement_day distribution:\n%s",
             df["announcement_day"].value_counts().to_string())

    # ── Stage 5: Statistical analysis ────────────────────────────────────────
    log.info(_SEP)
    log.info("STAGE 5  Statistical analysis")
    from src.stats import run_analysis
    stats_results = run_analysis(df)

    # ── Stage 6: Figures ─────────────────────────────────────────────────────
    log.info(_SEP)
    log.info("STAGE 6  Generating figures → %s/", results_dir)
    from src.plots import make_all_plots
    make_all_plots(df, stats_results, results_dir)

    # ── Stage 7: Tables ──────────────────────────────────────────────────────
    log.info(_SEP)
    log.info("STAGE 7  Writing tables")
    _write_tables(stats_results, results_dir)

    # ── Stage 8: RESULTS.md ──────────────────────────────────────────────────
    log.info(_SEP)
    log.info("STAGE 8  Writing RESULTS.md")
    _write_results_md(
        df=df,
        stats_results=stats_results,
        results_dir=results_dir,
        journal=journal,
        n_ads=n_ads,
        n_with_arxiv=n_with_arxiv,
        n_no_arxiv=n_no_arxiv,
        n_after_merge=n_after_merge,
        n_non_astroph=n_non_astroph,
        n_final=n_final,
    )

    log.info(_SEP)
    log.info("Pipeline complete. All outputs in: %s/", results_dir)


# ── Table writer ─────────────────────────────────────────────────────────────

def _write_tables(stats_results: dict, results_dir: Path) -> None:
    for label in ("submission_day", "announcement_day"):
        bs: pd.DataFrame = stats_results[label]["bin_stats"]
        bs_out = bs.copy()
        bs_out.columns = ["Day", "N", "Mean", "SEM", "Median", "CI_lo_95", "CI_hi_95"]
        bs_out.to_csv(results_dir / f"table_{label}.csv", index=False, float_format="%.4f")
        with open(results_dir / f"table_{label}.md", "w", encoding="utf-8") as fh:
            fh.write(f"### Per-bin statistics — {label.replace('_', ' ')}\n\n")
            fh.write(bs_out.to_markdown(index=False, floatfmt=".2f"))
            fh.write("\n")

        pw: pd.DataFrame = stats_results[label]["pairwise"]
        pw.to_csv(results_dir / f"pairwise_{label}.csv", index=False, float_format="%.6g")
        with open(results_dir / f"pairwise_{label}.md", "w", encoding="utf-8") as fh:
            fh.write(f"### Pairwise Mann-Whitney U (Holm-corrected) — {label.replace('_', ' ')}\n\n")
            fh.write(pw.to_markdown(index=False, floatfmt=".4g"))
            fh.write("\n")

    # Year-stratified tables
    for label in ("submission_day", "announcement_day"):
        ys: pd.DataFrame = stats_results["year_stratified"][label]
        ys.to_csv(results_dir / f"year_stratified_{label}.csv", index=False, float_format="%.4f")

    # Year-normalized bin stats
    for label in ("submission_day", "announcement_day"):
        yn: pd.DataFrame = stats_results["year_normalized"][label]
        yn.to_csv(results_dir / f"year_normalized_{label}.csv", index=False, float_format="%.4f")

    # Listing-size proxy
    lsp: pd.DataFrame = stats_results["listing_size_proxy"]
    lsp.to_csv(results_dir / "listing_size_proxy.csv", index=False, float_format="%.4f")
    with open(results_dir / "listing_size_proxy.md", "w", encoding="utf-8") as fh:
        fh.write("### Listing-size proxy (Dietrich 2007 motivation)\n\n")
        fh.write(lsp.to_markdown(index=False, floatfmt=".2f"))
        fh.write("\n")

    log.info("Tables written to %s", results_dir)


# ── RESULTS.md writer ────────────────────────────────────────────────────────

def _fmt_p(p: float) -> str:
    if np.isnan(p):
        return "N/A"
    if p < 0.001:
        return f"{p:.2e}"
    return f"{p:.4f}"


def _write_results_md(
    df: pd.DataFrame,
    stats_results: dict,
    results_dir: Path,
    journal: str,
    n_ads: int,
    n_with_arxiv: int,
    n_no_arxiv: int,
    n_after_merge: int,
    n_non_astroph: int,
    n_final: int,
) -> None:
    ww = stats_results["weekend_weekday"]
    sub_kw = stats_results["submission_day"]["kruskal"]
    ann_kw = stats_results["announcement_day"]["kruskal"]
    sub_bs = stats_results["submission_day"]["bin_stats"]
    ann_bs = stats_results["announcement_day"]["bin_stats"]
    lsp = stats_results["listing_size_proxy"]

    def _row(bs, day):
        r = bs[bs["day"] == day]
        if r.empty:
            return "N/A", "N/A", "N/A", "N/A"
        return (
            int(r["n"].values[0]),
            f"{r['median'].values[0]:.1f} [{r['ci_lo'].values[0]:.1f}, {r['ci_hi'].values[0]:.1f}]",
            f"{r['mean'].values[0]:.1f}",
            f"{r['sem'].values[0]:.2f}",
        )

    lines = [
        f"# Results — {journal}  (arXiv day-of-week citation study)",
        "",
        f"Auto-generated by `run_pipeline.py`. Methodology follows Desai (arXiv:2410.03342).",
        "",
        "---",
        "",
        "## Pipeline summary",
        "",
        f"| Stage | N |",
        f"|---|---|",
        f"| ADS records returned | {n_ads:,} |",
        f"| Records with parseable arXiv ID | {n_with_arxiv:,} |",
        f"| Dropped (no arXiv ID) | {n_no_arxiv:,} |",
        f"| After merge with arXiv metadata | {n_after_merge:,} |",
        f"| Excluded (non astro-ph primary category) | {n_non_astroph:,} |",
        f"| **Final analysis sample** | **{n_final:,}** |",
        "",
        "---",
        "",
        "## 1. Submission day (7-bin)",
        "",
        "Day of week of the arXiv v1 timestamp converted to America/New_York.",
        "",
        "| Day | N | Median [95% CI] | Mean | SEM |",
        "|---|---|---|---|---|",
    ]
    for day in ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]:
        n, med, mean, sem = _row(sub_bs, day)
        lines.append(f"| {day} | {n} | {med} | {mean} | {sem} |")

    lines += [
        "",
        f"**Kruskal-Wallis (7 bins):** H = {sub_kw['statistic']:.3f},  "
        f"p = {_fmt_p(sub_kw['pvalue'])}",
        "",
        "### Weekend vs weekday (headline test)",
        "",
        f"| Group | N | Median | Mean |",
        f"|---|---|---|---|",
        f"| Weekend (Sat+Sun) | {ww['weekend_n']} | "
        f"{ww['weekend_median']:.1f} | {ww['weekend_mean']:.1f} |",
        f"| Weekday (Mon–Fri) | {ww['weekday_n']} | "
        f"{ww['weekday_median']:.1f} | {ww['weekday_mean']:.1f} |",
        "",
        f"Mann-Whitney U = {ww['statistic']:.0f},  p = {_fmt_p(ww['pvalue'])}",
        f"Mean difference (weekend − weekday): {ww['mean_diff']:.2f} citations",
        "",
        "> **Comparison with arXiv:2509.09601:** That study (hep/nucl categories, ADS) found "
        "weekend submissions receive ~6–7 fewer mean citations (>10σ, Mann-Whitney). "
        f"Our {journal}/astro-ph result shows a mean difference of "
        f"{ww['mean_diff']:.2f} citations "
        f"(p = {_fmt_p(ww['pvalue'])}). "
        "Interpret this comparison cautiously: citation cultures differ between "
        "hep/nucl and astro-ph, and our sample spans different years.",
        "",
        "---",
        "",
        "## 2. Announcement day (5-bin)",
        "",
        "Effective arXiv listing day after applying the 14:00 ET deadline rule "
        "and rolling Sat/Sun → Monday.",
        "",
        "| Day | N | Median [95% CI] | Mean | SEM |",
        "|---|---|---|---|---|",
    ]
    for day in ["Monday","Tuesday","Wednesday","Thursday","Friday"]:
        n, med, mean, sem = _row(ann_bs, day)
        lines.append(f"| {day} | {n} | {med} | {mean} | {sem} |")

    lines += [
        "",
        f"**Kruskal-Wallis (5 bins):** H = {ann_kw['statistic']:.3f},  "
        f"p = {_fmt_p(ann_kw['pvalue'])}",
        "",
        "---",
        "",
        "## 3. Listing-size proxy (Dietrich 2007 motivation)",
        "",
        "Dietrich (arXiv:0712.1037) showed that papers near the top of a longer "
        "astro-ph listing receive ~2× citations, and that Monday listings are "
        "longest because they absorb three days of submissions (Fri+Sat+Sun). "
        "The table below counts papers in our sample per announcement date, "
        "averaged by weekday. **This uses only the journal sub-sample, not the "
        "full astro-ph listing**, so it is a proxy for relative dilution, not a "
        "reconstruction of true listing position.",
        "",
        "| Day | N (papers) | Median citations | Avg listing size (sample proxy) |",
        "|---|---|---|---|",
    ]
    for _, row in lsp.iterrows():
        lines.append(
            f"| {row['announcement_day']} | {int(row['n'])} | "
            f"{row['median_citations']:.1f} | {row['avg_listing_size']:.1f} |"
        )

    lines += [
        "",
        "---",
        "",
        "## 4. Caveats",
        "",
        "1. **Listing-position effect (Dietrich 2007):** Papers appearing earlier in "
        "a daily astro-ph listing may receive disproportionately more citations. "
        "Monday listings are systematically larger (absorbing Fri–Sun submissions), "
        "which could suppress per-paper visibility on Mondays. We cannot reconstruct "
        "true listing positions from ADS metadata alone.",
        "",
        "2. **Listing-size dilution:** Even without position effects, a larger daily "
        "listing means each paper competes for reader attention against more papers.",
        "",
        "3. **Holiday schedule shifts:** US federal holidays occasionally delay arXiv "
        "announcements by one business day. The `announcement_day()` function does not "
        "model this; affected papers will be mis-binned by one day.",
        "",
        "4. **Citation-age differences across years:** Papers published in 2020 have "
        "had ~4 years to accumulate citations vs ~1 year for 2023 papers. The "
        "year-stratified and year-normalized analyses (see CSVs) help assess whether "
        "the day-of-week pattern is stable or driven by year-level confounds.",
        "",
        "5. **Single-journal scope:** Results are specific to "
        f"{journal} (2020–2023). Rerun with `--journal ApJ` to assess robustness "
        "across journals. Cross-journal differences in editorial turnaround or "
        "author demographics could interact with submission-day patterns.",
        "",
        "6. **Bootstrap CI interpretation:** 95% percentile bootstrap CIs for the "
        "median are reported following Desai (arXiv:2410.03342). With 10,000 "
        "resamples and seed=42, results are fully reproducible.",
        "",
        "---",
        "",
        "## 5. Reproducibility",
        "",
        "All raw API responses are cached in `data/raw/`. "
        "Re-running `python run_pipeline.py --journal "
        f"{journal}` after the initial fetch operates fully offline "
        "and produces bit-identical statistical results.",
        "",
        "_End of auto-generated report._",
    ]

    out_path = results_dir / "RESULTS.md"
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    log.info("RESULTS.md written to %s", out_path)


if __name__ == "__main__":
    main()
