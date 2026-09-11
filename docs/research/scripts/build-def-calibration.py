#!/usr/bin/env python3
"""Fold the raw CFBD pull into docs/research/def-calibration-team-games.csv.

One row per SEC/Big Ten team-game: points allowed plus the defensive and
special-teams counting stats the DEF scoring decision (#10) is sized against.

Usage: build-def-calibration.py <raw-dir> <out.csv>
"""
import collections, csv, json, os, re, sys

YEARS = [2022, 2023, 2024, 2025]
CONF_QUERY = ['SEC', 'B1G']          # what the API accepts as ?conference=
UNIVERSE = {'SEC', 'Big Ten'}        # what comes back in the game records


def num(s, default=0):
    if s is None:
        return default
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return default


def main(raw, out):
    games = {}
    teamstats = {}
    for y in YEARS:
        for c in CONF_QUERY:
            for g in json.load(open(f'{raw}/games_{y}_{c}.json')):
                games[g['id']] = g
            for g in json.load(open(f'{raw}/games_teams_{y}_{c}.json')):
                for t in g['teams']:
                    teamstats[(g['id'], t['teamId'])] = {x['category']: x['stat'] for x in t['stats']}

    # Safeties are credited to the team on defense for the play.
    safeties = collections.Counter()
    for f in sorted(f for f in os.listdir(raw) if re.fullmatch(r'sf_\d{4}_w\d+\.json', f)):
        for p in json.load(open(f'{raw}/{f}')):
            if p['playType'] == 'Safety':          # excludes "Offensive 1pt Safety"
                safeties[(p['gameId'], p['defense'])] += 1

    rows, skipped = [], collections.Counter()
    for gid, g in games.items():
        if not g.get('completed'):
            skipped['not_completed'] += 1
            continue
        for side, opp in (('home', 'away'), ('away', 'home')):
            if g[f'{side}Conference'] not in UNIVERSE:
                continue
            if g[f'{side}Points'] is None or g[f'{opp}Points'] is None:
                skipped['no_score'] += 1
                continue
            st = teamstats.get((gid, g[f'{side}Id'])) or {}
            opp_st = teamstats.get((gid, g[f'{opp}Id'])) or {}
            rows.append(dict(
                game_id=gid, season=g['season'], week=g['week'], season_type=g['seasonType'],
                team=g[f'{side}Team'], team_id=g[f'{side}Id'], conference=g[f'{side}Conference'],
                home_away=side,
                opponent=g[f'{opp}Team'], opponent_conference=g[f'{opp}Conference'],
                opponent_classification=g[f'{opp}Classification'],
                conference_game=g['conferenceGame'], neutral_site=g['neutralSite'],
                points_for=g[f'{side}Points'], points_allowed=g[f'{opp}Points'],
                has_team_stats=bool(st),
                sacks=num(st.get('sacks')),
                # passesIntercepted is the DEFENSIVE count; `interceptions` is INTs THROWN.
                def_interceptions=num(st.get('passesIntercepted')),
                int_return_yards=num(st.get('interceptionYards')),
                int_tds=num(st.get('interceptionTDs')),
                # fumblesRecovered overcounts takeaways ~15%; opp_fumbles_lost is the clean one.
                fumbles_recovered=num(st.get('fumblesRecovered')),
                defensive_tds=num(st.get('defensiveTDs')),
                kick_return_tds=num(st.get('kickReturnTDs')),
                punt_return_tds=num(st.get('puntReturnTDs')),
                tackles_for_loss=num(st.get('tacklesForLoss')),
                passes_deflected=num(st.get('passesDeflected')),
                qb_hurries=num(st.get('qbHurries')),
                safeties=safeties.get((gid, g[f'{side}Team']), 0),
                has_opponent_stats=bool(opp_st),
                opp_fumbles_lost=num(opp_st.get('fumblesLost')),
                opp_ints_thrown=num(opp_st.get('interceptions')),
            ))

    rows.sort(key=lambda r: (r['season'], r['season_type'] != 'regular', r['week'], r['team']))
    with open(out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f'{len(rows)} team-games from {len(games)} games -> {out}; skipped {dict(skipped)}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
