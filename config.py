"""
All configuration in one place, loaded from environment variables so
nothing sensitive is hardcoded. Copy .env.example to .env and fill it in.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- GA4 (real data, via the public Google Merchandise Store demo account) ---
GA4_PROPERTY_ID = os.getenv("GA4_PROPERTY_ID", "213025502")
GA4_OAUTH_CLIENT_SECRETS_FILE = os.getenv("GA4_OAUTH_CLIENT_SECRETS_FILE", "client_secret.json")
GA4_TOKEN_FILE = os.getenv("GA4_TOKEN_FILE", "token.json")

# --- Postgres (landing zone Power BI connects to) ---
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "marketing_analytics")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

DATABASE_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

# --- Federal Grants CSV (real data, replaces the synthetic CRM leg) ---
# Download from: https://www.kaggle.com/datasets/webdevbadger/federal-grants-and-funding-opportunities
GRANTS_CSV_PATH = os.getenv("GRANTS_CSV_PATH", "data/federal_grants.csv")

# --- Synthetic data (still stands in for the social API) ---
SYNTHETIC_SEED = int(os.getenv("SYNTHETIC_SEED", "42"))
