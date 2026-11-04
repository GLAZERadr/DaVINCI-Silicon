#!/bin/sh
# Create (or replace) the Modal secret "davinci-silicon" used by modal_app.py from .env.local.
# Prints only the key names, never the values. Run from the repo root:
#   sh scripts/modal_secret.sh
set -e
cd "$(dirname "$0")/.."
get() { grep -E "^$1=" .env.local | head -1 | cut -d= -f2- | tr -d '"'; }
export MODAL_TOKEN_ID="$(get MODAL_TOKEN_ID)" MODAL_TOKEN_SECRET="$(get MODAL_TOKEN_SECRET)"
set --
for k in META_API_KEY PRICE_IN_META PRICE_OUT_META DAVINCI_BUDGET_USD DAVINCI_API_TOKEN DAVINCI_PROVIDER \
         DAVINCI_REASONING_EFFORT DAVINCI_MAX_OUTPUT_TOKENS \
         GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET GITHUB_CLIENT_ID GITHUB_CLIENT_SECRET; do
  v="$(get "$k")"
  if [ -n "$v" ]; then set -- "$@" "$k=$v"; echo "including $k"; else echo "skipping $k (empty)"; fi
done
.venv/bin/modal secret create davinci-silicon --force "$@" > /dev/null && echo "secret davinci-silicon written"
