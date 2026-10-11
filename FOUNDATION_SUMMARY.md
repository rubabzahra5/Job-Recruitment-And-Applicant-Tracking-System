# Job Recruitment And Applicant Tracking System — Foundation Summary (Phase 1)

Date: 2026-10-10. Workspace: `/home/hatch/workspace/job-recruitment-and-applicant-tracking-system`.

## Pinned versions (exact, verified installed)

| Package | Version | Package | Version |
| ------- | ------- | ------- | ------- |
| next | 15.5.27 | eslint-config-next | 15.5.27 |
| react / react-dom | 19.3.0 | @supabase/ssr | 0.12.7 |
| typescript | 5.9.3 | @supabase/supabase-js | 2.117.3 |
| tailwindcss / @tailwindcss/postcss | 4.3.3 | zod | 4.6.5 |
| eslint (+ @eslint/eslintrc) | 9.39.5 (+ 3.3.7) | react-hook-form | 7.89.0 |
| vitest | 5.0.3 | @hookform/resolvers | 5.9.1 |
| @testing-library/react | 16.3.3 | jsdom | 30.1.2 |
| playwright / @playwright/test | 1.64.0 | tsx | 4.23.15 |
| @vitejs/plugin-react | 6.1.2 | server-only | 0.0.1 |
| @types/node / react / react-dom | 26.6.5 / 19.3.0 / 19.3.0 | | |

next@15.5.27 is the latest 15.x Maintenance LTS (Sept 30 2026 security release).
`@hookform/resolvers@5.9.1` peer-supports `zod ^3.25 || ^4`. All versions above
were confirmed present in `node_modules` (no range drift).

## What was built

**App shell** — `app/layout.tsx`, `app/globals.css` (Tailwind v4), `app/not-found.tsx`,
route groups with layouts + placeholder pages:
`app/(public)/`, `app/(candidate)/candidate/`, `app/(employer)/employer/`,
`app/(admin)/control-center/`. `middleware.ts` (redirect-only protection for the
three private prefixes; role checks are server-side). `instrumentation.ts`
(fail-fast env validation at server boot).

**Supabase clients** — `lib/supabase/client.ts` (browser, anon key),
`lib/supabase/server.ts` (request cookies, RLS applies; awaits `cookies()`
before env so builds never need credentials), `lib/supabase/admin.ts`
(service role + `server-only` import so client bundling fails at build time).

**Core libs** — `lib/env.ts` (zod validation, cached, secret-free errors),
`lib/auth.ts` (`getSessionUser` / `requireSessionUser`),
`lib/rbac.ts` (`requireOrgRole` incl. `{ atLeast }` rank checks,
`requireOrgMembership`, `requireSuperAdmin`, `getUserOrgRole` — always read
from `user_roles` via the admin client, active membership required),
`lib/audit.ts` (INSERT-only `audit_logs` writer), `lib/notifications.ts`
(in-app create + delivery-log abstraction), `lib/email.ts` (provider interface;
optional Resend; returns `{ sent: false, reason: 'email_unconfigured' }` when
unconfigured and never claims a send), `lib/uploads.ts` (10 MB default cap,
magic-byte sniffing for PDF/DOCX, extension/content agreement,
`{bucket}/{user_id}/{uuid}.{ext}` paths), `lib/phone.ts` (strict PK mobile
`03…`/`+923…` validator + lenient `normalizePhone` that does NOT assume PK
numbers), `lib/pipeline.ts` (transition validation against DB-loaded
`pipeline_stages`/`pipeline_transitions`), `lib/format.ts` (PKR as
`Rs 85,000` with Pakistani digit grouping — `Rs 15,00,000`; Asia/Karachi
display, UTC storage), `lib/csv.ts` (bounded RFC-4180 export with
formula-injection neutralization).

**UI primitives** — `components/ui/`: Button, Input, Textarea, Select, Card,
Table, Dialog + ConfirmDialog (focus trap, Escape, aria-modal), Badge, Tabs
(arrow-key nav), Pagination, EmptyState, LoadingState, Alert (`role=alert`),
FormField (label/hint/error wiring), Stat.

