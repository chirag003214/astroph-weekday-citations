"""
Step 1 & 2 of independent validation.

Reconstructs the final merged/filtered analysis table exactly as
run_pipeline.py does (Stages 1-4), using the existing on-disk caches
(data/raw/MNRAS_ads_raw.json, data/raw/arxiv_meta.jsonl) so no network
calls are made. Prints the row count and selects 6 rows for manual
verification.

NOTE: this script DOES import src/ (ads_client, arxiv_client, schedule)
because its purpose is to reproduce the pipeline's own table for
inspection -- it is NOT the independent check (that's step 3/4).
"""
import json
from datetime import datetime, timezone

import pandas as pd

import config
from src.ads_client import build_dataframe
from src.schedule import submission_day, announcement_day

JOURNAL = "MNRAS"

# ── Load cached ADS + arXiv data (no network) ────────────────────────────────
ads_cache = config.get_ads_cache_path(JOURNAL)
with open(ads_cache, encoding="utf-8") as fh:
    raw_records = json.load(fh)

df_ads, n_no_arxiv = build_dataframe(raw_records)

arxiv_cache = config.get_arxiv_cache_path()
arxiv_records = []
with open(arxiv_cache, encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if line:
            arxiv_records.append(json.loads(line))
df_arxiv = pd.DataFrame(arxiv_records)

df = df_ads.merge(df_arxiv, on="arxiv_id", how="inner")
n_after_merge = len(df)
df = df[df["primary_category"].str.startswith("astro-ph", na=False)].copy()
n_final = len(df)

df["v1_utc"] = pd.to_datetime(df["v1_published"], utc=True)
df["submission_day"] = df["v1_utc"].apply(lambda dt: submission_day(dt.to_pydatetime()))
df["announcement_day"] = df["v1_utc"].apply(lambda dt: announcement_day(dt.to_pydatetime()))

print("=" * 70)
print(f"Source ADS cache : {ads_cache}")
print(f"Source arXiv cache: {arxiv_cache}")
print(f"After merge       : {n_after_merge}")
print(f"Final (astro-ph)  : {n_final}  rows  <-- final analysis table")
print("=" * 70)

# ── Identify candidate rows for the 6 categories ─────────────────────────────
EASTERN = df["v1_utc"].dt.tz_convert("America/New_York")
df["_eastern"] = EASTERN
df["_hour_min"] = df["_eastern"].dt.hour + df["_eastern"].dt.minute / 60.0
df["_local_weekday"] = df["_eastern"].dt.weekday  # 0=Mon..6=Sun

picks = []

# 2 ordinary weekday submissions (weekday local, far from 14:00 boundary)
ordinary = df[
    (df["_local_weekday"] < 5)
    & ((df["_hour_min"] < 12.0) | (df["_hour_min"] > 16.0))
]
picks.append(ordinary.iloc[0])
picks.append(ordinary.iloc[1])

# 1 Saturday submission (local weekday == 5)
sat = df[df["_local_weekday"] == 5]
picks.append(sat.iloc[0])

# 1 Sunday submission (local weekday == 6)
sun = df[df["_local_weekday"] == 6]
picks.append(sun.iloc[0])

# 2 papers within 90 minutes of 14:00 ET on a weekday (12:30-15:30)
boundary = df[
    (df["_local_weekday"] < 5)
    & (df["_hour_min"] >= 12.5)
    & (df["_hour_min"] <= 15.5)
]
picks.append(boundary.iloc[0])
picks.append(boundary.iloc[1])

print("\nSelected 6 rows:\n")
header = f"{'arXiv ID':<14} {'v1_published (UTC, stored)':<28} {'America/New_York':<26} {'sub_day':<10} {'ann_day':<10} {'citations':>9}"
print(header)
print("-" * len(header))
ids_for_step3 = []
for row in picks:
    aid = row["arxiv_id"]
    raw_utc = row["v1_published"]
    eastern_str = row["_eastern"].strftime("%Y-%m-%d %H:%M:%S %Z")
    print(f"{aid:<14} {raw_utc:<28} {eastern_str:<26} {row['submission_day']:<10} {row['announcement_day']:<10} {row['citation_count']:>9}")
    ids_for_step3.append({
        "arxiv_id": aid,
        "stored_v1_published": raw_utc,
        "stored_eastern": eastern_str,
        "pipeline_submission_day": row["submission_day"],
        "pipeline_announcement_day": row["announcement_day"],
        "citation_count": int(row["citation_count"]),
    })

print("\nIDs/data passed to step 3/4 standalone script:")
print(json.dumps(ids_for_step3, indent=2))

print("\nDirect links:")
for r in ids_for_step3:
    print(f"  https://arxiv.org/abs/{r['arxiv_id']}")
