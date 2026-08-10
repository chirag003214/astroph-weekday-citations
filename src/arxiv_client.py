"""arXiv API client with incremental JSONL caching."""
import json
import logging
import random
import time
import xml.etree.ElementTree as ET

import requests

import config

log = logging.getLogger(__name__)

_ATOM_NS = "http://www.w3.org/2005/Atom"
_ARXIV_NS = "http://arxiv.org/schemas/atom"

# Size and inter-batch delay for the quarantine-retry pass.
_RETRY_BATCH_SIZE = 50
_RETRY_SLEEP = 10.0


class _BatchFetchError(Exception):
    """Raised by _fetch_batch when all retries are exhausted."""


def _parse_entries(xml_text: str) -> list:
    """Parse Atom XML returned by the arXiv API into a list of metadata dicts."""
    root = ET.fromstring(xml_text)
    entries = []
    for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
        id_elem = entry.find(f"{{{_ATOM_NS}}}id")
        pub_elem = entry.find(f"{{{_ATOM_NS}}}published")
        cat_elem = entry.find(f"{{{_ARXIV_NS}}}primary_category")

        if id_elem is None or pub_elem is None:
            continue

        # ID URL: "http://arxiv.org/abs/2001.01234v1"  →  "2001.01234"
        raw_id = (id_elem.text or "").strip()
        arxiv_id = raw_id.split("/abs/")[-1]
        if "v" in arxiv_id:
            arxiv_id = arxiv_id[: arxiv_id.rfind("v")]

        primary_category = (
            cat_elem.get("term", "") if cat_elem is not None else ""
        )

        entries.append(
            {
                "arxiv_id": arxiv_id,
                "v1_published": (pub_elem.text or "").strip(),
                "primary_category": primary_category,
            }
        )
    return entries


def _fetch_batch(arxiv_ids: list, attempt: int = 0) -> list:
    """Fetch one batch from the arXiv API with exponential-backoff retry.

    Raises _BatchFetchError (not RuntimeError) when all retries are exhausted
    so the caller can quarantine the batch rather than aborting the whole run.
    """
    params = {
        "id_list": ",".join(arxiv_ids),
        "max_results": len(arxiv_ids),
    }
    try:
        resp = requests.get(config.ARXIV_API_URL, params=params, timeout=90)
        resp.raise_for_status()
        return _parse_entries(resp.text)
    except Exception as exc:
        if attempt >= config.ARXIV_MAX_RETRIES - 1:
            raise _BatchFetchError(
                f"arXiv API request failed after {config.ARXIV_MAX_RETRIES} retries: {exc}"
            ) from exc
        delay = config.ARXIV_RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 2)
        log.warning(
            "arXiv request error (%s); retrying in %.1fs (attempt %d/%d)",
            exc, delay, attempt + 1, config.ARXIV_MAX_RETRIES,
        )
        time.sleep(delay)
        return _fetch_batch(arxiv_ids, attempt + 1)


