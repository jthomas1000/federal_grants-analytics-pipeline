# Connecting Power BI to This Pipeline

## 1. Get Data
Power BI Desktop → **Home → Get Data → More → Database → PostgreSQL database**

- Server: `localhost:5432` (or wherever your Postgres instance runs)
- Database: `marketing_analytics`
- Data Connectivity mode:
  - **Import** if you're just building a portfolio dashboard from a fixed
    sample of data (faster, works offline once loaded).
  - **DirectQuery** if you want the dashboard to reflect new Airflow runs
    without manually refreshing — closer to how this would work at a job,
    but slower to interact with in the Desktop app.
- Enter your Postgres username/password when prompted.

## 2. Pick the tables/views to load
Instead of pointing Power BI at the raw `fact_marketing_metrics` table,
use the pre-aggregated views in `sql/power_bi_views.sql`:

- `vw_daily_source_summary` — time series by source, good for a line chart
- `vw_channel_award_amount` — grant award amount by agency and day, good for a bar chart
- `vw_latest_metric_totals` — one row per metric, good for KPI cards

Views keep the DAX/query logic in Power BI simple, since the grouping
already happened in SQL.

## 3. Suggested first dashboard
A simple but complete portfolio dashboard:

1. **KPI cards** across the top: total sessions, total award amount, total
   awards expected, total social engagements (from `vw_latest_metric_totals`).
2. **Line chart**: `metric_date` on the x-axis, `total_value` on the
   y-axis, `source` as the legend, filtered to `metric_name = 'award_amount'`
   — shows how each source's contribution trends over time.
3. **Bar chart**: `vw_channel_award_amount`, agency on the x-axis, award
   amount on the y-axis — shows which federal agency is funding the most.
4. **Slicer**: date range, so the whole dashboard can be filtered to a
   specific week/month — useful for demoing "what if I only look at last
   week" in an interview.

## 4. What to say about it in an interview / portfolio write-up
This is the part that actually differentiates the project: be ready to
explain *why* GA4 uses OAuth2 while the grants CSV is a static file pull
and the social leg stands in for an API-key-authenticated source, why
the fact table has the unique constraint it does, and what would need to
change to add a fourth data source (add an extract function + a
normalize function that maps to the same five columns — nothing else in
the DAG or the database schema has to change). Also be ready to explain
*why* you picked real government grant data over a synthetic sales
dataset for the "deals" leg — that's a deliberate trade worth being able
to articulate: real data over a topically perfect fit.
