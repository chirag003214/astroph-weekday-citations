"""
Tests for the quarantine-and-retry logic in src/arxiv_client.fetch_arxiv_metadata.

Scenario A — all retries fail on every batch:
  * fetch_arxiv_metadata raises RuntimeError naming the count and the file.
  * failed_ids_<journal>.txt exists and lists exactly the requested IDs.

Scenario B — first pass fails, retry succeeds:
  * fetch_arxiv_metadata returns the recovered records.
  * failed_ids_<journal>.txt is removed after successful retry.
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

import config
import src.arxiv_client as ac


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_entry(arxiv_id: str) -> dict:
    return {
        "arxiv_id": arxiv_id,
        "v1_published": "2022-01-01T00:00:00Z",
        "primary_category": "astro-ph.GA",
    }


TEST_IDS = [f"2201.{i:05d}" for i in range(7)]
JOURNAL = "TestJ"


# ── Scenario A: persistent failure → RuntimeError ────────────────────────────

def test_quarantine_raises_when_retry_also_fails(tmp_path):
    cache_file = tmp_path / "arxiv_meta.jsonl"

    with (
        patch.object(config, "DATA_DIR", tmp_path),
        patch("src.arxiv_client.config.DATA_DIR", tmp_path),
        patch("src.arxiv_client.config.get_arxiv_cache_path", return_value=cache_file),
        patch("src.arxiv_client.config.ARXIV_BATCH_SIZE", 3),
        patch("src.arxiv_client._RETRY_BATCH_SIZE", 4),
        patch("src.arxiv_client._RETRY_SLEEP", 0),
        patch("src.arxiv_client.config.ARXIV_SLEEP_SECONDS", 0),
        patch(
            "src.arxiv_client._fetch_batch",
            side_effect=ac._BatchFetchError("mocked network failure"),
        ),
    ):
        with pytest.raises(RuntimeError) as exc_info:
            ac.fetch_arxiv_metadata(TEST_IDS, journal=JOURNAL)

    msg = str(exc_info.value)
    assert str(len(TEST_IDS)) in msg, "Error message should state the count of unfetched IDs"

    failed_path = tmp_path / f"failed_ids_{JOURNAL}.txt"
    assert failed_path.exists(), "failed_ids file must be written on persistent failure"

    ids_in_file = set(failed_path.read_text(encoding="utf-8").splitlines())
    assert ids_in_file == set(TEST_IDS), "All requested IDs must appear in the failed_ids file"


# ── Scenario B: first pass fails, retry succeeds → file removed ──────────────

def test_quarantine_file_removed_when_retry_succeeds(tmp_path):
    cache_file = tmp_path / "arxiv_meta.jsonl"
    call_count = {"n": 0}

    def _flaky_fetch(ids, attempt=0):
        call_count["n"] += 1
        # First two calls (main-pass batches) fail; subsequent calls (retry) succeed.
        if call_count["n"] <= 2:
            raise ac._BatchFetchError("first-pass failure")
        return [_make_entry(aid) for aid in ids]

    with (
        patch.object(config, "DATA_DIR", tmp_path),
        patch("src.arxiv_client.config.DATA_DIR", tmp_path),
        patch("src.arxiv_client.config.get_arxiv_cache_path", return_value=cache_file),
        patch("src.arxiv_client.config.ARXIV_BATCH_SIZE", 3),
        patch("src.arxiv_client._RETRY_BATCH_SIZE", 10),
        patch("src.arxiv_client._RETRY_SLEEP", 0),
        patch("src.arxiv_client.config.ARXIV_SLEEP_SECONDS", 0),
        patch("src.arxiv_client._fetch_batch", side_effect=_flaky_fetch),
    ):
        results = ac.fetch_arxiv_metadata(TEST_IDS, journal=JOURNAL)

    assert len(results) == len(TEST_IDS), "All IDs should be returned after successful retry"
    returned_ids = {r["arxiv_id"] for r in results}
    assert returned_ids == set(TEST_IDS)

    failed_path = tmp_path / f"failed_ids_{JOURNAL}.txt"
    assert not failed_path.exists(), "failed_ids file must be removed after successful retry"
