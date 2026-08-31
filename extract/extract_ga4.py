"""
Pulls real session/user/conversion/revenue data from the GA4 Demo Account
(Google Merchandise Store) using the GA4 Data API's REST endpoint directly.

This is the "real API" leg of the pipeline: auth is OAuth2 (a refresh
token saved by setup_ga4_auth.py), which is a different auth model than
the API keys used for the synthetic CRM/social sources — that contrast is
the main integration lesson this project demonstrates.

Note: this calls the REST endpoint via google-auth's AuthorizedSession
instead of the official google-analytics-data client library. That library
pulls in grpc, which some locked-down environments (e.g. Windows machines
with Smart App Control enabled) block at the DLL level. The REST endpoint
returns identical data with zero compiled/native dependencies.
"""
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials

from config import GA4_PROPERTY_ID, GA4_TOKEN_FILE

GA4_REPORT_URL = "https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"


def _get_session() -> AuthorizedSession:
    credentials = Credentials.from_authorized_user_file(GA4_TOKEN_FILE)
    return AuthorizedSession(credentials)


def fetch_ga4_metrics(start_date: str, end_date: str) -> list[dict]:
    """
    Returns one dict per (date, channel) with session/user/conversion/revenue
    counts — the GA4 API's native shape, before any normalization happens.
    start_date / end_date use 'YYYY-MM-DD' format (or GA4 relative strings
    like '7daysAgo', 'yesterday').
    """
    session = _get_session()

    body = {
        "dateRanges": [{"startDate": start_date, "endDate": end_date}],
        "dimensions": [{"name": "date"}, {"name": "sessionDefaultChannelGroup"}],
        "metrics": [
            {"name": "sessions"},
            {"name": "totalUsers"},
            {"name": "conversions"},
            {"name": "totalRevenue"},
        ],
    }

    url = GA4_REPORT_URL.format(property_id=GA4_PROPERTY_ID)
    response = session.post(url, json=body)
    response.raise_for_status()
    payload = response.json()

    rows = []
    for row in payload.get("rows", []):
        dim_values = row["dimensionValues"]
        metric_values = row["metricValues"]
        rows.append(
            {
                "date": dim_values[0]["value"],
                "channel": dim_values[1]["value"],
                "sessions": metric_values[0]["value"],
                "totalUsers": metric_values[1]["value"],
                "conversions": metric_values[2]["value"],
                "totalRevenue": metric_values[3]["value"],
            }
        )
    return rows


if __name__ == "__main__":
    # Quick manual check: python -m extract.extract_ga4
    sample = fetch_ga4_metrics("7daysAgo", "yesterday")
    for r in sample[:5]:
        print(r)
