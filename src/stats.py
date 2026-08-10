"""Statistical analysis for the day-of-week citation study."""
import logging
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

import config

log = logging.getLogger(__name__)

SUBMISSION_DAY_ORDER = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
]
ANNOUNCEMENT_DAY_ORDER = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"
]
_WEEKEND = {"Saturday", "Sunday"}
_WEEKDAY = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"}


# ── Core estimators ──────────────────────────────────────────────────────────

def bootstrap_median_ci(
    data: np.ndarray,
    n_resamples: int = config.BOOTSTRAP_RESAMPLES,
    ci: float = config.BOOTSTRAP_CI,
    seed: int = config.RANDOM_SEED,
) -> tuple:
    """
    Return (median, lower_ci, upper_ci) via percentile bootstrap.
    Uses 10,000 resamples by default, following Desai (arXiv:2410.03342).
    """
    if len(data) == 0:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed)
    resampled = rng.choice(data, size=(n_resamples, len(data)), replace=True)
    boot_medians = np.median(resampled, axis=1)
    alpha = (100.0 - ci) / 2.0
    return (
        float(np.median(data)),
        float(np.percentile(boot_medians, alpha)),
        float(np.percentile(boot_medians, 100.0 - alpha)),
    )


def bin_stats(df: pd.DataFrame, day_col: str, day_order: list) -> pd.DataFrame:
    """Compute N, mean, SEM, median, and 95% bootstrap CI per day bin."""
    rows = []
    for day in day_order:
        vals = df.loc[df[day_col] == day, "citation_count"].values.astype(float)
        n = len(vals)
        if n == 0:
            rows.append(
                dict(day=day, n=0, mean=np.nan, sem=np.nan,
                     median=np.nan, ci_lo=np.nan, ci_hi=np.nan)
            )
            continue
        median, ci_lo, ci_hi = bootstrap_median_ci(vals)
        rows.append(
            dict(
                day=day, n=int(n),
                mean=float(np.mean(vals)),
                sem=float(scipy_stats.sem(vals)),
                median=median,
                ci_lo=ci_lo,
                ci_hi=ci_hi,
            )
        )
    return pd.DataFrame(rows)


# ── Hypothesis tests ─────────────────────────────────────────────────────────

def kruskal_wallis(groups: dict) -> dict:
    """Kruskal-Wallis H-test across all non-empty groups."""
    non_empty = [g for g in groups.values() if len(g) > 0]
    if len(non_empty) < 2:
        return {"statistic": np.nan, "pvalue": np.nan}
    stat, pvalue = scipy_stats.kruskal(*non_empty)
    return {"statistic": float(stat), "pvalue": float(pvalue)}


def pairwise_mannwhitney_holm(groups: dict, day_order: list) -> pd.DataFrame:
    """
    Pairwise two-sided Mann-Whitney U tests with Holm-Bonferroni correction.
    Only non-empty bins are tested.
    """
    keys = [d for d in day_order if d in groups and len(groups[d]) > 0]
    rows = []
    for a, b in combinations(keys, 2):
        stat, pval = scipy_stats.mannwhitneyu(
            groups[a], groups[b], alternative="two-sided"
        )
        rows.append(
            {"group_a": a, "group_b": b,
             "statistic": float(stat), "p_value": float(pval)}
        )
    if not rows:
        return pd.DataFrame(
            columns=["group_a", "group_b", "statistic", "p_value", "p_holm"]
        )
    df = pd.DataFrame(rows).sort_values("p_value").reset_index(drop=True)
    m = len(df)
    # Holm adjusted p-values: p_holm(i) = min(1, max_{j<=i} (m-j+1)*p(j))
    adj = [(m - i) * float(df.loc[i, "p_value"]) for i in range(m)]
    for i in range(1, m):
        adj[i] = max(adj[i], adj[i - 1])
    df["p_holm"] = np.minimum(1.0, adj)
    return df


def weekend_vs_weekday_mwu(df: pd.DataFrame) -> dict:
    """
    Mann-Whitney U test: weekend (Sat+Sun) vs weekday (Mon–Fri) submission days.
    This is the headline test for the arXiv:2509.09601 comparison.
    """
    weekend_vals = df.loc[
        df["submission_day"].isin(_WEEKEND), "citation_count"
    ].values.astype(float)
    weekday_vals = df.loc[
        df["submission_day"].isin(_WEEKDAY), "citation_count"
    ].values.astype(float)

    if len(weekend_vals) == 0 or len(weekday_vals) == 0:
        return {
            "statistic": np.nan, "pvalue": np.nan,
            "weekend_n": int(len(weekend_vals)),
            "weekday_n": int(len(weekday_vals)),
            "weekend_median": np.nan, "weekday_median": np.nan,
            "weekend_mean": np.nan, "weekday_mean": np.nan,
            "mean_diff": np.nan,
        }

    stat, pval = scipy_stats.mannwhitneyu(
        weekend_vals, weekday_vals, alternative="two-sided"
    )
    mean_diff = float(np.mean(weekend_vals)) - float(np.mean(weekday_vals))
    return {
        "statistic": float(stat),
        "pvalue": float(pval),
        "weekend_n": int(len(weekend_vals)),
        "weekday_n": int(len(weekday_vals)),
        "weekend_median": float(np.median(weekend_vals)),
        "weekday_median": float(np.median(weekday_vals)),
        "weekend_mean": float(np.mean(weekend_vals)),
        "weekday_mean": float(np.mean(weekday_vals)),
        "mean_diff": mean_diff,
    }


# ── Robustness checks ────────────────────────────────────────────────────────

