# Job Recruitment And Applicant Tracking System — Module C: Employer / HR Portal (Agent C)

Date: 2026-10-10. Workspace: `/home/hatch/workspace/job-recruitment-and-applicant-tracking-system`.

Complete employer portal under `app/(employer)/` plus the invitation-acceptance
route `app/(public)/invite/[token]/`. Shared server helpers live in
`app/(employer)/_lib/`; colocated client components in `app/(employer)/_components/`;
server actions in per-route `actions.ts` files.

`npx tsc --noEmit` — clean for all `app/(employer)/**` and `app/(public)/invite/**` files.
`npx eslint` on the same — clean (0 errors, 0 warnings).
`npm run build` — compiles; page-data collection succeeds for every employer/invite
route (the only build failures observed come from other agents' in-progress
`app/(admin)` / `app/(candidate)` files, which are outside this module).

## Routes

| Route | File(s) | Notes |
| ----- | ------- | ----- |
| `/employer` | `employer/page.tsx`, `_components/DashboardFilters.tsx` | Real metrics from live queries: active/draft/pending-review jobs, total/new applications, awaiting screening, shortlisted, upcoming interviews, pending offers, hires, rejected/withdrawn, avg time-to-hire, avg time-to-first-review, fill rate, pipeline funnel. Filters: date range, department, vacancy, recruiter, stage. Definitions printed on the page. |
| `/employer/jobs` | `employer/jobs/page.tsx`, `actions.ts`, `job-schema.ts` | List with status/search filters, per-job application counts, workflow buttons (submit/review/approve/reject/publish/pause/close/archive) via `JobActions` + ConfirmDialog. |
| `/employer/jobs/new` | `employer/jobs/new/page.tsx`, `_components/JobForm.tsx` | Full RHF+zod form: title, slug (auto), department, category, location, description, responsibilities, qualifications, skills[], experience min/max, education, employment type, workplace, PKR salary min/max (min≤max enforced), period, disclosed toggle, openings, fresh-graduate flag, deadline (Asia/Karachi), benefits, instructions, questions builder (20 max). |
| `/employer/jobs/[jobId]/edit` | `employer/jobs/[jobId]/edit/page.tsx` | Same form pre-filled; editable only in draft/rejected/approved. |
| `/employer/applications` | `employer/applications/page.tsx`, `actions.ts` | Kanban board (13 pipeline stages, per-card validated move) + searchable/sortable table with bulk stage update (bounded 50, per-row validation, ConfirmDialog). Filters: vacancy, stage, recruiter, date, text. |
| `/employer/applications/[applicationId]` | `employer/applications/[applicationId]/page.tsx`, `_components/ApplicationWorkspace.tsx`, `CvViewer.tsx`, `AssignmentControl.tsx`, `StageMoveControl.tsx` | Candidate snapshot (job-related fields), CV via signed URL, answers + cover letter, structured 5-criterion rating rubric (persisted as internal `application_notes` JSON `kind='rubric'`), internal notes CRUD, candidate-visible message thread, assignments, full status-history timeline, linked interviews/offers. |
| `/employer/interviews` | `employer/interviews/page.tsx`, `actions.ts`, `_components/InterviewForm.tsx`, `InterviewActions.tsx` | Schedule (Karachi wall-clock, format, venue/genuine meeting link, interviewer multi-select, instructions), reschedule/cancel with notifications, conflict detection (same application or shared interviewer overlap → blocked), attendance (completed/no-show), structured feedback (1–5 + hire/maybe/no-hire). |
| `/employer/offers` | `employer/offers/page.tsx`, `actions.ts`, `_components/OfferForm.tsx`, `OfferActions.tsx` | Create/edit draft offers (PKR compensation, joining date, expiry, terms) → submit for approval → approve/reject by org_admin/hr_manager (≠ creator) → send (honest email result reported) → accept/decline → withdraw with reason → mark hired (creates `hiring_records` + `hired` stage, rolled back if the stage move fails). Salary visible only to org_admin/hr_manager. |
| `/employer/reports` | `employer/reports/page.tsx`, `actions.ts`, `_components/CsvDownloadButton.tsx` | Applications-by-stage, time-to-hire, applications-by-vacancy with CSV export via `lib/csv.ts` (bounded 2,000 rows, authorized columns only, audit-logged). Source stats unavailable — no source column in schema (documented on page). |
| `/employer/team` | `employer/team/page.tsx`, `actions.ts`, `_components/InviteForm.tsx`, `TeamActions.tsx` | Member list (roles, departments, titles), invite (token, role, department, expiry; honest email + shareable link), resend, revoke, change role (org_admin only; no super_admin escalation; last-admin protection), remove (deactivates membership). |
| `/invite/[token]` | `app/(public)/invite/[token]/page.tsx`, `actions.ts` | Validates token/expiry (marks expired), requires login, email-must-match guard, creates membership + `user_roles` row (rolls back membership if the role grant fails), marks invitation accepted. |
| `/employer/departments` | `employer/departments/page.tsx`, `actions.ts`, `_components/DepartmentManager.tsx` | CRUD; delete blocked while jobs/members reference the department. |
| `/employer/profile` | `employer/profile/page.tsx`, `actions.ts`, `_components/OrgProfileForm.tsx` | Org profile edit (org_admin): name, about, industry, website, contact, size, locations (stored in `organization_settings` — the `organizations` table has no location column), logo upload to `org-logos` (PNG/JPEG magic bytes, 5 MB). |
| `/employer/settings` | `employer/settings/page.tsx`, `actions.ts`, `_components/OrgSettingsForm.tsx` | `organization_settings`: max active postings, default deadline days, recruiter notify flag. Actually consumed (see below). |
| `/employer/employee/*` | `employer/employee/{page,profile,documents,requests,settings}/page.tsx`, `actions.ts`, `_components/EmployeeForms.tsx`, `EmployeeSubNav.tsx` | Minimal portal behind `platform_settings.employee_portal_enabled` (server-checked, 404 when disabled): home, profile (display name + title), documents (own uploaded docs, signed URLs), HR requests (in-app notifications to HR staff + sent-list), notification preferences. |

