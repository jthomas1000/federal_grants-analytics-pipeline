"""
Loads the Federal Grants and Funding Opportunities dataset (real data,
sourced from grants.gov):
https://www.kaggle.com/datasets/webdevbadger/federal-grants-and-funding-opportunities

This replaces generate_synthetic_crm.py as the "deals" leg of the pipeline
-- a static downloaded CSV instead of a live API call, which is why this
module has no auth or rate limiting of its own (there's no API here to
call against; it's just a file on disk).

Download the CSV from the Kaggle link above and place it in this
project's data/ folder (or point GRANTS_CSV_PATH at wherever you saved it).
"""
from pathlib import Path

import pandas as pd

from config import GRANTS_CSV_PATH


def fetch_grant_opportunities(start_date: str, end_date: str, csv_path: str | None = None) -> list[dict]:
    """
    Returns grant opportunity records with a close date in [start_date,
    end_date] (inclusive), as a list of dicts -- the same "list of raw
    records" shape the GA4 and social extract functions return, so
    transform.normalize.build_unified_table() can treat all three sources
    identically.

    start_date / end_date: 'YYYY-MM-DD' strings.
    csv_path: override for testing; defaults to config.GRANTS_CSV_PATH.
    """
    path = Path(csv_path or GRANTS_CSV_PATH)
    if not path.exists():
        raise FileNotFoundError(
            f"Couldn't find the grants CSV at {path}. Download it from "
            "https://www.kaggle.com/datasets/webdevbadger/federal-grants-and-funding-opportunities "
            "and place it there, or set GRANTS_CSV_PATH in your .env."
        )

    df = pd.read_csv(path, low_memory=False)

    # The close-date column's real name varies by dataset version -- reuse
    # the same alias lookup normalize_crm() uses, so this file and the
    # normalization step never disagree about what the column is called.
    from transform.normalize import _find_grants_column

    close_date_col = _find_grants_column(df.columns.tolist(), "close_date")
    df["_parsed_close_date"] = pd.to_datetime(df[close_date_col], errors="coerce")

    mask = (df["_parsed_close_date"] >= start_date) & (df["_parsed_close_date"] <= end_date)
    filtered = df.loc[mask].drop(columns=["_parsed_close_date"])

    return filtered.to_dict(orient="records")


if __name__ == "__main__":
    # Quick manual check: python -m extract.extract_grants
    sample = fetch_grant_opportunities("2023-01-01", "2024-12-31")
    print(f"{len(sample)} grant opportunities closing in range")
    for r in sample[:3]:
        print(r)
