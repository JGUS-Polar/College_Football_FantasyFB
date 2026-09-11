# What a fantasy week actually looks like in SEC + Big Ten football

**Ticket:** [#7 What is a fantasy week? Byes and lineup locks](https://github.com/JGUS-Polar/College_Football_FantasyFB/issues/7)
**Decision:** [ADR 0002](../adr/0002-fantasy-week-model.md)
**Reproduce:** `scripts/pull-2026-schedule.sh <dir>` (3 CFBD calls) then `scripts/analyse-schedule.py <dir>`
**Pulled:** 2026-09-11, during week 2 of the 2026 season. 34 CollegeTeams, 252 regular-season games.

All day-of-week and clock figures are computed in **US Eastern**. Computing them in UTC silently reclassifies Saturday-night kickoffs as Sunday games, which is how "college football has Sunday games" becomes a false conclusion.

## 1. There is no midweek problem — there is a Friday problem

| Day (ET) | Games |
|---|---|
| Saturday | 225 |
| Friday | 20 |
| Thursday | 4 |
| Sunday | 3 |

**SEC and Big Ten play no Tuesday or Wednesday games at all.** Weeknight "MACtion" is a Mid-American Conference phenomenon and is entirely outside the Player Universe, so it cannot inform this design. The real midweek exposure is **Friday**, and it concentrates in Thanksgiving week 13 — five Friday games, all rivalries: Texas–Texas A&M, Ole Miss–Mississippi State, Iowa–Nebraska, Minnesota–Wisconsin, Florida–Florida State.

Three Sunday games exist, all in week 1 on Labor Day weekend.

**Every one of the 27 non-Saturday games has a confirmed kickoff time.** The games that would break a single weekly lock are precisely the ones whose times are already known — which is what makes per-game lock cheap to implement rather than expensive.

## 2. CFBD week 1 is eight days long and contains two Saturdays

| wk | range (ET) | Saturdays | teams playing | on bye | kickoff TBD |
|---|---|---|---|---|---|
| 1 | Sat 08-29 15:00 → Sun 09-06 19:30 | **2** | 34 | 0 | 0/35 |
| 2 | Fri 09-11 19:30 → Sat 09-12 23:00 | 1 | 33 | 1 | 0/29 |
| 3 | Fri 09-18 22:30 → Sat 09-19 23:00 | 1 | 34 | 0 | 0/27 |
| 4 | Fri 09-25 19:00 → Sat 09-26 20:00 | 1 | 34 | 0 | 14/19 |
| 5 | Fri 10-02 20:00 → Sat 10-03 20:00 | 1 | 29 | 5 | 12/15 |
| 6 | Fri 10-09 21:00 → Sat 10-10 15:30 | 1 | 29 | 5 | 13/15 |
| 7 | Fri 10-16 20:00 → Sat 10-17 13:00 | 1 | 29 | 5 | 13/15 |
| 8 | Sat 10-24 00:00 → Sat 10-24 12:00 | 1 | **24** | **10** | 11/12 |
| 9 | Sat 10-31 00:00 → Sat 10-31 15:30 | 1 | 27 | 7 | 13/14 |
| 10 | Fri 11-06 20:00 → Sat 11-07 00:00 | 1 | 32 | 2 | 15/16 |
| 11 | Fri 11-13 21:00 → Sat 11-14 00:00 | 1 | 34 | 0 | 16/17 |
| 12 | Fri 11-20 20:00 → Sat 11-21 15:30 | 1 | 34 | 0 | 14/19 |
| 13 | Fri 11-27 12:00 → Sat 11-28 12:00 | 1 | 34 | 0 | 13/19 |

Week 1 absorbs what other providers call "week 0". Every other week is a clean Friday–Saturday block, and the weeks are **disjoint with 4–6 day gaps** — no game falls between two weeks.

The consequence that settles the Week model:

```
USC plays 2x in CFBD week 1:
  Sat 2026-08-29 15:00  San José State @ USC
  Fri 2026-09-04 21:00  Fresno State @ USC
```

If the fantasy Week *is* the CFBD week number, a USC player scores two games in one fantasy week and the "opponent" column has two answers. All 34 teams play exactly 12 games, so this is a week-numbering artifact, not a scheduling oddity.

The week count is also **not stable across seasons**: 2025 ran 15 regular-season weeks, 2026 has 13. Week numbers are only meaningful within one season.

## 3. Half the season's kickoff times are a midnight placeholder

**134 of 252 games (53%) carry `startTimeTBD: true` — and every single one has a `startDate` of midnight ET on its Saturday.** Not a plausible-looking guess; exactly `00:00`.

A lock rule keyed naively off `startDate` would therefore freeze half the season's lineups at midnight on game day — before a manager wakes up, and up to 15 hours before a mid-afternoon kickoff.

Times resolve about a week out: week 3 (one week away at time of pull) is 0/27 TBD, while week 4 (two weeks away) is still 14/19. **The schedule must be re-synced weekly.** Pulling it once at season setup is a correctness bug, not merely staleness.

## 4. Byes: one per team, clustered, worst in week 8

Every one of the 34 teams plays exactly 12 games and takes **exactly one bye**. Byes fall in **weeks 5–10**, with a single outlier (Northwestern, week 2).

**Week 8 is the floor: 10 of 34 teams idle (29.4%)** — Arkansas, Florida, Georgia, Maryland, Missouri, Nebraska, Ohio State, Penn State, Purdue, Washington. A mid-season October launch begins *inside* this window.

### The thin-roster problem is smaller than it looks, and lives at scarce positions

Modelled against week 8 with 9 starters and a 6-man bench:

- Expected byes on a 15-man roster: **4.4**. On 9 starters: **2.6**. A six-man bench absorbs this comfortably at RB and WR, which are deep.
- The bite is at **singleton positions**. With one K and one DEF rostered, each has a **29.4%** chance of being idle in week 8. Two QBs both idle is **8.0%**; three of anything is 2.0%.
- Free-agent depth rescues it. In a **12-team** league week 8 offers roughly **16 startable DEF** and **7 startable QB** free agents.

**No rule change is warranted** — managing byes is fantasy football. What the data does produce is a **league-size constraint** rather than a bye rule: the startable-QB pool is what tightens first as leagues grow.

## 5. Conference championships are regular season, not postseason

The 2025 SEC Championship is `seasonType: regular`, **week 15**, `neutralSite: true`, `notes: "SEC Championship"`. Assuming it lives in `postseason` would be wrong.

Meanwhile **all 12 SEC postseason games — every bowl and the entire College Football Playoff — collapse into a single `postseason week 1` bucket.** Week numbers are unique only within a season type.

Championship week involves **four of the 34 teams**, so it cannot carry a fantasy matchup. It must be excluded **structurally rather than by week number**, because the number moves: week 15 in 2025, and likely week 14 in 2026 since week 1 swallowed an extra Saturday.

A Week is scoreable only if at least half the Player Universe (**17 of 34**) has a Game. The margins are wide in both directions — championship week has 4, the worst bye week has 24, a normal week has 34 — and the rule survives realignment changing the team count.

## 6. CFBD's 2026 season is incomplete, and absence is ambiguous

**CFBD's 2026 data currently stops at week 13.** Conference championship week is not yet published.

This makes a naive bye derivation actively dangerous: *today*, every team has no Game in week 14, so "bye = absence of a Game" would confidently tell every manager their entire roster is idle. **Absence of a Game has three meanings** — on a bye, not yet scheduled, or postponed — and only a per-season `scheduleKnownThroughWeek` high-water mark can tell them apart.

## Open item for ingestion

Not verified here, and it should not be assumed: **whether CFBD re-dates *and* renumbers a postponed game, or leaves the original date stale.** Keying the fantasy Week on dates makes renumbering harmless either way, but if CFBD leaves the old date in place the move is invisible to us and a postponed game would score in the wrong Week. This needs checking against a real historical postponement — handed to [#17](https://github.com/JGUS-Polar/College_Football_FantasyFB/issues/17).
