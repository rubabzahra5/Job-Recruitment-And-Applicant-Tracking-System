# MODULE_SUMMARY_D — Super Admin Control Center (Agent D)

Date: 2026-10-10. Territory: `app/(admin)/control-center/` + `app/(admin)/_components/`
(shared admin chrome/helpers). Nothing outside this territory was modified.

## Routes built (17 sections + export endpoint)

| Route | Purpose |
| ----- | ------- |
| `/control-center/login` | Dedicated admin login: email+password via Supabase Auth (client), then server-side `verifyAdminLogin()` checks the super_admin grant fresh from `user_roles`; non-admins are signed out and get one generic message ("Invalid email or password, or unauthorized account") — no distinction between bad credentials and non-admin, no org internals leaked. Signed-in super admins redirect to the dashboard; signed-in non-admins are signed out + shown "unauthorized". NOTE: middleware.ts redirects *unauthenticated* visitors of `/control-center/*` to the main `/login` first (middleware is out of my territory), so this page is the authorization checkpoint + standalone fallback; documented in the page. |
| `/control-center` | Overview: real metrics (orgs, pending approvals, internal users, active/suspended accounts, candidates, active/draft vacancies, pending job approvals, applications + by-stage, scheduled interviews, pending offers, hires), recently created accounts, recent admin actions, failed/pending notification deliveries, system config checklist (env present, email configured?, storage buckets, operating mode). Date-range filter + summary CSV export. |
| `/control-center/organizations` | List (search/verification/account filters), create (RHF+zod, slug validated), verify/reject, suspend/reactivate/archive. Detail `[id]`: edit, member management (add/remove/change org role), recent jobs/applications, org-level permission notes. Suspension writes audit metadata noting the enforcement contract: public listings must filter `organizations.account_status='active'`. |
| `/control-center/users` | Search/filter (email, role, active), invite (token-based `organization_invitations`, 7-day expiry, token shown for manual delivery), direct provisioning (auth user + role + recovery link shown, no email claimed as sent), pending-invitation resend (new token shown) / revoke. Detail `[id]`: role grants + revoke, assign role (super_admin requires typed `GRANT SUPER ADMIN`), memberships, invitations, suspend/reactivate, password reset via real Supabase recovery link (shown for manual delivery, honest status), per-user audit trail. |
| `/control-center/roles` | Static role matrix: all 7 roles × capabilities, documented from the `lib/rbac.ts` rank model (employee 1 … org_admin 5; super_admin/candidate platform-wide), plus assignment rules (who can grant what). |
| `/control-center/jobs` | Cross-org moderation: filters (status/org/category/search), approve/reject with required moderation notes → `job_approvals`, publish/pause/close/archive, application counts. Detail `[id]`: posting details, applications by stage, moderation history. |
| `/control-center/applications` | Cross-org browser (org/job/stage/date filters). Stage changes via `StageChangeDialog`: only allowed next stages offered, validated by `assertValidTransition` on DB-loaded pipeline (plus the DB trigger), written to `application_status_history` and audited. |
| `/control-center/candidates` | Privacy-guarded: minimal columns only, PII masked by default; `revealCandidatePII` audit-logs the disclosure (`candidate_pii_revealed`) before returning data. Privacy-requests retention queue: in_progress/completed/rejected with notes; deletion+completed cascades the candidate profile (education/experience/skills/certs/documents); applications retained as hiring-org business records (stated in UI + audit). |
| `/control-center/interviews` | Cross-org monitoring (org/status/date filters), read-only. |
| `/control-center/offers` | Cross-org monitoring (org/status/date filters), read-only. |
| `/control-center/categories` | CRUD for `job_categories` (name/slug unique, slug format validated); delete blocked while jobs reference the category. |
| `/control-center/locations` | CRUD for `locations` (city + province unique, province CHECK = Pakistan's 7 provinces/territories); delete blocked while referenced. |
| `/control-center/approvals` | Unified queue: pending org verifications, pending jobs, pending offers — approve/reject each with required notes (→ `job_approvals` / `offer_approvals` / verification status; approved offers move to `sent`, rejected to `draft`). |
| `/control-center/reports` | CSV exports (summary, users, orgs, jobs, applications) with date filters and documented column scopes; downloads served by `/control-center/export`. |
| `/control-center/audit-logs` | Filterable (actor email, action substring, entity type, org, date range), paginated, read-only. |
| `/control-center/notifications` | Tabs: `email_templates` CRUD; delivery logs (channel/status filters) with honest retry (provider contacted only when configured; unconfigured → refused with explicit `email_unconfigured` status, nothing claims delivery); in-app notification browser. Email-unconfigured banner shown. |
| `/control-center/settings` | `platform_settings` editor: 16 keys (brand, operating_mode, currency, timezone, registration open?, employer_approval_required, job_moderation_required, application limits, CV limits/types, retention days, notification defaults, privacy/support contacts). Zod-validated, upserted, every save audited with changed keys; each field shows its "consumed by" contract note. |
| `/control-center/security` | Security events (audit_logs filtered to auth/role/suspension/PII/invitation/settings/privacy patterns), suspended-accounts list, session/revocation guidance, rate-limit guidance, honest note that failed-login signals live in the Supabase dashboard (not exposed via API). |
| `/control-center/export` (route handler) | Authorized CSV downloads (kinds: summary/users/orgs/jobs/applications), bounded at 5,000 rows via `exportScopedCsv`, every download audited (`report.exported`). |

Admin chrome: `app/(admin)/control-center/layout.tsx` renders `AdminShell` — dark sidebar nav (all 17 sections, visually distinct from the public site; responsive mobile nav), hidden on `/control-center/login`. No control-center links were added to any public navigation (public nav is out of territory anyway).

Shared pieces (colocated per instructions): `app/(admin)/_components/` — `admin-server.ts` (guards, pagination/date helpers, `asRows`, `loadPipelineAdmin`, last-admin guard, `mask`), `AdminShell.tsx`, `AdminDenied.tsx`, `filters.tsx` (URL-driven `FilterBar` + `PaginationNav`), `action-buttons.tsx` (`ConfirmActionButton`, `NoteActionButton` with RHF+zod required notes).

## Authorization approach (per page / action / route handler)

- **Every** server component calls `adminPageGuard(nextPath)` first: `requireSessionUser()` → on failure redirect to `/login?next=…`; then `requireSuperAdmin(user.id)` — a **fresh DB read of `user_roles` via the service-role client on every request** (no cached/stale role trust, no client claims). Signed-in non-admins get `AdminDeniedError` → generic "Access denied" screen (no leak of which check failed or org internals).
- **Every** server action and the export route handler call `adminContext()` (same two checks; throws `AuthorizationError` on failure — the export route maps it to 403, unauthenticated to 401). The service-role client is constructed **only after** the checks pass.
- Middleware is treated as redirect-only (per its own contract); it is never relied upon for authorization. (middleware.ts untouched — out of territory.)
- `lib/supabase/admin.ts` (server-only) is imported only in server code (`admin-server.ts`, actions, route handler, login page/action). No service-role key reaches client components.
- **Last-active-super-admin guard** (`ensureNotLastActiveSuperAdmin`): refusing to revoke the super_admin grant or suspend the account of the final active super admin (active = grant present AND `profiles.is_active`). Also blocks self-suspension.
- **Audit**: every mutating action writes `audit_logs` via `lib/audit.ts` (actor, action, entity, org, metadata) — org verify/suspend/archive, member add/remove/role change, role grant/revoke, user suspend/reactivate/provision, password-reset initiation, invitation create/resend/revoke, job approve/reject/status, application stage change, candidate PII reveal, privacy-request decisions, category/location CRUD, template CRUD, delivery retry (incl. refusals), settings saves, report exports, admin logins.
- Destructive/privileged UI uses `ConfirmDialog`; moderation decisions use `NoteActionButton` (required zod-validated note stored with the decision).

## Settings → code consumption map

Verified 2026-10-10 by grepping all of `app/`, `lib/`, `scripts/` for `platform_settings`, `operating_mode`, `job_moderation_required`, `employer_approval_required`: **no route or lib code reads `platform_settings` yet** (only migrations/RLS reference the table). The employer/candidate/public agents are building those paths concurrently, so each setting's "consumed by" note in `settings/settings-spec.ts` is documented as the **contract** they should honor:

| Setting | Contract for consumer agents |
| ------- | ---------------------------- |
| `operating_mode` (centralized\|internal) | Employer onboarding: centralized = public org registration → `verification_status='pending'` → Approvals queue; internal = single-org private mode. Public org directory visibility. |
| `job_moderation_required` (bool) | Employer job submit: when true → `jobs.status='pending_review'` (Approvals queue); when false → publish directly. |
| `employer_approval_required` (bool) | New org registration → pending verification when true. |
| `registration_open` (bool) | Candidate/employer registration pages gate. |
| `platform_name` | Public header/footer, email templates, titles. |
| `currency` / `timezone` | Salary display (`lib/format.ts` CURRENCY) / all display + interview scheduling (`DISPLAY_TIMEZONE`). |
| `max_active_applications_per_candidate` | Candidate apply flow cap (alongside DB partial-unique index). |
| `cv_max_file_mb`, `cv_allowed_types` | CV uploads (`lib/uploads.ts` caps + magic-byte/extension checks). |
| `data_retention_days` | Retention processing; candidates privacy queue. |
| `notify_on_new_application`, `notify_on_stage_change` | Notification fan-out defaults (`lib/notifications.ts`). |
| `privacy_contact_email`, `support_email`, `support_phone` | Privacy pages, public footer/contact. |

Settings UI persists to `platform_settings` (key → JSON value) with zod validation and audit; the settings page itself displays a banner stating the "not yet consumed" verification status.

## Verification performed

- `npx tsc --noEmit` — clean for all of `app/(admin)` (strict + `noUncheckedIndexedAccess`).
- `npx eslint "app/(admin)/**/*.{ts,tsx}"` — clean (exit 0).
- `npm run build` — compiles successfully including all control-center routes; the build's page-data collection step currently fails on **`/employer/applications`** (`"use server" file can only export async functions` — the employer agent's file, out of my territory, not modified by me).