def fetch_arxiv_metadata(arxiv_ids: list, journal: str = "unknown") -> list:
    """
    Fetch v1 timestamps and primary categories for the given arXiv IDs.

    Uses incremental caching: already-fetched records are read from
    data/raw/arxiv_meta.jsonl.  Only missing IDs hit the network.
    Each batch of 100 is separated by a sleep to respect arXiv's rate limit.

    Resilience: if a batch exhausts all retries, its IDs are quarantined and
    the run continues.  After all batches finish, quarantined IDs are retried
    once more in smaller batches of 50 with a 10-second inter-batch delay.
    If IDs still cannot be fetched, RuntimeError is raised naming the count and
    the file where the IDs are listed (data/raw/failed_ids_<journal>.txt).

    Returns a list of dicts: {arxiv_id, v1_published, primary_category}.
    IDs not found in the API response (withdrawn papers, bad IDs) are logged
    and omitted from the result.
    """
    cache_path = config.get_arxiv_cache_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Load existing cache ──────────────────────────────────────────────────
    cached: dict = {}
    if cache_path.exists():
        with open(cache_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    cached[rec["arxiv_id"]] = rec
                except json.JSONDecodeError:
                    pass
        log.info("Loaded %d arXiv records from cache", len(cached))

    # ── Identify missing IDs ─────────────────────────────────────────────────
    missing = [aid for aid in arxiv_ids if aid not in cached]
    log.info(
        "%d IDs to fetch from arXiv API  (%d already cached)",
        len(missing), len(cached),
    )

    quarantined: list = []

    if missing:
        batches = [
            missing[i: i + config.ARXIV_BATCH_SIZE]
            for i in range(0, len(missing), config.ARXIV_BATCH_SIZE)
        ]
        n_batches = len(batches)
        start_time = time.time()

        with open(cache_path, "a", encoding="utf-8") as cache_fh:
            for i, batch in enumerate(batches):
                try:
                    entries = _fetch_batch(batch)
                except _BatchFetchError as exc:
                    log.warning(
                        "Batch %d/%d exhausted all retries — quarantining %d IDs: %s",
                        i + 1, n_batches, len(batch), exc,
                    )
                    quarantined.extend(batch)
                    if i < n_batches - 1:
                        time.sleep(config.ARXIV_SLEEP_SECONDS)
                    continue

                for entry in entries:
                    cached[entry["arxiv_id"]] = entry
                    cache_fh.write(json.dumps(entry) + "\n")
                cache_fh.flush()

                elapsed = time.time() - start_time
                done = i + 1
                rate = done / elapsed if elapsed > 0 else done
                eta_min = (n_batches - done) / rate / 60
                ids_done = min(done * config.ARXIV_BATCH_SIZE, len(missing))
                log.info(
                    "arXiv batch %d/%d  |  %d/%d IDs fetched  |  ETA %.1f min",
                    done, n_batches, ids_done, len(missing), eta_min,
                )
                if i < n_batches - 1:
                    time.sleep(config.ARXIV_SLEEP_SECONDS)

    # ── Quarantine-retry pass ────────────────────────────────────────────────
    if quarantined:
        failed_path = config.DATA_DIR / f"failed_ids_{journal}.txt"
        failed_path.parent.mkdir(parents=True, exist_ok=True)
        failed_path.write_text("\n".join(quarantined) + "\n", encoding="utf-8")
        log.warning(
            "%d IDs quarantined; retrying in batches of %d with %gs delay  (list: %s)",
            len(quarantined), _RETRY_BATCH_SIZE, _RETRY_SLEEP, failed_path,
        )

        retry_batches = [
            quarantined[i: i + _RETRY_BATCH_SIZE]
            for i in range(0, len(quarantined), _RETRY_BATCH_SIZE)
        ]
        still_failed: list = []

        with open(cache_path, "a", encoding="utf-8") as cache_fh:
            for i, batch in enumerate(retry_batches):
                try:
                    entries = _fetch_batch(batch)
                    for entry in entries:
                        cached[entry["arxiv_id"]] = entry
                        cache_fh.write(json.dumps(entry) + "\n")
                    cache_fh.flush()
                    log.info(
                        "Retry batch %d/%d recovered %d IDs",
                        i + 1, len(retry_batches), len(entries),
                    )
                except _BatchFetchError as exc:
                    log.warning(
                        "Retry batch %d/%d still failing — %d IDs remain unrecoverable: %s",
                        i + 1, len(retry_batches), len(batch), exc,
                    )
                    still_failed.extend(batch)
                if i < len(retry_batches) - 1:
                    time.sleep(_RETRY_SLEEP)

        if still_failed:
            failed_path.write_text("\n".join(still_failed) + "\n", encoding="utf-8")
            raise RuntimeError(
                f"{len(still_failed)} arXiv IDs could not be fetched after quarantine retry; "
                f"see {failed_path}"
            )
        else:
            failed_path.unlink(missing_ok=True)
            log.info("All quarantined IDs recovered on retry.")

    # ── Assemble results in request order ────────────────────────────────────
    results = []
    not_found = 0
    for aid in arxiv_ids:
        if aid in cached:
            results.append(cached[aid])
        else:
            not_found += 1

    if not_found:
        log.warning(
            "%d arXiv IDs not returned by API (withdrawn papers or bad IDs) — excluded",
            not_found,
        )
    return results
