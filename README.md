# Job Recruitment And Applicant Tracking System

Job recruitment + applicant tracking system (ATS) for Pakistan.

**Brand note:** "Job Recruitment And Applicant Tracking System" is a *temporary, configurable* product name. The
platform brand is a runtime setting (`platform_settings.platform_name`,
editable in the control center under Settings) and should be renamed before
any public launch.

**What this is:** a complete web application — public job board, candidate
portal, employer/HR portal, and super-admin control center — built on Next.js
15 (App Router) + Supabase (PostgreSQL, Auth, Storage), all on free-tier
services. Primary market: Pakistan. Currency: PKR. Language: English (the
architecture leaves room for Urdu/RTL later). Default display timezone:
`Asia/Karachi`; timestamps are stored in UTC.

**Two operating modes** (configurable via `platform_settings.operating_mode`,
no rebuild needed):
- **Mode A — centralized:** a public recruitment portal run by the platform
  owner; organizations register and await verification.
- **Mode B — internal:** a single organization using the platform privately as
  its internal recruitment system.

## Stack (pinned, verified Oct 2026)

Exact versions confirmed present in `node_modules` (no range drift —
`package.json` pins every version):

| Package            | Version  |
| ------------------ | -------- |
| next / eslint-config-next | 15.5.27 |
| react / react-dom  | 19.3.0   |
| typescript         | 5.9.3    |
| tailwindcss / @tailwindcss/postcss | 4.3.3 |
| @supabase/ssr      | 0.12.7   |
| @supabase/supabase-js | 2.117.3 |
| zod                | 4.6.5    |
| react-hook-form    | 7.89.0   |
| @hookform/resolvers| 5.9.1    |
| vitest             | 5.0.3    |
| @testing-library/react | 16.3.3 |
| jsdom              | 30.1.2   |
| playwright / @playwright/test | 1.64.0 |
| eslint / @eslint/eslintrc | 9.39.5 / 3.3.7 |
| tsx                | 4.23.15  |
| server-only        | 0.0.1    |

`next@15.5.27` is the latest 15.x Maintenance LTS (Sept 30 2026 security
release). `engines.node >= 20.9.0`.

## Prerequisites

- Node.js ≥ 20.9
- A Supabase project (PostgreSQL + Auth + Storage) — free tier works for
  development. See `docs/free-tier-limits.md` for the current quotas.
- PostgreSQL 14–16 binaries locally (optional; only needed for
  `npm run db:validate`).

## Local install

```bash
cp .env.example .env      # fill in your Supabase credentials
npm install
npm run dev               # http://localhost:3000
```

All environment variables are documented in `.env.example`. `lib/env.ts`
validates them with zod and fails fast at server boot (`instrumentation.ts`);
error messages name variables only — secret values are never echoed.

## Database migrations

Migrations live in `supabase/migrations/`, applied in order: `0001_identity.sql`
through `0010_contact_messages.sql`.

Apply them with the Supabase CLI (`supabase db push`) or the dashboard SQL
editor. To validate them locally without Supabase:

```bash
npm run db:validate
```

`scripts/validate-migrations.sh` spins up a throwaway PostgreSQL cluster,
stubs the Supabase-provided `auth` and `storage` schemas, applies every
migration in order, and runs functional checks (stage transitions,
terminal-stage lock, re-apply flow, full-text search, seed counts).

> What you have NOT yet tested until you run against a real Supabase project:
> auth flows, storage signed URLs, RLS interplay with real sessions, and email.
> See "What remains unverified" below and `docs/deployment.md`.

## Seed data (development only)

```bash
SEED_CONFIRM=yes npm run seed
```

- `scripts/seed.ts` refuses to run unless `SEED_CONFIRM` is exactly `yes`.
- It never runs automatically (no hooks, no build-time import).
- All data is fictional: organizations are suffixed "(Fictional — Seed Data)"
  so they can never be mistaken for real records.
- The reference seed in migration `0009_seed.sql` (categories, cities,
  pipeline stages, platform defaults) is idempotent and safe in production.

## Bootstrap the first super admin

There is intentionally **no public super-admin registration page**. After
creating your Supabase project and applying migrations:

```bash
BOOTSTRAP_ADMIN_EMAIL=owner@example.com npm run bootstrap-admin
```

`scripts/bootstrap-admin.ts`:
1. Requires `BOOTSTRAP_ADMIN_EMAIL` (the user must already exist in Supabase Auth).
2. Refuses if a `super_admin` grant already exists (unless `--force` with a
   typed re-confirmation).
