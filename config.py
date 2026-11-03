"""Central configuration for the astroph-weekday-citations pipeline."""
import os
from pathlib import Path

# ── Journal presets ──────────────────────────────────────────────────────────
# "{years}" in ads_query is filled with "START-END" (see get_ads_query).
JOURNALS = {
    "MNRAS": {
        "bibstem": "MNRAS",
        "ads_query": "bibstem:MNRAS year:{years} property:refereed doctype:article",
    },
    "ApJ": {
        "bibstem": "ApJ",
        "ads_query": "bibstem:ApJ year:{years} property:refereed doctype:article",
    },
    "ApJL": {
        "bibstem": "ApJL",
        "ads_query": "bibstem:ApJL year:{years} property:refereed doctype:article",
    },
    "ApJS": {
        "bibstem": "ApJS",
        "ads_query": "bibstem:ApJS year:{years} property:refereed doctype:article",
    },
    # bibstem "A&A" — the & is URL-encoded by requests; quoted in Solr to prevent
    # the & being parsed as a boolean operator.  Directory name uses "AandA".
    "A&A": {
        "bibstem": "A&A",
        "ads_query": 'bibstem:"A&A" year:{years} property:refereed doctype:article',
    },
    "JCAP": {
        "bibstem": "JCAP",
        "ads_query": "bibstem:JCAP year:{years} property:refereed doctype:article",
    },
    "AJ": {
        "bibstem": "AJ",
        "ads_query": "bibstem:AJ year:{years} property:refereed doctype:article",
    },
    "PASJ": {
        "bibstem": "PASJ",
        "ads_query": "bibstem:PASJ year:{years} property:refereed doctype:article",
    },
}

# ── Publication-year window ──────────────────────────────────────────────────
# Main analysis period.  Other windows (e.g. the 2015–2020 appendix sample) are
# selected with run_pipeline.py --years and get their own cache/results paths.
DEFAULT_YEARS = (2020, 2023)


def years_label(years: tuple) -> str:
    return f"{years[0]}-{years[1]}"


def parse_years(text: str) -> tuple:
    """Parse "START-END" (e.g. "2015-2020") into an (int, int) tuple."""
    try:
        start, end = (int(x) for x in text.split("-"))
    except ValueError:
        raise ValueError(f"years must look like START-END, got {text!r}")
    if start > end:
        raise ValueError(f"start year {start} is after end year {end}")
    return start, end


def get_ads_query(journal: str, years: tuple = DEFAULT_YEARS) -> str:
    return JOURNALS[journal]["ads_query"].format(years=years_label(years))

# ── ADS API ──────────────────────────────────────────────────────────────────
ADS_SEARCH_URL = "https://api.adsabs.harvard.edu/v1/search/query"
ADS_FIELDS = "bibcode,identifier,citation_count,pubdate,title"
ADS_ROWS = 2000
ADS_MAX_RETRIES = 5
ADS_RETRY_BASE_DELAY = 2.0

# ── arXiv API ────────────────────────────────────────────────────────────────
ARXIV_API_URL = "http://export.arxiv.org/api/query"
ARXIV_BATCH_SIZE = 100
ARXIV_SLEEP_SECONDS = 6
ARXIV_MAX_RETRIES = 5
ARXIV_RETRY_BASE_DELAY = 5.0

# ── Statistics ───────────────────────────────────────────────────────────────
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_CI = 95
RANDOM_SEED = 42

# ── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR = Path("data/raw")
RESULTS_BASE_DIR = Path("results")


def _dir_safe(journal: str) -> str:
    """Return a filesystem-safe directory/file-name component for a journal key.

    Replaces '&' with 'and' so A&A becomes AandA (safe on all OSes,
    especially Windows where '&' in paths causes shell-expansion issues).
    """
    return journal.replace("&", "and")


def get_ads_cache_path(journal: str, years: tuple = DEFAULT_YEARS) -> Path:
    # The default period keeps the original un-suffixed file names so existing
    # caches remain valid.
    if tuple(years) == DEFAULT_YEARS:
        return DATA_DIR / f"{_dir_safe(journal)}_ads_raw.json"
    return DATA_DIR / f"{_dir_safe(journal)}_{years_label(years)}_ads_raw.json"


def get_arxiv_cache_path() -> Path:
    return DATA_DIR / "arxiv_meta.jsonl"


def get_results_dir(journal: str, years: tuple = DEFAULT_YEARS) -> Path:
    if tuple(years) == DEFAULT_YEARS:
        return RESULTS_BASE_DIR / _dir_safe(journal)
    return RESULTS_BASE_DIR / years_label(years) / _dir_safe(journal)
