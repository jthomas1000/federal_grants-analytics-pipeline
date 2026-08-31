"""
Daily pipeline: pull GA4 (real API, OAuth2), load the Federal Grants CSV
(real data, standing in for a CRM's deals) filtered to the run day, and
generate synthetic social data (standing in for an API-key-authenticated
source), normalize all three into one schema, and load into Postgres for
Power BI.

The three extract tasks run in parallel and retry independently — a GA4
hiccup shouldn't block the grants/social legs, and vice versa.

Note on the grants leg: unlike GA4 (live, updates daily), the Federal
Grants CSV is a static historical file. Most days in a fresh DAG run will
find zero grants closing on that exact date, which is fine — the load
step is idempotent, and normalize/build_unified_table already handle an
empty source gracefully. To actually populate history, run a backfill
across the CSV's real date range (see README) rather than relying on the
daily schedule to pick up new rows the way it does for GA4.
"""
from datetime import datetime, timedelta

# When run inside the project's Docker Compose setup, the whole repo is
# mounted at /opt/airflow/project (see docker-compose.yaml volumes +
# PYTHONPATH). chdir there so relative paths in .env (GA4_TOKEN_FILE,
# GA4_OAUTH_CLIENT_SECRETS_FILE, GRANTS_CSV_PATH) resolve the same way
# they do when running scripts locally from the project root. This is a
# no-op locally, where the DAG isn't normally executed directly anyway.
import os

_PROJECT_ROOT = "/opt/airflow/project"
if os.path.isdir(_PROJECT_ROOT):
    os.chdir(_PROJECT_ROOT)

from airflow import DAG
from airflow.operators.python import PythonOperator

from extract.extract_ga4 import fetch_ga4_metrics
from extract.extract_grants import fetch_grant_opportunities
from extract.generate_synthetic_social import fetch_social_insights
from transform.normalize import build_unified_table
from load.load_to_postgres import load_unified_metrics

default_args = {
    "owner": "student",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def _extract_ga4(ds: str, **_):
    return fetch_ga4_metrics(start_date=ds, end_date=ds)


def _extract_grants(ds: str, **_):
    return fetch_grant_opportunities(start_date=ds, end_date=ds)


def _extract_social(ds: str, **_):
    return fetch_social_insights(start_date=ds, end_date=ds)


def _normalize_and_load(ti, **_):
    ga4_raw = ti.xcom_pull(task_ids="extract_ga4")
    grants_raw = ti.xcom_pull(task_ids="extract_grants")
    social_raw = ti.xcom_pull(task_ids="extract_social")

    unified_df = build_unified_table(ga4_raw or [], grants_raw or [], social_raw or [])

    if unified_df.empty:
        raise ValueError("No rows produced by normalization — check the extract tasks' output")

    rows_written = load_unified_metrics(unified_df)
    ti.xcom_push(key="rows_written", value=rows_written)


def _quality_check(ti, **_):
    rows_written = ti.xcom_pull(task_ids="normalize_and_load", key="rows_written")
    if not rows_written:
        raise ValueError("Quality check failed: zero rows were written to Postgres")
    print(f"Quality check passed: {rows_written} rows loaded")


with DAG(
    dag_id="marketing_analytics_pipeline",
    default_args=default_args,
    description="GA4 (real) + Federal Grants (real) + synthetic social -> unified Postgres table for Power BI",
    schedule="0 6 * * *",  # daily at 6am
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["portfolio", "marketing-analytics"],
) as dag:

    extract_ga4 = PythonOperator(task_id="extract_ga4", python_callable=_extract_ga4)
    extract_grants = PythonOperator(task_id="extract_grants", python_callable=_extract_grants)
    extract_social = PythonOperator(task_id="extract_social", python_callable=_extract_social)

    normalize_and_load = PythonOperator(
        task_id="normalize_and_load",
        python_callable=_normalize_and_load,
        # Run once all three extract tasks have finished, regardless of
        # whether any of them failed (default trigger_rule is "all_success",
        # which would block this task -- and the whole DAG -- any time a
        # single source like the GA4 demo property is temporarily
        # unavailable). _normalize_and_load already treats a missing/failed
        # upstream's xcom as an empty list via `ti.xcom_pull(...) or []`,
        # so the other two sources still load successfully on their own.
        trigger_rule="all_done",
    )
    quality_check = PythonOperator(task_id="quality_check", python_callable=_quality_check)

    [extract_ga4, extract_grants, extract_social] >> normalize_and_load >> quality_check
