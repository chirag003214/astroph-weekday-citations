"""Tests for the journal / publication-year helpers in config.py."""
from pathlib import Path

import pytest

import config


def test_default_period_keeps_original_paths():
    # Existing 2020-2023 caches and results must not move.
    assert config.get_ads_cache_path("MNRAS") == Path("data/raw/MNRAS_ads_raw.json")
    assert config.get_ads_cache_path("A&A") == Path("data/raw/AandA_ads_raw.json")
    assert config.get_results_dir("A&A") == Path("results/AandA")


def test_other_period_gets_separate_paths():
    years = (2015, 2020)
    assert config.get_ads_cache_path("A&A", years) == Path("data/raw/AandA_2015-2020_ads_raw.json")
    assert config.get_results_dir("PASJ", years) == Path("results/2015-2020/PASJ")


@pytest.mark.parametrize("journal", list(config.JOURNALS))
def test_query_contains_year_window(journal):
    q = config.get_ads_query(journal, (2015, 2020))
    assert "year:2015-2020" in q
    assert "{years}" not in q
    assert "property:refereed doctype:article" in q


def test_default_query_unchanged():
    assert config.get_ads_query("MNRAS") == (
        "bibstem:MNRAS year:2020-2023 property:refereed doctype:article"
    )


def test_new_journals_registered():
    assert "AJ" in config.JOURNALS and "PASJ" in config.JOURNALS


@pytest.mark.parametrize("text", ["2015", "2015-", "a-b", "2020-2015"])
def test_parse_years_rejects_bad_input(text):
    with pytest.raises(ValueError):
        config.parse_years(text)


def test_parse_years():
    assert config.parse_years("2015-2020") == (2015, 2020)
