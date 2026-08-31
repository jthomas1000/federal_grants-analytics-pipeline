-- Run this once to set up the database:
--   psql -h localhost -U postgres -d marketing_analytics -f sql/create_tables.sql

CREATE TABLE IF NOT EXISTS fact_marketing_metrics (
    id            SERIAL PRIMARY KEY,
    metric_date   DATE            NOT NULL,
    source        VARCHAR(50)     NOT NULL,
    channel       VARCHAR(100)    NOT NULL,
    metric_name   VARCHAR(50)     NOT NULL,
    metric_value  NUMERIC(18, 4)  NOT NULL,
    currency      VARCHAR(3),
    loaded_at     TIMESTAMPTZ     DEFAULT now(),

    -- One row per (date, source, channel, metric). Re-running the pipeline
    -- for a day that's already loaded updates the value instead of
    -- duplicating the row (see load/load_to_postgres.py).
    CONSTRAINT uq_metric_identity UNIQUE (metric_date, source, channel, metric_name)
);

-- Power BI's most common query pattern: "show me this metric over a date
-- range, optionally filtered by source" — this index covers that directly.
CREATE INDEX IF NOT EXISTS ix_fact_date_source
    ON fact_marketing_metrics (metric_date, source);

-- Supports "total award_amount across all sources" style cross-source rollups.
CREATE INDEX IF NOT EXISTS ix_fact_metric_name
    ON fact_marketing_metrics (metric_name);

-- Supports channel-level breakdowns within a date window (e.g. a Power BI
-- bar chart of award_amount by awarding agency for the selected quarter).
CREATE INDEX IF NOT EXISTS ix_fact_date_channel_metric
    ON fact_marketing_metrics (metric_date, channel, metric_name);
