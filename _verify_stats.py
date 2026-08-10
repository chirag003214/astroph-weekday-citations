"""
Independent statistics sanity check.

Does NOT import src/stats.py. Reconstructs the final df the same way
_verify_step1_2.py did (via src/ads_client.build_dataframe + src/schedule
for the day-of-week labels only -- those were already independently
verified in the previous check), then recomputes:
  - Tuesday submission_day bin: N and median citation count
  - Weekend-vs-weekday Mann-Whitney U test (statistic, p-value, medians)
using scipy/numpy directly.
"""
import json

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

import config
from src.ads_client import build_dataframe
from src.schedule import submission_day, announcement_day

JOURNAL = "MNRAS"

with open(config.get_ads_cache_path(JOURNAL), encoding="utf-8") as fh:
    raw_records = json.load(fh)
df_ads, _ = build_dataframe(raw_records)

arxiv_records = []
with open(config.get_arxiv_cache_path(), encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if line:
            arxiv_records.append(json.loads(line))
df_arxiv = pd.DataFrame(arxiv_records)

df = df_ads.merge(df_arxiv, on="arxiv_id", how="inner")
df = df[df["primary_category"].str.startswith("astro-ph", na=False)].copy()
print(f"Final sample N = {len(df)}")

df["v1_utc"] = pd.to_datetime(df["v1_published"], utc=True)
df["submission_day"] = df["v1_utc"].apply(lambda dt: submission_day(dt.to_pydatetime()))

# ── Tuesday submission_day bin ───────────────────────────────────────────────
tue = df[df["submission_day"] == "Tuesday"]["citation_count"]
print("\n--- Tuesday submission_day bin ---")
print(f"N      = {len(tue)}")
print(f"Median (np.median) = {np.median(tue):.1f}")
print("RESULTS.md says: N=2841, Median=17.0")
print(f"Match: N {'OK' if len(tue) == 2841 else 'MISMATCH'}, "
      f"Median {'OK' if np.median(tue) == 17.0 else 'MISMATCH'}")

# ── Weekend vs weekday Mann-Whitney ──────────────────────────────────────────
weekend = df[df["submission_day"].isin(["Saturday", "Sunday"])]["citation_count"]
weekday = df[~df["submission_day"].isin(["Saturday", "Sunday"])]["citation_count"]

print("\n--- Weekend vs weekday ---")
print(f"Weekend N = {len(weekend)}, median = {np.median(weekend):.1f}, mean = {weekend.mean():.2f}")
print(f"Weekday N = {len(weekday)}, median = {np.median(weekday):.1f}, mean = {weekday.mean():.2f}")

stat, p = mannwhitneyu(weekend, weekday, alternative="two-sided")
print(f"\nMann-Whitney U = {stat:.0f}, p = {p:.3e}")
print("RESULTS.md says: U = 5655092, p = 3.90e-13")
print(f"Match: U {'OK' if abs(stat - 5655092) < 1 else 'MISMATCH'}, "
      f"p {'OK' if abs(p - 3.90e-13) / 3.90e-13 < 0.05 else 'MISMATCH (check direction/alternative)'}")
print(f"\nMean diff (weekend - weekday) = {weekend.mean() - weekday.mean():.2f}")
print("RESULTS.md says: -5.55")
