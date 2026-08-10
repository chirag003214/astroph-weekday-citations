"""Publication-quality figures for the day-of-week citation analysis."""
import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# Publication-quality rcParams (no seaborn dependency)
plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.size": 11,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 9,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "grid.linestyle": "--",
    }
)

_SUB_ORDER = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
]
_ANN_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
_DAY_ABBR = {d: d[:3] for d in _SUB_ORDER}
_YEAR_COLORS = plt.cm.viridis(np.linspace(0.15, 0.85, 4))
_TAB10 = plt.cm.tab10


def _colors(n: int):
    return _TAB10(np.linspace(0, 0.9, n))


def _save(fig, path_stem: Path):
    for ext in ("png", "pdf"):
        fig.savefig(f"{path_stem}.{ext}", bbox_inches="tight")
    plt.close(fig)
    log.info("Saved %s.(png|pdf)", path_stem)


def _get_col(df_stats: pd.DataFrame, day: str, col: str) -> float:
    rows = df_stats.loc[df_stats["day"] == day, col]
    return float(rows.values[0]) if len(rows) > 0 else np.nan


# ── Individual plot functions ─────────────────────────────────────────────────

def plot_median_ci(
    bin_stats: pd.DataFrame, day_order: list, title: str, path_stem: Path
):
    """Bar chart: median citations ± 95% bootstrap CI per day bin."""
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(day_order))
    colors = _colors(len(day_order))

    medians = [_get_col(bin_stats, d, "median") for d in day_order]
    ci_lo = [_get_col(bin_stats, d, "ci_lo") for d in day_order]
    ci_hi = [_get_col(bin_stats, d, "ci_hi") for d in day_order]
    yerr_lo = [m - lo for m, lo in zip(medians, ci_lo)]
    yerr_hi = [hi - m for m, hi in zip(medians, ci_hi)]

    ax.bar(
        x, medians, color=colors,
        yerr=[yerr_lo, yerr_hi], capsize=5,
        error_kw={"linewidth": 1.5, "ecolor": "black"},
        alpha=0.85, zorder=3,
    )
    ax.set_xticks(x)
    ax.set_xticklabels([_DAY_ABBR.get(d, d[:3]) for d in day_order])
    ax.set_xlabel("Day of Week")
    ax.set_ylabel("Median Citation Count")
    ax.set_title(title)
    fig.tight_layout()
    _save(fig, path_stem)


def plot_mean_sem(
    bin_stats: pd.DataFrame, day_order: list, title: str, path_stem: Path
):
    """Bar chart: mean citations ± SEM per day bin."""
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(day_order))
    colors = _colors(len(day_order))

    means = [_get_col(bin_stats, d, "mean") for d in day_order]
    sems = [_get_col(bin_stats, d, "sem") for d in day_order]

    ax.bar(
        x, means, color=colors,
        yerr=sems, capsize=5,
        error_kw={"linewidth": 1.5, "ecolor": "black"},
        alpha=0.85, zorder=3,
    )
    ax.set_xticks(x)
    ax.set_xticklabels([_DAY_ABBR.get(d, d[:3]) for d in day_order])
    ax.set_xlabel("Day of Week")
    ax.set_ylabel("Mean Citation Count")
    ax.set_title(title)
    fig.tight_layout()
    _save(fig, path_stem)


