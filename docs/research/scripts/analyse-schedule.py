#!/usr/bin/env python3
"""Derives every figure quoted in docs/research/fantasy-week-schedule-shape.md.

Usage: analyse-schedule.py <raw-dir>   (raw-dir produced by pull-2026-schedule.sh)

All day-of-week and clock figures are computed in US Eastern. Computing them in
UTC silently reclassifies Saturday-night kickoffs as Sunday games.
"""
import collections, datetime, json, sys, zoneinfo
from math import comb

ET = zoneinfo.ZoneInfo("America/New_York")
RAW = sys.argv[1] if len(sys.argv) > 1 else "./raw"


def load(*names):
    out = []
    for n in names:
        out += json.load(open(f"{RAW}/{n}"))
    return list({g["id"]: g for g in out}.values())  # SEC/B1G crossovers appear twice


def et(game):
    return datetime.datetime.fromisoformat(
        game["startDate"].replace("Z", "+00:00")
    ).astimezone(ET)


games = load("games_2026_SEC.json", "games_2026_B1G.json")
reg = [g for g in games if g["seasonType"] == "regular"]
teams = {
    g[s + "Team"]
    for g in reg
    for s in ("home", "away")
    if g[s + "Conference"] in ("SEC", "Big Ten")
}
by_week = collections.defaultdict(list)
for g in reg:
    by_week[g["week"]].append(g)

print(f"Player Universe: {len(teams)} CollegeTeams, {len(reg)} regular-season games\n")

print("== kickoff day-of-week (ET) ==")
print(collections.Counter(et(g).strftime("%a") for g in reg), "\n")

print("== CFBD week ranges, byes, and unpublished kickoff times ==")
print(f"{'wk':<4}{'range (ET)':<28}{'sats':<6}{'playing':<9}{'bye':<5}{'TBD'}")
for w in sorted(by_week):
    gs = by_week[w]
    ts = sorted(et(g) for g in gs)
    sats = {t.date() for t in ts if t.strftime("%a") == "Sat"}
    playing = {g[s + "Team"] for g in gs for s in ("home", "away") if g[s + "Team"] in teams}
    tbd = sum(1 for g in gs if g.get("startTimeTBD"))
    rng = f"{ts[0]:%a %m-%d %H:%M} -> {ts[-1]:%a %m-%d %H:%M}  "
    flag = "  <== TWO SATURDAYS" if len(sats) > 1 else ""
    print(f"{w:<4}{rng:<28}{len(sats):<6}{len(playing):<9}{len(teams)-len(playing):<5}{tbd}/{len(gs)}{flag}")

print("\n== teams playing twice inside one CFBD week ==")
per = collections.defaultdict(lambda: collections.defaultdict(list))
for g in reg:
    for s in ("home", "away"):
        if g[s + "Team"] in teams:
            per[g[s + "Team"]][g["week"]].append(g)
for t, weeks in per.items():
    for w, gs in weeks.items():
        if len(gs) > 1:
            print(f"  {t} plays {len(gs)}x in week {w}:")
            for g in sorted(gs, key=lambda g: g["startDate"]):
                print(f"    {et(g):%a %Y-%m-%d %H:%M} {g['awayTeam']} @ {g['homeTeam']}")

print("\n== games per team ==")
counts = collections.Counter(
    g[s + "Team"] for g in reg for s in ("home", "away") if g[s + "Team"] in teams
)
print(" ", collections.Counter(counts.values()))

print("\n== startDate placeholders on unpublished kickoff times ==")
tbd = [g for g in reg if g.get("startTimeTBD")]
print(f"  {len(tbd)} of {len(reg)} games TBD; their ET times:",
      collections.Counter(et(g).strftime("%a %H:%M") for g in tbd))

print("\n== byes ==")
byes = collections.defaultdict(list)
for w in sorted(by_week):
    playing = {g[s + "Team"] for g in by_week[w] for s in ("home", "away") if g[s + "Team"] in teams}
    for t in teams - playing:
        byes[t].append(w)
worst = max(by_week, key=lambda w: len(teams) - len({
    g[s + "Team"] for g in by_week[w] for s in ("home", "away") if g[s + "Team"] in teams}))
n_bye = len(teams) - len({g[s + "Team"] for g in by_week[worst]
                          for s in ("home", "away") if g[s + "Team"] in teams})
print(f"  bye-count distribution: {collections.Counter(len(v) for v in byes.values())}")
print(f"  worst bye week: {worst} ({n_bye} of {len(teams)} idle, {100*n_bye/len(teams):.1f}%)")
print(f"  bye weeks used: {sorted({w for v in byes.values() for w in v})}")

print(f"\n== thin-roster model, week {worst} (9 starters / 6 bench, 12-team league) ==")
tot, bye, play = len(teams), n_bye, len(teams) - n_bye
print(f"  expected byes on a 15-man roster: {15*bye/tot:.1f}   on 9 starters: {9*bye/tot:.1f}")
for n in (1, 2, 3):
    print(f"  P(all {n} rostered at a scarce position idle): {100*comb(bye,n)/comb(tot,n):.1f}%")
L = 12
print(f"  {L}-team league, 1 DEF each: ~{play - L*play/tot:.0f} startable DEF free agents")
print(f"  {L}-team league, 2 QB each:  ~{play - 2*L*play/tot:.0f} startable QB free agents")

print("\n== how bowls and the CFP are typed (2025) ==")
post = load("games_2025_SEC_postseason.json")
print("  ", collections.Counter((g["seasonType"], g["week"]) for g in post))
