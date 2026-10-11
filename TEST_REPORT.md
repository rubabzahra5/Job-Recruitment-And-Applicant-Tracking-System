# Job Recruitment And Applicant Tracking System — Test Report (Test Agent)

Date: 2026-10-10. Agent: test agent (subagent). Territory: `tests/`, `e2e/`, `TEST_REPORT.md`.
Read-only everywhere else — no changes were made to `app/`, `lib/`, `components/`,
`supabase/`, `scripts/`, `package.json`, or docs.

## Commands executed (exact) and results

| Command | Result |
|---|---|
| `npx vitest run` | **172/172 pass, 17 files** (51 pre-existing foundation tests still pass; 121 new) |
| `npx tsc --noEmit` | **clean** (strict + `noUncheckedIndexedAccess`; includes new tests + e2e specs) |
| `npm run build` | **passes** (exit 0; all routes compiled incl. page-data collection) |
| `npx eslint tests/ e2e/` | **clean** (exit 0) |
| `npx playwright test e2e/smoke.spec.ts` (with `PLAYWRIGHT_CHROMIUM_PATH=/opt/meta-chromium/chrome`, server booted on `:3100` with dummy env) | **3/3 fail — environmental, not app behavior**: `page.goto: net::ERR_BLOCKED_BY_LOCAL_NETWORK_ACCESS_CHECKS at http://127.0.0.1:3100/`. The config's `--disable-features=LocalNetworkAccessChecks` flag does not unblock this Chromium build (v152). Matches the foundation's earlier finding. |
| `npx playwright test e2e/candidate.spec.ts e2e/recruiter.spec.ts e2e/admin.spec.ts e2e/tenant-isolation.spec.ts` | **11/11 skipped** — honest skip: `E2E_SUPABASE_URL` / `E2E_SUPABASE_SERVICE_ROLE_KEY` are absent in this environment, and every spec skip-guards on them. |

## New test files (all under my territory)

**Unit / integration (`tests/`)**
- `tests/phone-validation.test.ts` (11) — PK formats `03…`/`+923…`/`923…` accepted + normalized; separators tolerated; landlines/wrong lengths/letters rejected; `normalizePhone` keeps non-PK `+`-numbers, blanks → null, rejects non-E.164.
- `tests/job-schema.test.ts` (11) — `jobPayloadSchema` salary `min<=max` refine (incl. equal/null ends, negatives, message path `salaryMax`); experience range; `JOB_TRANSITIONS` lifecycle facts.
- `tests/pipeline-matrix.test.ts` (13) — full seed matrix (13 stages / 27 transitions): happy path, invalid jumps, terminal lock on all 4 terminal stages, every non-terminal → `withdrawn`, `assertValidTransition` error, `loadPipeline` mapping + error path.
- `tests/rbac.test.ts` (17) — real `lib/rbac.ts` with mocked admin client: grant/deny, `{atLeast}` rank, list-based checks, **inactive membership denies even with a grant**, super_admin passthrough, org-scoped "super_admin" grant ≠ platform admin, highest-rank pick, `requireOrgMembership`.
- `tests/uploads-security.test.ts` (15) — near-miss `%PDX` header rejected, text-as-PDF rejected, oversized/at-cap, caller-supplied smaller cap, uppercase extension, 50 unique randomized paths, path strictly `{bucket}/{user}/{uuid}.{ext}`.
- `tests/format-csv.test.ts` (19) — PKR Pakistani grouping (`Rs 85,000`, `Rs 15,00,000`, `Rs 1,00,00,000`, negatives/strings/missing/rounding), `formatSalaryRange` periods + open ends, CSV quoting/CRLF, formula-injection neutralization (`=`,`+`,`-`,`@` → `'`-prefixed), `exportScopedCsv` bound.
- `tests/submit-application.test.ts` (10) — real `submitApplication` with mocked Supabase: **23505 → `{ok:false, code:"ALREADY_APPLIED"}`**, pre-check short-circuit (no INSERT), non-23505 errors re-thrown, required-question/unknown-question/CV-ownership/consent/closed-job/past-deadline rejections, happy path inserts all 5 rows + notification.
- `tests/withdraw-application.test.ts` (7) — real `withdrawApplication`: allowed from `applied`/`offer_pending`; **refused from `hired`, `offer_accepted` (policy stricter than transition table), `rejected`, `withdrawn`**; unowned/missing application fails; no update attempted on refusal.
- `tests/duplicate-application-sql.test.ts` (4) — **ran for real** against a throwaway PostgreSQL 16 cluster (initdb + all 10 migrations applied): duplicate active application rejected by `applications_user_job_active_uniq` (23505); withdraw auto-stamps `withdrawn_at` via trigger and frees the re-apply slot; terminal lock enforced at SQL level; valid transition accepted. Skips cleanly when PG binaries are absent.

