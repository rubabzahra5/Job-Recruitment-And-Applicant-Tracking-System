# Job Recruitment And Applicant Tracking System — Module B: Candidate Portal (Agent B)

Date: 2026-10-10. Workspace: `/home/hatch/workspace/job-recruitment-and-applicant-tracking-system`.

Complete candidate portal under `app/(candidate)/`. All pages and server
actions enforce `requireCandidate()` (see `app/(candidate)/_lib/candidate-guard.ts`):
`requireSessionUser()` + DB-backed `candidate` role check via `lib/rbac.ts`
(`isCandidate()` reads `user_roles`). Users holding only org roles get an
access-denied error boundary (`app/(candidate)/candidate/error.tsx`).
All data access uses the service-role client **after** authorization, with
explicit `user_id = auth.uid()` (or profile-owned) scoping on every query.
`application_notes` is never queried anywhere in this module.

`npx tsc --noEmit` — clean for all `app/(candidate)/**` files.
`npx eslint "app/(candidate)/**/*.{ts,tsx}"` — clean.
`npx vitest run` — 51/51 pass (untouched foundation tests).

## Routes

| Route | File(s) | Notes |
| ----- | ------- | ----- |
| `/candidate` | `candidate/page.tsx` | Dashboard: profile-completion %, active application count, applications-by-stage breakdown, saved-jobs count, unread-notification count, upcoming interviews (via applications), recent status-history activity. All from live DB queries. |
| `/candidate/profile` | `candidate/profile/page.tsx`, `_actions.ts`, `_schemas.ts`, `_components/ProfileForms.tsx`, `_components/ProfileLists.tsx` | Full CRUD: contact (name/headline/phone/city+province from `locations`), summary, education, experience, skills, certifications, languages, portfolio links, employment preferences (availability, expected salary PKR, notice period, searchability opt-in). Profile-strength sidebar with weighted checklist. |
| `/candidate/resume` | `candidate/resume/page.tsx`, `_actions.ts`, `_components/ResumeManager.tsx`, `download/[documentId]/route.ts` | CV upload (PDF/DOCX, 10 MB, magic-byte validation via `lib/uploads.ts`, randomized `cvs/{userId}/{uuid}.ext` paths), list, set-current, delete with retention guard, ownership-checked downloads via 2-min signed URLs. |
| `/candidate/apply/[jobSlug]` | `candidate/apply/[jobSlug]/page.tsx`, `_actions.ts`, `_components/ApplyWizard.tsx` | 4-step wizard: review job → job-specific questions → CV + cover letter → review/consent/submit → confirmation. Server: published + deadline checks, required-question validation, duplicate-active-application block (pre-check + 23505 mapping), transactional-style inserts (applications, application_answers, application_documents CV snapshot, status history, `consent_records` purpose=`job_application`), in-app notification. |
| `/candidate/applications` | `candidate/applications/page.tsx` | List with stage badges + stage filter bar with counts. |
| `/candidate/applications/[applicationId]` | `candidate/applications/[applicationId]/page.tsx`, `_actions.ts`, `_components/ApplicationActions.tsx`, `documents/[docId]/route.ts` | Job snapshot, attached docs (ownership-checked signed-URL downloads), cover letter, answers, interviews, candidate-visible message thread (candidate can post), status-history timeline, withdraw button (ConfirmDialog). |
| `/candidate/saved-jobs` | `candidate/saved-jobs/page.tsx`, `_actions.ts`, `_components/SavedJobCard.tsx` | Save/unsave list; `toggleSaveJob(jobId)` exported for reuse by public job cards. |
| `/candidate/job-alerts` | `candidate/job-alerts/page.tsx`, `_actions.ts`, `_components/AlertManager.tsx` | CRUD alerts (name + filters JSON + active toggle). Deep-link prefill for "create alert from search": `/candidate/job-alerts?from_search=1&keyword=…&city=…&category=<slug\|name>&employment_type=…`. |
| `/candidate/notifications` | `candidate/notifications/page.tsx`, `_actions.ts`, `_components/NotificationCenter.tsx` | List, mark read/unread, mark-all-read, preferences form (`notification_preferences` upsert). Honest warning when the email channel is unconfigured (`isEmailConfigured()`); in-app is stated as the primary channel. |
| `/candidate/settings` | `candidate/settings/page.tsx`, `_actions.ts`, `_components/SettingsForms.tsx` | Display name (`profiles`), email change via real Supabase `auth.updateUser` confirmation flow, password change via Supabase, session/account info, links to notification prefs + privacy. |
| `/candidate/privacy` | `candidate/privacy/page.tsx`, `_actions.ts`, `_components/PrivacyTools.tsx` | Privacy notice, JSON data export (live queries; CV bytes excluded — metadata only), deletion request (`privacy_requests` type=`deletion`, honest pending-review semantics), correction request, request history. |

