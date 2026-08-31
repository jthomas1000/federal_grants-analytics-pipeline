-- Run after create_tables.sql, and again any time you want to refresh
-- the view definitions:
--   psql -h localhost -U postgres -d marketing_analytics -f sql/power_bi_views.sql

-- One row per day/source/metric — good for a Power BI line chart with
-- Source as a legend field.
CREATE OR REPLACE VIEW vw_daily_source_summary AS
SELECT
    metric_date,
    source,
    metric_name,
    SUM(metric_value) AS total_value
FROM fact_marketing_metrics
GROUP BY metric_date, source, metric_name;

-- Award amount by agency (channel) and day — good for a Power BI
-- bar/stacked-column chart, or a matrix visual with agency as rows and
-- date as columns. Renamed from vw_channel_revenue: the real Federal
-- Grants data has no "revenue" metric, only award_amount.
CREATE OR REPLACE VIEW vw_channel_award_amount AS
SELECT
    metric_date,
    channel,
    SUM(metric_value) AS award_amount
FROM fact_marketing_metrics
WHERE metric_name = 'award_amount'
GROUP BY metric_date, channel;

-- A single "as of today" snapshot per metric — good for KPI card visuals.
CREATE OR REPLACE VIEW vw_latest_metric_totals AS
SELECT
    metric_name,
    SUM(metric_value) AS total_value,
    MAX(metric_date) AS as_of_date
FROM fact_marketing_metrics
GROUP BY metric_name;
