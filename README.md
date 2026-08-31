# Marketing Analytics Pipeline

A daily pipeline that pulls real GA4 traffic data (Google Merchandise
Store demo account), loads the real Federal Grants and Funding
Opportunities dataset (grants.gov-sourced, standing in for a CRM's deals),
generates realistic synthetic social media data, normalizes all three
into one schema, and loads it into Postgres for a Power BI dashboard.

**Companion notebook:** a simplified, standalone version of the CRM
(grants) normalization leg, with exploratory charts, is published on
Kaggle: https://www.kaggle.com/code/justinthomas100/federal-grants-crm-leg-normalization-companion-no

**Data source note:** genuinely real, row-level, recent (2023–2026)
commercial sales/CRM data doesn't really exist publicly — companies don't
publish that. The Federal Grants dataset is a real substitute: real
agencies, real award amounts, real close dates, just federal funding
instead of commercial sales. The synthetic social data is clearly labeled
as such rather than dressed up as real (see `power_bi/CONNECTING.md`,
section 4, for more on data provenance).

## Design notes

- **Two different auth/access models.** GA4 uses OAuth2 (a refresh token
  you get once via a browser login). The grants leg is a static file pull
  with no auth at all (it's a downloaded CSV, not a live API). The social
  leg stands in for an API-key-authenticated source. `extract/extract_ga4.py`,
  `extract/extract_grants.py`, and `extract/generate_synthetic_social.py`
  show all three patterns and why the DAG treats them uniformly anyway.
- **Schema normalization.** GA4 returns dimension/metric arrays, the
  grants CSV returns one row per opportunity, a social API returns metric
  blocks with daily values. `transform/normalize.py` flattens all three
  into one five-column table.
- **Real-world column drift.** The grants CSV's column names vary by
  export version (`AgencyName` vs `agency_name` vs `Agency Name`).
  `normalize_crm()`'s alias-lookup handles that instead of assuming one
  fixed spelling — and fails loudly with a clear error if none of the
  known aliases match, rather than silently producing wrong data.
- **Idempotent loading.** Re-running the pipeline for a day that's
  already loaded updates the row instead of duplicating it (Postgres
  `ON CONFLICT`, see `sql/create_tables.sql`).
- **Orchestration.** An Airflow DAG runs the three extracts in parallel,
  with independent retries, before normalizing and loading.
- **BI-readiness.** SQL views (`sql/power_bi_views.sql`) give Power BI
  pre-aggregated tables instead of forcing all the grouping logic into DAX.

## Project layout

```
config.py                        -- all settings, loaded from .env
setup_ga4_auth.py                -- run once to authorize GA4 access
data/
  federal_grants.csv             -- (you download this, see Setup step 3)
extract/
  extract_ga4.py                 -- real GA4 data via official Google client
  extract_grants.py              -- loads the real Federal Grants CSV, filtered by date
  generate_synthetic_social.py   -- fake social insights (Faker, seeded/reproducible)
transform/
  normalize.py                   -- pandas: maps all 3 sources to one schema
load/
  load_to_postgres.py            -- upserts into fact_marketing_metrics
sql/
  create_tables.sql              -- table + indexes
  power_bi_views.sql             -- pre-aggregated views for Power BI
dags/
  marketing_pipeline_dag.py      -- Airflow DAG wiring it all together
power_bi/
  CONNECTING.md                  -- step-by-step Power BI setup
tests/
  test_normalize.py              -- normalization logic, no credentials/files needed
  test_extract_grants.py         -- CSV date-filtering, using a small fixture file
  test_synthetic_generators.py   -- social generator determinism/schema checks
```

## Setup

### 1. Environment
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your Postgres credentials
```

### 2. GA4 access (one-time)
1. Join the GA4 Demo Account: https://support.google.com/analytics/answer/6367342
2. In Google Cloud Console, enable the **Google Analytics Data API** and
   create an OAuth client ID (type: **Desktop app**). Download the JSON
   as `client_secret.json` in the project root.
3. Run `python setup_ga4_auth.py` — this opens a browser, you log in,
   and it saves `token.json`. You only do this once.

### 3. Federal Grants CSV (one-time download)
1. Download the CSV from
   https://www.kaggle.com/datasets/webdevbadger/federal-grants-and-funding-opportunities
2. Save it as `data/federal_grants.csv` (or set `GRANTS_CSV_PATH` in `.env`
   to wherever you put it).

The dataset's real columns are confirmed (via the Kaggle dataset card):
`opportunity_id`, `opportunity_title`, `opportunity_number`,
`opportunity_category`, `funding_instrument_type`,
`category_of_funding_activity`, `cfda_numbers`, `eligible_applicants`,
`eligible_applicants_type`, `agency_code`, `agency_name`, `post_date`,
`close_date`, `last_updated_date`, `archive_date`, `award_ceiling`,
`award_floor`, `estimated_total_program_funding`,
`expected_number_of_awards`, `cost_sharing_or_matching_requirement`,
`additional_information_url` — all snake_case, matching grants.gov's own
field names. `normalize_crm()` only uses `agency_name`, `close_date`,
`award_ceiling`, and `expected_number_of_awards`; the rest are ignored but
available if you want to add more dimensions later (`eligible_applicants_type`
would make a good second channel dimension, for example).

If your download ever comes from a different mirror with different column
casing, `normalize_crm()` will raise a clear `KeyError` naming exactly
which column it couldn't find — add the real name to
`transform/normalize.py`'s `_GRANTS_COLUMN_ALIASES` and it's a one-line fix.

### 4. Database
```bash
createdb marketing_analytics
psql -d marketing_analytics -f sql/create_tables.sql
psql -d marketing_analytics -f sql/power_bi_views.sql
```

### 5. Run the tests
```bash
pytest tests/ -v
```
These run without GA4 credentials, without a live Postgres connection,
and without the real grants CSV (the grants tests use a small fixture
file), so you can verify the logic before wiring up any real credentials.

### 6. Run the pipeline manually (before wiring up Airflow)
```python
from extract.extract_ga4 import fetch_ga4_metrics
from extract.extract_grants import fetch_grant_opportunities
from extract.generate_synthetic_social import fetch_social_insights
from transform.normalize import build_unified_table
from load.load_to_postgres import load_unified_metrics

ga4 = fetch_ga4_metrics("2026-08-01", "2026-08-07")
grants = fetch_grant_opportunities("2024-01-01", "2024-12-31")  # the CSV's real date range
social = fetch_social_insights("2026-08-01", "2026-08-07")

unified = build_unified_table(ga4, grants, social)
load_unified_metrics(unified)
```
Note the grants call uses a date range that actually exists in the
historical CSV (2024, not 2026) — unlike GA4 and the social generator,
this leg isn't "today's data," it's a fixed historical file.

### 7. Run it on a schedule with Airflow
```bash
export AIRFLOW_HOME=~/airflow
airflow standalone   # spins up a local Airflow with a web UI
# then copy/symlink dags/marketing_pipeline_dag.py into $AIRFLOW_HOME/dags/
```
Because the grants CSV is historical, the daily schedule will mostly find
zero new grants closing on "today's" date — that's expected, not a bug
(see the comment at the top of `dags/marketing_pipeline_dag.py`). To
actually populate history, run a backfill over the CSV's real date range
instead of relying on daily runs:
```bash
airflow backfill create --dag-id marketing_analytics_pipeline \
  --from-date 2023-01-01 --to-date 2023-02-01
```
(`--to-date` is exclusive, so add one day past the last date you want.)

### 8. Connect Power BI
See `power_bi/CONNECTING.md`.

## Possible extensions

- **A backfill script wrapper.** The manual `airflow backfill create`
  command above works, but a small script around it (with sensible
  defaults for the grants CSV's real date range) would make repeated
  demos or re-runs less error-prone.
- **Data-quality checks between normalize and load.** Something like
  Great Expectations or pandera would catch schema drift earlier and
  more explicitly than the current alias-lookup + `KeyError` approach.
- **A lighter-weight dashboard alternative.** A small Streamlit app
  reading from the same Postgres views would make the project viewable
  in a browser without requiring Power BI Desktop.
- **Replace the social leg with a real API.** If access to a real
  Meta/YouTube/Reddit page becomes available, swapping
  `generate_synthetic_social.py` for a real API call would make all
  three legs genuinely real — the normalize/load/DAG code doesn't need
  to change either way.