Shared: `app/(candidate)/_lib/candidate-guard.ts` (auth gate, profile get-or-create,
locations, signed-URL helpers), `app/(candidate)/_lib/profile-completion.ts`
(weighted 100-point checklist), `app/(candidate)/_components/` (StageBadge,
PortalNav, SignOutButton, form-helpers incl. `zodOutputResolver` + `zodFieldErrors`).
Layout `app/(candidate)/candidate/layout.tsx`: portal shell with sidebar nav.

## Tables used

`profiles`, `candidate_profiles`, `candidate_education`, `candidate_experience`,
`candidate_skills`, `candidate_certifications`, `candidate_documents`,
`saved_jobs`, `job_alerts`, `applications`, `application_answers`,
`application_documents`, `application_status_history`, `candidate_messages`,
`notifications`, `notification_preferences`, `notification_delivery_logs`
(via `lib/notifications.ts`), `consent_records`, `privacy_requests`, `jobs`
(published only), `job_questions`, `job_categories`, `locations`,
`organizations`, `interviews`, `pipeline_stages`/`pipeline_transitions`
(withdraw validation via `lib/pipeline.ts`). Storage bucket `cvs`.

## Validation rules enforced (server-side, always; client mirrors via RHF+zod)

- Phone: `normalizePhone()` (lenient; PK `03…`/`+923…` normalized to E.164,
  other `+`-prefixed internationals accepted, blank allowed). Never required.
- City/province: city must match `locations`; province auto-derived and
  cross-checked.
- CV upload: PDF/DOCX only, extension↔magic-byte agreement, ≤10 MB
  (`lib/uploads.ts`).
- Apply: job must be `published` and before deadline; required
  `job_questions` answered; CV must belong to the candidate; one active
  application per job (partial unique index; 23505 → friendly message);
  privacy consent checkbox required.
- Withdraw: allowed only from non-terminal pre-offer stages
  (`applied`…`offer_pending`; not `offer_accepted`/`offer_declined`/`hired`/`rejected`/`withdrawn`)
  + `assertValidTransition(→withdrawn)` via `lib/pipeline.ts`; DB trigger is
  the backstop. Sets `stage='withdrawn'` (trigger stamps `withdrawn_at`) +
  history row + notification.
- CV delete: blocked when `application_documents` rows with the same
  `storage_path` belong to non-withdrawn applications (explained in the
  error); the storage object is removed only when no application snapshot
  references it, so retained applications keep working. Deleting the current
  CV promotes the newest remaining one.
- Never required: CNIC, date of birth, marital status, photo, religion.
- All display dates via `lib/format.ts` (Asia/Karachi); money via
  `formatPKR`/`formatSalaryRange`; timestamps stored as UTC timestamptz.

## Conventions / decisions

- Languages + portfolio links share `candidate_profiles.portfolio_links`
  (jsonb array): `{kind:"link",label,url}` and
  `{kind:"language",language,proficiency}`; plain strings treated as legacy
  links. Documented in code + used consistently by profile completion.
- Email is never claimed as sent when unconfigured (`lib/email.ts` contract
  honored; notifications page states this explicitly).
- `toggleSaveJob` is exported from the candidate module for the public job
  board's save buttons (Agent A/C territory).

## Unverifiable here (no live Supabase credentials in this environment)

- Nothing was run against a real Supabase project: auth flows (email/password
  change confirmation), storage uploads/signed URLs, RLS interplay, and the
  apply transaction were type-checked and logic-reviewed but not executed
  end-to-end. First integration test should exercise: sign-up → candidate role
  grant → profile → CV upload → apply → withdraw, against a dev project.
- `loadPipeline()`'s FK-hint join
  (`pipeline_transitions_from_stage_fkey`) compiles via an adapter (the
  Supabase builder isn't a real Promise, which `PipelineLoader` requires);
  verify the transition query returns rows at runtime.
- E2E browser tests not run (Playwright browsers unavailable in sandbox, per
  foundation notes).
- Cross-agent contract: public `/jobs` and `/jobs/[slug]` pages (another
  agent) should link apply CTAs to `/candidate/apply/[slug]` and may import
  `toggleSaveJob` from
  `app/(candidate)/candidate/saved-jobs/_actions.ts`; the job-alert deep link
  above is ready for their "create alert from search" button.
