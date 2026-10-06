#!/usr/bin/env bash
# Deploys the portal (site + API in one container) to Google Cloud Run, with the users' data in
# Firestore. Cloud Build builds the Dockerfile remotely, so Docker is not needed locally. Secrets
# go to Secret Manager. The service scales to zero.
#
# Requirements: the gcloud CLI logged in on a project with billing enabled, and .env with
# GOOGLE_CLIENT_ID, SESSION_SECRET, FMP_API_KEY and SEC_USER_AGENT. The news writer takes its
# Anthropic key from Secret Manager: ANTHROPIC_SECRET names the secret (default
# market-hub-anthropic-api-key; it can be one another service already uses). A key in
# ANTHROPIC_API_KEY is stored there first; with no key and no secret the news items keep the
# titles the code writes.
#
# Optional overrides: GCP_PROJECT, GCP_REGION, SERVICE_NAME, MAX_INSTANCES, FIRESTORE_LOCATION,
# FIRESTORE_DATABASE.
set -euo pipefail

cd "$(dirname "$0")/.."

fail() {
  echo "error: $*" >&2
  exit 1
}

command -v gcloud >/dev/null || fail "gcloud is not installed."

GCP_PROJECT="${GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}"
GCP_REGION="${GCP_REGION:-europe-west1}"
# The database stays in the EU (Belgium), as the privacy page says.
FIRESTORE_LOCATION="${FIRESTORE_LOCATION:-europe-west1}"
# A database of its own: the project's "(default)" one belongs to other apps and is in the US.
FIRESTORE_DATABASE="${FIRESTORE_DATABASE:-market-hub}"
SERVICE_NAME="${SERVICE_NAME:-market-hub}"
MAX_INSTANCES="${MAX_INSTANCES:-2}"
ENV_FILE=".env"

[[ -n "$GCP_PROJECT" ]] || fail "No GCP project selected. Run 'gcloud init' or set GCP_PROJECT."
[[ -f "$ENV_FILE" ]] || fail "$ENV_FILE not found."

