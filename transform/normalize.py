"""
Normalizes the three sources' very different shapes into one table:

    metric_date | source | channel | metric_name | metric_value | currency

This is the core "integration" work of the project — GA4's dimension/metric
arrays, the grants dataset's per-opportunity rows, and the social API's
metric-block format all get flattened into the same five columns so they
can sit in one Postgres table and be sliced together in Power BI.
"""
import re

import pandas as pd

# Maps each source's raw field name to the canonical metric name used
# downstream. Keeping this explicit (rather than passing raw names through)
# is what makes three different schemas queryable as one.
GA4_METRIC_MAP = {
    "sessions": "sessions",
    "totalUsers": "users",
    "conversions": "conversions",
    "totalRevenue": "revenue",
}

SOCIAL_METRIC_MAP = {
    "page_impressions": "impressions",
    "page_engaged_users": "engaged_users",
    "page_post_engagements": "engagements",
}


def normalize_ga4(raw_rows: list[dict]) -> pd.DataFrame:
    if not raw_rows:
        return pd.DataFrame(columns=["metric_date", "source", "channel", "metric_name", "metric_value", "currency"])

    df = pd.DataFrame(raw_rows)
    df["metric_date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    df["channel"] = df["channel"]

    long_df = df.melt(
        id_vars=["metric_date", "channel"],
        value_vars=list(GA4_METRIC_MAP.keys()),
        var_name="raw_metric",
        value_name="metric_value",
    )
    long_df["metric_name"] = long_df["raw_metric"].map(GA4_METRIC_MAP)
    long_df["metric_value"] = pd.to_numeric(long_df["metric_value"])
    long_df["source"] = "google_analytics"
    long_df["currency"] = long_df["metric_name"].apply(lambda m: "USD" if m == "revenue" else None)

    return long_df[["metric_date", "source", "channel", "metric_name", "metric_value", "currency"]]


# The Federal Grants and Funding Opportunities dataset (kaggle.com/datasets/
# webdevbadger/federal-grants-and-funding-opportunities) is scraped from
# the real grants.gov API. The dataset's documented schema (confirmed via
# the Kaggle dataset card) is:
#   opportunity_id, opportunity_title, opportunity_number,
#   opportunity_category, funding_instrument_type,
#   category_of_funding_activity, cfda_numbers, eligible_applicants,
#   eligible_applicants_type, agency_code, agency_name, post_date,
#   close_date, last_updated_date, archive_date, award_ceiling,
#   award_floor, estimated_total_program_funding,
#   expected_number_of_awards, cost_sharing_or_matching_requirement,
#   additional_information_url
# All snake_case, matching grants.gov's own field names. The lookup below
# still checks a couple of casing variants as a safety net in case a
# different export of this dataset uses different capitalization, but the
# primary alias for each field is now the confirmed real column name.
_GRANTS_COLUMN_ALIASES = {
    "agency_name": ["agency_name", "AgencyName", "Agency Name"],
    "close_date": ["close_date", "CloseDate", "Close Date"],
    "award_ceiling": ["award_ceiling", "AwardCeiling", "Award Ceiling"],
    "expected_number_of_awards": [
        "expected_number_of_awards", "ExpectedNumberOfAwards", "Expected Number of Awards",
    ],
}


def _find_grants_column(columns: list[str], canonical_name: str) -> str:
    """Finds the real column name in the CSV matching one of our known aliases."""
    for alias in _GRANTS_COLUMN_ALIASES[canonical_name]:
        if alias in columns:
            return alias
    # Fall back to a whitespace/underscore/case-insensitive match.
    normalized_lookup = {re.sub(r"[\s_]", "", c).lower(): c for c in columns}
    key = re.sub(r"[\s_]", "", canonical_name).lower()
    if key in normalized_lookup:
        return normalized_lookup[key]
    raise KeyError(
        f"normalize_crm(): couldn't find a column for '{canonical_name}'. "
        f"Available columns were: {columns}. "
        f"Add the real column name to _GRANTS_COLUMN_ALIASES['{canonical_name}']."
    )


def normalize_crm(raw_grants: list[dict]) -> pd.DataFrame:
    """
    Normalizes the Federal Grants and Funding Opportunities dataset (real
    data, sourced from grants.gov) into the unified schema. This replaces
    the synthetic CRM-deals version of this function: a grant opportunity
    stands in for a "deal," the awarding agency (agency_name) stands in
    for a lead source/channel, and award_ceiling stands in for a deal
    amount.

    raw_grants: the CSV loaded as records, e.g.
        pd.read_csv("federal_grants.csv").to_dict(orient="records")
    Only agency_name, close_date, award_ceiling, and
    expected_number_of_awards are used here; the CSV's other columns
    (opportunity_category, eligible_applicants_type, cfda_numbers, etc.)
    are ignored but available if you want to add more dimensions later —
    eligible_applicants_type in particular could become a second channel
    dimension (e.g. filtering to Government vs Non-Government applicants).
    """
    if not raw_grants:
        return pd.DataFrame(columns=["metric_date", "source", "channel", "metric_name", "metric_value", "currency"])

    df = pd.DataFrame(raw_grants)
    columns = df.columns.tolist()

    close_date_col = _find_grants_column(columns, "close_date")
    agency_col = _find_grants_column(columns, "agency_name")
    ceiling_col = _find_grants_column(columns, "award_ceiling")
    awards_col = _find_grants_column(columns, "expected_number_of_awards")

    df["metric_date"] = pd.to_datetime(df[close_date_col], errors="coerce")
    # A handful of grants.gov rows have no close date (rolling/forecasted
    # opportunities) — drop them rather than guessing a date for them.
    df = df.dropna(subset=["metric_date"])

    df["channel"] = df[agency_col].fillna("unknown_agency")

    # award_ceiling is the maximum a single award under this opportunity can
    # pay out — the closest real-data analog to a CRM deal's dollar amount.
    amount_rows = df.assign(
        source="federal_grants",
        metric_name="award_amount",
        metric_value=pd.to_numeric(df[ceiling_col], errors="coerce").fillna(0.0),
        currency="USD",
    )

    # expected_number_of_awards is the grants-world equivalent of counting
    # closed deals: how many awards this opportunity is expected to make.
    count_rows = df.assign(
        source="federal_grants",
        metric_name="awards_expected",
        metric_value=pd.to_numeric(df[awards_col], errors="coerce").fillna(1.0),
        currency=None,
    )

    combined = pd.concat([amount_rows, count_rows], ignore_index=True)
    combined = combined[["metric_date", "source", "channel", "metric_name", "metric_value", "currency"]]

    # fact_marketing_metrics has a UNIQUE(metric_date, source, channel,
    # metric_name) constraint, so multiple grant opportunities that close
    # on the same day for the same agency would otherwise collapse into
    # one row via last-write-wins on upsert, silently discarding all but
    # the final opportunity loaded. Aggregate here instead, so the stored
    # value is an intentional daily total per agency (sum of award amounts,
    # sum of awards expected) rather than an arbitrary survivor.
    aggregated = (
        combined.groupby(["metric_date", "source", "channel", "metric_name", "currency"], dropna=False)["metric_value"]
        .sum()
        .reset_index()
    )
    return aggregated[["metric_date", "source", "channel", "metric_name", "metric_value", "currency"]]


def normalize_social(raw_blocks: list[dict]) -> pd.DataFrame:
    records = []
    for block in raw_blocks:
        canonical = SOCIAL_METRIC_MAP.get(block.get("name"))
        if not canonical:
            continue  # skip metrics we don't have a mapping for
        for point in block.get("values", []):
            records.append(
                {
                    "metric_date": pd.to_datetime(point["end_time"]).normalize(),
                    "source": "social_media",
                    "channel": "facebook_page",
                    "metric_name": canonical,
                    "metric_value": float(point.get("value", 0)),
                    "currency": None,
                }
            )
    return pd.DataFrame(records, columns=["metric_date", "source", "channel", "metric_name", "metric_value", "currency"])


def build_unified_table(ga4_raw: list[dict], crm_raw: list[dict], social_raw: list[dict]) -> pd.DataFrame:
    """Combines all three normalized frames into the single fact table."""
    frames = [normalize_ga4(ga4_raw), normalize_crm(crm_raw), normalize_social(social_raw)]
    non_empty = [f for f in frames if not f.empty]
    if not non_empty:
        return pd.DataFrame(columns=["metric_date", "source", "channel", "metric_name", "metric_value", "currency"])
    return pd.concat(non_empty, ignore_index=True)
