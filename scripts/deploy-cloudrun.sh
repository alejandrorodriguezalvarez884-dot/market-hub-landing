#!/usr/bin/env bash
# Deploys the portal (site + API in one container) to Google Cloud Run, with the users' data in
# Firestore. Cloud Build builds the Dockerfile remotely, so Docker is not needed locally. Secrets
# go to Secret Manager. The service scales to zero.
#
# Requirements: the gcloud CLI logged in on a project with billing enabled, and .env with
# GOOGLE_CLIENT_ID, SESSION_SECRET and SEC_USER_AGENT. Prices come from Yahoo Finance, which takes
# no key; an FMP_API_KEY, when there is one, is deployed as the provider behind it (MARKET_DATA=fmp
# makes it the only one). The news writer takes its
# Anthropic key from Secret Manager: ANTHROPIC_SECRET names the secret (default
# market-hub-anthropic-api-key; it can be one another service already uses). A key in
# ANTHROPIC_API_KEY is stored there first; with no key and no secret the news items keep the
# titles the code writes.
#
# Accounts with an email and a password are made behind a captcha (Cloudflare Turnstile). Its two
# keys are not in .env: they live in Secret Manager (market-hub-turnstile-site-key and
# market-hub-turnstile-secret) and the service reads them from there. Without them nobody can
# make such an account (Google still works). To store or change one:
#   printf '%s' '<key>' | gcloud secrets versions add market-hub-turnstile-secret --data-file=-
#
# Readers send articles in for review (/opinion/submit/). They are kept in a bucket this script
# makes (private, in the same region as the database) and the owner is told by email, through the
# mail server named in .env (SMTP_USER; SMTP_HOST and SMTP_PORT default to Gmail's). Its password
# is not in .env: it lives in Secret Manager (market-hub-smtp-password). For a Gmail mailbox it is
# an "app password" (myaccount.google.com/apppasswords), never the account's own:
#   printf '%s' '<app password>' | gcloud secrets versions add market-hub-smtp-password --data-file=-
# Without SMTP_USER or without that secret, the page says articles cannot be sent in.
#
# Optional overrides: GCP_PROJECT, GCP_REGION, SERVICE_NAME, MAX_INSTANCES, FIRESTORE_LOCATION,
# FIRESTORE_DATABASE, SUBMISSIONS_BUCKET.
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
MARKET_DATA="$(env_value MARKET_DATA)"
SEC_USER_AGENT="$(env_value SEC_USER_AGENT)"
ANTHROPIC_KEY="$(env_value ANTHROPIC_API_KEY)"
ANTHROPIC_SECRET="${ANTHROPIC_SECRET:-$(env_value ANTHROPIC_SECRET)}"
ANTHROPIC_SECRET="${ANTHROPIC_SECRET:-market-hub-anthropic-api-key}"
EARNINGS_RADAR_URL="$(env_value EARNINGS_RADAR_URL)"
FUNDAMENTALS_LAB_URL="$(env_value FUNDAMENTALS_LAB_URL)"
COOKIE_DOMAIN="$(env_value MARKETHUB_COOKIE_DOMAIN)"
ADMINS="$(env_value MARKETHUB_ADMINS)"
PASSWORD_LOGIN="$(env_value MARKETHUB_PASSWORD_LOGIN)"
# Where the phone app's Google sign-in may send its code besides the installed app (appsignin.py).
APP_REDIRECTS="$(env_value MARKETHUB_APP_REDIRECTS)"
[[ "$APP_REDIRECTS" != *"|"* ]] || fail "MARKETHUB_APP_REDIRECTS in $ENV_FILE cannot contain '|'."
# Readers' articles: where they are kept, and the mailbox that tells the owner (submissions.py).
SUBMISSIONS_BUCKET="${SUBMISSIONS_BUCKET:-$(env_value MARKETHUB_SUBMISSIONS_BUCKET)}"
SUBMISSIONS_BUCKET="${SUBMISSIONS_BUCKET:-$GCP_PROJECT-market-hub-submissions}"
SMTP_USER="$(env_value SMTP_USER)"
SMTP_HOST="$(env_value SMTP_HOST)"
SMTP_PORT="$(env_value SMTP_PORT)"
REVIEW_EMAIL="$(env_value MARKETHUB_REVIEW_EMAIL)"
MAIL_FROM="$(env_value MARKETHUB_MAIL_FROM)"
[[ "$SMTP_USER$SMTP_HOST$SMTP_PORT$REVIEW_EMAIL$MAIL_FROM" != *"|"* ]] || fail "The mail settings in $ENV_FILE cannot contain '|'."
[[ "$GOOGLE_CLIENT_ID" == *.apps.googleusercontent.com ]] || fail "GOOGLE_CLIENT_ID in $ENV_FILE is not an OAuth client id."
[[ ${#SESSION_SECRET} -ge 32 ]] || fail "SESSION_SECRET in $ENV_FILE must be at least 32 characters."
[[ -n "$FMP_KEY" || "$MARKET_DATA" != "fmp" ]] || fail "MARKET_DATA=fmp needs FMP_API_KEY in $ENV_FILE."
[[ "$SEC_USER_AGENT" == *@* ]] || fail "SEC_USER_AGENT in $ENV_FILE needs a contact email."
grep -qE '^MARKETHUB_INSECURE_COOKIES=1' "$ENV_FILE" && echo "note: MARKETHUB_INSECURE_COOKIES is for local use; it is not deployed."

gcp() { gcloud --project "$GCP_PROJECT" --quiet "$@"; }

# Give the service's account a role on something, only if it does not have it yet. A policy is
# one document: two deploys writing it at the same moment collide ("concurrent policy changes"),
# and the second fails. Reading it first means that in the ordinary deploy nothing is written,
# so the services' deploys can run side by side.
#   grant projects "$GCP_PROJECT" roles/run.builder --condition=None
#   grant secrets my-secret roles/secretmanager.secretAccessor
#   grant "storage buckets" "gs://my-bucket" roles/storage.objectAdmin
grant() {
  local kind="$1" resource="$2" role="$3" member="serviceAccount:$SERVICE_ACCOUNT"
  shift 3
  # $kind is left unquoted on purpose: "storage buckets" is two words of the command. grep reads
  # the whole answer (no -q): leaving early would break the pipe, and that would read as "missing".
  if gcp $kind get-iam-policy "$resource" --flatten='bindings[].members' --format='value(bindings.role,bindings.members)' 2>/dev/null \
      | tr -d '\r' | grep -xF "$role"$'\t'"$member" >/dev/null; then
    return 0
  fi
  gcp $kind add-iam-policy-binding "$resource" --member "$member" --role "$role" "$@" >/dev/null
}

echo "→ Enabling APIs in $GCP_PROJECT"
gcp services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com firestore.googleapis.com storage.googleapis.com

PROJECT_NUMBER="$(gcp projects describe "$GCP_PROJECT" --format='value(projectNumber)')"
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
grant projects "$GCP_PROJECT" roles/run.builder --condition=None
grant projects "$GCP_PROJECT" roles/datastore.user --condition=None

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
  grant secrets "$name" roles/secretmanager.secretAccessor
}
echo "→ Secrets"
put_secret market-hub-session-secret "$SESSION_SECRET"
SECRETS="SESSION_SECRET=market-hub-session-secret:latest"
if [[ -n "$FMP_KEY" ]]; then
  put_secret market-hub-fmp-api-key "$FMP_KEY"
  SECRETS="$SECRETS,FMP_API_KEY=market-hub-fmp-api-key:latest"
fi
if [[ -n "$ANTHROPIC_KEY" ]]; then
  put_secret "$ANTHROPIC_SECRET" "$ANTHROPIC_KEY"
fi
if gcp secrets describe "$ANTHROPIC_SECRET" >/dev/null 2>&1; then
  grant secrets "$ANTHROPIC_SECRET" roles/secretmanager.secretAccessor
  SECRETS="$SECRETS,ANTHROPIC_API_KEY=$ANTHROPIC_SECRET:latest"
  echo "→ News writer on, key from the secret $ANTHROPIC_SECRET"
else
  echo "note: no Anthropic key anywhere: news items will keep the titles the code writes."
fi

# The captcha's keys are only ever in Secret Manager: the service is pointed at them, nothing is copied.
if gcp secrets describe market-hub-turnstile-site-key >/dev/null 2>&1 && gcp secrets describe market-hub-turnstile-secret >/dev/null 2>&1; then
  for name in market-hub-turnstile-site-key market-hub-turnstile-secret; do
    grant secrets "$name" roles/secretmanager.secretAccessor
  done
  SECRETS="$SECRETS,TURNSTILE_SITE_KEY=market-hub-turnstile-site-key:latest,TURNSTILE_SECRET_KEY=market-hub-turnstile-secret:latest"
  echo "→ Accounts with a password: on, behind the captcha (keys from Secret Manager)"
else
  echo "note: no Turnstile keys in Secret Manager: nobody can make an account with a password (Google sign-in is not affected)."
fi

# The articles readers send in. The bucket is private, and only this service's account writes to it.
echo "→ Bucket for readers' articles (gs://$SUBMISSIONS_BUCKET, $FIRESTORE_LOCATION)"
if ! gcp storage buckets describe "gs://$SUBMISSIONS_BUCKET" >/dev/null 2>&1; then
  gcp storage buckets create "gs://$SUBMISSIONS_BUCKET" --location="$FIRESTORE_LOCATION"     --uniform-bucket-level-access --public-access-prevention >/dev/null
fi
grant "storage buckets" "gs://$SUBMISSIONS_BUCKET" roles/storage.objectAdmin
# The mailbox's password is only ever in Secret Manager, like the captcha's keys.
if [[ -n "$SMTP_USER" ]] && gcp secrets describe market-hub-smtp-password >/dev/null 2>&1; then
  grant secrets market-hub-smtp-password roles/secretmanager.secretAccessor
  SECRETS="$SECRETS,SMTP_PASSWORD=market-hub-smtp-password:latest"
  echo "→ Readers' articles: on, the owner is told from $SMTP_USER"
else
  echo "note: no SMTP_USER in $ENV_FILE or no market-hub-smtp-password in Secret Manager: readers cannot send articles in."
fi

echo "→ Building with Cloud Build and deploying '$SERVICE_NAME' to $GCP_REGION (a few minutes)"
gcp run deploy "$SERVICE_NAME" \
  --source . \
  --region "$GCP_REGION" \
  --allow-unauthenticated \
  --port 8080 \
  --cpu 1 \
  --memory 1Gi \
  --min-instances 0 \
  --max-instances "$MAX_INSTANCES" \
  --timeout 60 \
  --set-secrets "$SECRETS" \
  --set-env-vars "^|^MARKETHUB_FIRESTORE=1|MARKETHUB_FIRESTORE_DATABASE=$FIRESTORE_DATABASE|GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID|SEC_USER_AGENT=$SEC_USER_AGENT|EARNINGS_RADAR_URL=$EARNINGS_RADAR_URL|FUNDAMENTALS_LAB_URL=$FUNDAMENTALS_LAB_URL|MARKETHUB_COOKIE_DOMAIN=$COOKIE_DOMAIN|MARKETHUB_ADMINS=$ADMINS|MARKETHUB_PASSWORD_LOGIN=${PASSWORD_LOGIN:-1}|MARKET_DATA=${MARKET_DATA:-yahoo}|MARKETHUB_APP_REDIRECTS=$APP_REDIRECTS|MARKETHUB_SUBMISSIONS_BUCKET=$SUBMISSIONS_BUCKET|SMTP_USER=$SMTP_USER|SMTP_HOST=${SMTP_HOST:-smtp.gmail.com}|SMTP_PORT=${SMTP_PORT:-587}|MARKETHUB_REVIEW_EMAIL=$REVIEW_EMAIL|MARKETHUB_MAIL_FROM=$MAIL_FROM"

URL="$(gcp run services describe "$SERVICE_NAME" --region "$GCP_REGION" --format 'value(status.url)')"
if curl -fsS "$URL/api/health" >/dev/null; then
  echo "✓ Deployed: $URL"
  echo "  Add $URL to the OAuth client's Authorised JavaScript origins if it is not there yet."
else
  fail "Deployed, but $URL/api/health failed. Logs: gcloud run services logs read $SERVICE_NAME --region $GCP_REGION"
fi
