#!/usr/bin/env bash
# Reproduces the raw CFBD pull behind docs/research/def-scoring-distribution.md.
# 77 quota-counted calls. Requires CFBD_API_KEY in .env.local (gitignored).
set -euo pipefail
set -a; . "$(dirname "$0")/../../../.env.local"; set +a
OUT="${1:-./raw}"; mkdir -p "$OUT"
API=https://api.collegefootballdata.com
get() { curl -s -H "Authorization: Bearer $CFBD_API_KEY" "$API$1" -o "$2"; sleep 0.25; }

# 16 calls: game results + team box scores, per season per conference.
# NOTE: the conference QUERY string is B1G; the conference NAME in responses is "Big Ten".
for y in 2022 2023 2024 2025; do
  for c in SEC B1G; do
    get "/games?year=$y&conference=$c"       "$OUT/games_${y}_${c}.json"
    get "/games/teams?year=$y&conference=$c" "$OUT/games_teams_${y}_${c}.json"
  done
done

# 1 call: play-type vocabulary (Safety = id 20, abbreviation SF).
get "/plays/types" "$OUT/play_types.json"

# 58 calls: safeties are not a team box-score category, so they come from /plays,
# which requires year AND week. Regular season only.
for y in 2022 2023 2024 2025; do
  mw=15; [ "$y" -lt 2024 ] && mw=14
  for w in $(seq 1 $mw); do
    get "/plays?year=$y&week=$w&playType=SF" "$OUT/sf_${y}_w${w}.json"
  done
done
