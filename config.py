"""Central configuration for the astroph-weekday-citations pipeline."""
import os
from pathlib import Path

# ── Journal presets ──────────────────────────────────────────────────────────
JOURNALS = {
    "MNRAS": {
        "bibstem": "MNRAS",
        "ads_query": "bibstem:MNRAS year:2020-2023 property:refereed doctype:article",
    },
    "ApJ": {
        "bibstem": "ApJ",
        "ads_query": "bibstem:ApJ year:2020-2023 property:refereed doctype:article",
    },
    "ApJL": {
        "bibstem": "ApJL",
        "ads_query": "bibstem:ApJL year:2020-2023 property:refereed doctype:article",
    },
    "ApJS": {
        "bibstem": "ApJS",
        "ads_query": "bibstem:ApJS year:2020-2023 property:refereed doctype:article",
    },
    # bibstem "A&A" — the & is URL-encoded by requests; quoted in Solr to prevent
    # the & being parsed as a boolean operator.  Directory name uses "AandA".
    "A&A": {
        "bibstem": "A&A",
        "ads_query": 'bibstem:"A&A" year:2020-2023 property:refereed doctype:article',
    },
    "JCAP": {
        "bibstem": "JCAP",
        "ads_query": "bibstem:JCAP year:2020-2023 property:refereed doctype:article",
    },
}

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


def get_ads_cache_path(journal: str) -> Path:
    return DATA_DIR / f"{_dir_safe(journal)}_ads_raw.json"


def get_arxiv_cache_path() -> Path:
    return DATA_DIR / "arxiv_meta.jsonl"


def get_results_dir(journal: str) -> Path:
    return RESULTS_BASE_DIR / _dir_safe(journal)
