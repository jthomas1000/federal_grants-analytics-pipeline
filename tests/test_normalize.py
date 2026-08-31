"""
Tests that each source's raw payload normalizes correctly. The GA4 and
social samples mirror what fetch_ga4_metrics / fetch_social_insights
return; the grants samples mirror the real Federal Grants and Funding
Opportunities CSV (grants.gov-sourced) once loaded with pd.read_csv(...)
.to_dict(orient="records"). None of this needs live credentials or a
network connection to test.
"""
import pandas as pd
import pytest

from transform.normalize import normalize_ga4, normalize_crm, normalize_social, build_unified_table


def test_normalize_ga4_maps_all_metrics():
    raw = [
        {"date": "20260801", "channel": "Organic Search",
         "sessions": "120", "totalUsers": "100", "conversions": "5", "totalRevenue": "250.0"},
    ]
    df = normalize_ga4(raw)
    assert set(df["metric_name"]) == {"sessions", "users", "conversions", "revenue"}
    revenue_row = df[df["metric_name"] == "revenue"].iloc[0]
    assert revenue_row["metric_value"] == 250.0
    assert revenue_row["currency"] == "USD"


def test_normalize_crm_produces_award_amount_and_expected_awards():
    # Confirmed real schema (from the Kaggle dataset card): snake_case,
    # matching grants.gov's own field names -- this is the primary case
    # to test, not a fallback.
    raw = [
        {"opportunity_id": "1", "agency_name": "National Science Foundation",
         "close_date": "2026-08-01", "award_ceiling": 500000.0, "expected_number_of_awards": 3},
        {"opportunity_id": "2", "agency_name": "Department of Energy",
         "close_date": "2026-08-01", "award_ceiling": 300000.0, "expected_number_of_awards": 2},
    ]
    df = normalize_crm(raw)
    assert set(df["metric_name"]) == {"award_amount", "awards_expected"}
    total_amount = df[df["metric_name"] == "award_amount"]["metric_value"].sum()
    assert total_amount == 800000.0
    total_expected = df[df["metric_name"] == "awards_expected"]["metric_value"].sum()
    assert total_expected == 5.0
    assert set(df["channel"]) == {"National Science Foundation", "Department of Energy"}


def test_normalize_crm_aggregates_same_agency_same_day():
    # fact_marketing_metrics has UNIQUE(metric_date, source, channel,
    # metric_name), so two opportunities from the same agency closing on
    # the same day must be summed here -- otherwise the second load's
    # upsert silently overwrites the first instead of adding to it.
    raw = [
        {"opportunity_id": "1", "agency_name": "Department of Energy",
         "close_date": "2026-08-01", "award_ceiling": 500000.0, "expected_number_of_awards": 3},
        {"opportunity_id": "2", "agency_name": "Department of Energy",
         "close_date": "2026-08-01", "award_ceiling": 300000.0, "expected_number_of_awards": 2},
    ]
    df = normalize_crm(raw)
    # One row per metric_name for this (date, agency) pair, not two.
    amount_rows = df[df["metric_name"] == "award_amount"]
    assert len(amount_rows) == 1
    assert amount_rows["metric_value"].iloc[0] == 800000.0
    expected_rows = df[df["metric_name"] == "awards_expected"]
    assert len(expected_rows) == 1
    assert expected_rows["metric_value"].iloc[0] == 5.0


def test_normalize_crm_handles_alternate_column_casing():
    # Safety net only -- the real dataset uses snake_case (tested above),
    # but this checks the alias lookup still works if a different export
    # of the same data uses CamelCase instead.
    raw = [
        {"OpportunityID": "1", "AgencyName": "NASA",
         "CloseDate": "2026-08-01", "AwardCeiling": 100000.0, "ExpectedNumberOfAwards": 1},
    ]
    df = normalize_crm(raw)
    assert df[df["metric_name"] == "award_amount"].iloc[0]["metric_value"] == 100000.0
    assert df.iloc[0]["channel"] == "NASA"


def test_normalize_crm_raises_clear_error_on_unrecognized_columns():
    raw = [{"totally_unexpected_column": "value"}]
    with pytest.raises(KeyError, match="couldn't find a column"):
        normalize_crm(raw)


def test_normalize_crm_drops_rows_with_no_close_date():
    raw = [
        {"opportunity_id": "1", "agency_name": "NIH",
         "close_date": None, "award_ceiling": 100000.0, "expected_number_of_awards": 1},
        {"opportunity_id": "2", "agency_name": "NIH",
         "close_date": "2026-08-01", "award_ceiling": 200000.0, "expected_number_of_awards": 1},
    ]
    df = normalize_crm(raw)
    # Only the second row (has a close date) should survive, x2 metrics.
    assert len(df) == 2


def test_normalize_social_skips_unmapped_metrics():
    raw = [{"name": "some_other_metric", "values": [{"value": 1, "end_time": "2026-08-01T00:00:00+0000"}]}]
    df = normalize_social(raw)
    assert df.empty


def test_normalize_social_maps_known_metrics():
    raw = [{"name": "page_impressions", "values": [{"value": 4200, "end_time": "2026-08-01T00:00:00+0000"}]}]
    df = normalize_social(raw)
    assert df.iloc[0]["metric_name"] == "impressions"
    assert df.iloc[0]["metric_value"] == 4200.0


def test_build_unified_table_combines_all_three():
    ga4_raw = [{"date": "20260801", "channel": "Organic Search",
                "sessions": "120", "totalUsers": "100", "conversions": "5", "totalRevenue": "250.0"}]
    grants_raw = [{"opportunity_id": "1", "agency_name": "NASA",
                   "close_date": "2026-08-01", "award_ceiling": 500000.0, "expected_number_of_awards": 1}]
    social_raw = [{"name": "page_impressions", "values": [{"value": 4200, "end_time": "2026-08-01T00:00:00+0000"}]}]

    unified = build_unified_table(ga4_raw, grants_raw, social_raw)
    assert set(unified["source"]) == {"google_analytics", "federal_grants", "social_media"}
    assert len(unified) == 4 + 2 + 1  # ga4: 4 metrics, grants: 2 metrics, social: 1 point


def test_build_unified_table_handles_all_empty():
    unified = build_unified_table([], [], [])
    assert unified.empty
