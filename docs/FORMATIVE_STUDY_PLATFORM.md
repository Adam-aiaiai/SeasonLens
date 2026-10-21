# SeasonLens integrated formative study platform

## Participant flow

The integrated route at `/` enforces:

```text
Welcome → A → researcher release → B → researcher release → C
→ researcher release → D → researcher release
→ three existing Group C SeasonLens items → E → Complete
```

Sections B–D expose only the approved questionnaire image(s), stable material IDs,
and response fields. They never call the diagnostic or hint services and their
participant projection excludes hashes, provenance, expert regions, correctness,
hints, and diagnostics. Later sections are not projected until the researcher
releases them.

The original standalone prototype remains available at `/prototype.html`. Its
item content, order, region thresholds, deterministic diagnostic, adaptive hint
logic, reveal, reflection, per-item JSON/CSV structure, and event names are
unchanged.

## Local setup

Python 3.11 or later is required. SQLite is used by default:

```powershell
python apps/api/main.py
```

Set researcher credentials before using the dashboard. Generate a password hash:

```powershell
python scripts/hash_researcher_password.py
```

Then set:

- `SEASONLENS_RESEARCHER_USERNAME`
- `SEASONLENS_RESEARCHER_PASSWORD_HASH`

For disposable local development only, `SEASONLENS_RESEARCHER_PASSWORD` may be
used instead of a hash. Do not use that variable in production.

Open `/researcher.html` and sign in. Researcher sessions use opaque, hashed,
12-hour server-side sessions in an HttpOnly, SameSite=Strict cookie. Mutations
also require a per-session CSRF token. `?debug=1` and the former
`X-SeasonLens-Researcher` header do not authenticate a researcher.

## Persistence and migrations

`DATABASE_URL` selects storage:

- unset: `runtime-data/seasonlens.db` (SQLite);
- `sqlite:///...`: another SQLite file;
- `postgresql://...` or `postgres://...`: PostgreSQL through psycopg.

The idempotent migration runs at process startup in a transaction and records
version 1 in `schema_migrations`. The equivalent reference SQL is in
`extensions/seasonlens/backend/migrations/001_integrated_study.sql`.

Study responses, materials, stage transitions, researcher sessions, prototype
snapshots, and complete prototype event histories survive application restarts.
Optimistic study versions prevent lost draft, submit, release, and configuration
updates. The server serializes in-process state-machine mutations and each
database write is transactional.

## Researcher workflow

1. Create or observe a participant study at `/`.
2. Sign in at `/researcher.html`.
3. Inspect the participant’s current stage and saved responses.
4. Release B, C, D, and the prototype only when the study protocol permits.
5. Optionally record a researcher ID, manual date, and notes.
6. Configure material metadata before its section is released. Images must use a
   project-controlled `/assets/` path, include provenance, and match their stored
   SHA-256 hash. Released material configurations are immutable.
7. Download questionnaire-only or combined JSON/CSV, XLSX, or the complete ZIP.

The ZIP contains combined and questionnaire-only datasets plus the unchanged JSON
and CSV log for every linked prototype item. Combined JSON retains all study and
prototype event arrays; the flat CSV stores nested histories as JSON rather than
discarding them.

## Railway deployment

1. Attach a Railway PostgreSQL service and expose its `DATABASE_URL` to the app.
2. Configure `SEASONLENS_RESEARCHER_USERNAME` and
   `SEASONLENS_RESEARCHER_PASSWORD_HASH` as Railway variables.
3. Deploy the repository. `railway.json`/`Procfile` start the server on Railway’s
   `PORT`, and `/api/health` is the health check.
4. Verify the health response reports `database: postgresql` and
   `researcher_auth_configured: true`.
5. Sign in, create a non-production test study, restart the service, and verify the
   record resumes before enrolling participants.

Deployment does not require or authorize destructive migrations. Back up the
PostgreSQL service before future schema changes. This implementation has not been
deployed by the repository changes themselves.

## Verification

```powershell
python scripts/check_seasonlens.py
node --check apps/web/app.js
node --check apps/web/study.js
node --check apps/web/researcher.js
node --test apps/web/tests/*.test.cjs
npm.cmd --prefix packages/frontend-core run typecheck
```
