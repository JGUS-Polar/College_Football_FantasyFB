# The fantasy Week is a date range, not a provider week number

**Status:** accepted
**Date:** 2026-09-11
**Ticket:** [#7 What is a fantasy week? Byes and lineup locks](https://github.com/JGUS-Polar/College_Football_FantasyFB/issues/7)
**Evidence:** [2026 schedule shape](../research/fantasy-week-schedule-shape.md)

A **Week** owns an explicit `startsAt`/`endsAt` date range and is the unit of fantasy competition. A **Game belongs to the Week its kickoff falls inside.** CFBD's own week number is stored alongside as `cfbdWeek`, a join key used only to fetch stats — it is never the Week's identity, and never the thing a Matchup, Lineup or StatLine points at.

**LineupSlots lock individually, one hour before their Game kicks off.** Lock is a property of the slot, not of the Lineup or the Week.

## Considered options

**Adopt CFBD's week number as the Week.** Free, and every stat endpoint is keyed by `year + week` so the join is trivial. Rejected on three counts, all confirmed against the real 2026 SEC/B1G schedule:

- **CFBD week 1 2026 spans eight days and two Saturdays** (Aug 29 and Sep 5), because it absorbs the games other providers call "week 0". Inside it, **USC plays twice** — San José State on Aug 29 and Fresno State on Sep 4. A USC player would score two games in one fantasy week and the "opponent" column would have two answers.
- **The week count is not stable across seasons.** 2025 ran 15 regular-season weeks; 2026 currently has 13. Week numbers are not comparable year to year, so anything keyed on them is only meaningful within one season.
- **A postponed game silently migrates.** If CFBD renumbers a moved game, its points move to a different fantasy week with no event we can observe.

**Adopt CFBD's number but special-case week 1.** Rejected as the same decision with a patch. The anomaly is not a bug in CFBD — an eight-day opening week is a real feature of the college calendar, and it will recur in some form every season. Encoding it as a branch in code rather than a row in a table means re-discovering it annually.

## Consequences

**"At most one Game per Player per Week" becomes an assertable invariant.** It was the thing option A quietly broke; under a date range it is checkable at ingestion, and a violation is an alert rather than a silently doubled score. Week 1 is split into two Weeks as *data*, and USC plays once in each.

**Postponement stops being a special case.** A Game scores in the Week containing its kickoff — that is the same rule that governs every normal game, so the hurricane case needs no separate machinery. A game moved out of its Week carries its points to the Week it lands in, and the Manager who started that player in the original Week gets nothing for them. The alternative — holding the original Matchup open until the makeup is played — was rejected because it contradicts "a Matchup freezes when the Week closes" and would leave standings and playoff seeding unresolved for weeks. A cancelled game has no kickoff, so it has no Week, so it never scores. A weather-shortened game scores exactly as played.

**Lock composes with this rather than fighting it.** Because a slot locks off *its own Game*, a Game that moves out of the Week leaves its Player with no Game in that Week — and a slot whose Player has no Game never locks, so the slot simply reopens and the Manager can replace them. No exploit is created: anything worth swapping in has already locked at its own kickoff minus one hour. A Manager is only stranded if the cancellation lands inside that final hour.

**Kickoff times are not trustworthy at rest, so the schedule must be re-synced weekly.** As of 2026-09-11, **134 of 252 games (53%) carry `startTimeTBD: true`, and every one of them has a `startDate` of midnight ET on its Saturday.** A lock keyed naively off `startDate` would freeze half the season's lineups at 11pm the night before, hours before a mid-afternoon kickoff. TBD resolves reliably about a week out, so the midnight placeholder is retained only as a *fail-safe backstop* — locking early rather than failing open — and is rendered as "time TBD", never as a time. Pulling the schedule once at season setup is therefore a correctness bug, not merely staleness. This is binding on [#17](https://github.com/JGUS-Polar/College_Football_FantasyFB/issues/17).

**Absence of a Game has three meanings, and the UI must distinguish them.** A CollegeTeam with no Game in a Week is on a **bye** only if that Week's schedule is published; otherwise it is **unscheduled**; and if its Game moved, it is **postponed**. CFBD's 2026 data currently stops at week 13 — conference championship week is not yet published — so a naive derivation would today tell every Manager their entire roster is idle in week 14. A per-season `scheduleKnownThroughWeek` high-water mark gates the distinction.

**The season ends at the last full slate; championship week never scores.** Conference championships are `seasonType: regular` — not postseason, as one might assume — and involve four of the 34 teams. They are excluded structurally rather than by week number, which shifts annually: **a Week is scoreable only if at least half the Player Universe (17 of 34 CollegeTeams) has a Game.** The margin is wide in both directions — championship week has 4, the worst bye week has 24, a normal week has 34 — and the rule survives realignment changing the team count. The result is stored as `finalScoringWeek` and is human-overridable. Everything in `seasonType: postseason` (all bowls and the entire CFP collapse into a single `week 1` bucket) is never scored, confirming rather than inheriting the assumption recorded in [#6](https://github.com/JGUS-Polar/College_Football_FantasyFB/issues/6).
