# SeasonLens integrated study server

From the repository root:

```powershell
python apps/api/main.py
```

Open <http://127.0.0.1:8000>. SQLite is used locally unless `DATABASE_URL` selects
PostgreSQL. The API composition root imports the shared backend core and SeasonLens
extension directly from their source trees.

The integrated participant route is `/`, the backward-compatible standalone
prototype is `/prototype.html`, and the authenticated researcher dashboard is
`/researcher.html`. Configure `SEASONLENS_RESEARCHER_USERNAME` and
`SEASONLENS_RESEARCHER_PASSWORD_HASH`; the old debug header is not accepted.

New integrated studies use questionnaire/material version 3.1 and progress
self-guided through A→B→C→D→E. Existing version 3 studies retain their stored
researcher-assisted prototype workflow. The researcher dashboard remains available
for inspection, notes, material provenance, and exports; it is not needed for new
participant progression.

`GET /api/items` lists public authored item views. Completing the current item
enables **Next item**, which starts a linked session for the next item without
overwriting earlier responses or logs. See [SEASONLENS_MVP.md](../../SEASONLENS_MVP.md)
for the prototype item schema and logging. See
[FORMATIVE_STUDY_PLATFORM.md](../../docs/FORMATIVE_STUDY_PLATFORM.md) for database,
authentication, migration, export, researcher, and Railway instructions.