## Unverifiable items (no live Supabase credentials in this environment)

- No queries were executed against a real database: all metrics, filters, mutations, CSV exports, and the recovery-link/invitation flows are **code-complete but untested against live Supabase** (auth, RLS interplay, storage bucket listing, `generateLink`, `createUser`).
- Email: `RESEND_API_KEY`/`EMAIL_FROM_ADDRESS` absent here; only the honest unconfigured path (`sent:false`, "email unconfigured" UI) could be reasoned about, not the send path.
- E2E: not run (Playwright browsers unavailable in this sandbox per foundation notes); the login→dashboard and action flows need manual verification against a dev project.
- `scripts/bootstrap-admin.ts` (first super admin provisioning) was not executed — the control center is unreachable until it is.

## Known gaps / open items for the parent

1. **Suspension enforcement gap (documented, not fixed — `lib/auth.ts` out of territory):** suspending a user sets `profiles.is_active=false`, but `requireSessionUser()` does not re-check `is_active` per request and middleware doesn't check it either. Sign-in is blocked (no new session), but hardening per-request checks belongs to the foundation owner. Surfaced honestly on the Users and Security pages.
2. **Public-listing suspension contract:** suspending an org hides its jobs only if public/employer queries filter `organizations.account_status='active'` — flagged in audit metadata, org pages, and here for the public/jobs agents to implement.
3. **`platform_settings` consumers:** none exist yet (see map above); consumer agents must read the contract.
4. **ACTIVE write collision with Agent C (unresolved — needs parent intervention):** `app/(admin)/control-center/candidates/actions.ts` was replaced **four times** during this session by a stub authored by Agent C ("TEMPORARY BUILD STUB — replaced during Agent C's build validation"). The original cause was real — my first version exported a non-async `mask()` from a `"use server"` file — but the stub kept being re-applied (roughly every minute, last observed 10:47 UTC) even after I fixed the violation and restored the full, build-clean implementation. Each restore verified `tsc`/`eslint` clean. I restored the complete implementation a final time at handoff; **if the file is a stub when you read this, restore it from the full implementation documented in my report history — the logic is: `revealCandidatePII` (audit-logged PII reveal) and `processPrivacyRequest` (in_progress/completed/rejected + cascade delete on deletion+completed)**. Please ask Agent C to stop the stubbing loop and fix their own `/employer/applications` server-action export instead (that file is what currently breaks `npm run build`).
5. **Login reachability:** `middleware.ts` (untouchable) redirects unauthenticated `/control-center/*` visitors to the main `/login`; the dedicated `/control-center/login` therefore acts as the super-admin checkpoint/fallback rather than the first touchpoint. Documented in the page.
6. **Failed-login signal:** not available via Supabase JS admin API — dashboard-only; documented on the Security page.
7. Session revocation for suspended users requires the Supabase dashboard (no "revoke all sessions" in the JS admin API used here); documented.
8. Other agents' in-progress type errors exist under `app/(candidate)` and `app/(employer)` — untouched (out of territory).
