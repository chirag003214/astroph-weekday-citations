"""
Unit tests for arXiv ID extraction in src/ads_client.py.

Verifies that the strict _ARXIV_OLD pattern:
  - Accepts genuine old-style arXiv IDs  (astro-ph/0601001, gr-qc/0601001, cs.AI/0601001)
  - Accepts genuine new-style arXiv IDs  (2205.15274, 2001.01234v2, arXiv:2112.00001)
  - Rejects journal-internal look-alikes  (aa/2022131, doi:10.1051/..., plain bibcodes)

Also checks that build_dataframe counts rejected records in the n_filtered log
path rather than the n_dropped path.
"""
import pytest
from unittest.mock import patch, MagicMock

from src.ads_client import _extract_arxiv_id, _ARXIV_OLD, _ARXIV_OLD_LOOSE


# ── _ARXIV_OLD strict pattern: reject / accept cases ─────────────────────────

@pytest.mark.parametrize("ident", [
    "aa/2022131",          # A&A internal bibcode prefix — the primary motivation
    "aa/2020345",          # another A&A internal ID
    "ab/1234567",          # 2-char archive, no hyphen/dot → rejected
])
def test_strict_old_pattern_rejects(ident):
    assert _ARXIV_OLD.search(ident) is None, (
        f"_ARXIV_OLD should NOT match journal-internal identifier: {ident!r}"
    )


@pytest.mark.parametrize("ident", [
    "astro-ph/0601001",
    "astro-ph/0612345",
    "hep-th/0601001",
    "gr-qc/0601001",
    "quant-ph/0601001",
    "cond-mat/0601001",
    "math-ph/0601001",
    "nucl-th/0601001",
    "math/0601001",
    "nlin/0601001",
    "physics/0601001",
    "cs.AI/0601001",
    "arXiv:astro-ph/0601001",
])
def test_strict_old_pattern_accepts(ident):
    assert _ARXIV_OLD.search(ident) is not None, (
        f"_ARXIV_OLD should match real old-style arXiv ID: {ident!r}"
    )


# ── Loose vs strict discriminates exactly the false-positive cases ────────────

@pytest.mark.parametrize("ident", [
    "aa/2022131",
    "aa/2020345",
])
def test_loose_matches_but_strict_rejects(ident):
    """These are the identifiers _ARXIV_OLD_LOOSE used to admit incorrectly."""
    assert _ARXIV_OLD_LOOSE.search(ident) is not None, (
        f"_ARXIV_OLD_LOOSE should match {ident!r} (it is the loose pattern)"
    )
    assert _ARXIV_OLD.search(ident) is None, (
        f"_ARXIV_OLD should reject {ident!r} (stricter pattern)"
    )


# ── _extract_arxiv_id end-to-end ─────────────────────────────────────────────

def test_extract_rejects_aa_bibcode():
    """aa/2022131 in an identifier list → None (not admitted as an arXiv ID)."""
    assert _extract_arxiv_id(["aa/2022131"]) is None


def test_extract_accepts_modern_id():
    """2205.15274 is a valid modern arXiv ID."""
    assert _extract_arxiv_id(["2205.15274"]) == "2205.15274"


def test_extract_accepts_modern_id_with_arxiv_prefix():
    assert _extract_arxiv_id(["arXiv:2205.15274"]) == "2205.15274"


def test_extract_accepts_modern_id_with_version():
    assert _extract_arxiv_id(["2205.15274v2"]) == "2205.15274"


def test_extract_accepts_old_style_id():
    """astro-ph/0601001 is a valid old-style arXiv ID."""
    assert _extract_arxiv_id(["astro-ph/0601001"]) == "astro-ph/0601001"


def test_extract_accepts_old_style_with_arxiv_prefix():
    assert _extract_arxiv_id(["arXiv:astro-ph/0601001"]) == "astro-ph/0601001"


def test_extract_prefers_real_arxiv_over_aa_bibcode():
    """When a record has both a real arXiv ID and an aa/ identifier, the real ID wins."""
    result = _extract_arxiv_id(["aa/2022131", "arXiv:2201.01234"])
    assert result == "2201.01234"


def test_extract_returns_none_for_empty_list():
    assert _extract_arxiv_id([]) is None


def test_extract_returns_none_for_non_arxiv_identifiers():
    """DOI and plain bibcodes must not be mistaken for arXiv IDs."""
    assert _extract_arxiv_id(["10.1051/0004-6361/202142693", "2022A&A...640A...1D"]) is None


# ── build_dataframe: filtered count is logged, not mixed into n_dropped ───────

def test_build_dataframe_counts_filtered_separately(caplog):
    """
    A record whose only identifier is 'aa/2022131' should increment the
    internal n_filtered counter (logged) rather than n_dropped, so the two
    exclusion reasons remain distinguishable in the pipeline output.
    """
    import logging
    from src.ads_client import build_dataframe

    records = [
        # Real arXiv paper — should appear in the DataFrame
        {
            "bibcode": "2022MNRAS.510.1111A",
            "identifier": ["arXiv:2205.15274", "10.1093/mnras/stab3456"],
            "citation_count": 5,
            "pubdate": "2022-01-00",
            "title": ["A real paper"],
        },
        # A&A-internal-only record — should be excluded and counted as filtered
        {
            "bibcode": "2022A&A...640A...1D",
            "identifier": ["aa/2022131"],
            "citation_count": 0,
            "pubdate": "2022-01-00",
            "title": ["A filtered paper"],
        },
        # Truly no arXiv ID — should be excluded and counted as dropped
        {
            "bibcode": "2022MNRAS.510.9999Z",
            "identifier": ["10.1093/mnras/stab0000"],
            "citation_count": 0,
            "pubdate": "2022-01-00",
            "title": ["No arXiv ID"],
        },
    ]

    with caplog.at_level(logging.INFO, logger="src.ads_client"):
        df, n_dropped = build_dataframe(records)

    assert len(df) == 1, "Only the real arXiv paper should be in the DataFrame"
    assert df.iloc[0]["arxiv_id"] == "2205.15274"
    assert n_dropped == 1, "Only the truly-no-ID record should be in n_dropped"
    assert any("filter" in msg.lower() and "1" in msg for msg in caplog.messages), (
        "build_dataframe should log 1 filtered record"
    )
