# CFBD API capability survey

Research for issue [#2](https://github.com/JGUS-Polar/College_Football_FantasyFB/issues/2).
Completed 2026-09-10. No API key was used; everything below comes from public
sources.

## How to read this document

Every claim is tagged:

- **[VERIFIED]** — read directly in a primary source (the OpenAPI spec, the
  official docs site, the pricing page, or the MIT-licensed API server source).
  A URL is cited.
- **[INFERRED]** — a conclusion I drew from verified facts. The reasoning is
  shown so it can be checked.
- **[UNVERIFIED]** — could not be established from public sources. Needs an
  empirical test with a real API key before any design depends on it.

### Primary sources used

| Source | URL |
| --- | --- |
| OpenAPI 3.0 spec (v5.27.1, fetched 2026-09-10) | https://api.collegefootballdata.com/api-docs.json (identical bytes at https://apinext.collegefootballdata.com/api-docs.json) |
| Docs site (Zudoku) | https://api.collegefootballdata.com/ |
| Getting started / auth | https://api.collegefootballdata.com/getting-started , https://api.collegefootballdata.com/authentication |
| Usage and access | https://api.collegefootballdata.com/usage-and-access |
| Data availability (coverage verified by CFBD 2026-09-03) | https://api.collegefootballdata.com/data-availability |
| Pricing / tiers | https://collegefootballdata.com/api-tiers |
| Key issuance | https://collegefootballdata.com/key |
| Terms of use (effective 2026-08-12) | https://collegefootballdata.com/terms |
| API server source (MIT) | https://github.com/CFBD/cfb-api-v2 |
| Server architecture doc | https://github.com/CFBD/cfb-api-v2/blob/main/ARCHITECTURE.md |
| Public DB schema dump | https://github.com/CFBD/cfb-test-database/blob/main/schema_dump.sql |
| GraphQL docs | https://graphqldocs.collegefootballdata.com/ |

The API server is open source under MIT, so for several questions the
authoritative answer is the shipping code rather than prose documentation. Where
that is the case it is cited by file path.

---

## Executive summary

Three findings drive the design:

1. **Live in-progress data exists, but it carries no per-player stat
   attribution.** `GET /live/plays` and `GET /scoreboard` both expose
   in-progress state. Neither returns a player stat line. The only
   player-identifying content in the live feed is a free-text `playText` field.
   Near-live fantasy scoring is therefore *possible* but requires parsing
   natural-language play descriptions. Worse — CFBD's upstream feed *does*
   carry structured `participants[]` with athlete ids, and CFBD's mapping code
   throws it away. See Q1.
2. **There is no injury, availability, suspension, or depth-chart data of any
   kind.** Not partial, not stale — absent. See Q4.
3. **Tier 2 = $5/month = 30,000 calls is correct**, and the free tier cannot
   touch live data at all. `/scoreboard` is free of quota charge on Tier 1+,
   which materially changes the sync architecture. See Q8.

---

## Q1. Live / in-progress data

**Verdict: live data exists at two levels, but no live player box score.**

### Direct answers

| Question | Answer | Confidence |
| --- | --- | --- |
| Is live data gated? | **Yes. Free and Academic tiers get neither.** Live Scoreboard needs Tier 1 ($1/mo); Live Play-by-Play needs Tier 2 ($5/mo). Enforced in code, not just marketing. | [VERIFIED] |
| What does Live Scoreboard return? | **Team-level only** — score, period, clock, possession, a `lastPlay` string, line scores, win probability. **No per-player stats.** Not sufficient for fantasy scoring on its own. | [VERIFIED] |
| Can Live Play-by-Play derive per-player stats? | **Only by parsing prose.** Each play has `playType`, `yardsGained`, down/distance/field position in structured fields, but the players involved appear **only** inside the free-text `playText`. No passer/rusher/receiver/tackler fields, no athlete id. | [VERIFIED] |
| Is Scoreboard bulk or per-game? | **Bulk** — `GET /scoreboard?conference=SEC` returns every game for a conference in one call. 2 calls covers SEC + Big Ten. | [VERIFIED] |
| Is Play-by-Play bulk or per-game? | **Per-game** — `gameId` is a required parameter. ~15 calls per poll cycle for a SEC/B1G Saturday. | [VERIFIED] |
| Poll freshness | Scoreboard: server snapshot refreshes every **60 s** — polling faster gains nothing. Live plays: **5 s** result cache, 10 s upstream timeout. | [VERIFIED] |
| Quota cost | **`/scoreboard` does not count against the monthly quota at all.** `/live/plays` does. | [VERIFIED] |
| Concurrency | **Max 2 in-flight `/live/plays` requests per key**, across all game ids. Serialize the poller. | [VERIFIED] |

### `GET /scoreboard` — game-level live state

**[VERIFIED]** Description: "Returns current scoreboard data."
Params: `classification` (defaults to `fbs`), `conference`.
Source: OpenAPI spec, path `/scoreboard`.

**[VERIFIED]** The `ScoreboardGame` response contains: `id`, `status` (enum
`scheduled` | `in_progress` | `completed`), `period`, `clock`, `situation`,
`possession`, `lastPlay`, per-team `points`, `lineScores`, `winProbability`,
plus venue, weather and betting blocks.
Source: OpenAPI spec, `components.schemas.ScoreboardGame` and
`components.schemas.GameStatus`.

**[VERIFIED] Freshness: up to ~60 seconds stale.** The server keeps a Redis
snapshot with `SNAPSHOT_TTL_SECONDS = 60` and a per-process local copy with
`LOCAL_SNAPSHOT_TTL_MS = 1000`.
Source: https://github.com/CFBD/cfb-api-v2/blob/main/src/app/games/scoreboard.ts

**[VERIFIED] Tier 1+.** The controller applies
`middlewares.requirePatreonTier(1)`.
Source: https://github.com/CFBD/cfb-api-v2/blob/main/src/app/games/controller.ts
(`@Route('scoreboard')`, line ~278).

**[VERIFIED] `/scoreboard` does NOT consume monthly quota.** It is listed in
`ignoredPaths` in the quota middleware, alongside `/auth/graphql`, `/info` and
`/info/usage`.
Source: https://github.com/CFBD/cfb-api-v2/blob/main/src/config/middleware/quotas.ts

> Note in the same file: `/live/plays` and `/games/weather` appear in
> `ignoredPaths` **commented out**, i.e. they were formerly quota-exempt and are
> now metered. Do not rely on stale community advice that live plays are free.

### `GET /live/plays` — drive- and play-level live state

**[VERIFIED]** Description: "Returns live play-by-play data and advanced metrics
for a game. Results may be cached for up to five seconds after calculation."
Param: `gameId` (required).
Source: OpenAPI spec, path `/live/plays`.

**[VERIFIED] Freshness: ~5 s server cache on top of an upstream feed with a 10 s
timeout.** `resultTtlMs = 5_000`, `maxCachedGames = 128`, `feedTimeoutMs =
10_000`.
Source: https://github.com/CFBD/cfb-api-v2/blob/main/src/app/live/service.ts and
the "Live Play Cache" section of ARCHITECTURE.md.

**[VERIFIED] Tier 2+.** The controller applies
`middlewares.requirePatreonTier(2)`.
Source: https://github.com/CFBD/cfb-api-v2/blob/main/src/app/live/controller.ts

**[VERIFIED] Max 2 concurrent `/live/plays` requests per user, across all game
IDs.** Excess requests get `429` with `Retry-After: 1`; admission failure gets
`503`. The rule is `{ path: '/live/plays', methods: ['GET'], maxConcurrent: 2,
leaseMs: 75000 }`.
Sources:
https://github.com/CFBD/cfb-api-v2/blob/main/src/config/middleware/index.ts ,
ARCHITECTURE.md ("The standard concurrency limiter allows two active requests
per authenticated user per configured endpoint").

**[VERIFIED] The live response has NO player stat attribution.** `LiveGame`
contains `teams[]` (`LiveGameTeam`: EPA/success-rate/explosiveness team
aggregates only) and `drives[]` → `plays[]` (`LiveGamePlay`). `LiveGamePlay`
fields are: `id`, `homeScore`, `awayScore`, `period`, `clock`, `wallClock`,
`teamId`, `team`, `down`, `distance`, `yardsToGoal`, `yardsGained`,
`playTypeId`, `playType`, `epa`, `garbageTime`, `success`, `rushPass`,
`downType`, `playText`. **There is no athlete id and no player name field.**
Source: OpenAPI spec, `components.schemas.LiveGame`, `LiveGameTeam`,
`LiveGameDrive`, `LiveGamePlay`.

**[INFERRED] The live feed is ESPN-derived.** `fetchLivePlays` calls a
configured `PLAYS_URL` with `{ event: gameId }` and reads
`response.data.header.competitions[0].competitors` and
`response.data.drives.previous` — the exact shape of the ESPN game-summary
endpoint. CFBD then computes EPA/success/garbage-time on top.
Source: https://github.com/CFBD/cfb-api-v2/blob/main/src/app/live/service.ts

### The upstream feed HAS structured player attribution — CFBD discards it

**This is the most consequential single finding in this survey.**

**[VERIFIED]** CFBD's own TypeScript type for the upstream play it receives is:

```ts
export interface GamePlay {
  id: string;
  sequenceNumber: string;
  type: Type2;
  text: string;
  awayScore: number;
  homeScore: number;
  period: Period5;
  clock: Clock5;
  scoringPlay: boolean;
  priority: boolean;
  modified: string;
  wallclock: string;
  start: Start4;
  end: End3;
  statYardage: number;
  scoreValue?: number;
  participants?: Participant[];   // <-- structured player attribution
}

export interface Participant {
  athlete: Athlete3;
  stats: Stat[];
  type: string;
}

export interface Athlete3 {
  id: string;
  uid: string;
  guid: string;
  lastName: string;
  fullName: string;
  displayName: string;
  shortName: string;
  links: Link3[];
  headshot: Headshot2;
  jersey: string;
  position: Position;
  team: Team7;
  status: Status;
}
```

Source: https://github.com/CFBD/cfb-api-v2/blob/main/src/app/live/types.ts
(lines ~454–460 and ~579–597).

**[VERIFIED] CFBD's mapping code never reads `participants`.** Grepping the
entire live service for `participant` returns nothing; the only text-bearing
mapping is a single line:

```ts
playText: play.text,
```

Source: https://github.com/CFBD/cfb-api-v2/blob/main/src/app/live/service.ts
(line 264).

**[VERIFIED] Sample play object** (the fixture CFBD's own test suite feeds the
service — this is the upstream shape, before CFBD strips it):

```ts
{
  id: 'play-1',
  type: { id: '5', text: 'Rush' },
  start: { team: {...}, down: 1, distance: 10, yardsToEndzone: 50 },
  end:   { team: {...}, down: 2, distance: 5,  yardsToEndzone: 45 },
  period: { number: 1 },
  clock: { displayValue: '10:00' },
  wallclock: '2026-09-05T18:00:00Z',
  statYardage: 5,
  homeScore: 0,
  awayScore: 0,
  scoringPlay: false,
  text: 'Rush for five yards',
}
```

Source: https://github.com/CFBD/cfb-api-v2/blob/main/src/app/live/service.test.ts

After CFBD's mapping, the consumer receives `playType: 'Rush'`,
`yardsGained: 5`, `playText: 'Rush for five yards'` — and no player.

**[INFERRED] Consequences, in order of importance:**

1. Live per-player fantasy scoring **cannot** be done from CFBD's live API with
   structured fields. It requires regex/NLP over `playText`, plus name→athlete-id
   matching against the roster.
2. The structured data the app actually wants (athlete id, jersey, position, and
   a per-play `stats[]` array) exists one hop upstream. **A downstream ticket
   should evaluate calling ESPN's public game-summary endpoint directly for the
   live tier**, keeping CFBD as the authoritative post-game and historical
   source. That path yields real athlete ids on every play with no text parsing
   — but it is an undocumented, unsupported, unversioned third-party endpoint
   with no SLA, and it is outside the CFBD terms that permit our commercial use.
   The tradeoff is a genuine architectural decision, not an obvious win.
3. Paying for Tier 3+ GraphQL does **not** solve this. GraphQL exposes the same
   stored tables; there is no `livePlayParticipant` entity in the operation list.

### Earliest post-game availability of final stats

**[UNVERIFIED].** CFBD publishes no ingest-latency SLA. The data-availability
page says only: "`Present` means the dataset is still maintained, but the
current season may be incomplete while games are being played or source data is
being updated."
Source: https://api.collegefootballdata.com/data-availability

**[UNVERIFIED — must be tested with a key]** Whether `GET /games/players`
returns partial rows *during* a game, or only after final. This is the single
most valuable empirical test to run once a key exists: if it populates
in-progress, it removes the need to parse `playText` entirely.

### What this means

**[INFERRED]** Near-live fantasy scoring is achievable, by one of two routes:

- **A — playText parsing.** Poll `/scoreboard` (free of quota) to find
  in-progress games, then poll `/live/plays` per game and regex the `playText`
  strings for player names and events. Player names in text must then be matched
  back to roster athlete IDs. Fragile; needs a reconciliation pass against the
  authoritative box score after the game.
- **B — post-game only.** Skip live entirely; sync `/games/players` after games
  complete. Cheap and exact, but scores update in batches, not live.

A sane design is B as the source of truth with A layered on as a provisional
"live" view that is reconciled and overwritten when finals land.

---

## Q2. Player game statistics

**Primary endpoint: `GET /games/players`** — "Returns player box score
statistics by game."
Params: `year`, `week`, `team`, `conference`, `classification`, `seasonType`,
`category`, `id` (game id). One of `week`, `team`, or `conference` is required
when filtering by year.
**[VERIFIED]** Source: OpenAPI spec, path `/games/players`.

**[VERIFIED] `conference` is a supported filter.** This is the key call-budget
fact: one call returns every player box score for every game in a conference for
a week.

**[VERIFIED] Response shape is category-bucketed strings, not typed numbers.**
`GamePlayerStats` → `teams[]` (`GamePlayerStatsTeam`: `team`, `conference`,
`homeAway`, `points`, `categories[]`) → `GamePlayerStatCategories` (`name`,
`types[]`) → `GamePlayerStatTypes` (`name`, `athletes[]`) →
`GamePlayerStatPlayer` `{ id: string, name: string, stat: string }`.
Note `stat` is typed `string`, because some values are composite (`"18/27"`).
Source: OpenAPI spec, those five schemas.

**[VERIFIED] Category names include `passing`, `rushing`, `receiving`,
`punting`, `kickReturns`, `puntReturns`, `interceptions`, `kicking`.** These
appear as literals in the server's aggregation SQL.
Source: https://github.com/CFBD/cfb-api-v2/blob/main/src/app/stats/service.ts
(lines ~280–470).

**[VERIFIED] Stat-type names confirmed in code:** `C/ATT` (passing, composite
`completions/attempts`), `YDS`, `CAR` (rushing attempts), `REC` (receptions),
`NO` (punts / returns count), `INT`, `FG` (composite `made/attempted`), `XP`
(composite `made/attempted`), `AVG`.
Source: same file — the server derives `COMPLETIONS`/`ATT` by
`split_part(stat, '/', 1|2)` on `C/ATT`, and `FGM`/`FGA`, `XPM`/`XPA` the same
way from `FG` and `XP`.

**[VERIFIED] Receptions are available.** `REC` is an explicit stat type in the
`receiving` category. PPR is supported.

**[VERIFIED] Fumbles are available as a category.** `fumbles` is a documented
player stat category.
Source (corroborating, third-party but linked from CFBD's own nav as
"cfbfastR (Third-party support)"):
https://cfbfastr.sportsdataverse.org/reference/cfbd_game_player_stats.html

**[VERIFIED] Field-goal *distance per attempt* is NOT in the box score.** The
`kicking` category carries `FG` as `made/attempted` and `XP` as
`made/attempted`. There is no per-attempt distance field anywhere in
`GamePlayerStats`.
Source: OpenAPI spec + stats service SQL, as above.

**[INFERRED] Distance-weighted FG scoring must come from play data.** Two
options:
- `GET /plays?year&week&conference=` — every play, with `playType` and
  `playText`. Distance is in the text.
- `GET /plays/stats?year&week&gameId&athleteId&statTypeId` — returns
  `{ athleteId, athleteName, statType, stat, yardsToGoal, down, distance, ... }`
  per play. `yardsToGoal` on a FG attempt gives the kick distance arithmetically.
  **[VERIFIED] `/plays/stats` is hard-capped at 2,000 records per response**
  ("Returns player and play-stat associations, limited to 2,000 records") and is
  subject to the 2-concurrent limiter.
  Source: OpenAPI spec path `/plays/stats`; middleware/index.ts.

**Supplementary per-player-per-game endpoints (all [VERIFIED] from the spec):**

| Endpoint | Content | Coverage |
| --- | --- | --- |
| `GET /passing/players/games` | Passer production, advanced metrics, pass-location breakdowns | 2025–present |
| `GET /rushing/players/games` | Individually attributed rusher production, incl. individually attributed sacks | 2025–present |
| `GET /ppa/players/games` | Per-player per-game PPA | 2001–present |
| `GET /player/season/overview` | One player's season box score + usage + PPA | 2004–present |
| `GET /stats/player/season` | Season-aggregated player stats, `startWeek`/`endWeek` filterable | 2004–present |

Coverage source: https://api.collegefootballdata.com/data-availability

**[VERIFIED] `/rushing/players/games` explicitly does not reconcile to team
totals:** "Player totals include only guarded rusher attribution... They do not
include team-only or unresolved attempts and therefore are not expected to sum
to team totals." Do not use the enriched rushing endpoints as a scoring source
of truth.
Source: OpenAPI spec, path `/rushing/players/games` description.

**[VERIFIED] Box-score coverage begins in 2004** (schedules and raw plays go
back further, box scores do not).
Source: data-availability, "Team and player box-score statistics | 2004–present".

---

## Q3. Team defensive / special-teams statistics

**Primary endpoint: `GET /games/teams`** — "Returns team box score statistics by
game." Same param set as `/games/players` minus `category`, including
`conference`.
**[VERIFIED]** Source: OpenAPI spec, path `/games/teams`.

**[VERIFIED] Response shape:** `GameTeamStats` → `teams[]` (`GameTeamStatsTeam`:
`teamId`, `team`, `conference`, `homeAway`, **`points`**, `stats[]`) →
`GameTeamStatsTeamStat` `{ category: string, stat: string }`.
Source: OpenAPI spec, those schemas.

**[VERIFIED] Points allowed is directly available.** Each game returns both
teams with a `points` field, so points allowed = the opponent entry's `points`.
No extra call.

**[UNVERIFIED — the exact `category` string list is not published.** The
categories are rows in a `team_stat_type` table, and CFBD does not enumerate
them in the OpenAPI spec, the docs site, or the public schema dump (which
contains DDL only, no data).
Source: https://github.com/CFBD/cfb-test-database/blob/main/schema_dump.sql
(`CREATE TABLE public.team_stat_type (id, name, abbreviation)` — no inserts).

**[INFERRED, corroborated by third-party docs]** The category set includes
`sacks`, `interceptions` / `passesIntercepted`, `interceptionYards`,
`interceptionTDs`, `fumblesRecovered`, `fumblesLost`, `totalFumbles`,
`defensiveTDs`, `tacklesForLoss`, `tackles`, `qbHurries`, `passesDeflected`,
`turnovers`, `kickReturns`, `kickReturnYards`, `kickReturnTDs`, `puntReturns`,
`puntReturnYards`, `puntReturnTDs`, `kickingPoints`, `possessionTime`,
`firstDowns`, `thirdDownEff`, `fourthDownEff`, `totalYards`, `netPassingYards`,
`rushingYards`, `totalPenaltiesYards`.
Source: https://cfbfastr.sportsdataverse.org/reference/cfbd_game_team_stats.html
**This list must be confirmed empirically before the DEF scoring rules are
written.** One call to `/games/teams` with a key settles it.

**[VERIFIED] Sacks, interceptions, fumble recoveries, defensive TDs and
special-teams return TDs are all obtainable at team-game granularity** (via the
above, plus `GET /stats/game/havoc` for havoc components — tackles for loss,
forced fumbles, passes defended, interceptions — available 2004–present).
Source: OpenAPI spec `/stats/game/havoc`; data-availability, "Havoc" row.

**[VERIFIED] Safeties are NOT a listed team stat category.** They do not appear
in any schema, any documented category list, or the third-party column list.
**[INFERRED]** Safeties must be derived from `GET /plays` by inspecting
`playType` (the play-type vocabulary is retrievable once from
`GET /plays/types`, which takes no parameters and is cacheable forever).

**[VERIFIED] Individual defensive player stats exist too** — the `defensive`
category on `/games/players` (tackles, sacks, TFL, PD, QB hurries). Relevant if
IDP scoring is ever added.
Source: cfbfastR category list (corroborating); category filter is a free-text
`category` param on `/games/players` in the spec.

---

## Q4. Player status — injury, availability, suspension, depth chart

## **VERDICT: NONE OF THIS DATA EXISTS. NOT PARTIALLY. NOT AT ANY TIER.**

This confirms the ticket's suspicion, and it should be treated as settled.

**[VERIFIED] Evidence 1 — the OpenAPI spec.** Searching the full 217 KB spec
(v5.27.1) case-insensitively:

| Term | Occurrences |
| --- | --- |
| `injur` | **0** |
| `suspen` | **0** |
| `depth` | 9, **all** in `PassDepth` / `averageDepthOfTarget` (pass-location metrics) |
| `snap` | 4, **all** in "CFP snapshot" (playoff ranking snapshots) |

There are 84 paths in the spec. None concerns player availability.

**[VERIFIED] Evidence 2 — the data-availability page.** It enumerates every data
family CFBD maintains: games/schedules, calendar, drives, plays, box scores,
advanced stats, havoc, play-level player stats, enriched passing/rushing,
ratings and probabilities, teams/rosters/coaches/player movement, polls,
recruiting, playoffs, draft, betting lines, weather, media. **No injury, status,
availability, or depth-chart family is listed.**
Source: https://api.collegefootballdata.com/data-availability

**[VERIFIED] Evidence 3 — the database schema.** The public schema dump has no
injury, status, availability or depth-chart table. The `athlete` table has an
`active boolean` column, but it is not exposed on any API response schema and
its semantics (roster-wide, all-time "is this athlete current") are unrelated to
weekly game availability.
Source: https://github.com/CFBD/cfb-test-database/blob/main/schema_dump.sql

**[VERIFIED] Evidence 4 — tier gating.** Exactly seven endpoints are behind a
paywall: `/games/weather`, `/scoreboard`, `/live/plays`, `/wepa/team/season`,
`/wepa/players/passing`, `/wepa/players/rushing`, `/wepa/players/kicking`.
("Patreon checks are operation-bound middleware on the seven existing paid
handlers.") So there is no hidden higher-tier injury feed.
Source: ARCHITECTURE.md, "Authentication, Quotas, And Slowdown".

### The closest available proxies (all weak)

**[INFERRED]** and all after-the-fact rather than predictive:

- **Did-not-play**: absence of a player from `GET /games/players` for a
  completed game means they recorded no stats. Zero-stat participation and
  non-participation are indistinguishable.
- **Snap-share collapse**: `GET /player/usage` (season-level, 2013–present) or
  week-over-week deltas in `/games/players`. Backward-looking only.
- **Transfer portal**: `GET /player/portal` marks departures, but see Q7 —
  no athlete id on those rows.

**Product implication.** The league cannot show injury designations, cannot
auto-bench an out player, and cannot warn a manager before lock. Any
availability signal must come from outside CFBD (manual entry, a scraped source,
or a second paid provider) or be designed around entirely — e.g. generous
waiver rules, forgiving lineup lock, or scoring that tolerates zeroed starters.
A downstream ticket must own this.

---

## Q5. Rosters

**Endpoint: `GET /roster`** — "Returns historical roster data."
Params: `team`, `year` (defaults to 2025), `classification` (`fbs` or `fcs`).
**[VERIFIED]** Source: OpenAPI spec, path `/roster`.

**[VERIFIED] There is NO `conference` filter on `/roster`.** The server query
supports `team` (exact, case-insensitive school name) and `classification`
(joins conference division) only.
Source: https://github.com/CFBD/cfb-api-v2/blob/main/src/app/teams/service.ts
(`getRoster`).

**[INFERRED]** Therefore SEC + Big Ten rosters are fetched either as **34 calls**
(one per team) or **1 call** (`?classification=fbs`, ~140 teams, filtered
locally). The one-call form is strictly cheaper on quota at the cost of a larger
payload.

**[VERIFIED] `RosterPlayer` fields:** `id` (string), `firstName`, `lastName`,
`team`, `height`, `weight`, `jersey`, `year` *(marked `deprecated: true` in the
spec)*, `position`, `homeCity`/`homeState`/`homeCountry`/`homeLatitude`/
`homeLongitude`/`homeCountyFIPS`, `recruitIds[]`.
Source: OpenAPI spec, `components.schemas.RosterPlayer`.

**[VERIFIED] Jersey numbers and positions: present** (both nullable).

**[VERIFIED] Class / eligibility year: present but DEPRECATED and not
season-scoped.** `year` reads from a single `athlete.year` column on the athlete
row, not from the per-season `athlete_team` stint, and the service falls back to
the requested year when null (`year: r.year ?? year`).
Sources: the `athlete` table DDL in schema_dump.sql (`year smallint` on
`athlete`, not on `athlete_team`); `getRoster` in teams/service.ts; the
`"deprecated": true` flag in the spec.
**Do not build eligibility logic on this field.**

**[VERIFIED] Coverage: 2004–present.** "Player and biographical field
completeness varies by season and team."
Source: data-availability.

---

## Q6. Schedules, weeks, and bye weeks

**Endpoint: `GET /games`** — params `year`, `week`, `seasonType`,
`classification`, `team`, `home`, `away`, `conference`, `id`, `competition`,
`round`. `conference` matches "Conference of either team".
**[VERIFIED]** Source: OpenAPI spec, path `/games`.

**[VERIFIED] `Game` fields relevant here:** `id`, `season`, `week`,
`seasonType`, `startDate` (`date-time`), `startTimeTBD` (boolean), `completed`
(boolean), `neutralSite`, `conferenceGame`, `venue`, home/away team + id +
conference + classification + points + lineScores, and post-game Elo/win-prob.
Source: OpenAPI spec, `components.schemas.Game`.

**[VERIFIED] Kickoff times: yes, via `startDate`, with an explicit `startTimeTBD`
flag** for games whose time is not yet set. Design for TBD kickoffs — lineup
lock cannot assume a known time.

**[VERIFIED] `/games` has no in-progress status.** It carries only `completed:
boolean`. The tri-state `scheduled | in_progress | completed` enum exists **only**
on `/scoreboard`.
Source: OpenAPI spec — `GameStatus` is referenced by `ScoreboardGame` and by
nothing else.

**Week numbering — `GET /calendar?year=`** (required param).
**[VERIFIED]** `CalendarWeek` = `season`, `week`, `seasonType`, `startDate`,
`endDate`, plus deprecated `firstGameStart` / `lastGameStart`.
**[VERIFIED]** "Calendar weeks are derived from the games available for a
season." Coverage 2002–present.
Sources: OpenAPI spec `/calendar`; data-availability.

**[VERIFIED] `SeasonType` enum:** `regular`, `postseason`, `both`, `allstar`,
`spring_regular`, `spring_postseason`. Week numbers are scoped by season type —
week 1 regular and week 1 postseason are different weeks. Any internal week key
must be `(season, seasonType, week)`, not `week` alone.
Source: OpenAPI spec, `components.schemas.SeasonType`.

### Bye / open weeks

**[VERIFIED] There is no bye-week or open-week endpoint or field.** The string
`bye` appears exactly twice in the entire spec, both times as
`CfpParticipant.firstRoundBye` — a College Football Playoff concept, unrelated
to regular-season byes. `open week` and `openWeek` appear zero times.

**[INFERRED] Byes must be computed locally:** cross `GET /calendar?year=` (the
set of weeks) against `GET /games?year=&conference=` (the weeks in which each
team appears). A team missing from week *N* has a bye. This costs no extra API
calls — both datasets are already needed.

---

## Q7. Player identity, ID stability, and transfers

**[VERIFIED] Player IDs are stable across seasons and across schools.** The
`athlete` table has a single `id bigint` primary key holding identity and
biographical data. Team membership lives in a separate `athlete_team` join table
(`athlete_id`, `team_id`, `start_year`, `end_year`). A transfer creates a new
*stint row*, not a new athlete.
Source: https://github.com/CFBD/cfb-test-database/blob/main/schema_dump.sql

**[VERIFIED] The roster endpoint returns exactly that `athlete.id`.**
`getRoster` selects `athlete.id` after joining
`team → athleteTeam → athlete` and filtering
`athleteTeam.startYear <= year <= athleteTeam.endYear`.
Source: teams/service.ts, `getRoster`.

**[VERIFIED] The same ID space appears on the stat endpoints:**
`GamePlayerStatPlayer.id` (string), `PlayStat.athleteId` (string),
`PlayerStat.playerId` (string), `PlayerSearchResult.id` (string),
`PlayerSeasonOverview.id` (string). All are the string rendering of
`athlete.id`.
Source: OpenAPI spec + `getRoster`/`getGamePlayerStats` queries in the server.

**[VERIFIED] Transfers are visible on the player record.**
`GET /player/search` returns `PlayerSearchResult` with `activeStartYear`,
`activeEndYear`, and `teamStints[]` — an array of
`{ team, startYear, endYear }`. One athlete id, several schools.
Source: OpenAPI spec, `PlayerSearchResult` / `PlayerSearchTeamStint`.

**[VERIFIED] `GET /player/search` returns at most 100 matches** ("Returns up to
100 players whose names match the search term"). Params: `searchTerm`
(required), `year`, `team`, `position`.

### The transfer-portal gap

**[VERIFIED] `GET /player/portal?year=` exists** ("Returns transfer portal
entries for a season"), coverage 2021–present.
Source: OpenAPI spec `/player/portal`; data-availability, "Transfer portal".

**[VERIFIED] `PlayerTransfer` has NO athlete id.** Fields are: `season`,
`firstName`, `lastName`, `position`, `origin`, `destination`, `transferDate`,
`rating`, `stars`, `eligibility` (enum `Withdrawn`, `TBD`, `PendingAppeal`,
`SittingOne`, `Immediate`). The underlying `transfer` table likewise stores
`first_name`, `last_name`, `position_id`, `from_team_id`, `to_team_id` — and no
`athlete_id` column.
Sources: OpenAPI spec `components.schemas.PlayerTransfer`;
schema_dump.sql `CREATE TABLE public.transfer`.

**[INFERRED] Portal rows can only be joined to players by fuzzy name +
position + origin school matching.** This is a real correctness risk for any
feature that tracks a player through the portal. The reliable alternative is to
ignore `/player/portal` for identity purposes and detect school changes from
`teamStints` on `/player/search`, or simply from a player's presence on a
different team's `/roster` in the new season — both of which are keyed on the
stable athlete id.

**[VERIFIED] `destination` is nullable** — a player in the portal without a
landing spot yet. Combined with `eligibility: 'Withdrawn'`, portal rows are not
a reliable "this player left" signal on their own.

---

## Q8. Tiers, quotas, and rate limits

### The ticket's assumption is CORRECT

> "Confirm or correct the assumption that Tier 2 is $5/month for 30,000 calls."

**[VERIFIED] Tier 2 is $5/month for 30,000 calls.** Verbatim from the pricing
page: "Tier 2 — Most popular for analytics — $5/month — 30k API calls/month".

### Full tier table

**[VERIFIED]** all values from https://collegefootballdata.com/api-tiers,
fetched 2026-09-10.

| Tier | Price | Monthly calls | Adjusted metrics | Weather | Live scoreboard | Live play-by-play | GraphQL |
| --- | --- | --- | :-: | :-: | :-: | :-: | :-: |
| Free | $0 | 1,000 | — | — | — | — | — |
| Academic (`.edu` required) | $0 | 3,000 | — | — | — | — | — |
| Tier 1 | $1/mo | 5,000 | yes | yes | yes | — | — |
| **Tier 2** | **$5/mo** | **30,000** | yes | yes | yes | **yes** | — |
| Tier 3 | $10/mo | 75,000 | yes | yes | yes | yes | yes |
| Tier 4 | $15/mo | 125,000 | yes | yes | yes | yes | yes |
| Tier 5 | $20/mo | 200,000 | yes | yes | yes | yes | yes |
| Tier 6 | $30/mo | 500,000 | yes | yes | yes | yes | yes |

Every tier including Free gets: basic endpoints, historical data, team stats,
player stats, recruiting, betting lines, and advanced metrics (EPA/PPA/win
probability).

### Per-endpoint gating — verified in code, not just marketing copy

**[VERIFIED]** Exactly seven handlers carry a Patreon requirement
("Patreon checks are operation-bound middleware on the seven existing paid
handlers", ARCHITECTURE.md):

| Endpoint | Required tier | Source |
| --- | --- | --- |
| `GET /scoreboard` | 1+ | games/controller.ts `requirePatreonTier(1)` |
| `GET /games/weather` | 1+ | games/controller.ts `requirePatreonTier(1)` |
| `GET /wepa/team/season` | 1+ | wepa/controller.ts |
| `GET /wepa/players/passing` | 1+ | wepa/controller.ts |
| `GET /wepa/players/rushing` | 1+ | wepa/controller.ts |
| `GET /wepa/players/kicking` | 1+ | wepa/controller.ts |
| `GET /live/plays` | **2+** | live/controller.ts `requirePatreonTier(2)` |

The rejection message is: `Unauthorized. This endpoint requires a Patreon
subscription at Tier {n} or higher.`
Source: https://github.com/CFBD/cfb-api-v2/blob/main/src/config/middleware/patreon.ts

GraphQL (Tier 3+) is a separate service at
https://graphqldocs.collegefootballdata.com/ and offers **subscriptions**
(push instead of poll) over tables including `scoreboard`, `gamePlayerStat`,
`gameTeam`, `athlete`, `athleteTeam`, `transfer`, `playerStatCategory`,
`playerStatType`.
**[VERIFIED]** from the GraphQL docs operation list.
**[UNVERIFIED]** whether GraphQL calls are metered per query, per subscription,
or not at all. `/auth/graphql` (the token-mint endpoint) is quota-exempt, which
says nothing about the GraphQL service itself.

### Quota mechanics — verified in source

**[VERIFIED] One call = one request.** `checkCallQuotas` atomically decrements
`remaining_calls` per request. Response size and row count are irrelevant.
Source: middleware/quotas.ts.

**[VERIFIED] Quota-exempt paths:** `/scoreboard`, `/auth/graphql`, `/info`,
`/info/usage`. (`/live/plays` and `/games/weather` are commented out of the
exempt list — they *are* metered.)
Source: `ignoredPaths` in middleware/quotas.ts.

**[VERIFIED] Failed requests are refunded.** `updateQuotas` refunds the reserved
call for any non-2xx response before sending. A 400/401/429/500 does not cost a
call.
Source: middleware/quotas.ts; ARCHITECTURE.md.

**[VERIFIED] Every response carries `X-CallLimit-Remaining`.** Use it for live
budget telemetry rather than polling `/info`.
Source: middleware/quotas.ts.

**[VERIFIED] Over quota → `429 {"message":"Monthly call quota exceeded."}`.**
The pricing page adds: "Your API key may be temporarily disabled until the next
month."

**[VERIFIED] The quota pool is SHARED between CollegeFootballData and
CollegeBasketballData.** Terms: "Requests to CFBD and CBBD count against the
same shared quota pool for your subscription tier... One subscription covers
both CFBD and CBBD." The `/info` response has a `sharedPool: boolean` and
`/info/usage` reports "the authenticated user's shared CFB and CBB call pool."
Sources: https://collegefootballdata.com/terms ; OpenAPI spec `UserInfo`,
`/info/usage`.

### Rate limits (as distinct from monthly quota)

**[VERIFIED] There is no documented per-second or burst rate limit.** The
usage-and-access docs page states that the tiers page is the source for "current
access levels, limits, and pricing" and lists no throughput limit. What the code
actually enforces is:

**[VERIFIED] A per-user *concurrency* limit of 2 in-flight requests on six
specific endpoints** — `/live/plays` (across all game ids), `/plays/stats`,
`/stats/player/season`, `/stats/season/advanced`, `/stats/game/advanced`,
`/stats/player/success/game`. Over the limit → `429` +
`Retry-After: 1`, or `503` + `Retry-After: 1` if admission coordination is
unavailable. Slots release on response finish or after a 75 s safety lease.
Source: middleware/index.ts; middleware/concurrency.ts; ARCHITECTURE.md.

**[VERIFIED] A per-user *slowdown* rule on exactly one endpoint:**
`/stats/player/season` — after **15 requests in a 10 s window**, each further
request is delayed by 250 ms, capped at 2,000 ms. It delays; it does not reject.
Source: `createRateSlowdown` config in middleware/index.ts.

**[INFERRED] Sequential polling is safe; parallel fan-out is not.** A live poller
that iterates games one at a time will never hit the concurrency limit. A poller
that fires 15 `/live/plays` requests at once will get 429s on 13 of them. Cap
in-flight live requests at 2, or serialize.

### Account introspection

**[VERIFIED] `GET /info`** — "Returns the authenticated user's Patreon level and
remaining API calls." `UserInfo` = `patronLevel`, `tierName`, `monthlyLimit`,
`remainingCalls`, `usedCalls`, `resetAt`, `sharedPool`, `products[]`,
`features` (`UserFeatureAccess`: `adjustedMetrics`, `weather`, `scoreboard`,
`livePlayByPlay`, `graphQl` — all booleans).

**[VERIFIED] `GET /info/usage`** — trailing-window usage for the shared pool.
Params: `days` (default 7, max 31), `limit` (default 10, max 50), `api`
(`all` | `cfb` | `cbb`). Returns `topEndpoints[]` and `recentRequests[]`.

Both are quota-exempt, so a budget dashboard is free. `features` is the correct
runtime way to detect what the current key can do — do not hardcode tier
numbers.
Source: OpenAPI spec paths `/info`, `/info/usage`; schemas `UserInfo`,
`UserFeatureAccess`, `UserUsage`.

---

## Q9. Authentication

**[VERIFIED] Scheme: HTTP bearer.** The spec declares a single security scheme
`apiKey`: `{ type: 'http', scheme: 'bearer', description: 'CollegeFootballData
API key supplied as a bearer token.' }`.
Source: OpenAPI spec, `components.securitySchemes`.

**[VERIFIED] Header:** `Authorization: Bearer <key>`. "Data requests require the
exact `Authorization: Bearer <token>` form. Browser `Origin` and `Host` values
are not authentication."
Sources: https://api.collegefootballdata.com/authentication ; ARCHITECTURE.md.

**[VERIFIED] Every data endpoint requires a key.** Unauthenticated calls to
`/stats/categories`, `/plays/types` and `/info` all returned `401` with:
`Unauthorized. Did you forget to add "Bearer " before your key? ...`
(tested 2026-09-10 against https://api.collegefootballdata.com).

**[VERIFIED] Base URL: `https://api.collegefootballdata.com`** (the sole entry in
the spec's `servers`). `apinext.collegefootballdata.com` serves the identical
spec; treat `api.` as canonical.

**[VERIFIED] Key issuance: self-service by email.** Submit an email address at
https://collegefootballdata.com/key ; "The key is sent to your inbox after the
request completes." No credit card. Academic tier requires a `.edu` address.
Tier upgrades happen through Patreon and "take effect quickly"; downgrades apply
at the next billing cycle.

**[VERIFIED] Commercial use is permitted.** "Commercial use is permitted. Your
subscription tier determines your API usage quota, not whether you may use the
API commercially... There is no separate commercial API tier." **Redistribution
is not** — "Providing API Data itself to a third party as a standalone dataset,
bulk download, raw feed, database mirror, substitute API, or substantially
equivalent data service."
Source: https://collegefootballdata.com/terms (effective 2026-08-12).

**[INFERRED]** A fantasy app that derives scores and standings is a permitted
commercial use; an endpoint that re-serves raw CFBD rows to third parties is
not. Keep the CFBD mirror internal.

**Key handling (documented guidance, [VERIFIED]):** store in an environment
variable, never in source control, never in a URL, never in client-side
JavaScript. Server-side only.

---

## Q10. Tooling

**[VERIFIED] OpenAPI spec URL:** `https://api.collegefootballdata.com/api-docs.json`
(OpenAPI 3.0.0, `info.version` 5.27.1 as of 2026-09-10, MIT licensed,
84 paths). Also served at
`https://apinext.collegefootballdata.com/api-docs.json` (byte-identical) and
downloadable from the docs site as `cfbd-openapi`.
Legacy Swagger UI: `https://api.collegefootballdata.com/swagger`.
Sources: fetched directly; `docs-site/zudoku.config.tsx`; ARCHITECTURE.md.

**[VERIFIED] Official SDKs** (linked from CollegeFootballData.com's own nav):

| Language | Package | Repo |
| --- | --- | --- |
| Python | `pip install cfbd` | https://github.com/CFBD/cfbd-python |
| TypeScript | `pnpm add cfbd` | https://github.com/CFBD/cfbd-typescript |
| C# / .NET | `CollegeFootballData` | https://github.com/CFBD/cfbd-net |

The TypeScript client exposes typed operations plus a fetch client:
`client.setConfig({ headers: { Authorization: \`Bearer ${apiKey}\` } })` then
`getGames({ query: { year, team } })`.
Source: https://api.collegefootballdata.com/libraries/typescript

**[VERIFIED] `cfbfastR` (R) is listed by CFBD as "third-party support"**, not
official: https://cfbfastr.sportsdataverse.org/

**[VERIFIED] Type generation is viable.** The spec is generated by TSOA from
TypeScript controllers, so it is complete and mechanical: every path has a
typed 200 response referencing a named schema, every schema has `required` and
`additionalProperties: false`, and enums are declared (e.g. `SeasonType`,
`GameStatus`, `DivisionClassification`, `TransferEligibility`, `PassLocation`).
Source: ARCHITECTURE.md ("TSOA registers routes generated from
`src/**/controller.ts`"); the spec itself.

**[VERIFIED] Two documented caveats for codegen:**
1. Stat values are **strings**, not numbers, and some are composite
   (`GamePlayerStatPlayer.stat` holds `"18/27"` for `C/ATT`, `"2/3"` for `FG`).
   Generated types will say `string`. A parsing layer is mandatory.
2. `GameTeamStatsTeamStat` is an untyped `{ category: string, stat: string }`
   bag — the category vocabulary is *not* in the schema (see Q3). Generated
   types give no compile-time safety over team stat names.

**[VERIFIED] Errors:** `400` bad params/param combination, `401` unauthorized,
`404` unknown route, `429` quota exceeded or too many concurrent requests
(with `Retry-After: 1`), `503` admission unavailable (with `Retry-After: 1`),
`500` server error.
Sources: https://api.collegefootballdata.com/usage-and-access ;
`src/config/errors.ts` mapping described in ARCHITECTURE.md; the middleware
sources.

**[VERIFIED] Support channels:** GitHub https://github.com/CFBD and Discord
https://discord.gg/Eb3ex5a (both named on the data-availability page as the
route for reporting data corrections).

---

## Call-count estimates: one week of SEC + Big Ten (34 teams)

Assumptions, stated so they can be corrected:
- SEC (16) + Big Ten (18) = 34 teams. **[INFERRED]**
- ~15–20 games per week involve at least one of those 34 teams (most are
  intra-conference; some teams are on bye). **[INFERRED]**
- Conference filter values are `SEC` and `B1G`. **[UNVERIFIED]** — the exact
  abbreviation strings come from `GET /conferences`; confirm once with a key.
  The `conference` param is documented as "Conference name or abbreviation", so
  the full name is a fallback.

### Season-setup calls (once, then cached)

| Capability | Endpoint | Calls | Notes |
| --- | --- | --- | --- |
| Week calendar | `GET /calendar?year=2026` | **1** | whole season |
| Conference membership | `GET /conferences?year=2026` | **1** | resolves abbreviations |
| Team list + ids | `GET /teams?conference=SEC&year=2026` ×2 | **2** | one per conference |
| Full-season schedule | `GET /games?year=2026&conference=SEC` ×2 | **2** | byes derived from this × calendar |
| Rosters (all 34) | `GET /roster?year=2026&classification=fbs` | **1** | no conference filter exists; 1 big call beats 34 small ones |
| Play-type vocabulary | `GET /plays/types` | **1** | no params, cache forever |
| Play-stat-type vocabulary | `GET /plays/stats/types` | **1** | no params, cache forever |
| **Season setup total** | | **~9 calls** | |

Roster refresh: **[INFERRED]** re-run the 1-call FBS roster weekly to catch
mid-season roster edits → **1 call/week**.

### Weekly sync calls (post-game, the scoring source of truth)

| Capability | Endpoint | Calls/week | Notes |
| --- | --- | --- | --- |
| Schedule/score refresh | `GET /games?year=2026&week=N&conference=SEC` ×2 | **2** | `completed`, final points |
| **Player box scores (Q2)** | `GET /games/players?year=2026&week=N&conference=SEC` ×2 | **2** | all players, all games, both conferences |
| **Team box scores (Q3, DEF/ST)** | `GET /games/teams?year=2026&week=N&conference=SEC` ×2 | **2** | includes `points` → points allowed |
| Roster refresh | `GET /roster?year=2026&classification=fbs` | **1** | optional |
| **Core weekly total** | | **7 calls/week** | **~30 calls/month** |

Optional weekly add-ons:

| Capability | Endpoint | Calls/week | Notes |
| --- | --- | --- | --- |
| Safeties + FG distance + any play-derived scoring | `GET /plays?year=2026&week=N&conference=SEC` ×2 | **2** | large payloads; conference-filterable |
| Per-play player attribution | `GET /plays/stats?year=2026&week=N&gameId=…` | **~15–20** | 2,000-record cap forces per-game calls; 2-concurrent limit |
| Havoc / advanced team stats | `GET /stats/game/havoc?year=2026&week=N&conference=SEC` ×2 | **2** | |
| Kicker PAAR | `GET /wepa/players/kicking?year=2026&conference=SEC` ×2 | **2** | Tier 1+ |

**[INFERRED] Post-game-only scoring costs roughly 40–50 calls/month for
SEC + Big Ten — comfortably inside the FREE tier's 1,000.** The free tier is
sufficient for a non-live product.

### Live-scoring calls (the expensive part)

**`GET /scoreboard?conference=SEC` + `?conference=B1G` — 2 calls per poll,
QUOTA-EXEMPT. [VERIFIED]**

| Poll interval | Calls per 13-hour Saturday | Quota cost |
| --- | --- | --- |
| 60 s (matches the server's own snapshot TTL) | 1,560 | **0** |
| 30 s (wasteful — snapshot is 60 s stale anyway) | 3,120 | **0** |

**[INFERRED]** Poll `/scoreboard` at 60 s. Faster gains nothing, since the
server-side snapshot only refreshes every 60 s. It is free, so it should be the
backbone of the live pipeline: use it to detect which games are in progress and
to drive score/clock UI, and only spend metered calls on games that are live.

**`GET /live/plays?gameId=` — 1 call per game per poll, METERED, Tier 2+,
max 2 concurrent. [VERIFIED]**

**[INFERRED]** With ~15 SEC/B1G games per Saturday, each ~3.5 hours (210 min):

| Poll interval | Calls/game | Calls/Saturday (15 games) | Calls/month (4.3 wks) | Fits in Tier 2 (30k)? |
| --- | --- | --- | --- | --- |
| 120 s | 105 | 1,575 | ~6,800 | yes, comfortably |
| **60 s** | **210** | **3,150** | **~13,500** | **yes** |
| 30 s | 420 | 6,300 | ~27,100 | barely — ~90% of quota |
| 15 s | 840 | 12,600 | ~54,200 | **no** — needs Tier 4 ($15) |
| 5 s (the cache floor) | 2,520 | 37,800 | ~162,600 | no — needs Tier 5 ($20) |

Add the ~30 core weekly calls and any weekday backfill on top.

**[INFERRED] Recommendation: Tier 2 ($5/month) with 60-second `/live/plays`
polling.** That lands at roughly 45% of the 30,000 monthly allowance, leaving
headroom for backfills, retries, development, and the shared CFB/CBB pool. Going
below a 30 s interval requires Tier 4 or higher.

**[VERIFIED] Serialize the live poller.** 15 games cannot be polled in parallel:
the concurrency cap is 2 in-flight `/live/plays` requests per user. A sequential
sweep of 15 games at ~200 ms each is ~3 s, well inside a 60 s cycle.

**[INFERRED] Failed calls are free**, so retry-on-429/503 with the advertised
`Retry-After: 1` costs nothing but time.

---

## Open questions requiring an API key

Ordered by how much design depends on them.

1. **Does `GET /games/players` populate during an in-progress game?** If yes,
   near-live scoring needs no `playText` parsing at all and the whole live
   design collapses to "poll `/games/players` by conference every N minutes" —
   2 calls per poll instead of 15. This is the highest-value test.
2. **What is the exact `category` vocabulary on `GET /games/teams`?** The DEF/ST
   scoring rules cannot be written without it (Q3).
3. **What are the exact `playerStatType` names per category on
   `GET /games/players`,** especially in `kicking` (is there a `LONG`?) and
   `defensive`?
4. **What is the real post-game latency** from final whistle to complete
   `/games/players` rows?
5. **Are the conference filter values `SEC` and `B1G`?** One call to
   `GET /conferences` settles it.
6. **How is GraphQL (Tier 3+) metered,** and would a `scoreboard` /
   `gamePlayerStat` subscription replace polling entirely? If subscriptions are
   not per-message metered, Tier 3 at $10 could be cheaper than Tier 2 polling.
7. **Does `/live/plays` `playText` reliably contain full player names** in a
   parseable, consistent format across all games?
