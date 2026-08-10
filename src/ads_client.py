"""NASA ADS API client with disk caching."""
import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Optional

import requests

import config

log = logging.getLogger(__name__)

# arXiv ID patterns inside ADS identifier lists.
# New style (2007+): YYMM.NNNNN[vN]  e.g. "arXiv:2001.01234" or "2001.01234v2"
# Old style (pre-2007): archive/YYMMNNN[vN]  e.g. "astro-ph/0601001"
#
# The old-style lookahead (?=[a-z]{2}[a-z0-9.\-]) requires a third non-slash
# character after the first two letters, which is present in every real arXiv
# archive name (gr-qc: '-', cs.AI: '.', math: 't', astro-ph: 't') but absent
# in journal-internal bibcode prefixes like "aa/" (position 2 is '/').
_ARXIV_NEW = re.compile(r"(?:arxiv:)?(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)
_ARXIV_OLD = re.compile(
    r"(?:arxiv:)?(?=[a-z]{2}[a-z0-9.\-])([a-z][a-z0-9-]+(?:\.[a-z]{2})?/\d{7})(?:v\d+)?",
    re.IGNORECASE,
)
# Original loose old-style pattern — kept only to count identifiers that the
# stricter _ARXIV_OLD rejects (e.g. "aa/2022131") for honest funnel logging.
_ARXIV_OLD_LOOSE = re.compile(
    r"(?:arxiv:)?([a-z][a-z0-9-]+(?:\.[a-z]{2})?/\d{7})(?:v\d+)?", re.IGNORECASE
)


def _extract_arxiv_id(identifiers: list) -> Optional[str]:
    """Return the canonical arXiv ID (no version suffix) from an ADS identifier list."""
    if not identifiers:
        return None
    for ident in identifiers:
        m = _ARXIV_NEW.search(ident)
        if m:
            return m.group(1)
        m = _ARXIV_OLD.search(ident)
        if m:
            return m.group(1).lower()
    return None


def _ads_get(params: dict, token: str, attempt: int = 0) -> dict:
    """Single ADS GET request with exponential-backoff retry."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(
            config.ADS_SEARCH_URL, params=params, headers=headers, timeout=60
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        if attempt >= config.ADS_MAX_RETRIES - 1:
            raise RuntimeError(
                f"ADS request failed after {config.ADS_MAX_RETRIES} retries: {exc}"
            ) from exc
        delay = config.ADS_RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
        log.warning(
            "ADS request error (%s); retrying in %.1fs (attempt %d/%d)",
            exc, delay, attempt + 1, config.ADS_MAX_RETRIES,
        )
        time.sleep(delay)
        return _ads_get(params, token, attempt + 1)


def fetch_ads_records(journal: str, token: str) -> list:
    """
    Fetch all ADS records for the given journal using offset-based pagination.

    Results are cached to data/raw/{journal}_ads_raw.json. Subsequent calls
    return the cached data without hitting the network.

    Raises EnvironmentError if token is empty/None.
    """
    cache_path = config.get_ads_cache_path(journal)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if cache_path.exists():
        log.info("Loading ADS records from cache: %s", cache_path)
        with open(cache_path, encoding="utf-8") as fh:
            return json.load(fh)

    if not token:
        raise EnvironmentError(
            "ADS_API_TOKEN is not set. "
            "Obtain a free token at https://ui.adsabs.harvard.edu/user/settings/token "
            "and export it:  export ADS_API_TOKEN=<your-token>"
        )

    journal_cfg = config.JOURNALS[journal]
    all_docs: list = []
    start = 0

    log.info("Querying ADS: %s", journal_cfg["ads_query"])
    while True:
        params = {
            "q": journal_cfg["ads_query"],
            "fl": config.ADS_FIELDS,
            "rows": config.ADS_ROWS,
            "start": start,
            "sort": "bibcode asc",
        }
        data = _ads_get(params, token)
        response = data.get("response", {})
        docs = response.get("docs", [])
        num_found = response.get("numFound", 0)

        if not docs:
            break
        all_docs.extend(docs)
        start += len(docs)
        log.info("  ADS records fetched: %d / %d", len(all_docs), num_found)
        if start >= num_found:
            break

    log.info("Total ADS records: %d — writing cache to %s", len(all_docs), cache_path)
    with open(cache_path, "w", encoding="utf-8") as fh:
        json.dump(all_docs, fh)
    return all_docs


def build_dataframe(records: list):
    """
    Parse raw ADS records into a pandas DataFrame.

    Returns (df, n_dropped) where n_dropped is the count of records that had
    no parseable arXiv ID in their identifier list.  Records whose identifier
    field contained a non-arXiv look-alike (e.g. journal-internal bibcodes
    like "aa/2022131") that was rejected by the stricter _ARXIV_OLD filter are
    counted separately and logged, but are NOT included in n_dropped — they too
    are excluded from the DataFrame.
    """
    import pandas as pd

    rows = []
    n_dropped = 0    # no arXiv-shaped identifier found at all
    n_filtered = 0   # had a look-alike rejected by the stricter old-style filter

    for rec in records:
        identifiers = rec.get("identifier") or []
        arxiv_id = _extract_arxiv_id(identifiers)
        if arxiv_id is None:
            # Distinguish "no candidate at all" from "candidate rejected by strict filter"
            if any(_ARXIV_OLD_LOOSE.search(ident) for ident in identifiers):
                n_filtered += 1
            else:
                n_dropped += 1
            continue

        pubdate = rec.get("pubdate") or ""
        year = int(pubdate[:4]) if len(pubdate) >= 4 and pubdate[:4].isdigit() else None

        title_field = rec.get("title")
        title = title_field[0] if isinstance(title_field, list) and title_field else ""

        rows.append({
            "bibcode": rec.get("bibcode", ""),
            "arxiv_id": arxiv_id,
            "citation_count": int(rec.get("citation_count") or 0),
            "pubdate": pubdate,
            "pub_year": year,
            "title": title,
        })

    if n_filtered:
        log.info(
            "  Strict arXiv-ID filter rejected %d record(s) whose identifier field "
            "matched a non-arXiv pattern (e.g. 'aa/NNNNNNN') — excluded from analysis",
            n_filtered,
        )
    return pd.DataFrame(rows), n_dropped