Layout `app/(employer)/employer/layout.tsx`: employer nav (preserves `?org=`) + org switcher.

## Workflows implemented

- **Job lifecycle** (server-enforced `JOB_TRANSITIONS` in `job-schema.ts`):
  `draft → pending_review → approved/rejected → published ⇄ paused → closed → archived`.
  Direct `draft → published` is blocked when `platform_settings.job_moderation_required`
  is true. Approvals/rejections write `job_approvals` rows. Publishing enforces the
  org's `max_active_job_postings` setting. `published_at` stamped on publish.
- **Application pipeline**: every move validated via `lib/pipeline.ts`
  (`loadPipeline` + `assertValidTransition`) before the update, then an
  `application_status_history` row (from/to/who/when/reason) and an `audit_logs`
  entry; the DB trigger enforces the same rules for direct SQL. Candidates are
  notified in-app on stage changes, messages, interviews, and offers.
- **Interviews**: scheduling auto-advances the application to `interview_scheduled`
  only when the pipeline allows it; completion advances to `interview_completed`
  likewise. Conflicts (same application, or any shared interviewer overlapping)
  block scheduling/rescheduling with a message.
- **Offers**: approval required before send unless the sender is org_admin/hr_manager;
  approver must differ from creator. Sending moves the application to
  `offer_pending` (a failed transition blocks the send — no silent skips). Email is
  attempted via `lib/email.ts` and the honest outcome is shown in the UI; in-app
  notification is primary. Withdrawing an offer from `offer_pending` moves the
  application to `rejected` with the reason recorded.

## Tenant-isolation approach

`app/(employer)/_lib/org.ts` is the single choke point:

1. `requireSessionUser()` — who is calling.
2. `getOrgContext(?org=)` — resolves the org **only from active
   `organization_memberships`** (via `getUserOrgIds`); a client-supplied `?org=`
   is accepted only when the user is an active member (super admins may pass an
   explicit existing org id). Throws `NoOrganizationError` otherwise.
3. `requireOrgRole(user.id, orgId, …)` — DB-backed role check on **every page and
   every server action** (roles read from `user_roles` + active membership).
4. Defense in depth: every query is scoped with `.eq("org_id", orgId)`, and
   resource actions re-load the row and verify `row.org_id === ctx.orgId`
   (`getOrgJob`, `getOrgApplication`, `getOrgOffer`) before mutating.
5. **hiring_manager scoping**: application/job/interview/offer lists are restricted
   to applications with an `application_assignments` row for that user
   ("assigned vacancies"); the dashboard notes the scoping.
6. Internal notes (`application_notes.is_internal=true`, incl. rubrics) are never
   queried by or exposed to the candidate module; candidate-visible communication
   goes only through `candidate_messages`. CVs: server-generated signed URLs
   (10 min) after the RBAC check — staff never get direct `cvs` bucket access.

## Definitions (also printed on the dashboard / reports pages)

- **Time to hire**: `hiring_records.hired_at − applications.submitted_at`, in days,
  averaged over hires in the selected period.
- **Time to first review**: `first application_status_history.created_at −
  submitted_at`, in days, averaged over applications in the filter set.
- **Fill rate**: hired applications in the period ÷ jobs currently `published`
  with `openings ≥ 1`. Can exceed 100% when one vacancy yields multiple hires.
- All timestamps stored UTC, displayed Asia/Karachi. Money as `Rs 85,000`
  (Pakistani grouping) via `lib/format.ts`.

## Settings actually consumed by app code

- `organization_settings.max_active_job_postings` → enforced in `transitionJob`
  when publishing (`jobs/actions.ts`).
- `organization_settings.default_deadline_days` → pre-fills the deadline in
  `JobForm` (`jobs/actions.ts#getJobFormData`).
- `organization_settings.notify_recruiters_on_new_application` → documented
  contract for the candidate module's application intake (notify org recruiters
  in-app on new applications); `locations` → rendered on the org profile page.
- `platform_settings.employee_portal_enabled` → gates the whole employee module
  server-side (`requireEmployeePortal`, 404 when disabled).

## Schema notes / deviations

- `jobs` has no `benefits`/`instructions` columns: the form captures them and
  persists them as labeled, machine-readable `<!-- BENEFITS -->` /
  `<!-- INSTRUCTIONS -->` sections inside `description` (`_lib/job-text.ts`
  round-trips them on edit).
- `jobs.skills` (text[]) is the source of truth for search; `job_skills` rows
  are also written for the normalized table.
- `organizations` has no location column: office locations live in
  `organization_settings.settings.locations`.
- `application_documents` is preferred for the CV link, falling back to
  `applications.document_id → candidate_documents`, then the candidate's current CV.
- Meeting links are stored and shown **only when genuinely provided** — never fabricated.
- Phone numbers on the application detail page are shown to recruiter+ roles only
  (documented on the page); candidate email addresses are never displayed in the
  employer portal (contact happens via in-app messaging/notifications).

## Unverifiable items (no live Supabase in this environment)

- No Supabase credentials exist here: nothing was run against a real project.
  Auth, RLS behavior, storage signed URLs, and email delivery are untested live.
- `npm run build` compiles cleanly and collects page data for every
  `/employer/*` and `/invite/[token]` route; the full build currently fails only
  on other agents' in-progress `app/(admin)` / `app/(candidate)` files
  (a `"use server"` module exporting a non-async value, since partially fixed by
  that agent). Those files were restored byte-identical after temporary
  build-validation stubs — verify with git before merging.
- Invitation emails, interview/offer notifications, and the CSV downloads were
  verified at the code level only; exercise them against a dev Supabase project.
- `scripts/validate-migrations.sh` was not re-run (migrations untouched, as required).
