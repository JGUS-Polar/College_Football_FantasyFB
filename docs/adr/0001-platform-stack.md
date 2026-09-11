# Platform stack: Supabase + Vercel + Resend, on free tiers

**Status:** accepted
**Date:** 2026-09-10
**Ticket:** [#5 Lock the platform stack](https://github.com/JGUS-Polar/College_Football_FantasyFB/issues/5)
**Research:** [Platform comparison](../research/platform-comparison.md) ([#4](https://github.com/JGUS-Polar/College_Football_FantasyFB/issues/4))

The app runs on **Next.js / Vercel (Hobby), Supabase (Free), and Resend (Free)** — database, auth, realtime, storage and scheduled jobs all from Supabase; Vercel hosts the app; Resend sends transactional email. Data access is **Drizzle ORM** over the Supavisor transaction pooler for all CRUD, with `supabase-js` reserved for Auth, Realtime and Storage. The binding requirement was a **free path to a sub-minute scheduled CFBD sync**, and Supabase's `pg_cron` is the only one that exists: Vercel Hobby cron is daily-only, and Neon Free cannot keep compute awake for `pg_cron` at all.

## Considered options

The comparison evaluated four stacks. Three were eliminated by the free-tier constraint rather than on merit:

- **Neon + Auth.js, and Neon-via-Vercel + Clerk** — eliminated structurally. Neon Free allows 100 CU-hours/month with a 5-minute autosuspend that cannot be disabled, and Neon's own docs state `pg_cron` jobs only run while compute is active. There is no free Neon path to a scheduled sync. Both options also require a paid realtime vendor (Ably, $29/mo) once past 200 concurrent connections.
- **Convex** — a genuinely better draft room (reactive queries would erase most realtime bookkeeping) and a worse scoring engine (fantasy scoring is relational and aggregate-heavy; Convex is not SQL). Decisive factor: leaving Convex is a rewrite, not a migration.
- **Clerk for auth** — the only option that removes the transactional email provider from the stack entirely, and its per-MAU pricing is *not* a valid objection (50,000 free monthly users since Feb 2026). Rejected because removing the "Secured by Clerk" badge costs $25/mo, and because auth is the one surface that would otherwise live outside the design system.

Worth recording honestly: **Neon is the better database on the merits** — included point-in-time recovery, cheaper branching, three times the extension coverage, a higher pooled-connection ceiling. Supabase is chosen for what is bolted around it, not for its Postgres. If the bolted-on parts stop earning their keep, the database was never the reason to stay.

## Consequences

Five constraints follow from the free tier and are binding on downstream design.

**No backups exist.** Automated daily backups are a Pro feature; Supabase Free has none. A nightly `pg_dump` of the league-owned tables (leagues, teams, rosters, draft picks, transactions, matchups, chat) into Supabase Storage is therefore the entire disaster-recovery story, not a supplement to one. It runs on the same `pg_cron` → Edge Function path as the CFBD sync. Point-in-time recovery was rejected outright: $100/month per 7 days of retention is more than twice the projected all-in launch cost.

**The database is capped at 500 MB, and exceeding it makes it read-only** — not throttled, read-only, which mid-season means no lineup changes, waivers or chat. CFBD player-week stats alone were estimated at 200–300 MB, so this wall is close. Postgres therefore holds the current season plus derived stat lines only; **raw CFBD payloads go to Storage** (a separate 1 GB allowance) as compressed JSON, which preserves the ability to reprocess a mapping bug without re-spending API calls; historical seasons pulled for DEF calibration are processed and discarded rather than retained.

**Authorization is application-layer, and RLS is not load-bearing.** Drizzle connects with a service-role credential that bypasses row-level security entirely, so the common advice to "keep authz in the app and use RLS as defence-in-depth" is self-contradictory once an ORM is the CRUD path — RLS is simply off for 90% of access. The gap is deliberate and must be closed structurally rather than by per-query vigilance: league-scoped data access goes through a layer where a query cannot be constructed without the requesting user, so the type system enforces what RLS would have. RLS is still enabled deny-by-default on anything `supabase-js` touches, Storage especially.

**Realtime is Broadcast, never Postgres Changes.** Supabase's own docs note Postgres Changes authorizes every event against every subscriber individually, caps out near 64 changes/second, and should be abandoned for Broadcast beyond ~3,000 subscribers. Broadcast costs the same and keeps scaling; retrofitting a live draft room from one to the other is expensive. The free ceiling is **200 concurrent connections ≈ 16 simultaneous draft rooms**, which the draft room must degrade against legibly rather than throw on. Scores are **polled from a cached route, not pushed** — pushing per-play updates multiplies message volume by the entire active user base.

**Two remote projects exist.** Local development runs the full stack in Docker via the Supabase CLI, which does not count against that. Until real users exist, the two slots are spent as one production project with Vercel preview deploys pointing at it; the first stranger's league in the database is the trigger to stand up a separate staging project and repoint previews. Migrations are Drizzle Kit, committed to the repo, so any environment is reproducible from source.

## Known risks accepted

- **Vercel Hobby is licensed for non-commercial, personal use.** The app is free-to-play with no ads and no paid entry, so this is defensible today. The first revenue of any kind makes Vercel Pro mandatory regardless of usage.
- **Free Supabase projects pause after 7 days idle.** Harmless during development and in-season; it will pause every February–July off-season and need a manual unpause.
- **Resend's free tier is 3,000 emails/month and 100/day.** The daily cap is the tighter one and is low enough to rule email out as a real-time notification channel.
- **All pricing was retrieved 2026-09-10.** Clerk moved its free tier fivefold in February 2026 and Vercel Postgres ceased to exist as a product in December 2024. Re-verify before provisioning if more than ~3 months pass.
