"""Tests for the social synthetic generator (the grants extractor has its
own test file, test_extract_grants.py, since it reads a CSV rather than
generating data)."""
from extract.generate_synthetic_social import fetch_social_insights


def test_social_generator_is_deterministic_with_seed():
    run1 = fetch_social_insights("2026-08-01", "2026-08-02", seed=1)
    run2 = fetch_social_insights("2026-08-01", "2026-08-02", seed=1)
    assert run1 == run2


def test_social_generator_covers_all_metrics_and_days():
    blocks = fetch_social_insights("2026-08-01", "2026-08-03", seed=1)
    metric_names = {b["name"] for b in blocks}
    assert metric_names == {"page_impressions", "page_engaged_users", "page_post_engagements"}
    for block in blocks:
        assert len(block["values"]) == 3  # 3 days in range
