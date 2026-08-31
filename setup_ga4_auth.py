"""
Run this ONCE, locally, before the pipeline can pull real GA4 data.

It opens a browser, asks you to sign in with the Google account you used
to join the GA4 Demo Account, and saves a refresh token to token.json.
The pipeline (extract/extract_ga4.py) reuses that token file on every run
after that, so you don't have to log in again.

Setup before running this script:
  1. Join the GA4 demo account: https://support.google.com/analytics/answer/6367342
  2. In Google Cloud Console, enable the "Google Analytics Data API"
  3. Create an OAuth client ID (type: Desktop app) and download the JSON
     as client_secret.json in this project's root folder.
"""
from google_auth_oauthlib.flow import InstalledAppFlow

from config import GA4_OAUTH_CLIENT_SECRETS_FILE, GA4_TOKEN_FILE

SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]


def main() -> None:
    flow = InstalledAppFlow.from_client_secrets_file(GA4_OAUTH_CLIENT_SECRETS_FILE, SCOPES)
    credentials = flow.run_local_server(port=0)

    with open(GA4_TOKEN_FILE, "w") as f:
        f.write(credentials.to_json())

    print(f"Saved refresh token to {GA4_TOKEN_FILE}. You're ready to run the pipeline.")


if __name__ == "__main__":
    main()
