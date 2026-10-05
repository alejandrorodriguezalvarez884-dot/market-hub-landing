#!/usr/bin/env bash
# Creates .env from .env.example if it is missing, and fills what can be filled without the user:
# GOOGLE_CLIENT_ID from .env.example (it is public) and a fresh random SESSION_SECRET. Values
# already in .env are never touched. The secret is never printed.
set -euo pipefail

cd "$(dirname "$0")/.."

ENV_FILE=".env"
EXAMPLE=".env.example"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$EXAMPLE" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "Created $ENV_FILE from $EXAMPLE."
fi

value() { grep -E "^$1=" "$2" | tail -1 | cut -d= -f2- || true; }

# Sets KEY=VALUE in .env, replacing an empty KEY= line or appending one.
put() {
  if grep -qE "^$1=" "$ENV_FILE"; then
    python3 - "$ENV_FILE" "$1" "$2" <<'EOF'
import sys
path, key, val = sys.argv[1:]
lines = open(path).read().splitlines()
out = [f"{key}={val}" if l.split("=", 1)[0] == key and not l.split("=", 1)[1].strip() else l for l in lines]
open(path, "w").write("\n".join(out) + "\n")
EOF
  else
    printf '%s=%s\n' "$1" "$2" >>"$ENV_FILE"
  fi
}

if [[ -z "$(value GOOGLE_CLIENT_ID "$ENV_FILE")" && -n "$(value GOOGLE_CLIENT_ID "$EXAMPLE")" ]]; then
  put GOOGLE_CLIENT_ID "$(value GOOGLE_CLIENT_ID "$EXAMPLE")"
  echo "Set GOOGLE_CLIENT_ID in $ENV_FILE."
fi

if [[ -z "$(value SESSION_SECRET "$ENV_FILE")" ]]; then
  put SESSION_SECRET "$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  echo "Generated SESSION_SECRET in $ENV_FILE."
fi

for key in FMP_API_KEY SEC_USER_AGENT; do
  [[ -n "$(value "$key" "$ENV_FILE")" ]] || echo "note: $key is empty in $ENV_FILE (prices and ticker search need it)."
done
