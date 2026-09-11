# DEF scoring: the points-allowed distribution for SEC and Big Ten

Data pull for issue [#9](https://github.com/JGUS-Polar/College_Football_FantasyFB/issues/9).
Completed 2026-09-11. Everything below is computed from a real CFBD pull with the
free-tier key in `.env.local`; **77 quota-counted API calls** were consumed.

This document has no opinions about what the DEF tiers should be. It exists so
that [DEF scoring model and points-allowed tiers](https://github.com/JGUS-Polar/College_Football_FantasyFB/issues/10)
can be decided against real numbers. Where a number would make a tier choice
*look* obvious, it is still only an input — #10 makes the call.

## Provenance

| | |
| --- | --- |
| Source | CollegeFootballData API (`api.collegefootballdata.com`), free tier |
| Seasons | **2022, 2023, 2024, 2025** (four — the ticket asked for at least three; the budget allowed a fourth) |
| Universe | Every team whose conference *in that season* was SEC or Big Ten — 28 teams in 2022–23, 34 in 2024–25, after realignment |
| Grain | One row per **team-game**: 1,504 regular-season + 102 postseason = **1,606** |
| Distinct games touched | 1,038 |
| Raw data | [`def-calibration-team-games.csv`](./def-calibration-team-games.csv) |
| Reproduce | [`scripts/pull-def-calibration.sh`](./scripts/pull-def-calibration.sh) → [`scripts/build-def-calibration.py`](./scripts/build-def-calibration.py) → [`scripts/analyse-def-calibration.py`](./scripts/analyse-def-calibration.py) (the last needs no API calls — it reads the committed CSV and prints every figure in this document) |

### API calls consumed: 77

| Endpoint | Calls | What it bought |
| --- | --- | --- |
| `/games?year&conference` | 8 | Final scores, `conferenceGame`, opponent classification — **points allowed comes from here, not from the box score** |
| `/games/teams?year&conference` | 9 | Team box scores: sacks, interceptions, fumbles, defensive and return TDs (8 + 1 exploratory) |
| `/plays?year&week&playType=SF` | 59 | Safeties, which are not a box-score category at all (58 + 1 exploratory) |
| `/plays/types` | 1 | Play-type vocabulary (Safety = id 20, abbreviation `SF`) |

`conference` filters work on both `/games` and `/games/teams`, so a whole
season of one conference is **one call**. `/plays` is the expensive one: it
requires `year` *and* `week`, so safeties alone cost 58 of the 77. Budget
remaining on the free tier after this pull: **917 of 1,000** for the month.

---

## Executive summary

**1. College defenses do not allow more points than NFL defenses. They allow
*less predictable* points.** SEC/B1G teams allowed a mean of **22.24** points per
regular-season game, which is close to the NFL's long-run team average (commonly
cited at roughly 22 — *not verified in this pull; no NFL data was fetched*). The
misfit is entirely in the spread: **sd 13.3**, p10 = 6, p90 = 41, max 66. The centre is
NFL-shaped; the tails are not.

**2. Applied unchanged, the NFL bands turn points allowed into a penalty.**
18.6% of SEC/B1G team-games land in the 35+ (**−4**) band against 4.5% in the
shutout (**+10**) band — the worst band fires **four times** as often as the
best. Half of all team-games (51.5%) earn **zero or less** from points allowed.
Across the whole schedule the band component averages **+0.91 points**, just 13%
of a full NFL-style DEF score. The tier ladder that is supposed to be the heart
of DEF scoring becomes a rounding error with a bad tail.

**3. The FCS distortion is real but it is not where you would look for it.** FCS
games barely move the mean (22.24 with them, 23.23 without — 6.7% of games). The
distortion is concentrated in the top tier: a defense is **shut out 23.8% of the
time against FCS opposition and 1.6% of the time in conference play**, and FCS
games supply 35% of all shutouts from 6.7% of the schedule. Every team plays
exactly one, and under NFL scoring that single game is on average **18% of its
season DEF total**.

**4. Two CFBD fields mean the opposite of what they are named,** and one stat
does not exist in the box score at all. Scoring rules written naively against
`interceptions` and `fumblesRecovered` would be wrong — see
[Field semantics](#6-field-semantics-two-traps-and-a-missing-stat).

---

## 1. Points allowed

Regular season, all 1,504 team-games. (Postseason is shown for completeness only
— the domain model says [we never score bowl games](https://github.com/JGUS-Polar/College_Football_FantasyFB/issues/15).)

| Segment | n | mean | median | sd | p25 | p75 | max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **All regular-season games** | 1,504 | **22.24** | **21** | **13.29** | 13 | 31 | 66 |
| Conference games | 1,068 | 25.01 | 24 | 12.72 | 16 | 34 | 66 |
| Non-conference vs FBS | 335 | 17.54 | 14 | 12.48 | 7 | 24 | 66 |
| Non-conference vs FCS | 101 | 8.46 | 7 | 7.53 | 3 | 13 | 31 |
| *Everything except FCS* | 1,403 | 23.23 | 22 | 13.06 | 13 | 31 | 66 |
| *Postseason (not scored)* | 102 | 24.70 | 24 | 13.01 | 14 | 34 | 63 |

### Deciles

| | p0 | p10 | p20 | p30 | p40 | **p50** | p60 | p70 | p80 | p90 | p100 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **All** | 0 | 6 | 10 | 14 | 17 | **21** | 24 | 28 | 34 | 41 | 66 |
| Conference | 0 | 10 | 14 | 17 | 21 | **24** | 27 | 31 | 36 | 42 | 66 |
| Non-conf FBS | 0 | 3 | 7 | 10 | 13 | **14** | 19 | 23 | 27 | 36 | 66 |
| FCS | 0 | 0 | 0 | 3 | 6 | **7** | 10 | 10 | 14 | 17 | 31 |

The whole conference-play distribution sits roughly **one band higher** than the
all-games distribution: the conference median (24) is the all-games 60th
percentile.

### Stability across seasons

| Season | n | mean | median | sd |
| --- | ---: | ---: | ---: | ---: |
| 2022 | 340 | 23.10 | 22.5 | 13.93 |
| 2023 | 340 | 22.67 | 21 | 13.07 |
| 2024 | 412 | 21.43 | 20 | 13.14 |
| 2025 | 412 | 21.98 | 21 | 13.02 |

Four seasons within 1.7 points of each other, spanning the 2024 realignment.
Tiers calibrated on this will not need re-cutting every year.

### Home/away

| | n | mean points allowed |
| --- | ---: | ---: |
| Home | 889 | **19.76** |
| Away | 615 | **25.81** |

A **6-point** home-field swing — larger than the width of most candidate bands.
It is not a neutral-site artefact: dropping the 76 neutral-site team-games leaves
19.63 at home against 26.01 away.
A defense's fantasy week is materially decided by where the game is played, which
is schedule luck, not managerial skill. Whether that is acceptable is a question
for #10; it is also an input for
[Matchup win probability](https://github.com/JGUS-Polar/College_Football_FantasyFB/issues/31).

---

## 2. The low end (where tiers pay out)

| Points allowed | team-games | share | conference | non-conf FBS | FCS |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 (shutout) | 68 | 4.5% | 17 | 27 | 24 |
| ≤ 3 | 119 | 7.9% | 35 | 48 | 36 |
| ≤ 7 | 235 | 15.6% | 91 | 85 | 59 |
| ≤ 10 | 353 | 23.5% | 161 | 121 | 71 |
| ≤ 14 | 503 | 33.4% | 252 | 170 | 81 |

Conditional rates make the segmentation stark:

| | P(shutout) | P(≥35 allowed) |
| --- | ---: | ---: |
| Conference game | **1.6%** | **22.7%** |
| Non-conference vs FBS | 8.1% | 11.3% |
| Non-conference vs FCS | **23.8%** | **0.0%** |

FCS games are 6.7% of the schedule and **35% of all shutouts**. In four seasons
of SEC and Big Ten football, not one FCS opponent scored 35.

Non-conference FBS games deserve as much attention as the FCS ones: they are
22% of the schedule and produce 40% of shutouts, because SEC and Big Ten teams
schedule MAC, Sun Belt and Conference USA opponents (the most common
non-conference opponents in the pull are Mid-American 61, ACC 59, Sun Belt 34,
American 33, C-USA 31). **Excluding FCS games would not remove the cupcake
effect; it would remove about a third of it.**

Schedule shape: every team plays **12 regular-season games** (13 for the two
conference-championship participants), and 101 of 124 team-seasons contain
**exactly one** FCS game. The other 23 contain none — so the distortion is not
even applied uniformly across a league.

---

## 3. Play-based stats

Regular season, per team-game. `P(≥1)` is the share of games in which a defense
records at least one.

| Stat | mean/game | sd | max | P(≥1) | P(≥2) | P(≥3) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Sacks | **2.245** | 1.79 | 10 | 83.1% | 60.4% | 38.9% |
| Interceptions | **0.807** | 0.90 | 6 | 55.3% | 19.7% | 4.7% |
| Fumbles recovered | **0.527** | 0.76 | 5 | 40.3% | 9.6% | 2.0% |
| Defensive TDs | **0.160** | 0.41 | 3 | 14.4% | 1.4% | 0.2% |
| Special-teams return TDs | **0.053** | 0.24 | 2 | 4.9% | 0.3% | — |
| Safeties | **0.031** | 0.18 | 2 | 3.1% | 0.1% | — |
| *Tackles for loss* | 5.714 | 2.90 | 16 | 98.5% | 95.9% | 88.3% |
| *Passes deflected* | 3.300 | 2.18 | 15 | 93.8% | 80.2% | 59.9% |
| *QB hurries* | 2.652 | 2.43 | 17 | 80.8% | 61.2% | 44.6% |

The last three are not in the ticket's scope but are available at no extra call
cost, and they are the only stats here that a defense records nearly every week.
If #10 wants a DEF score with a floor rather than a lottery, they are the
candidates.

### Full count distributions (share of team-games)

| Stat | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Sacks | 16.9% | 22.7% | 21.5% | 16.9% | 11.1% | 5.6% | 2.6% |
| Interceptions | 44.7% | 35.6% | 15.1% | 4.0% | 0.4% | 0.2% | 0.1% |
| Fumbles recovered | 59.7% | 30.7% | 7.6% | 1.3% | 0.5% | 0.1% | — |
| Defensive TDs | 85.6% | 13.0% | 1.2% | 0.2% | — | — | — |
| Special-teams TDs | 95.1% | 4.6% | 0.3% | — | — | — | — |
| Safeties | 96.9% | 3.0% | 0.1% | — | — | — | — |

**Frequency ratios, which are what a point value has to respect:** a sack is
**2.8×** as common as an interception, **4.3×** as common as a fumble recovery, **14×**
as common as a defensive TD, **42×** as common as a special-teams TD, and **72×**
as common as a safety. A scoring rule that pays 6 for a defensive TD and 1 for a
sack is saying one defensive TD is worth six sacks; the data says a defensive TD
happens once every 6.3 games and six sacks happen about as often.

### By segment (mean per game)

| Stat | conference | non-conf FBS | FCS |
| --- | ---: | ---: | ---: |
| Sacks | 2.211 | 2.290 | 2.465 |
| Interceptions | 0.771 | 0.913 | 0.842 |
| Fumbles recovered | 0.537 | 0.487 | 0.564 |
| Defensive TDs | 0.127 | 0.191 | **0.406** |
| Special-teams TDs | 0.037 | 0.075 | **0.149** |
| Safeties | 0.026 | 0.036 | 0.069 |

**The counting stats barely move across segments; the scoring plays triple.** A
defense records roughly the same number of sacks and takeaways against Indiana
State as against Georgia — but is **3.2× more likely to return one for a
touchdown**. The FCS effect is concentrated in exactly the two places that pay
the most: shutouts and return touchdowns.

### By season

| Season | sacks | INTs | fum rec | def TDs | ST TDs | safeties |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2022 | 2.176 | 0.782 | 0.626 | 0.138 | 0.053 | 0.021 |
| 2023 | 2.379 | 0.841 | 0.479 | 0.156 | 0.059 | 0.029 |
| 2024 | 2.257 | 0.847 | 0.556 | 0.158 | 0.029 | 0.044 |
| 2025 | 2.180 | 0.760 | 0.456 | 0.184 | 0.070 | 0.029 |

Stable. Fumble recoveries drift down ~27% across the window, which is the only
trend worth a second look, and it is small in absolute terms (0.63 → 0.46).

---

## 4. The NFL bands, applied to college

The Yahoo/ESPN standard schedule: **0 → +10, 1–6 → +7, 7–13 → +4, 14–20 → +1,
21–27 → 0, 28–34 → −1, 35+ → −4.**

| Band | pts | all games | conference | non-conf FBS | FCS |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | +10 | 4.5% | 1.6% | 8.1% | 23.8% |
| 1–6 | +7 | 5.7% | 3.5% | 9.6% | 16.8% |
| 7–13 | +4 | 18.6% | 14.9% | 25.1% | 36.6% |
| 14–20 | +1 | 19.7% | 19.7% | 21.2% | 14.9% |
| 21–27 | 0 | 19.4% | 21.7% | 16.1% | 5.9% |
| 28–34 | −1 | 13.4% | 16.0% | 8.7% | 2.0% |
| **35+** | **−4** | **18.6%** | **22.7%** | 11.3% | 0.0% |

Three ways the misfit shows up:

- **The ladder is bottom-heavy.** 32.0% of team-games land in the two negative
  bands; 10.2% in the two richest. In conference play it is 38.7% against 5.1%.
- **Points allowed stops carrying the score.** The band component averages
  **+0.91** with a median of **0**; 51.5% of team-games earn nothing or less from
  it. Under a full NFL-style schedule (bands + 1/sack, 2/takeaway, 6/TD,
  2/safety) the mean DEF score is **7.17**, of which the bands contribute
  **13%**. DEF becomes a sack-and-takeaway stat with a points-allowed penalty
  attached.
- **The bad weeks are very bad.** 12.2% of team-games score negative; the spread
  is p10 = −1, median 6, p90 = 16, max 43.

Season and segment effects under that same full NFL-style scoring:

| | mean DEF score per game |
| --- | ---: |
| Conference game | 5.99 |
| Non-conference vs FBS | 8.90 |
| Non-conference vs FCS | **13.89** |

Team-season totals run **15 to 182** (mean 86.9, sd 32.9). Best four:
Indiana 2025 (182), Penn State 2023 (181), Michigan 2023 (165), Ohio State 2024
(148). Worst: UCLA 2025 and Purdue 2024 (15 each). **A 12× spread between the
best and worst starting defense in a league** — and the bottom of that range is
a roster slot that cost a draft pick and returned about one point a week.

And the FCS game inside those totals: for the 101 team-seasons that have one, it
is on average **18.0%** of the season DEF total (median 14.6%, max 88.9%).

---

## 5. Candidate band sets — frequency only

Not recommendations. These are four band sets scored against the actual
distribution so #10 can see what each one would do. All figures are the share of
all regular-season team-games landing in each band.

| Band set | Distribution |
| --- | --- |
| **NFL standard** | 0: 4.5% · 1–6: 5.7% · 7–13: 18.6% · 14–20: 19.7% · 21–27: 19.4% · 28–34: 13.4% · 35+: **18.6%** |
| **NFL + 7** | 0: 4.5% · 1–13: 24.3% · 14–20: 19.7% · 21–27: 19.4% · 28–34: 13.4% · 35–41: 9.4% · 42+: 9.2% |
| **Even-ish college** | 0: 4.5% · 1–9: 12.4% · 10–16: 19.3% · 17–23: 19.1% · 24–30: 17.7% · 31–40: 16.0% · 41+: 11.0% |
| **Septile-matched** | ≤7: 15.6% · 8–13: 13.2% · 14–19: 15.1% · 20–24: 17.4% · 25–30: 11.6% · 31–38: 14.6% · 39+: 12.4% |

Note what the septile-matched set exposes: to make seven **equally likely** bands
you have to put the top band at "7 or fewer" and collapse the shutout into it —
because a shutout is only 4.5% of games, no band boundary can isolate it and stay
equal-sized. Any scheme that keeps the shutout as its own top tier is accepting
an uneven ladder. That is a design choice, not an accident to be fixed.

---

## 6. Field semantics: two traps and a missing stat

These were found while building the dataset and verified across all 1,606 rows.
They are binding on
[CFBD ingestion architecture](https://github.com/JGUS-Polar/College_Football_FantasyFB/issues/17)
as much as on scoring.

**The `/games/teams` category vocabulary, confirmed empirically** (this closes
the survey's second open item — the list was previously inferred from
third-party docs):

```
completionAttempts  defensiveTDs  firstDowns  fourthDownEff  fumblesLost
fumblesRecovered  interceptionTDs  interceptionYards  interceptions
kickReturnTDs  kickReturnYards  kickReturns  kickingPoints  netPassingYards
passesDeflected  passesIntercepted  passingTDs  possessionTime  puntReturnTDs
puntReturnYards  puntReturns  qbHurries  rushingAttempts  rushingTDs
rushingYards  sacks  tackles  tacklesForLoss  thirdDownEff  totalFumbles
totalPenaltiesYards  totalYards  turnovers  yardsPerPass  yardsPerRushAttempt
```

**Trap 1 — `interceptions` is an *offensive* stat.** On a team's row,
`interceptions` is the number of passes that team's **offense threw away**;
`passesIntercepted` is the number its **defense caught**. Verified: a row's
`passesIntercepted` equals the opponent's `interceptions` in **1,605 of 1,606**
rows, and `turnovers = interceptions + fumblesLost` holds in **100%** of rows.
A DEF rule fed from `interceptions` would award points for throwing picks.

**Trap 2 — `fumblesRecovered` is not takeaways.** It includes a team recovering
its own fumble. It exceeds the opponent's `fumblesLost` in 6.2% of rows and
**overstates real takeaways by 14.9% in aggregate** (958 vs 834). The clean
takeaway count is the **opponent's `fumblesLost`**, which costs nothing extra —
`/games/teams` returns both teams' rows in the same response, including for FCS
opponents (present in 100% of rows here).

**Missing — safeties are not a box-score category at all.** They exist only as
plays (`playType` = `Safety`, id 20, abbreviation `SF`). Getting them cost 58 of
this pull's 77 calls because `/plays` demands `year` *and* `week`. At 0.031 per
team-game, #10 should decide whether a safety is worth its own ingestion path or
should simply be folded into `defensiveTDs`-style scoring and ignored. Note also
that `SF` is shared with **"Offensive 1pt Safety"** (id 78), which must be
filtered out.

**Also worth knowing:**

- **`defensiveTDs` already includes interception-return TDs** (`int_tds ≤
  defensive_tds` in 1,605 of 1,606 rows). Scoring both is double-counting.
  Kick- and punt-return TDs are separate fields and are *not* included.
- **The conference query string is `B1G`; the conference name in responses is
  `Big Ten`.** Filtering response rows by the string you queried with silently
  returns nothing — and per [#3](https://github.com/JGUS-Polar/College_Football_FantasyFB/issues/3),
  a wrong conference string returns `200` with an empty array and still costs a
  call. This bug cost a rebuild here; in production it is a zero-score week.
- **Points allowed should come from `/games`, not the box score.** `/games`
  carries the scores *plus* `conferenceGame`, `homeClassification` /
  `awayClassification` and `seasonType` — everything the segmentation needs — and
  it is where `completed` lives.
- **A few stats arrive fractional.** `tacklesForLoss` has half-values in 0.1% of
  rows (`sacks` did not in this window, but the field is typed the same way).
  Parse as float, not int.

---

## 7. What this pull does *not* settle

Left open for [#10](https://github.com/JGUS-Polar/College_Football_FantasyFB/issues/10):

- **Whether DEF scoring should be band-based at all.** The counting stats move
  far less between cupcakes and conference play than the bands do; a score
  weighted toward sacks, TFL and takeaways is measurably less schedule-dependent.
  This data says the bands are the noisy part.
- **Whether to neutralise the FCS week** — and if so, how: excluding FCS games
  contradicts standing decision 5, but so does letting one game be 18% of a
  season. Note that excluding FCS removes only about a third of the cupcake
  effect; the MAC and Sun Belt games are the rest.
- **Yardage-allowed as a second axis.** `totalYards` and `netPassingYards` are in
  the same response at no extra call cost, and this pull did not analyse them.
  Yards-allowed tiers are less shutout-dependent by construction.
- **Whether defenses are predictable year to year.** Not measured here. If DEF
  scores are mostly schedule noise, drafting one early is a trap, which is a
  draft-design question as much as a scoring one.
- **Team-defense scoring during a bye week or a cancelled game.** Out of this
  pull's scope; it is a [fantasy-week](https://github.com/JGUS-Polar/College_Football_FantasyFB/issues/7)
  question.