**Component (`tests/`, React Testing Library + fireEvent; server actions mocked)**
- `tests/register-form.test.tsx` (5) — renders all fields; empty/invalid submit shows inline errors (name/email/password); password mismatch error; valid submit calls the action and shows "Check your inbox"; server errors + field errors displayed.
- `tests/apply-wizard.test.tsx` (8) — step 0 renders; required question blocks Continue with "This question is required."; advances when answered; no-CV warning; consent gates submit (button disabled until checked); success shows "Application submitted" with correct payload; `ALREADY_APPLIED` and generic server errors surfaced.

**E2E (`e2e/`, written, skip-guarded, NOT runnable here)**
- `e2e/candidate.spec.ts` — register → login → upload CV → search → apply wizard → track → withdraw. Seeds org/job/confirmed candidate via service role; cleans up in `afterAll`.
- `e2e/recruiter.spec.ts` — stage move → schedule interview → feedback → offer create → approve by second admin → send → mark hired → assert `hired` stage.
- `e2e/admin.spec.ts` — control-center login → dashboard → create org → invite org admin → suspend → reactivate.
- `e2e/tenant-isolation.spec.ts` — org-A user forcing `?org=<B>` is rejected; cannot open org B's application; org B's job/applications never appear in org A's lists.

## What could NOT run, and why (no invented results)

1. **Playwright e2e (all specs): not runnable in this sandbox.**
   - No Playwright browsers are installed (`~/.cache/ms-playwright` absent; CDN download fails per foundation notes).
   - The only Chromium (`/opt/meta-chromium/chrome`, v152) enforces Local Network Access checks: every `page.goto` to the loopback dev server fails with `net::ERR_BLOCKED_BY_LOCAL_NETWORK_ACCESS_CHECKS`, even with the `--disable-features=LocalNetworkAccessChecks` launch arg already in `playwright.config.ts`. Verified 2026-10-10 against a booted `next start` server (which itself needed dummy `NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_ANON_KEY` to pass `instrumentation.ts` env validation).
   - The 4 new specs additionally require a live Supabase project (`E2E_SUPABASE_URL`, `E2E_SUPABASE_ANON_KEY`, `E2E_SUPABASE_SERVICE_ROLE_KEY`); all 11 tests skip honestly when these are absent. **Re-run `npm run test:e2e` with real credentials + working browsers before release.**
2. **No live Supabase anywhere in this environment** — auth, RLS interplay, storage signed URLs, and email remain untested against a real project (same standing limitation as foundation/modules).

## Fixes made to my own tests during the run

- `server-only` throws under jsdom: mocked it in `tests/rbac.test.ts` (the module under test is still the real `lib/rbac.ts`).
- `vi.mock` factory hoisting: switched shared fixtures to `vi.hoisted()` in the two server-action test files.
- zod v4 `uuid()` enforces RFC 4122 version/variant: fixture UUIDs updated.
- Two of my `formatSalaryRange` expectations were wrong (wrote western grouping); corrected to the true Pakistani grouping (`Rs 1,20,000`).
- SQL test: `psql -q` suppresses `RAISE NOTICE`; rewrote DO blocks to succeed silently / raise on failure. Also staged migrations into a postgres-readable temp dir (`/home/hatch` is not traversable by the `postgres` user).
- E2E specs: typed the service client as `SupabaseClient<any>` (repo has no generated DB types).

## Known gaps / follow-ups for the parent

- **Failures in others' code: none found.** `tsc`, `eslint`, `build`, and all 172 vitest tests pass. The previously reported in-progress breakages (candidate `_actions.ts` syntax error, control-center stub loop, employer `"use server"` export) appear resolved — the build is fully green.
- The new e2e specs use accessible-role selectors; a few assume specific control labels (e.g. "Move stage", "Schedule interview") — verify/adjust against the real UI on the first live run.
- Suggested next tests (not written): `lib/email.ts` unconfigured path (flagged in foundation), employer `JobForm` component, admin `NoteActionButton` required-note flow, `middleware.ts` redirect matrix.
- `tests/duplicate-application-sql.test.ts` uses port 55434 and `su postgres` when run as root; it cleans up its cluster in `afterAll`.
