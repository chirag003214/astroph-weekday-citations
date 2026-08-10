"""
Step 3 & 4 of independent validation.

Standalone script -- does NOT import anything from src/.
- Re-fetches v1 <published> timestamps directly from the arXiv API.
- Independently re-implements the 14:00 ET deadline + weekend roll-forward
  rule from scratch (separate code from src/schedule.py).
"""
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ATOM_NS = "{http://www.w3.org/2005/Atom}"
EASTERN = ZoneInfo("America/New_York")
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# From step 1/2 output
ROWS = [
    {"arxiv_id": "1910.06478", "stored_v1_published": "2019-10-15T01:54:51Z",
     "pipeline_submission_day": "Monday", "pipeline_announcement_day": "Tuesday", "citation_count": 13},
    {"arxiv_id": "1909.12715", "stored_v1_published": "2019-09-27T14:40:05Z",
     "pipeline_submission_day": "Friday", "pipeline_announcement_day": "Friday", "citation_count": 9},
    {"arxiv_id": "1910.12069", "stored_v1_published": "2019-10-26T14:10:21Z",
     "pipeline_submission_day": "Saturday", "pipeline_announcement_day": "Monday", "citation_count": 10},
    {"arxiv_id": "1910.08947", "stored_v1_published": "2019-10-20T10:54:49Z",
     "pipeline_submission_day": "Sunday", "pipeline_announcement_day": "Monday", "citation_count": 21},
    {"arxiv_id": "1907.10609", "stored_v1_published": "2019-07-24T18:00:00Z",
     "pipeline_submission_day": "Wednesday", "pipeline_announcement_day": "Thursday", "citation_count": 95},
    {"arxiv_id": "1910.01660", "stored_v1_published": "2019-10-03T18:00:42Z",
     "pipeline_submission_day": "Thursday", "pipeline_announcement_day": "Friday", "citation_count": 11},
]


def fetch_published(arxiv_id: str) -> str:
    """Hardcoded inline call to the arXiv API; returns raw <published> text."""
    url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}&max_results=1"
    with urllib.request.urlopen(url, timeout=30) as resp:
        xml_text = resp.read().decode("utf-8")
    root = ET.fromstring(xml_text)
    entry = root.find(f"{ATOM_NS}entry")
    pub = entry.find(f"{ATOM_NS}published")
    return pub.text.strip()


def independent_announcement_day(utc_iso: str) -> tuple[str, str]:
    """
    Second, from-scratch implementation of:
      1. UTC -> America/New_York
      2. If local hour >= 14, move to next calendar day
      3. Saturday -> Monday (+2), Sunday -> Monday (+1)
    Returns (submission_day, announcement_day).
    """
    dt_utc = datetime.strptime(utc_iso, "%Y-%m-%dT%H:%M:%SZ")
    dt_eastern = dt_utc.replace(tzinfo=ZoneInfo("UTC")).astimezone(EASTERN)

    sub_day = WEEKDAYS[dt_eastern.weekday()]

    eff_date = dt_eastern.date()
    if dt_eastern.hour >= 14:
        eff_date = eff_date + timedelta(days=1)

    dow = eff_date.weekday()  # 0=Mon ... 5=Sat, 6=Sun
    if dow == 5:
        eff_date = eff_date + timedelta(days=2)
    elif dow == 6:
        eff_date = eff_date + timedelta(days=1)

    ann_day = WEEKDAYS[eff_date.weekday()]
    return sub_day, ann_day


print("=" * 110)
hdr = f"{'arXiv ID':<12} {'stored UTC':<22} {'arXiv API <published>':<22} {'match':<6} {'pipe sub':<10} {'indep sub':<10} {'pipe ann':<10} {'indep ann':<10} {'match'}"
print(hdr)
print("-" * len(hdr))

for r in ROWS:
    api_pub = fetch_published(r["arxiv_id"])
    ts_match = "OK" if api_pub == r["stored_v1_published"] else "MISMATCH"

    indep_sub, indep_ann = independent_announcement_day(r["stored_v1_published"])
    ann_match = "OK" if (indep_sub == r["pipeline_submission_day"] and indep_ann == r["pipeline_announcement_day"]) else "MISMATCH"

    print(f"{r['arxiv_id']:<12} {r['stored_v1_published']:<22} {api_pub:<22} {ts_match:<6} "
          f"{r['pipeline_submission_day']:<10} {indep_sub:<10} {r['pipeline_announcement_day']:<10} {indep_ann:<10} {ann_match}")

print("\nDirect links:")
for r in ROWS:
    print(f"  https://arxiv.org/abs/{r['arxiv_id']}")