3. Asks the operator to **type the target email** to confirm, then grants
   `user_roles(super_admin, org_id NULL)`.
4. Prints instructions to disable/delete the script afterwards.

**After use:** delete `scripts/bootstrap-admin.ts` (or remove its npm script)
so it cannot be run again. Until you do, anyone with terminal access to the
deploy environment could re-run it.

## Commands

| Script                  | Purpose                                              |
| ----------------------- | ---------------------------------------------------- |
| `npm run dev`           | Start dev server                                     |
| `npm run build`         | Production build                                     |
| `npm run start`         | Serve production build                               |
| `npm run typecheck`     | `tsc --noEmit` (strict + `noUncheckedIndexedAccess`) |
| `npm run lint`          | ESLint                                               |
| `npm test`              | Vitest unit/integration tests (`npm run test:watch` for watch mode) |
| `npm run test:e2e`      | Playwright end-to-end tests                          |
| `npm run bootstrap-admin` | One-time super-admin provisioning (server-only)    |
| `npm run seed`          | Dev seed data (requires `SEED_CONFIRM=yes`)          |
| `npm run db:validate`   | Apply migrations against a throwaway local Postgres  |

## Project structure

```
app/
  (public)/                public job board + auth (/, /jobs, /companies,
                           /login, /register, /invite/[token], …)
  (candidate)/candidate/   candidate portal (profile, CVs, applications,
                           job alerts, privacy tools, …)
  (employer)/employer/     employer/HR portal (jobs, kanban, interviews,
                           offers, reports, team, …)
  (admin)/control-center/  super-admin control center (orgs, users, jobs,
                           approvals, audit logs, settings, security, …)
components/ui/            accessible design-system primitives (Button, Dialog,
                          Table, Pagination, FormField, …)
lib/                      supabase clients, env, auth, rbac, pipeline, email,
                          notifications, uploads, csv, phone, format, audit
supabase/migrations/      versioned SQL schema (0001…0010)
scripts/                  bootstrap-admin.ts, seed.ts, validate-migrations.sh
tests/                    vitest suites (51 tests, 6 files)
e2e/                      playwright smoke spec
docs/                     developer docs
```

## Security notes

- `SUPABASE_SERVICE_ROLE_KEY` is server-only: `lib/supabase/admin.ts` imports
  `server-only` so any client bundling fails at build time. It bypasses RLS,
  so server code must authorize via `lib/rbac.ts` **before** using it.
- `middleware.ts` is redirect-only; real authorization happens server-side on
  every page and server action (`requireSessionUser`, `requireOrgRole`,
  `requireSuperAdmin` — roles are always read fresh from `user_roles`).
- Defense in depth: RLS policies (migration `0007_rls.sql`) guard direct client
  queries; a `validate_application_stage_transition` trigger guards stage moves
  even via raw SQL.
- See `docs/deployment.md` for the full production-security checklist and
  `docs/architecture.md` for the security model.

## What remains unverified (as of Oct 2026)

This was built in a sandbox with **no live Supabase credentials**, so the
following have never been exercised against a real project: auth flows
(sign-up, email verification, password reset), storage uploads and signed
URLs, RLS behavior with real sessions, email sending (no `RESEND_API_KEY`),
and Playwright browser tests (browsers could not be downloaded in the
sandbox; the spec's assertions were verified against a running server with
curl instead). The first thing to do with a dev Supabase project is a full
manual pass: sign-up → candidate role → profile → CV upload → apply →
withdraw → recruiter review → interview → offer. See the smoke-test checklist
in `docs/deployment.md`.

## Docs

- `docs/DEVELOPMENT.md` — local development conventions
- `docs/SCHEMA.md` — database schema overview
- `docs/deployment.md` — beginner-friendly production deployment guide
- `docs/email-setup.md` — Supabase Auth emails + optional Resend; the honest
  unconfigured-email behavior
- `docs/compliance-pk.md` — launch checklist for qualified Pakistani
  legal/HR counsel review (not a compliance claim)
- `docs/free-tier-limits.md` — current Supabase/Vercel/GitHub free quotas
  (Oct 2026) and migration paths
- `docs/architecture.md` — system overview: routes, RBAC, RLS, notifications,
  settings map, multi-tenancy, limitations
- `FOUNDATION_SUMMARY.md`, `MODULE_SUMMARY_{A,B,C,D}.md` — build reports
  (foundation + public / candidate / employer / admin modules)
