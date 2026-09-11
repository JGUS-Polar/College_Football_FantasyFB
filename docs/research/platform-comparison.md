# Platform Comparison: Database + Auth + Realtime

**Research ticket:** [#4](https://github.com/JGUS-Polar/College_Football_FantasyFB/issues/4)
**All pricing and limits retrieved:** 2026-09-10. Pricing on all four vendors changes frequently — re-verify before signing anything.
**Legend:** **[V]** = VERIFIED against a primary source (linked). **[I]** = INFERRED — my reasoning or arithmetic on top of verified numbers, not a vendor statement.

---

## TL;DR

**Recommendation: Supabase + Vercel + Resend.** The dev's leaning survives contact with the facts, but *not* for the reason usually given, and with one correction: **"all-in-one" is a myth for every option here — you will run a separate transactional email provider no matter which stack you pick.** Supabase wins on a different axis than "fewest vendors": it is the only candidate where the **live draft room, in-league chat, sub-minute cron for CFBD sync, file storage, and Postgres are one bill and one mental model**, and where the realtime tier is genuinely free at this app's scale.

Three findings that cut against the naive version of the Supabase leaning:

1. **Supabase does not send your verification emails.** The built-in email service is rate-limited to **2 emails per hour** and will only deliver to members of your own Supabase org. A custom SMTP provider (Resend/Postmark) is *mandatory* for production. **[V]**
2. **Supabase's PITR is a $100/month add-on.** Neon includes point-in-time restore in the base plan. If backup/restore fidelity is a hard requirement, Supabase is the *expensive* option, not the cheap one. **[V]**
3. **Clerk's free tier is now 50,000 monthly retained users** (raised from 10,000 in Feb 2026), which defuses the "per-MAU pricing punishes success" worry at every scale in this ticket. The per-MAU argument against Clerk is out of date. **[V]**

---

## The four options as actually configured

Note upfront: **"Vercel Postgres" no longer exists as a product.** Vercel migrated all Vercel Postgres stores to Neon in December 2024, and Postgres is now provisioned through the Vercel Marketplace — the Vercel-native Neon integration. **[V]** ([Neon transition guide](https://neon.com/docs/guides/vercel-postgres-transition-guide), [Vercel changelog](https://vercel.com/changelog/neon-now-available-on-vercel-marketplace)) So option 3 in the ticket is really **"Neon-billed-through-Vercel + Clerk"**, and options 2 and 3 share a database engine. That collapses the comparison more than the ticket assumed.

| | **A. Supabase** | **B. Neon + Auth.js** | **C. Vercel(Neon) + Clerk** | **D. Convex** |
|---|---|---|---|---|
| Database | Supabase Postgres | Neon | Neon (via Vercel Marketplace) | Convex documents (not SQL) |
| Auth | Supabase Auth | Auth.js Credentials (hand-rolled) | Clerk | Better Auth / Clerk bolt-on |
| Realtime | Supabase Realtime | Ably or Pusher | Ably or Pusher | Native (core model) |
| Storage | Supabase Storage | Vercel Blob / S3 / R2 | Vercel Blob | Convex file storage |
| Email | **Resend required** | **Resend required** | Clerk sends them | **Resend required** |
| Cron | pg_cron (any interval) | Vercel Cron | Vercel Cron | Convex scheduled functions |
| Vendors to manage | 3 | 5 | 4 | 4 |

---

## Axis 1 — Postgres fidelity

| | Supabase | Neon (both B and C) | Convex |
|---|---|---|---|
| Real Postgres? | Yes, standard Postgres | Postgres compute on a custom storage engine; wire- and SQL-compatible | **No SQL at all** |
| Extensions | "over 50" pre-configured, more via database.dev **[V]** ([docs](https://supabase.com/docs/guides/database/extensions)) | "over 150" across PG14–PG18 **[V]** ([docs](https://neon.com/docs/extensions/pg-extensions)) | n/a |
| `pg_cron` | Yes — see Axis 10 | Yes (1.6), **but jobs only run while compute is active**; Neon recommends 24/7 compute or disabling scale-to-zero **[V]** | Native scheduler |
| Not supported | — | `sslinfo`, `file_fdw`, `plv8`; `pg_search`/`pg_ivm` deprecated **[V]** | — |
| Branching | Pro plan and above; no fixed fee, ~**$0.01344/hour** on default Micro compute **[V]** ([docs](https://supabase.com/docs/guides/platform/manage-your-usage/branching)) | Free: 10 branches/project; Launch 10, Scale 25 included, then **$1.50/branch-month** **[V]** ([pricing](https://neon.com/pricing)) | n/a |
| Point-in-time recovery | **$100/month per 7 days of retention**, Pro+ only, and requires at least the Small compute add-on **[V]** ([docs](https://supabase.com/docs/guides/platform/manage-your-usage/point-in-time-recovery)) | Included: Free 6h, paid default 1 day, configurable to 7 days (Launch) / 30 days (Scale) **[V]** ([docs](https://neon.com/docs/introduction/point-in-time-restore)) | Included |

**Read:** Neon is the better *database*. Branching is cheaper and more generous, PITR is included rather than a $100 tollgate, and extension coverage is 3x wider. Supabase's Postgres is perfectly good but it is not where Supabase wins.

**Practical note for this app [I]:** a fantasy league app's disaster-recovery need is real but modest — daily backups (included on Supabase Pro) plus the fact that CFBD data is re-syncable from source means the $100 PITR add-on is probably not needed at launch. Draft results and roster moves are the irreplaceable data; those are small and could be additionally exported nightly for pennies. This softens but does not erase the finding.

---

## Axis 2 — Auth: email/password + verification + Google OAuth

**The single most commonly-missed item in this whole comparison: who actually sends the verification email.**

### Supabase Auth
- Email/password with email confirmation is supported out of the box, and **confirmation is enabled by default on hosted projects**. Built-in `resetPasswordForEmail()` with user-enumeration protection. Google OAuth is a config toggle. **[V]** ([docs](https://supabase.com/docs/guides/auth/passwords))
- **But**: the default email service is *explicitly not for production*. Verbatim: rate limit of **"2 messages per hour"**, delivery only to "pre-authorized addresses" — i.e. members of your project's organization team; everyone else gets an `Email address not authorized` error. Supabase describes it as for "toy projects, demos or any non-mission-critical application." **[V]** ([docs](https://supabase.com/docs/guides/auth/auth-smtp))
- With custom SMTP configured, the initial limit rises to **30 messages/hour**, adjustable in the dashboard. **[V]**
- **Verdict: Resend (or Postmark) is mandatory, not optional.** Free tier: 3,000 emails/month, 100/day, custom domain not required on free. **[V]** ([Resend pricing](https://resend.com/pricing))

### Auth.js (NextAuth) Credentials provider
- Auth.js supports email/password only in the sense that the Credentials provider "forward[s] any credentials inserted into the login form" to *your* code. The docs actively discourage it: *"if possible, we recommend a more modern and secure authentication mechanism."* **[V]** ([docs](https://authjs.dev/getting-started/authentication/credentials))
- Verbatim on what you own: *"the Credentials provider does not persist data in the database... you just have to provide the necessary logic, eg. to encrypt passwords, add rate-limiting, add password reset functionality"* and *"Your own logic for dealing with plaintext password strings; be careful!"* **[V]**
- The Auth.js docs **do not cover user registration or email verification at all**. **[V]**
- **Verdict [I]: you are writing an auth system.** Password hashing, verification-token issuance and expiry, resend-throttling, reset flow, timing-safe comparison, enumeration protection, session invalidation on password change. That is a genuine 1–2 week build plus a permanent security surface you own. For a public app taking real passwords, this is the most expensive line item in this document and it does not appear on any invoice.
- **Neon Auth changes this option.** Neon now ships "Neon Auth (Managed Better Auth)" — users/sessions stored in a `neon_auth` schema in your own database, email/password and Google OAuth supported, **60,000 MAU free / 1M MAU on paid plans**. But it is explicitly **in Beta**. **[V]** ([docs](https://neon.com/docs/neon-auth/overview)) Docs do not state who sends verification email **[V — absence]**, so assume you still bring Resend **[I]**.

### Clerk
- Email/password with verification code *or* verification link out of the box; both expire in 10 minutes. Google OAuth built in. **[V]** ([docs](https://clerk.com/docs/guides/configure/auth-strategies/sign-up-sign-in-options))
- **Clerk sends the emails itself** via its own ESP (currently SendGrid). You can toggle "Delivered by Clerk" off per-template and take delivery yourself via the `emails.created` webhook, but you do not have to. **[V]** ([docs](https://clerk.com/docs/guides/customizing-clerk/email-sms-templates))
- **This is Clerk's genuine, under-rated advantage: it is the only option in this comparison that removes the email provider from your stack entirely.** **[V]**
- Custom domain works on the free plan; removing the "Secured by Clerk" badge requires Pro. **[V]** ([pricing](https://clerk.com/pricing))

**Axis 2 ranking:** Clerk > Supabase >> Auth.js. Clerk is the only "all-in-one" *for auth specifically*. Supabase is close but drags Resend in. Auth.js is not competitive for a public consumer app.

---

## Axis 3 — Realtime (the crux)

The draft room is the requirement that actually decides this. Vercel functions cannot hold long-lived WebSocket connections, so realtime **must** be someone else's service in every option.

**Workload [I]:** 12 concurrent users per draft room. Several rooms concurrent. A draft is ~200 picks over ~2 hours, plus timer ticks, presence, and chat. Counting fan-out (Supabase defines an event as "a WebSocket message delivered to, or sent from a client" **[V]** ([docs](https://supabase.com/docs/guides/realtime/limits)), so fan-out counting is the safe assumption **[I]**), one draft ≈ **6,000 messages**, and a league's in-season chat ≈ **10,000 messages** over 17 weeks. Call it **~16,000 realtime messages per league per season**, ≈ 3,200/month.

### Free tier and first paid tier, side by side

| Provider | Free: concurrent conns | Free: throughput | First paid tier | Paid: conns | Paid: throughput |
|---|---|---|---|---|---|
| **Supabase Realtime** | **200** | 100 msg/s; **2M messages/month** included | Pro $25/mo | **500** (10,000 with spend cap off) | 500 msg/s (2,500 uncapped); **5M msgs/month**, then **$2.50/M**; conns **$10 per 1,000** |
| **Ably** | **200** | 500 msg/s; **6M messages/month** | Standard **$29/mo** + usage | 10,000 | 2,500 msg/s; **$2.50/M msgs**, $1.00/M connection-minutes, $0.25/GiB |
| **Pusher Channels** | **100** | 200k messages/day | Startup **$49/mo** | 500 | 1M messages/mo |
| **Convex** | 1,000 concurrent sessions, 16 concurrent queries | 1M function calls | Pro $25/dev/mo | 10,000 sessions, 256 queries | 25M function calls |

**[V]** — [Supabase quotas](https://supabase.com/docs/guides/realtime/quotas), [Supabase pricing](https://supabase.com/pricing), [Ably pricing](https://ably.com/pricing), [Pusher pricing](https://pusher.com/channels/pricing/), [Convex pricing](https://www.convex.dev/pricing).

**What this means [I]:**
- **200 free concurrent connections = ~16 simultaneous draft rooms.** That covers the entire first season of a hobby launch on Supabase's or Ably's free tier. Pusher's 100-connection free tier only covers 8 rooms and is the weakest.
- The binding constraint is **peak concurrency during draft week**, not monthly messages. At 10,000 users (833 leagues) drafting across a two-week August window, a bad evening could put 1,000–2,000 users in draft rooms simultaneously. Supabase Pro *with the spend cap on* caps at 500 concurrent connections and would **hard-fail your draft night**. You must disable the spend cap (raising the ceiling to 10,000) and accept $10 per additional 1,000 connections. **This is a real operational trap and belongs in a runbook.**
- Message volume is a non-issue everywhere: 833 leagues × 3,200/mo ≈ 2.7M messages/month, inside Supabase Pro's 5M and inside Ably's free 6M.

### One Supabase-specific design warning **[V]**
Supabase's own docs: Postgres Changes "authorizes every event against each subscriber individually... throughput scales with the number of subscribers, not the write rate," processing is single-threaded to preserve ordering, and *"If you expect more than ~3,000 concurrent subscribers on the same changes, use Broadcast to stream database changes instead."* Benchmarks: max 64 changes/second, and with RLS enabled ~3,000–4,000 total messages/second regardless of instance size. ([docs](https://supabase.com/docs/guides/realtime/postgres-changes))

**Implication [I]:** build the draft room on **Broadcast**, not on Postgres Changes. At 12 subscribers per room this is comfortably inside either mechanism, but Broadcast is the one that keeps scaling and costs the same. Write it that way from day one; retrofitting a draft room from Postgres Changes to Broadcast late is unpleasant.

**Near-live score polling [I]:** do *not* push per-play scoring over realtime to every user — that multiplies your message count by your entire active user base. Poll a cached scores endpoint (Next.js route with a short revalidate) on a 30–60s client interval, and reserve realtime for the draft room and chat. This keeps every provider's realtime bill near zero and is why the message-volume columns above stay small.

---

## Axis 4 — Serverless connection pooling (the classic Vercel + Postgres failure mode)

The failure: each serverless function invocation opens its own Postgres connection; a traffic spike opens hundreds; Postgres hits `max_connections` and starts refusing everything, including your healthy traffic. Both providers have a real answer, but they are different answers.

| | Supabase | Neon |
|---|---|---|
| Mechanism | **Supavisor** — Postgres-protocol pooler | **PgBouncer** — transaction-mode pooler |
| Transaction mode | Port **6543**, "does not support prepared statements", **recommended for serverless and edge functions** **[V]** ([docs](https://supabase.com/docs/guides/database/connecting-to-postgres)) | Pooled connection string with **`-pooler`** suffix; "up to **10,000** concurrent connections" **[V]** ([docs](https://neon.com/docs/connect/connection-pooling)) |
| Session mode | Port 5432, keeps session state, for persistent backends | Direct (unpooled) endpoint, for migrations |
| Backend ceiling | Varies by compute add-on | Active transactions capped at 90% of `max_connections`, "ranging from 97 to 4,000 connections depending on RAM" **[V]** |
| App-side guidance | "Create the client once at module scope, not per request"; **set pool size to 1 per warm instance** **[V]** | Use pooled string in functions; unpooled for migrations |
| HTTP escape hatch | PostgREST — every query can go over plain HTTP, no connection at all | Neon serverless driver — SQL over HTTP/WebSocket |

**Read [I]:** This is close to a tie and neither provider will bite you if you follow the documented pattern. Two nuances worth knowing:

- **Neon's raw pooled ceiling (10,000) is higher than Supabase's**, and Neon's serverless driver over HTTP sidesteps the connection model entirely for one-shot queries — arguably the cleanest answer to the serverless problem in the whole comparison.
- **Supabase's PostgREST is the sleeper advantage for this app.** If the Next.js app talks to Supabase through `supabase-js` rather than a Postgres client, there is no connection pool to exhaust at all, because there is no Postgres connection from Vercel — it is HTTP to PostgREST. The classic failure mode is not mitigated, it is *absent*. You only re-enter connection-pool territory when you use an ORM (Drizzle/Prisma) against the Postgres port. **That is a genuine architectural decision to make deliberately, early.**
- **Gotcha, both:** transaction-mode pooling breaks prepared statements. Prisma and Drizzle need explicit configuration for this. Budget an afternoon.

---

## Axis 5 — File storage (avatars, team logos)

| | Supabase Storage | Vercel Blob | Neon |
|---|---|---|---|
| Included free | **1 GB** (Free), **100 GB** (Pro) then $0.0213/GB **[V]** | 5 GB storage, 100K simple ops, 10K advanced ops, 100 GB transfer (from Pro pricing example) **[V]** ([docs](https://vercel.com/docs/vercel-blob/usage-and-pricing)) | **None — no file storage product** |
| Access control | **RLS policies + custom policies** **[V]** ([docs](https://supabase.com/docs/guides/storage)) | Public or private stores; private delivery streams through a Function (and costs more transfer) **[V]** | n/a |
| Image transforms | **Built-in** resize/compress/transform on the fly **[V]** | Via Vercel Image Optimization (separately metered: 5K transforms free) **[V]** | n/a |
| S3-compatible | **Yes** **[V]** | No | n/a |
| CDN | 285+ cities **[V]** | Vercel CDN **[V]** |

**Read:** Clear Supabase win, and it is not close. Avatars and logos are exactly the "user-uploaded, must be authorization-checked, must be resized" case that Supabase Storage is built for. RLS on the same policy engine as your tables means one mental model. With Vercel Blob you hand-roll the authorization check and pay Function transfer to serve private files, or make everything public and accept that.

**Sizing [I]:** 10,000 avatars + 833 league logos at ~200 KB each ≈ **2 GB**. Free everywhere on a paid tier; exceeds Supabase's 1 GB free tier at around 5,000 users.

---

## Axis 6 — Pricing at 0 / 100 / 1,000 / 10,000 users

### Assumptions (all **[I]**, stated so you can argue with them)
- 12 users per league → 100 users ≈ 8 leagues, 1,000 ≈ 83, 10,000 ≈ 833.
- Realtime: ~16,000 messages per league per season; peak concurrency = ~20% of leagues drafting in the same evening window at the 10,000-user scale.
- Database: CFBD player-week stats are roughly fixed (~200–300 MB); league/roster/transaction data scales with users. ~0.5 GB at 100 users, ~1 GB at 1,000, ~4 GB at 10,000.
- Score polling is client-poll against a cached endpoint, not realtime push.
- **Vercel Pro ($20/mo) is assumed from 100 users onward in every column** for two independent reasons: (a) Hobby cron runs **once per day only** and (b) Hobby is restricted to **non-commercial, personal use**. See Axes 7 and 10.
- One developer. No SAML, no B2B add-ons.

### The table (USD/month, retrieved 2026-09-10)

| Users | **A. Supabase** | **B. Neon + Auth.js + Ably** | **C. Neon/Vercel + Clerk + Ably** | **D. Convex** |
|---|---|---|---|---|
| **0** (pre-launch) | **$0** | **$0** | **$0** | **$0** |
| **100** | **$45**<br>Vercel Pro 20 + Supabase Pro 25 + Resend 0 | **$45**<br>Vercel Pro 20 + Neon ~20 + Ably 0 + Resend 0 + Blob ~0 | **$70**<br>Vercel Pro 20 + Neon ~20 + **Clerk Pro 25** + Ably 0 | **$45**<br>Vercel Pro 20 + Convex Pro 25 |
| **1,000** | **$50**<br>Vercel 20 + Supabase Pro 25 + Small compute net 5 + Resend 0 | **$75**<br>Vercel 20 + Neon ~25 + **Ably Standard 29** + Resend 0 + Blob ~1 | **$100**<br>Vercel 20 + Neon ~25 + Clerk 25 + Ably 29 + Blob ~1 | **$50–60**<br>Vercel 20 + Convex 25 + overage |
| **10,000** | **~$135**<br>Vercel 20 + Supabase Pro 25 + Medium compute net 50 + realtime conns 15 + egress ~5 + Resend 20 | **~$165**<br>Vercel 20 + Neon ~80 + Ably ~40 + Resend 20 + Blob ~3 | **~$168**<br>Vercel 20 + Neon ~80 + Clerk 25 + Ably ~40 + Blob ~3 | **~$100–200**<br>highly sensitive to function-call volume |

**Line-item sourcing for the 10,000-user Supabase column [I on arithmetic, V on rates]:**
- Supabase Pro $25 includes a $10 compute credit; Medium compute is $60/mo → net +$50. **[V on rates]**
- Realtime: peak ~2,000 concurrent connections − 500 included = 1,500 → 2 × $10 = **$15**. **[V on rate]**
- Realtime messages 2.7M/mo < 5M included → **$0**. **[V]**
- Database 4 GB < 8 GB included → **$0**. Storage 2 GB < 100 GB → **$0**. **[V]**
- Egress ~300 GB − 250 GB included = 50 GB × $0.09 = **$4.50**. **[V on rate]**
- Resend: 10,000 users × ~2 lifecycle emails ≈ over the 3,000/mo free tier → **$20** Pro tier (50,000 emails). **[V on rate]**

### Per-MAU auth pricing — flagged as the ticket asked

| Provider | Free allowance | Rate beyond | Bites at |
|---|---|---|---|
| **Supabase Auth** | **50,000 MAU** free tier; **100,000 MAU** on Pro | **$0.00325 / MAU** | >100,000 users |
| **Clerk** | **50,000 MRU** (raised from 10,000 on 2026-02-05) | **$0.02 / MRU** — **6.2× Supabase's rate** | >50,000 users |
| **Neon Auth** (beta) | 60,000 MAU free / **1M MAU** on paid | n/a at our scale | >1,000,000 users |
| **Auth.js** | Unlimited — it is a library | $0 | never |

**[V]** — [Supabase pricing](https://supabase.com/pricing), [Clerk pricing](https://clerk.com/pricing), [Clerk changelog 2026-02-05](https://clerk.com/changelog/2026-02-05-new-plans-more-value), [Neon Auth](https://neon.com/docs/neon-auth/overview).

**The honest read [I]:** *per-MAU auth pricing does not bite anywhere in the 0–10,000 range for any option.* The "per-MAU punishes success" concern in the ticket is correct in principle but **inactive at this app's realistic scale**, and Clerk's Feb 2026 increase to 50,000 MRU removed the historic 10,000-MAU cliff that made this argument bite. Clerk's $25/mo is a *branding* charge here, not a user charge. **Do not reject Clerk on per-MAU grounds — reject it, if at all, for other reasons.** Note also Clerk bills MRU (users who return ≥24h after signup), a narrower unit than MAU, which further understates its cost relative to a naive MAU model. **[V]**

**Where per-MAU *would* bite [I]:** at 200,000 users, Clerk costs (200,000 − 50,000) × $0.02 = **$3,000/mo**, while Supabase costs (200,000 − 100,000) × $0.00325 = **$325/mo**. That is a 9x difference and a real strategic risk — but it is a problem for a year in which this app has 200,000 users, and it would be a good problem.

---

## Axis 7 — Free tier limits and what happens when you exceed them

This is where the options differ most sharply, and it is the axis most likely to ruin a draft night.

| Provider | Free limits | **Behaviour on exceeding** | Inactivity pausing |
|---|---|---|---|
| **Supabase** | 500 MB DB, 1 GB storage, 5 GB egress, 50,000 MAU, 200 realtime conns, 2M realtime msgs/mo, 2 active projects **[V]** | **Notified first; continued excess → service restrictions.** Restricted projects return **HTTP 402** with a reason. DB over 500 MB → **read-only mode**. Lifted by upgrading, or automatically when quota refills next cycle. **[V]** ([billing FAQ](https://supabase.com/docs/guides/platform/billing-faq), [status codes](https://supabase.com/docs/guides/troubleshooting/http-status-codes)) | **Yes — "Free projects are paused after 1 week of inactivity."** **[V]** ([pricing](https://supabase.com/pricing)) |
| **Neon** | 100 CU-hours/project/mo, 0.5 GB storage/project (capped), 5 GB egress, 10 branches **[V]** | **"Hitting any Free monthly limit... suspends compute until the next billing month."** Immediate resumption on upgrade. **[V]** ([pricing](https://neon.com/pricing)) | **Yes — autosuspend after 5 min**, and on Free it **cannot be disabled** (Launch: can be disabled; Scale: configurable 1 min to always-on). **[V]** |
| **Clerk** | 50,000 MRU **[V]** | Must upgrade to Pro; **a one-month grace period** applies so the app keeps running. Then $0.02/MRU. **[V]** | None |
| **Vercel Hobby** | 1M function invocations, 4 CPU-hrs Active CPU, 360 GB-hrs memory, 1M edge requests **[V]** | **"you will have to wait until 30 days have passed before you can use the feature again."** No overage billing — you are simply cut off. **[V]** ([Hobby plan](https://vercel.com/docs/plans/hobby)) | None, but **Hobby is "non-commercial, personal use only"** **[V]** |
| **Vercel Pro** | $20/seat + credit | On-demand billing past credit; **Spend Management** can notify, webhook, or **auto-pause projects** at a set spend **[V]** | None |
| **Supabase Pro** | see Axis 6 | **Spend Cap ON** (default): *"After exceeding the quota for a usage item, further usage of that item is disallowed until the next billing cycle."* **Spend Cap OFF**: projects keep running, you are billed overage. **Compute add-ons and branches are NOT covered by the Spend Cap.** **[V]** ([docs](https://supabase.com/docs/guides/platform/spend-cap)) | None |

### The three traps, ranked by how badly they would hurt this app **[I]**

1. **Supabase's Spend Cap will kill your draft night.** With the cap ON (the default), exceeding 500 concurrent realtime connections means *"further usage of that item is disallowed until the next billing cycle"* — i.e. your draft rooms stop accepting connections **for the rest of the month**, during the one week of the year that matters. **Turn the Spend Cap OFF before draft season and set a billing alert instead.** This is the single most important operational note in this document.
2. **Neon Free suspends compute for the rest of the month.** Not throttled — suspended. 100 CU-hours is ~137 hours of a 0.25 CU compute; an always-on 0.25 CU would need 182 CU-hours, so **you cannot run always-on compute on Neon Free at all** **[I]**. Combined with 5-minute autosuspend that cannot be disabled, this makes Neon Free unsuitable for anything that must respond promptly or run scheduled work (see Axis 10).
3. **Supabase Free pauses after 7 days of inactivity.** In the *offseason* — February through July — a free project with no traffic gets paused and needs a manual unpause. On the Pro plan this does not happen, which is a real reason a seasonal app should be on Pro even at 20 users **[I]**.

**Failure-mode ranking [I]:** Clerk (grace period, keeps running) > Vercel Pro (bills, or auto-pauses if you configure it) > Supabase Pro with cap off (bills) > Vercel Hobby (30-day lockout) > Supabase with cap on (per-item lockout to cycle end) ≈ Neon Free (compute suspended to cycle end).

---

## Axis 8 — Vercel integration and deployment ergonomics

- **Supabase**: "Vercel Native" Marketplace integration. Provisions the project, **auto-syncs ~a dozen env vars** with framework-correct prefixes (`NEXT_PUBLIC_` for Next.js), and **billing flows through Vercel**, consolidating invoices. Supabase's own docs warn to *"exercise extreme caution"* with the synced env vars — several are secrets and must not be exposed client-side. **[V]** ([marketplace](https://vercel.com/marketplace/supabase))
- **Neon**: also a Vercel-native Marketplace integration, billed through Vercel; Vercel actively recommends it as *the* Postgres path post-Vercel-Postgres. Pairs branches with preview deployments. **[V]** ([marketplace](https://vercel.com/marketplace/neon))
- **Clerk**: drop-in `<SignIn />`/`<UserButton />` components and Next.js middleware; the best-in-class DX of the four, at the cost of your login UI living in someone else's component tree.
- **Convex**: first-class Next.js support, but its reactive-query model is a different programming model, not a drop-in.

**Read [I]:** Effectively a tie between Supabase and Neon; both are Vercel-native with automatic env var wiring and consolidated billing. This axis does not decide anything. The old "Vercel Postgres has the tightest integration" argument is dead — Vercel Postgres *is* Neon now.

---

## Axis 9 — Lock-in and exit cost

The question: if this is abandoned in two years, what has to be **rewritten** versus **moved**?

| Component | Supabase | Neon | Clerk | Convex |
|---|---|---|---|---|
| **Data** | `pg_dump`. Standard Postgres. **Low.** | `pg_dump`. **Low.** | n/a | **Proprietary format. High.** |
| **Queries** | Portable SQL if you use an ORM; **PostgREST/`supabase-js` calls are Supabase-shaped and would need rewriting** | Portable SQL. **Lowest.** | n/a | Convex functions. **Total rewrite.** |
| **Auth** | Users export, but **password hashes and the `auth.users` schema are Supabase-shaped**; RLS policies referencing `auth.uid()` are Supabase-specific. **Medium.** | Neon Auth stores in *your* `neon_auth` schema — better exit story. Auth.js: you own everything. **Low.** | **User export requires contacting Clerk for password hashes** (standard for hosted auth). Every `<SignIn/>` component and middleware call is Clerk-shaped. **Medium-high.** | Medium |
| **Realtime** | Broadcast channel code is Supabase-shaped, but the *shape* (join channel, send/receive events) maps almost 1:1 onto Ably/Pusher. **Low-medium.** | Ably/Pusher — already portable, and swappable between each other. **Low.** | n/a | **High.** |
| **Storage** | S3-compatible → `rclone` to S3/R2. **Low.** | n/a | n/a | Medium |
| **Realistic exit cost [I]** | **~2 weeks**: rewrite the data layer if you used `supabase-js`, migrate auth, re-point realtime | **~1 week**: it is just Postgres | n/a | **~2 months**: full rewrite |

**Two things that dominate this axis [I]:**

1. **The largest lock-in decision on Supabase is one you make yourself: `supabase-js`/PostgREST versus an ORM over plain Postgres.** If you use Drizzle against the Postgres port, your exit cost is nearly Neon's — change a connection string. If you use `supabase-js` everywhere, every data access in the app is Supabase-shaped. **Recommendation [I]: use Drizzle for all normal data access and reserve `supabase-js` for the three things that are genuinely Supabase features — Auth, Realtime, Storage.** This is the single highest-leverage architectural decision in this document. It gets you Supabase's convenience where it is worth it and keeps the 90% of the app that is CRUD portable.
2. **RLS is real lock-in and it is easy to underestimate.** If authorization for leagues, rosters, and draft picks lives in Postgres RLS policies referencing `auth.uid()`, moving off Supabase means re-implementing your entire authorization model in application code. Consider keeping authorization in the application layer and using RLS as defence-in-depth rather than as the primary mechanism **[I]**.

**Convex is the outlier**: it is not a database you can leave, it is a platform you rewrite off. Given this is a hobby/side project with an uncertain two-year future, that is a meaningful mark against it regardless of how good the developer experience is.

---

## Axis 10 — Scheduled jobs / cron for the CFBD sync

**This axis produced the sharpest finding in the whole comparison.**

| Option | Mechanism | Minimum interval | Notes |
|---|---|---|---|
| **Vercel Cron — Hobby** | Function invocation | **Once per day**, precision ±59 min | Sub-daily cron expressions **fail at deployment** with an explicit error. **[V]** |
| **Vercel Cron — Pro** | Function invocation | **Once per minute**, per-minute precision | 100 cron jobs per project on every plan. **[V]** ([docs](https://vercel.com/docs/cron-jobs/usage-and-pricing)) |
| **Supabase Cron** | `pg_cron` extension | **Every second** to once a year | Runs SQL, database functions, or HTTP calls (e.g. invoke an Edge Function). Recommended max 8 concurrent jobs, ≤10 min per job. **[V]** ([docs](https://supabase.com/docs/guides/cron)) |
| **Neon `pg_cron`** | `pg_cron` 1.6 | n/a in practice | *"pg_cron jobs will only run when your compute is active"*; Neon recommends **24/7 computes or scale-to-zero disabled** — neither is possible on Neon Free. **[V]** |
| **Convex** | Native scheduled functions | Sub-minute | Included |

**The finding [V + I]:** a near-live scoring app needs the CFBD sync running every 1–5 minutes on Saturdays. **On the Neon-based options (B and C), this forces Vercel Pro at $20/mo** — there is no free path, because Vercel Hobby cron is daily-only and Neon Free cannot keep compute alive for `pg_cron`. **On Supabase, `pg_cron` runs at any interval on the free plan**, so option A is the only one with a genuinely free path to sub-minute scheduled sync. This is a small dollar difference but a large *architectural* one: Supabase gives you a scheduler that lives next to your data and does not consume Vercel function invocations.

**Design note [I]:** the ideal shape is `pg_cron` → `pg_net`/Edge Function → CFBD API → upsert into Postgres → clients poll a cached Next.js endpoint. The sync never touches Vercel, so it never burns function invocations or Active CPU, and Saturday traffic spikes hit a CDN-cached endpoint rather than your database.

---

## Convex — the brief note the ticket asked for

**[V]** ([pricing](https://www.convex.dev/pricing)): Free/Starter $0 (1M function calls, 0.5 GB storage, 1,000 concurrent sessions, 16 concurrent queries); Professional $25/developer/month (25M calls, 50 GB, 10,000 sessions, 256 queries); Business/Enterprise $2,500/mo minimum. Realtime and auth included on all tiers.

**Why it is genuinely compelling for this app [I]:** a draft room is *exactly* Convex's sweet spot. Reactive queries mean the draft board, pick timer, and roster views update automatically with no channel management, no subscription bookkeeping, and no "did I remember to broadcast that" bugs. The realtime code you would write in Supabase largely disappears. Its scheduled functions handle CFBD sync natively. It is the only option where realtime is the default rather than an addition.

**Why I am not recommending it [I]:**
- **It is not Postgres.** Fantasy football scoring is deeply relational and aggregate-heavy: "sum this player's weekly points, joined to rosters, filtered by league scoring settings, ranked." That is SQL's home turf. Doing it in a document model means hand-rolling aggregations.
- **Exit cost is a rewrite, not a migration** (Axis 9).
- **The free tier's 1M function calls is tighter than it looks** — in Convex every reactive query re-execution is a function call, and a 12-person draft room with a live board is call-hungry **[I]**. Cost at 10,000 users is the least predictable of the four.
- **Ecosystem depth**: Postgres has 25 years of tooling, Stack Overflow answers, and CFBD-adjacent examples. For a solo developer on a side project, that matters more than elegance.

**Fair summary:** Convex would probably produce the *nicest draft room* and the *worst scoring engine*. If the draft room were the whole app, it would win.

---

## RECOMMENDATION

### Build on Supabase + Vercel + Resend.

**Stack:**
- **Database**: Supabase Postgres, accessed via **Drizzle ORM** through the Supavisor transaction pooler (port 6543) for all normal CRUD.
- **Auth**: Supabase Auth (email/password with confirmation on, plus Google OAuth), with **Resend configured as custom SMTP from day one** — this is not optional.
- **Realtime**: Supabase Realtime **Broadcast** (not Postgres Changes) for the draft room and chat.
- **Storage**: Supabase Storage with RLS policies, using built-in image transforms for avatars.
- **Cron**: Supabase `pg_cron` → Edge Function → CFBD, every 2 minutes during game windows.
- **Scoring**: client polls a cached Next.js route on a 30–60s interval. **Do not push scores over realtime.**
- **Plan**: Vercel Hobby + Supabase Free for development; move to **Vercel Pro + Supabase Pro before the first real draft** ($45/mo).

### Why — the actual argument, not the "all-in-one" one

The "fewest moving parts" instinct is right, but "all-in-one" is not literally available: **every option here needs a separate transactional email provider except Clerk.** So the real comparison is 3 vendors (Supabase) versus 4–5 (the alternatives). Supabase wins because:

1. **It is the only option where realtime, storage, auth, and sub-minute cron are all included and all free at this app's scale.** Options B and C need Ably ($29/mo once past 200 concurrent connections) *and* Vercel Pro for cron *and* a blob store *and* Resend.
2. **The draft room — the hard requirement — is fully covered on the free tier** (200 concurrent connections ≈ 16 simultaneous rooms; 2M messages/month ≈ 125 league-seasons).
3. **`pg_cron` at any interval on the free plan** is a genuine capability the Neon options structurally cannot match.
4. **Storage with RLS-based authorization** is a real win for user-uploaded avatars, and the alternative (Vercel Blob) makes you build that yourself.
5. It is **~$30/mo cheaper at 10,000 users** than either alternative while being simpler.

### Two corrections to the leaning as stated

- **"All-in-one" is not true.** Budget Resend into the plan and the setup checklist now. The number of vendors is 3, not 1. A dev who believes Supabase sends production emails will discover otherwise when the second user of the hour cannot verify their account.
- **Neon is the better database on the merits** (included PITR, cheaper branching, 3x extensions, higher pooled connection ceiling). Supabase is not being chosen because its Postgres is better — it is being chosen because of everything bolted around it. Be honest about that, because it means **if the bolted-on parts stop earning their keep, the database was never the reason to stay.**

### Non-negotiable operational notes

1. **Turn OFF the Supabase Spend Cap before draft season** and set a billing alert instead. With it on, exceeding 500 concurrent realtime connections disables realtime *for the rest of the billing cycle* — during draft week.
2. **Configure Resend custom SMTP before any real user signs up.** Default: 2 emails/hour, org members only.
3. **Move to Supabase Pro before the offseason**, or free projects pause after 7 days of inactivity every February.
4. **Use Broadcast, not Postgres Changes**, for the draft room.
5. **Vercel Hobby is non-commercial only.** The moment this app takes money or runs ads, Vercel Pro is mandatory regardless of usage.
6. **Keep authorization in the application layer**; use RLS as defence-in-depth, not as the primary model, to keep exit cost bounded.

---

## What would change this recommendation

Concretely — each of these is a fact that, if true, flips the decision:

**→ Switch to Neon + Clerk if:**
- **Point-in-time recovery becomes a hard requirement.** Supabase charges $100/mo per 7 days of retention *plus* a mandatory Small compute add-on; Neon includes 7-day PITR on Launch and 30-day on Scale at no fixed fee. **This is a 3x swing in monthly cost at small scale and it flips the decision on its own.**
- **You end up hating hand-rolled auth UI more than you hate a fifth vendor.** Clerk's drop-in components plus its own email delivery genuinely removes two problems (auth UI and Resend). At 10,000 users the total cost difference is ~$33/mo. If auth screens are consuming your weekends, that is cheap.
- **The app is expected to exceed 100,000 users**, at which point re-run the per-MAU maths carefully — but note this favours *Supabase* ($0.00325/MAU) over Clerk ($0.02/MRU) by 6x, so this argument cuts the other way.
- **Database branching per pull request becomes central to the workflow.** Neon's branching is cheaper, more generous, and better integrated with Vercel previews.

**→ Switch to Convex if:**
- **The draft room turns out to be 80% of the engineering effort** and the scoring engine turns out to be trivial. If after building a prototype draft room on Supabase Broadcast you find you have written hundreds of lines of subscription bookkeeping and are still fighting state-sync bugs, Convex's reactive model would erase that code. Set a checkpoint: if the draft room takes more than ~3 weeks, re-open this question.
- **You decide the two-year exit cost does not matter** because this is a project you will either love or delete.

**→ Reconsider the whole realtime approach if:**
- **Peak concurrency exceeds ~2,000.** Above that, run the numbers against Ably again: Ably's free tier includes 6M messages/month versus Supabase Pro's 5M, and Ably's connection pricing ($1.00 per million connection-minutes) may beat Supabase's ($10 per 1,000 concurrent) for spiky draft-week traffic. **This is genuinely close and worth 30 minutes of arithmetic if drafts get big.**
- **Scores need to be *pushed* rather than polled.** Pushing per-play updates to every active user multiplies realtime message volume by the whole user base and would change every number in the Axis 6 table. If push scoring becomes a product requirement, redo Axis 3 from scratch.

**→ Re-verify everything if:**
- **More than ~3 months pass before implementation starts.** Clerk moved its free tier 5x in February 2026; Vercel Postgres ceased to exist as a product in December 2024. Every number here has a retrieval date of 2026-09-10 for a reason.

---

## Sources

All retrieved 2026-09-10.

**Supabase** — [Pricing](https://supabase.com/pricing) · [Realtime quotas](https://supabase.com/docs/guides/realtime/quotas) · [Realtime limits](https://supabase.com/docs/guides/realtime/limits) · [Postgres Changes scaling](https://supabase.com/docs/guides/realtime/postgres-changes) · [Custom SMTP](https://supabase.com/docs/guides/auth/auth-smtp) · [Passwords](https://supabase.com/docs/guides/auth/passwords) · [Connecting to Postgres / Supavisor](https://supabase.com/docs/guides/database/connecting-to-postgres) · [Spend Cap](https://supabase.com/docs/guides/platform/spend-cap) · [Billing FAQ](https://supabase.com/docs/guides/platform/billing-faq) · [PITR usage](https://supabase.com/docs/guides/platform/manage-your-usage/point-in-time-recovery) · [Branching usage](https://supabase.com/docs/guides/platform/manage-your-usage/branching) · [Cron](https://supabase.com/docs/guides/cron) · [Storage](https://supabase.com/docs/guides/storage) · [Extensions](https://supabase.com/docs/guides/database/extensions) · [HTTP status codes](https://supabase.com/docs/guides/troubleshooting/http-status-codes)

**Neon** — [Pricing](https://neon.com/pricing) · [Connection pooling](https://neon.com/docs/connect/connection-pooling) · [Point-in-time restore](https://neon.com/docs/introduction/point-in-time-restore) · [Extensions](https://neon.com/docs/extensions/pg-extensions) · [Neon Auth](https://neon.com/docs/neon-auth/overview) · [Vercel Postgres transition guide](https://neon.com/docs/guides/vercel-postgres-transition-guide)

**Vercel** — [Pricing](https://vercel.com/docs/pricing) · [Hobby plan](https://vercel.com/docs/plans/hobby) · [Cron usage & pricing](https://vercel.com/docs/cron-jobs/usage-and-pricing) · [Blob usage & pricing](https://vercel.com/docs/vercel-blob/usage-and-pricing) · [Supabase marketplace](https://vercel.com/marketplace/supabase) · [Neon marketplace](https://vercel.com/marketplace/neon) · [Neon GA changelog](https://vercel.com/changelog/neon-now-available-on-vercel-marketplace)

**Clerk** — [Pricing](https://clerk.com/pricing) · [Sign-up/sign-in options](https://clerk.com/docs/guides/configure/auth-strategies/sign-up-sign-in-options) · [Email & SMS templates](https://clerk.com/docs/guides/customizing-clerk/email-sms-templates) · [Production deployment](https://clerk.com/docs/guides/development/deployment/production) · [New plans changelog, 2026-02-05](https://clerk.com/changelog/2026-02-05-new-plans-more-value)

**Others** — [Auth.js Credentials provider](https://authjs.dev/getting-started/authentication/credentials) · [Convex pricing](https://www.convex.dev/pricing) · [Ably pricing](https://ably.com/pricing) · [Pusher Channels pricing](https://pusher.com/channels/pricing/) · [Resend pricing](https://resend.com/pricing)
