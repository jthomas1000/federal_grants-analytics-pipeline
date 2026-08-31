"""
Loads the unified pandas DataFrame into the fact_marketing_metrics table
in Postgres, upserting on the (date, source, channel, metric_name)
unique constraint so re-running the pipeline for an already-loaded day
updates values instead of creating duplicate rows.
"""
import pandas as pd
from sqlalchemy import create_engine, text

from config import DATABASE_URL

_UPSERT_SQL = text(
    """
    INSERT INTO fact_marketing_metrics (metric_date, source, channel, metric_name, metric_value, currency)
    VALUES (:metric_date, :source, :channel, :metric_name, :metric_value, :currency)
    ON CONFLICT ON CONSTRAINT uq_metric_identity
    DO UPDATE SET
        metric_value = EXCLUDED.metric_value,
        currency = EXCLUDED.currency,
        loaded_at = now()
    """
)


def load_unified_metrics(df: pd.DataFrame) -> int:
    """Upserts every row in df. Returns the number of rows processed."""
    if df.empty:
        return 0

    engine = create_engine(DATABASE_URL)
    records = df.to_dict(orient="records")

    with engine.begin() as conn:
        for record in records:
            conn.execute(_UPSERT_SQL, record)

    return len(records)
