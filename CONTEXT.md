# College Fantasy Football

A public, Yahoo/ESPN-style fantasy football platform for SEC and Big Ten college football: public league creation and joining, snake draft, head-to-head weekly matchups, and playoffs. Redraft only — every season starts from zero.

This file is a glossary and nothing else. Architecture lives in `docs/adr/`; the design spec lives alongside it.

## Language

### College football — the ingested world

**CollegeTeam**:
A real college football program (Alabama, Michigan). The SEC's 16 and the Big Ten's 18 are the only ones in scope.
_Avoid_: Team (ambiguous — see Franchise), School, Program

**Game**:
One real football game between two CollegeTeams.
_Avoid_: Matchup (that's the fantasy pairing), Contest

**Week**:
Which week of the season it is — the week number a Game belongs to. The fantasy season runs on regular-season weeks only; bowl and playoff games are never scored.
_Avoid_: Scoring period, game week, matchup week

**Bye**:
A CollegeTeam having no Game in a given Week. There is no source field for this; it is the absence of a Game.
_Avoid_: Open week, off week

**StatLine**:
One Player's raw, unscored production in one Game — the authoritative fact everything else is derived from. A Player of kind `team_defense` has a StatLine too, with its own stat vocabulary.
_Avoid_: Box score, stats, performance

### Players

**Player**:
Anything that can occupy a roster spot. Two kinds: an **athlete** (a human), or a **team_defense** (one CollegeTeam's defense, which is drafted, dropped, traded, and started exactly like an athlete). Identity only, stable forever — a transfer does not create a new Player.
_Avoid_: Athlete or Person as the umbrella term (a team defense is neither); Asset; Rosterable

**PlayerSeason**:
One Player's facts for one season: their CollegeTeam, position, jersey, and class. College-side facts are season-scoped, never current-valued — a Player's 2026 CollegeTeam is a different fact from their 2027 one.
_Avoid_: Roster entry (that's fantasy), PlayerTeam, stint

**Player Universe**:
The set of PlayerSeasons for a given season — every player whose production is scored. Bounded by SEC and Big Ten rosters, but **all** of their Games count, including non-conference and FCS opponents. A player who transfers out of the two conferences leaves the Universe and simply stops scoring.
_Avoid_: Player pool (that's the draft pool, a narrower thing)

### Leagues and people

**User**:
An account — one human, one login. A User may be in many Leagues.
_Avoid_: Player, Manager, Owner, Member

**League**:
A durable group of Users competing across one or more seasons. Holds only what survives a year: name, commissioner, membership, and discovery settings.
_Avoid_: Group, Room

**LeagueSeason**:
One League playing one season. Everything year-specific belongs here — the ScoringRuleset, RosterSettings, draft, schedule, and the Franchises themselves. This is where redraft is expressed: nothing about a roster crosses a LeagueSeason boundary.
_Avoid_: Season (that's the calendar year), League year

**LeagueMembership**:
A User's place in a League, carrying their role: `commissioner` or `manager`.
_Avoid_: Member, Participant, Invite

**Commissioner**:
The LeagueMembership role that can change settings, act on another Franchise's behalf, and overrule outcomes.
_Avoid_: Admin, Owner

**Franchise**:
One Manager's fantasy team within one LeagueSeason — its name, logo, Roster, and record. Exactly one per User per League.
_Avoid_: Team (reserved for CollegeTeam), Roster (that's its contents), Squad

### Rosters and lineups

**Roster**:
The set of Players a Franchise owns right now. It has no week dimension; it is the current state of ownership.
_Avoid_: Squad, Team, roster slots

**RosterSettings**:
A LeagueSeason's configuration of what a Roster and Lineup look like: which LineupSlots exist and how deep the bench goes.
_Avoid_: League settings (too broad), roster rules

**Lineup**:
The Players a Franchise starts in one Week. It freezes when the Week locks and is never recomputed, so it stays truthful about who was actually started.
_Avoid_: Starters, active roster, roster (a Lineup is chosen *from* a Roster)

**LineupSlot**:
One position in a Lineup — `QB`, `RB1`, `FLEX`, `DEF`, and so on. A team defense occupies a single `DEF` slot.
_Avoid_: RosterSlot (a slot is a lineup concept, never a roster one), position (that's the Player's attribute)

**Bench**:
A Player a Franchise owns who is not in that Week's Lineup. Derived, never stored — the Roster and the Lineup are the only two facts.
_Avoid_: Reserve, inactive

**Free agent**:
A Player in the season's Player Universe who is on no Roster in this LeagueSeason. A derived state, not a thing that is recorded.
_Avoid_: Waiver wire as an entity (it is a view of free agents), Available player

### Scoring

**ScoringRuleset**:
A LeagueSeason's per-stat scoring configuration, immutable and versioned — an edit produces a new version rather than changing one. It locks when the draft completes; any later change applies forward only, and past Weeks keep the version they scored under.
_Avoid_: Scoring settings, rules, scoring system, preset

**FantasyPoints**:
A StatLine scored through one version of a ScoringRuleset. The same Game yields different FantasyPoints in leagues whose rulesets differ, and identical FantasyPoints in leagues that share one — the ruleset version, not the league, is what a score belongs to.
_Avoid_: Points (ambiguous with a Game's real score), score, fantasy score

### Competition

**Matchup**:
One Week's head-to-head pairing of two Franchises in a LeagueSeason. It freezes its final scores and result when the Week closes, so a completed week cannot be rewritten.
_Avoid_: Game (that's the real football game), Contest, Fixture

**Standings**:
A LeagueSeason's ordering of Franchises, derived from its Matchups. Never stored as a thing to be edited.
_Avoid_: Table, leaderboard, rankings

### Transactions

**Transaction**:
An append-only record of one change of ownership — `draft`, `add`, `drop`, `waiver_award`, `trade`, or `commissioner_adjustment`. The complete ledger is the only source of truth for who owns whom; a Roster is a fold over it.
_Avoid_: Move, activity, roster change, history

**DraftPick**:
One selection in a LeagueSeason's draft — its slot, round, order, and timer. The resulting change of ownership is a Transaction; the pick is the process around it.
_Avoid_: Pick as a verb-noun, selection, draft slot

**WaiverClaim**:
One Franchise's request for a free agent through the waiver process, with its priority or bid, pending until awarded or denied.
_Avoid_: Waiver, claim, bid

**TradeProposal**:
One offer of Players between Franchises, with its own lifecycle — offered, then accepted, rejected, or vetoed. Distinct from the Transaction it produces on acceptance, because "was it offered" and "did it go through" are different questions.
_Avoid_: Trade (conflates the negotiation with the ownership move)
