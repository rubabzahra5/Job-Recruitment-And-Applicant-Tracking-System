# Module Summary — Agent A: Public Portal

Date: 2026-10-10. Territory: `app/(public)/` + one migration (`0010_contact_messages.sql`).
Did NOT touch: `components/ui/*`, `lib/*`, `middleware.ts`, `instrumentation.ts`,
`package.json`, migrations `0001`–`0009`, or other route groups.

## Routes built

| Route | Type | Data source |
|---|---|---|
| `/` | Server component | Live DB: `getLiveJobCounts` (one lightweight query, aggregated server-side), categories, locations, verified orgs (limit 6), latest jobs (8), fresh-graduate jobs (4). Hero search is a GET form → `/jobs`. All stats are real counts; empty states shown when tables are empty. |
| `/jobs` | Server component | `searchJobs()` — server-side filtering on `jobs` via RLS-bound client: PostgreSQL full-text (`textSearch` on the `search` tsvector, websearch config, ILIKE fallback), company (via `organization_public_profiles` ilike), city, province, category slug, employment type, workplace, experience level (derived from `experience_min_years`), education (ilike), min salary (disclosed `salary_max >=` ask), fresh-grad only, posted-within days, sort (relevance/newest/deadline/salary). Server-side pagination (`page`/`per_page`, `count: "exact"`), filters preserved in URL (shareable), clear-filters control, honest empty state. |
| `/jobs/[slug]` | Server component | `getLiveJobBySlug` + `job_questions` + similar jobs. `notFound()` for drafts/expired/closed jobs or inactive orgs. Apply CTA → `/login?next=/jobs/[slug]` (or `/candidate` when signed in). |
| `/companies` | Server component | `organization_public_profiles` where `verification_status='verified'` (public fields only) + live job counts per org. |
| `/companies/[slug]` | Server component | Verified org by slug (404 otherwise) + its live jobs via exact `orgId` filter. |
| `/categories` | Server component | `job_categories` + live counts per category. |
| `/locations` | Server component | `locations` grouped by province + live counts per city. |
| `/search` | Server component | Own page reusing `searchJobs()`: unified keyword/city/category form, top-10 inline matches, deep link to `/jobs` for full results. |
| `/about`, `/faq`, `/privacy`, `/terms` | Static | Genuine copy written for a Pakistani recruitment platform. Privacy page documents collection/use/retention (24-month applications, 12-month contact messages, 30-day deletion)/deletion rights/security honestly. |
| `/contact` | Client form + server action | Zod-validated; INSERTs to new `contact_messages` table (anon INSERT via RLS); best-effort in-app notification to super admins via `lib/notifications.ts`; success state. No email is claimed sent. |
| `/login` | Client form + server action | `supabase.auth.signInWithPassword`; honest "email not verified" messaging; server-side role-based redirect via `lib/rbac.ts` (`getUserRoles`) → `/control-center` (super_admin), `/employer` (any org role), `/candidate` (default). `next` param validated against open redirects. Already-signed-in users are redirected away. |
| `/register` | Client form + server action | Real `supabase.auth.signUp` with display name, account type, optional Pakistani phone (`lib/phone.ts` `normalizePhone`, server-side). Grants platform-wide `candidate` role server-side via service-role client (best-effort). Email-confirmation state handled honestly from the API response (session → redirect; no session → "check your inbox"). Employer org setup deferred to `/employer` onboarding. |
| `/forgot-password` | Client form + server action | `supabase.auth.resetPasswordForEmail`; always-generic response (no account enumeration). |
| `/reset-password` | Client form + server action | Exchanges the emailed `code` via `exchangeCodeForSession`, then `updateUser`; invalid/expired links reported honestly; success → `/login?message=password-updated`. |

## Shared layout & components (`app/(public)/`)

- `layout.tsx` → `SiteHeader` (auth-aware: session via `lib/auth.ts`, roles via `lib/rbac.ts`; Dashboard link by role; Login/Register when signed out; mobile nav; **no `/control-center` link in public nav**) + `SiteFooter` (navy footer with About/Contact/FAQ/Privacy/Terms links).
- `_lib/public-data.ts` — types, label maps, `searchJobs`, `getLiveJobBySlug`, `getJobQuestions`, reference-data fetchers, `getLiveJobCounts`. **Live-job rule enforced on every job query**: `status='published' AND (deadline IS NULL OR deadline > now()) AND org in active orgs` (via `organization_public_profiles`, which only contains active accounts).
- `_lib/dashboard.ts` — `getDashboardPath()` (roles from DB, never client input) + `safeNextPath()`.
- `_components/`: `JobCard`, `JobFilters` (GET form), `SortSelect`, `Pager` (shareable page links), `SiteHeader`, `SiteFooter`, `SignOutButton`, auth forms, `ContactForm`.

## Migration

- `supabase/migrations/0010_contact_messages.sql` — `contact_messages` table (uuid PK, name, email, subject, message, `created_at`, `is_read` default false), RLS enabled, anon+authenticated INSERT-only policy, super_admin FOR ALL policy. **Validated**: `npm run db:validate` — all 10 migrations applied cleanly to PostgreSQL 16.15; 45 tables with RLS; functional checks pass.

## Verification performed

- `npx tsc --noEmit` — clean for all `app/(public)/` files. (One pre-existing error exists in `app/(candidate)/candidate/apply/[jobSlug]/_actions.ts` — Agent B's territory, untouched.)
- `npx eslint "app/(public)/**/*.{ts,tsx}"` — clean.
- `npx vitest run` — 51/51 pass.
- `npm run db:validate` — OK (see above).
- Dev-server smoke test (temporary dummy env, removed after): `/about`, `/faq`, `/privacy`, `/terms`, `/contact`, `/login`, `/register`, `/forgot-password`, `/reset-password` → 200 with correct content; `/` correctly 500s against the unreachable dummy DB (data layer throws instead of showing fake data). `next build` currently fails due to **other agents' in-progress files** (syntax error in candidate `_actions.ts`, missing `./actions` modules in control-center) — none in my territory.

## Not verifiable here (no Supabase credentials in this environment)

- Real end-to-end auth flows (sign-up, email verification, password reset emails) against a live Supabase project.
- RLS behavior with real anon/authenticated sessions (policies validated statically against migration SQL only).
- `organization_public_profiles` view-owner RLS bypass (flagged in foundation summary; relied upon for public org fields).
- Homepage/job pages rendering with real data — queries are written against the migrated schema but untested against live data.
- Playwright E2E (same sandbox browser limitation noted in foundation summary).

## Notes for other agents / follow-ups

- Apply flow: public job pages link signed-in users to `/candidate` and signed-out users to `/login?next=/jobs/[slug]`; the candidate agent owns the actual application flow.
- Employer registration creates the auth user + candidate/employer account-type metadata; organization creation + staff roles are expected in `/employer` onboarding.
- Sort "relevance" = full-text match narrowed set ordered newest-first (documented in code; true `ts_rank` ordering would need raw SQL, unavailable through the RLS-bound client).
- `getUserRoles` (service role) is used for login redirect per spec; the public header falls back to `/candidate` if role lookup fails.
