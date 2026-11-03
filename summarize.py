#!/usr/bin/env python3
"""
Cross-journal summary of the weekend-vs-weekday test.

    python summarize.py                    # main period (2020-2023)
    python summarize.py --years 2015-2020  # appendix period

Reads results/<journal>/weekend_weekday.csv written by run_pipeline.py and
writes results/[<period>/]summary_weekend_weekday.(csv|md).  Journals that
have not been run for the requested period are skipped with a warning.
"""
import argparse

import pandas as pd

import config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument(
        "--years", type=config.parse_years, default=config.DEFAULT_YEARS,
        metavar="START-END",
    )
    args = parser.parse_args()
    years = args.years

    rows = []
    for journal in config.JOURNALS:
        path = config.get_results_dir(journal, years) / "weekend_weekday.csv"
        if not path.exists():
            print(f"WARNING: no results for {journal} ({config.years_label(years)}) — skipped")
            continue
        ww = pd.read_csv(path).iloc[0]
        n = int(ww["weekend_n"] + ww["weekday_n"])
        rows.append({
            "Journal": journal,
            "N": n,
            "N_weekend": int(ww["weekend_n"]),
            "Weekend_frac_pct": 100 * ww["weekend_n"] / n,
            "Median_weekend": ww["weekend_median"],
            "Median_weekday": ww["weekday_median"],
            # Same definition as the manuscript: 1 - weekend/weekday median.
            "Median_deficit_pct": 100 * (1 - ww["weekend_median"] / ww["weekday_median"]),
            "Mean_weekend": ww["weekend_mean"],
            "Mean_weekday": ww["weekday_mean"],
            "Mean_diff": ww["mean_diff"],
            "MWU_U": ww["statistic"],
            "MWU_p": ww["pvalue"],
        })

    if not rows:
        raise SystemExit("No journal results found; run run_pipeline.py first.")

    out = pd.DataFrame(rows)
    if tuple(years) == config.DEFAULT_YEARS:
        out_dir = config.RESULTS_BASE_DIR
    else:
        out_dir = config.RESULTS_BASE_DIR / config.years_label(years)
    out_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_dir / "summary_weekend_weekday.csv", index=False, float_format="%.6g")
    with open(out_dir / "summary_weekend_weekday.md", "w", encoding="utf-8") as fh:
        fh.write(f"### Weekend vs weekday, all journals ({years[0]}–{years[1]})\n\n")
        md = out.copy()
        md["MWU_p"] = md["MWU_p"].map(lambda p: f"{p:.2e}" if p < 1e-3 else f"{p:.4f}")
        fh.write(md.to_markdown(index=False, floatfmt=".1f"))
        fh.write("\n")
    print(out.to_string(index=False))
    print(f"\nWritten to {out_dir}/summary_weekend_weekday.(csv|md)")


if __name__ == "__main__":
    main()