**Migrations** — `supabase/migrations/0001_identity.sql` … `0009_seed.sql`:
identity/orgs/audit, catalog (jobs with generated `tsvector` + GIN), candidates
(private by default), applications (stage CHECK + transition trigger + partial
unique index), hiring, config, RLS (44 tables, least-privilege, anon sees only
live published jobs), storage buckets + policies (CVs owner-only; staff read via
server-side signed URLs), and idempotent reference seed (13 categories,
13 cities, 13 stages, 27 transitions, platform defaults).

**Scripts** — `scripts/bootstrap-admin.ts` (typed email confirmation; refuses
when a super admin exists unless `--force` + typed confirmation; disable after
use), `scripts/seed.ts` (fictional data, requires `SEED_CONFIRM=yes`),
`scripts/validate-migrations.sh` (throwaway PG cluster + Supabase stubs +
functional checks).

**Tests** — `tests/`: 51 tests, 6 files (phone, format, csv, uploads,
pipeline, UI render). **All pass** (`npx vitest run`).
**E2E** — `e2e/smoke.spec.ts` (homepage, auth redirects, 404). Playwright
browsers could not be downloaded in this sandbox (CDN download failure), and the
only available Chromium (`/opt/meta-chromium/chrome`, v152) enforces Local
Network Access checks that block navigation to loopback servers
(`ERR_BLOCKED_BY_LOCAL_NETWORK_ACCESS_CHECKS`) with no working disable flag.
The 3 specs were executed and failed on this environmental issue — not on app
behavior. Every assertion in the spec was instead verified against the running
production server with curl: `/` → 200 with the expected heading;
`/candidate`, `/employer`, `/control-center` → 307 to `/login?next=…`;
unknown path → 404 "Page not found". `playwright.config.ts` supports
`PLAYWRIGHT_CHROMIUM_PATH` for environments with a system Chromium.

**Docs** — `README.md`, `docs/DEVELOPMENT.md`, `docs/SCHEMA.md`, `.env.example`.

## Verification actually executed

- `npm run build` — passes (7 routes; `/` static, dashboards dynamic).
- `npx tsc --noEmit` — clean (strict + `noUncheckedIndexedAccess`).
- `npx eslint .` — clean.
- `npx vitest run` — 51/51 pass.
- `npm run db:validate` — all 9 migrations applied to a real PostgreSQL 16.15
  cluster; functional checks passed: valid/invalid stage transitions,
  terminal-stage lock, partial-unique re-apply flow, `withdrawn_at` auto-stamp,
  tsvector skill search. Seed counts verified (13 stages / 27 transitions /
  13 categories / 13 locations / 6 settings).

## How later agents should use lib/rbac.ts

```ts
import { requireSessionUser } from "@/lib/auth";
import { requireOrgRole, requireSuperAdmin } from "@/lib/rbac";

// In a server action / page:
const user = await requireSessionUser();
await requireOrgRole(user.id, orgId, { atLeast: "recruiter" }); // or ["org_admin"]
await requireSuperAdmin(user.id); // control-center only
```

- Middleware redirects only; never rely on it for authorization.
- The service-role client bypasses RLS — always authorize BEFORE using it.
- Stage moves: load once via `loadPipeline(admin)`, then
  `assertValidTransition(from, to, stages, transitions)` before updating
  `applications.stage`. The DB trigger enforces the same rules for direct SQL.
- Terminal stages (`hired`, `rejected`, `withdrawn`, `offer_declined`) accept
  no outgoing transitions. Candidates may only move to `withdrawn`.
- Candidate PII: staff reads require `can_view_candidate()` semantics
  (applied to their org, or `is_searchable = true`). CVs: owner-only storage
  policy; generate signed URLs server-side after an RBAC check.

## Could not verify / open items

- No Supabase credentials exist in this environment — nothing was run against a
  real Supabase project (auth, storage, realtime untested). First integration
  test should be manual against a dev project.
- E2E: the 3 Playwright specs were executed but could not pass in this sandbox
  (browser download blocked; system Chromium blocks loopback navigation — see
  above). Their assertions were verified via curl instead. Re-run
  `npm run test:e2e` in an environment with working Playwright browsers.
- `scripts/bootstrap-admin.ts` and `scripts/seed.ts` were type-checked but not
  executed (no live Supabase).
- Email sending not tested (no `RESEND_API_KEY`); the unconfigured path is
  unit-testable but has no test yet — later agents should add one.
- `organization_public_profiles` view relies on view-owner RLS bypass; flagged
  here for review when connecting the real project.
