"""
Generates synthetic social media insights shaped like a real platform API
(e.g. Meta Graph API "page insights"): a metric name plus a list of daily
values. Stands in for a real social API for the same reason as the CRM
generator — most students don't have an app-review-approved social API
token, and the pipeline logic downstream is identical either way.
"""
import random
from datetime import date, timedelta

from config import SYNTHETIC_SEED

METRICS = ["page_impressions", "page_engaged_users", "page_post_engagements"]

# Rough starting points so the numbers look plausible rather than random noise.
_BASE_VALUES = {
    "page_impressions": 4000,
    "page_engaged_users": 300,
    "page_post_engagements": 150,
}


def fetch_social_insights(start_date: str, end_date: str, seed: int = SYNTHETIC_SEED) -> list[dict]:
    """
    Returns data in the Graph-API-style shape: a list of metric blocks,
    each containing a list of {value, end_time} points.
    """
    random.seed(seed)
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    num_days = (end - start).days + 1

    blocks = []
    for metric_name in METRICS:
        values = []
        for day_offset in range(num_days):
            current_date = start + timedelta(days=day_offset)
            base = _BASE_VALUES[metric_name]
            daily_value = max(0, int(random.gauss(base, base * 0.15)))
            values.append(
                {"value": daily_value, "end_time": f"{current_date.isoformat()}T00:00:00+0000"}
            )
        blocks.append({"name": metric_name, "values": values})
    return blocks


if __name__ == "__main__":
    sample = fetch_social_insights("2026-08-01", "2026-08-03")
    for block in sample:
        print(block["name"], block["values"])