def plot_paper_counts(
    bin_stats_sub: pd.DataFrame, bin_stats_ann: pd.DataFrame, path_stem: Path
):
    """Side-by-side bar charts: paper counts per submission and announcement day."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    for ax, bstats, day_order, title in [
        (ax1, bin_stats_sub, _SUB_ORDER, "Papers per Submission Day"),
        (ax2, bin_stats_ann, _ANN_ORDER, "Papers per Announcement Day"),
    ]:
        x = np.arange(len(day_order))
        counts = [int(_get_col(bstats, d, "n") or 0) for d in day_order]
        colors = _colors(len(day_order))
        bars = ax.bar(x, counts, color=colors, alpha=0.85, zorder=3)
        ax.bar_label(bars, fmt="%d", fontsize=8, padding=2)
        ax.set_xticks(x)
        ax.set_xticklabels([_DAY_ABBR.get(d, d[:3]) for d in day_order])
        ax.set_xlabel("Day of Week")
        ax.set_ylabel("Paper Count")
        ax.set_title(title)
    fig.tight_layout()
    _save(fig, path_stem)


def plot_year_stratified(
    year_df: pd.DataFrame, day_order: list, title: str, path_stem: Path
):
    """Line plot: median citations per day, stratified by publication year."""
    fig, ax = plt.subplots(figsize=(9, 5))
    years = sorted(year_df["year"].unique().tolist())
    x = np.arange(len(day_order))

    for j, year in enumerate(years):
        ydf = year_df[year_df["year"] == year]
        medians = []
        for d in day_order:
            row = ydf.loc[ydf["day"] == d, "median"]
            medians.append(float(row.values[0]) if len(row) > 0 else np.nan)
        color = _YEAR_COLORS[j % len(_YEAR_COLORS)]
        ax.plot(x, medians, "o-", color=color, label=str(year), lw=2, ms=7, zorder=3)

    ax.set_xticks(x)
    ax.set_xticklabels([_DAY_ABBR.get(d, d[:3]) for d in day_order])
    ax.set_xlabel("Day of Week")
    ax.set_ylabel("Median Citation Count")
    ax.set_title(title)
    ax.legend(title="Pub. Year", framealpha=0.8)
    fig.tight_layout()
    _save(fig, path_stem)


def plot_survival(
    df: pd.DataFrame, day_col: str, day_order: list, title: str, path_stem: Path
):
    """
    Log-scale empirical survival functions (CCDF: P(Citations > x)) per day.
    Papers with 0 citations are excluded from the log-scale plot.
    """
    fig, ax = plt.subplots(figsize=(9, 6))
    colors = _colors(len(day_order))

    for j, day in enumerate(day_order):
        vals = df.loc[df[day_col] == day, "citation_count"].values
        vals = vals[vals > 0]
        if len(vals) == 0:
            continue
        sorted_vals = np.sort(vals)
        n = len(sorted_vals)
        survival = 1.0 - np.arange(1, n + 1) / n
        ax.plot(
            sorted_vals, survival,
            "-", lw=1.5, color=colors[j],
            label=_DAY_ABBR.get(day, day[:3]), alpha=0.85,
        )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Citation Count  (papers with 0 citations excluded)")
    ax.set_ylabel("P(Citations > x)")
    ax.set_title(title)
    ax.legend(title="Day", ncol=2, framealpha=0.8)
    fig.tight_layout()
    _save(fig, path_stem)


def plot_listing_size_proxy(proxy_df: pd.DataFrame, journal: str, path_stem: Path):
    """
    Dual-axis plot: median citations and average listing size by announcement day.
    Motivated by Dietrich (arXiv:0712.1037).
    """
    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax2 = ax1.twinx()
    x = np.arange(len(_ANN_ORDER))
    days = [d[:3] for d in _ANN_ORDER]

    median_cites = [
        float(proxy_df.loc[proxy_df["announcement_day"] == d, "median_citations"].values[0])
        if d in proxy_df["announcement_day"].values else np.nan
        for d in _ANN_ORDER
    ]
    avg_sizes = [
        float(proxy_df.loc[proxy_df["announcement_day"] == d, "avg_listing_size"].values[0])
        if d in proxy_df["announcement_day"].values else np.nan
        for d in _ANN_ORDER
    ]

    ax1.bar(x - 0.2, median_cites, width=0.35, color="steelblue", alpha=0.8,
            label="Median citations (left)", zorder=3)
    ax2.bar(x + 0.2, avg_sizes, width=0.35, color="coral", alpha=0.8,
            label="Avg. listing size (right)", zorder=3)

    ax1.set_xticks(x)
    ax1.set_xticklabels(days)
    ax1.set_xlabel("Announcement Day")
    ax1.set_ylabel("Median Citation Count", color="steelblue")
    ax2.set_ylabel("Avg. Papers per Day (sample proxy)", color="coral")
    ax1.tick_params(axis="y", labelcolor="steelblue")
    ax2.tick_params(axis="y", labelcolor="coral")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=9)
    ax1.set_title(f"{journal}: Citations vs Listing Size Proxy by Announcement Day")
    fig.tight_layout()
    _save(fig, path_stem)


# ── Master dispatcher ─────────────────────────────────────────────────────────

def make_all_plots(df: pd.DataFrame, stats_results: dict, results_dir: Path):
    """Generate and save all nine figures to results_dir."""
    results_dir.mkdir(parents=True, exist_ok=True)
    journal = results_dir.name

    sub_stats = stats_results["submission_day"]["bin_stats"]
    ann_stats = stats_results["announcement_day"]["bin_stats"]

    # Fig 1 – median ± CI, submission day
    plot_median_ci(
        sub_stats, _SUB_ORDER,
        f"{journal}: Median Citations by arXiv Submission Day (95% CI)",
        results_dir / "fig1_median_submission_day",
    )
    # Fig 2 – median ± CI, announcement day
    plot_median_ci(
        ann_stats, _ANN_ORDER,
        f"{journal}: Median Citations by arXiv Announcement Day (95% CI)",
        results_dir / "fig2_median_announcement_day",
    )
    # Fig 3 – mean ± SEM, submission day
    plot_mean_sem(
        sub_stats, _SUB_ORDER,
        f"{journal}: Mean Citations ± SEM by Submission Day",
        results_dir / "fig3_mean_sem_submission_day",
    )
    # Fig 4 – mean ± SEM, announcement day
    plot_mean_sem(
        ann_stats, _ANN_ORDER,
        f"{journal}: Mean Citations ± SEM by Announcement Day",
        results_dir / "fig4_mean_sem_announcement_day",
    )
    # Fig 5 – paper counts per bin
    plot_paper_counts(sub_stats, ann_stats, results_dir / "fig5_paper_counts")

    # Fig 6 – year-stratified medians, submission day
    plot_year_stratified(
        stats_results["year_stratified"]["submission_day"],
        _SUB_ORDER,
        f"{journal}: Year-Stratified Median Citations by Submission Day",
        results_dir / "fig6_year_stratified_submission_day",
    )
    # Fig 7 – year-stratified medians, announcement day
    plot_year_stratified(
        stats_results["year_stratified"]["announcement_day"],
        _ANN_ORDER,
        f"{journal}: Year-Stratified Median Citations by Announcement Day",
        results_dir / "fig7_year_stratified_announcement_day",
    )
    # Fig 8 – survival functions, submission day
    plot_survival(
        df, "submission_day", _SUB_ORDER,
        f"{journal}: Citation Distribution by Submission Day",
        results_dir / "fig8_survival_submission_day",
    )
    # Fig 9 – survival functions, announcement day
    plot_survival(
        df, "announcement_day", _ANN_ORDER,
        f"{journal}: Citation Distribution by Announcement Day",
        results_dir / "fig9_survival_announcement_day",
    )
    # Fig 10 – listing-size proxy
    plot_listing_size_proxy(
        stats_results["listing_size_proxy"], journal,
        results_dir / "fig10_listing_size_proxy",
    )

    log.info("All figures written to %s", results_dir)
