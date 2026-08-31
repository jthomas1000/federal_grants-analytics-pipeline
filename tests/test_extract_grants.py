"""
Tests for extract_grants.py. Uses a tiny fixture CSV (with the real
confirmed column names -- opportunity_id, agency_name, close_date,
award_ceiling, expected_number_of_awards) instead of the real 75,640-row
Kaggle download, so these run without needing the actual file on disk.
"""
import pandas as pd
import pytest

from extract.extract_grants import fetch_grant_opportunities


@pytest.fixture
def fixture_csv(tmp_path):
    csv_path = tmp_path / "federal_grants_fixture.csv"
    df = pd.DataFrame(
        [
            {"opportunity_id": "1", "agency_name": "NASA", "close_date": "2024-03-01",
             "award_ceiling": 500000.0, "expected_number_of_awards": 2},
            {"opportunity_id": "2", "agency_name": "NSF", "close_date": "2024-03-15",
             "award_ceiling": 250000.0, "expected_number_of_awards": 1},
            {"opportunity_id": "3", "agency_name": "NIH", "close_date": "2023-11-01",
             "award_ceiling": 750000.0, "expected_number_of_awards": 3},
        ]
    )
    df.to_csv(csv_path, index=False)
    return str(csv_path)


def test_fetch_grant_opportunities_filters_by_date_range(fixture_csv):
    records = fetch_grant_opportunities("2024-01-01", "2024-12-31", csv_path=fixture_csv)
    assert len(records) == 2
    assert {str(r["opportunity_id"]) for r in records} == {"1", "2"}


def test_fetch_grant_opportunities_returns_empty_for_no_matches(fixture_csv):
    records = fetch_grant_opportunities("2020-01-01", "2020-12-31", csv_path=fixture_csv)
    assert records == []


def test_fetch_grant_opportunities_raises_clear_error_if_file_missing():
    with pytest.raises(FileNotFoundError, match="Couldn't find the grants CSV"):
        fetch_grant_opportunities("2024-01-01", "2024-12-31", csv_path="does_not_exist.csv")
