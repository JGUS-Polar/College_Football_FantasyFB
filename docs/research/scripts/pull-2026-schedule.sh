#!/usr/bin/env bash
# Reproduces the raw CFBD pull behind docs/research/fantasy-week-schedule-shape.md.
# 3 quota-counted calls. Requires CFBD_API_KEY in .env.local (gitignored).
set -euo pipefail
set -a; . "$(dirname "$0")/../../../.env.local"; set +a
OUT="${1:-./raw}"; mkdir -p "$OUT"
API=https://api.collegefootballdata.com
get() { curl -s -H "Authorization: Bearer $CFBD_API_KEY" "$API$1" -o "$2"; sleep 0.25; }

# 2 calls: the 2026 schedule for both conferences.
# NOTE: the conference QUERY string is B1G; the conference NAME in responses is "Big Ten".
for c in SEC B1G; do
  get "/games?year=2026&conference=$c" "$OUT/games_2026_${c}.json"
done

# 1 call: 2025 postseason, to establish how bowls and the CFP are typed.
# Conference championships are NOT postseason -- they are regular-season week 15.
get "/games?year=2025&seasonType=postseason&conference=SEC" "$OUT/games_2025_SEC_postseason.json"