env_value() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' || true; }
GOOGLE_CLIENT_ID="$(env_value GOOGLE_CLIENT_ID)"
SESSION_SECRET="$(env_value SESSION_SECRET)"
FMP_KEY="$(env_value FMP_API_KEY)"
SEC_USER_AGENT="$(env_value SEC_USER_AGENT)"
ANTHROPIC_KEY="$(env_value ANTHROPIC_API_KEY)"
ANTHROPIC_SECRET="${ANTHROPIC_SECRET:-$(env_value ANTHROPIC_SECRET)}"
ANTHROPIC_SECRET="${ANTHROPIC_SECRET:-market-hub-anthropic-api-key}"
EARNINGS_RADAR_URL="$(env_value EARNINGS_RADAR_URL)"
FUNDAMENTALS_LAB_URL="$(env_value FUNDAMENTALS_LAB_URL)"
COOKIE_DOMAIN="$(env_value MARKETHUB_COOKIE_DOMAIN)"
ADMINS="$(env_value MARKETHUB_ADMINS)"
[[ "$GOOGLE_CLIENT_ID" == *.apps.googleusercontent.com ]] || fail "GOOGLE_CLIENT_ID in $ENV_FILE is not an OAuth client id."
[[ ${#SESSION_SECRET} -ge 32 ]] || fail "SESSION_SECRET in $ENV_FILE must be at least 32 characters."
[[ -n "$FMP_KEY" ]] || fail "FMP_API_KEY is empty in $ENV_FILE."
[[ "$SEC_USER_AGENT" == *@* ]] || fail "SEC_USER_AGENT in $ENV_FILE needs a contact email."
grep -qE '^MARKETHUB_INSECURE_COOKIES=1' "$ENV_FILE" && echo "note: MARKETHUB_INSECURE_COOKIES is for local use; it is not deployed."

gcp() { gcloud --project "$GCP_PROJECT" --quiet "$@"; }

echo "→ Enabling APIs in $GCP_PROJECT"
gcp services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com firestore.googleapis.com

PROJECT_NUMBER="$(gcp projects describe "$GCP_PROJECT" --format='value(projectNumber)')"
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gcp projects add-iam-policy-binding "$GCP_PROJECT" \
  --member "serviceAccount:$SERVICE_ACCOUNT" --role roles/run.builder --condition=None >/dev/null
gcp projects add-iam-policy-binding "$GCP_PROJECT" \
  --member "serviceAccount:$SERVICE_ACCOUNT" --role roles/datastore.user --condition=None >/dev/null

echo "→ Firestore (database '$FIRESTORE_DATABASE', $FIRESTORE_LOCATION)"
DB_LOCATION="$(gcp firestore databases describe --database="$FIRESTORE_DATABASE" --format='value(locationId)' 2>/dev/null || true)"
if [[ -z "$DB_LOCATION" ]]; then
  gcp firestore databases create --database="$FIRESTORE_DATABASE" --location="$FIRESTORE_LOCATION" --type=firestore-native >/dev/null
elif [[ "$DB_LOCATION" != "$FIRESTORE_LOCATION" ]]; then
  fail "Firestore database '$FIRESTORE_DATABASE' is in $DB_LOCATION, not $FIRESTORE_LOCATION (the privacy page says the EU)."
fi

put_secret() {
  local name="$1" value="$2"
  if ! gcp secrets describe "$name" >/dev/null 2>&1; then
    gcp secrets create "$name" --replication-policy automatic >/dev/null
  fi
  if [[ "$(gcp secrets versions access latest --secret "$name" 2>/dev/null || true)" != "$value" ]]; then
    printf '%s' "$value" | gcp secrets versions add "$name" --data-file=- >/dev/null
  fi
  gcp secrets add-iam-policy-binding "$name" \
    --member "serviceAccount:$SERVICE_ACCOUNT" --role roles/secretmanager.secretAccessor >/dev/null
}
echo "→ Secrets"
put_secret market-hub-session-secret "$SESSION_SECRET"
put_secret market-hub-fmp-api-key "$FMP_KEY"
SECRETS="SESSION_SECRET=market-hub-session-secret:latest,FMP_API_KEY=market-hub-fmp-api-key:latest"
if [[ -n "$ANTHROPIC_KEY" ]]; then
  put_secret "$ANTHROPIC_SECRET" "$ANTHROPIC_KEY"
fi
if gcp secrets describe "$ANTHROPIC_SECRET" >/dev/null 2>&1; then
  gcp secrets add-iam-policy-binding "$ANTHROPIC_SECRET" \
    --member "serviceAccount:$SERVICE_ACCOUNT" --role roles/secretmanager.secretAccessor >/dev/null
  SECRETS="$SECRETS,ANTHROPIC_API_KEY=$ANTHROPIC_SECRET:latest"
  echo "→ News writer on, key from the secret $ANTHROPIC_SECRET"
else
  echo "note: no Anthropic key anywhere: news items will keep the titles the code writes."
fi

echo "→ Building with Cloud Build and deploying '$SERVICE_NAME' to $GCP_REGION (a few minutes)"
gcp run deploy "$SERVICE_NAME" \
  --source . \
  --region "$GCP_REGION" \
  --allow-unauthenticated \
  --port 8080 \
  --cpu 1 \
  --memory 512Mi \
  --min-instances 0 \
  --max-instances "$MAX_INSTANCES" \
  --timeout 60 \
  --set-secrets "$SECRETS" \
  --set-env-vars "^|^MARKETHUB_FIRESTORE=1|MARKETHUB_FIRESTORE_DATABASE=$FIRESTORE_DATABASE|GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID|SEC_USER_AGENT=$SEC_USER_AGENT|EARNINGS_RADAR_URL=$EARNINGS_RADAR_URL|FUNDAMENTALS_LAB_URL=$FUNDAMENTALS_LAB_URL|MARKETHUB_COOKIE_DOMAIN=$COOKIE_DOMAIN|MARKETHUB_ADMINS=$ADMINS"

URL="$(gcp run services describe "$SERVICE_NAME" --region "$GCP_REGION" --format 'value(status.url)')"
if curl -fsS "$URL/api/health" >/dev/null; then
  echo "✓ Deployed: $URL"
  echo "  Add $URL to the OAuth client's Authorised JavaScript origins if it is not there yet."
else
  fail "Deployed, but $URL/api/health failed. Logs: gcloud run services logs read $SERVICE_NAME --region $GCP_REGION"
fi
