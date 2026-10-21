# SeasonLens integrated formative study platform

## Participant flow

The integrated route at `/` enforces:

```text
Welcome/Consent → A → B → C → D → E → Complete
```

For new v3.1 studies, each explicit submission atomically advances to the next
section. Sections B–D expose only the configured image(s), stable material IDs,
and response fields. They never call diagnostic or hint services, and participant
projections exclude hashes, provenance, expert regions, correctness, hints, and
diagnostics. Later sections are not projected before the current submission.

The original standalone prototype remains available at `/prototype.html`. Its
item content, order, region thresholds, deterministic diagnostic, adaptive hint
logic, reveal, reflection, per-item JSON/CSV structure, and event names are
unchanged.

Existing v3 study records retain their stored researcher-assisted workflow,
including release gates and the prototype stage. New records store
`questionnaire_version=3.1`, `material_set_version=3.1`,
`study_mode=self_guided`, and `enable_prototype_stage=false`.

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

The non-destructive migrations run at process startup in a transaction and record
versions 1 and 2 in `schema_migrations`. Migration 2 adds per-study configuration
and assigns the legacy v3 configuration to existing rows. Reference SQL is in
`extensions/seasonlens/backend/migrations/`.

Study responses, materials, stage transitions, researcher sessions, prototype
snapshots, and complete prototype event histories survive application restarts.
Optimistic study versions prevent lost draft, submit, release, and configuration
updates. The server serializes in-process state-machine mutations and each
database write is transactional.

## Researcher workflow

1. Create or observe a participant study at `/`.
2. Sign in at `/researcher.html`.
3. Inspect the participant’s current stage and saved responses.
4. For new self-guided studies, no release action is needed. A release control is
   shown only for historical researcher-assisted studies that are waiting.
5. Optionally record a researcher ID, manual date, and notes.
6. Configure material metadata before its section begins. Images must use a
   project-controlled `/assets/` path, include provenance, and match their stored
   SHA-256 hash. Released material configurations are immutable.
7. Download questionnaire-only or combined JSON/CSV, XLSX, or the complete ZIP.

The ZIP contains combined and questionnaire-only datasets plus unchanged JSON and
CSV logs for any linked prototype items. A self-guided v3.1 study exports empty
prototype arrays and creates no fabricated sessions or events. Combined JSON
retains all available event arrays; flat CSV stores nested histories as JSON.

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

For a real-browser smoke test, start the server against a disposable database,
launch an installed Chromium browser with a DevTools port, and run the
dependency-free verifier:

```powershell
$env:DATABASE_URL='sqlite:///C:/absolute/path/to/seasonlens-e2e.db'
$env:SEASONLENS_RESEARCHER_USERNAME='e2e_researcher'
$env:SEASONLENS_RESEARCHER_PASSWORD='e2e-password'
python apps/api/main.py --port 8765

& 'C:\Program Files\Google\Chrome\Application\chrome.exe' --headless=new --remote-debugging-port=9223 --user-data-dir='C:\absolute\path\to\chrome-e2e-profile' --no-first-run about:blank

$env:SEASONLENS_E2E_URL='http://127.0.0.1:8765'
$env:SEASONLENS_E2E_RESEARCHER_USERNAME='e2e_researcher'
$env:SEASONLENS_E2E_RESEARCHER_PASSWORD='e2e-password'
node scripts/verify_formative_browser.mjs
```

The verifier completes two independent participant runs, validates the rendered
B-D wording and image loads, confirms the A-E-only progress indicator, signs in
to the researcher dashboard, and downloads every combined export. If the
isolated database contains a v3 record with participant ID `E2E-LEGACY`, that
historical configuration is checked too; set
`SEASONLENS_E2E_REQUIRE_LEGACY=true` to require it.