def year_stratified(df: pd.DataFrame, day_col: str, day_order: list) -> pd.DataFrame:
    """Median citations per (publication year, day) for stratified analysis."""
    years = sorted(df["pub_year"].dropna().unique().astype(int).tolist())
    rows = []
    for year in years:
        ydf = df[df["pub_year"] == year]
        for day in day_order:
            vals = ydf.loc[ydf[day_col] == day, "citation_count"].values.astype(float)
            rows.append(
                dict(
                    year=int(year),
                    day=day,
                    n=int(len(vals)),
                    median=float(np.median(vals)) if len(vals) > 0 else np.nan,
                    mean=float(np.mean(vals)) if len(vals) > 0 else np.nan,
                )
            )
    return pd.DataFrame(rows)


def year_normalized_bin_stats(
    df: pd.DataFrame, day_col: str, day_order: list
) -> pd.DataFrame:
    """
    Bin stats on year-normalized citations.
    Each paper's citation count is divided by its publication-year median,
    making counts comparable across years regardless of accrual time.
    Papers from years where the median is 0 are excluded.
    """
    year_medians = df.groupby("pub_year")["citation_count"].median().to_dict()
    df2 = df.copy()
    df2["year_median"] = df2["pub_year"].map(year_medians)
    df2 = df2[df2["year_median"] > 0].copy()
    df2["citation_count"] = df2["citation_count"] / df2["year_median"]
    return bin_stats(df2, day_col, day_order)


def listing_size_proxy(df: pd.DataFrame) -> pd.DataFrame:
    """
    Proxy for visibility dilution motivated by Dietrich (arXiv:0712.1037),
    who showed listing position and list length affect citation counts.

    Counts papers in our sample per announcement date, averages by weekday
    (Monday absorbs Fri+Sat+Sun submissions so its listing should be largest),
    and reports median citations vs average listing size by weekday.

    NOTE: this uses only the journal sub-sample, not the full astro-ph listing,
    so it is a proxy for relative dilution, not a reconstruction of true position.
    """
    if "ann_date" not in df.columns:
        raise ValueError("DataFrame must have 'ann_date' column; run announcement_date() first.")

    daily = (
        df.groupby(["ann_date", "announcement_day"])
        .agg(papers_that_day=("arxiv_id", "count"))
        .reset_index()
    )

    rows = []
    for day in ANNOUNCEMENT_DAY_ORDER:
        subset = df[df["announcement_day"] == day]
        day_dates = daily[daily["announcement_day"] == day]
        rows.append(
            dict(
                announcement_day=day,
                n=int(len(subset)),
                median_citations=(
                    float(np.median(subset["citation_count"].values))
                    if len(subset) > 0 else np.nan
                ),
                avg_listing_size=(
                    float(day_dates["papers_that_day"].mean())
                    if len(day_dates) > 0 else np.nan
                ),
                n_announcement_dates=int(len(day_dates)),
            )
        )
    return pd.DataFrame(rows)


# ── Master entry point ───────────────────────────────────────────────────────

def run_analysis(df: pd.DataFrame) -> dict:
    """Run the full statistical analysis and return all results as a dict."""
    log.info("Running statistical analysis on %d papers...", len(df))

    sub_groups = {
        day: df.loc[df["submission_day"] == day, "citation_count"].values.astype(float)
        for day in SUBMISSION_DAY_ORDER
    }
    ann_groups = {
        day: df.loc[df["announcement_day"] == day, "citation_count"].values.astype(float)
        for day in ANNOUNCEMENT_DAY_ORDER
    }

    log.info("  Computing per-bin statistics...")
    sub_stats = bin_stats(df, "submission_day", SUBMISSION_DAY_ORDER)
    ann_stats = bin_stats(df, "announcement_day", ANNOUNCEMENT_DAY_ORDER)

    log.info("  Running Kruskal-Wallis tests...")
    sub_kw = kruskal_wallis(sub_groups)
    ann_kw = kruskal_wallis(ann_groups)

    log.info("  Running pairwise Mann-Whitney + Holm correction...")
    sub_pairwise = pairwise_mannwhitney_holm(sub_groups, SUBMISSION_DAY_ORDER)
    ann_pairwise = pairwise_mannwhitney_holm(ann_groups, ANNOUNCEMENT_DAY_ORDER)

    log.info("  Running weekend vs weekday test...")
    ww = weekend_vs_weekday_mwu(df)

    log.info("  Year-stratified analysis...")
    sub_year = year_stratified(df, "submission_day", SUBMISSION_DAY_ORDER)
    ann_year = year_stratified(df, "announcement_day", ANNOUNCEMENT_DAY_ORDER)

    log.info("  Year-normalized secondary analysis...")
    sub_norm = year_normalized_bin_stats(df, "submission_day", SUBMISSION_DAY_ORDER)
    ann_norm = year_normalized_bin_stats(df, "announcement_day", ANNOUNCEMENT_DAY_ORDER)

    log.info("  Listing-size proxy analysis...")
    lsp = listing_size_proxy(df)

    log.info("Analysis complete.")
    return {
        "submission_day": {
            "bin_stats": sub_stats,
            "kruskal": sub_kw,
            "pairwise": sub_pairwise,
        },
        "announcement_day": {
            "bin_stats": ann_stats,
            "kruskal": ann_kw,
            "pairwise": ann_pairwise,
        },
        "weekend_weekday": ww,
        "year_stratified": {
            "submission_day": sub_year,
            "announcement_day": ann_year,
        },
        "year_normalized": {
            "submission_day": sub_norm,
            "announcement_day": ann_norm,
        },
        "listing_size_proxy": lsp,
    }
