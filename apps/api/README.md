# SeasonLens MVP server

From the repository root:

```powershell
python apps/api/main.py
```

Open <http://127.0.0.1:8000>. No third-party server dependency is required for
this MVP. The API composition root imports the existing shared backend core and
the SeasonLens extension directly from their source trees.

Each mutation writes a JSON snapshot and append-only event trace to
`runtime-data/seasonlens/`. Add `?debug=1` to the web URL for researcher controls,
manual authored hint overrides, notes, reset, and JSON/CSV downloads. Researcher
endpoints (`/researcher`, `/log`, `/log.csv`, hint override, notes, reset) require
the `X-SeasonLens-Researcher: 1` header sent by that UI. This local debug gate is
not authentication; keep the default localhost binding for demonstrations.

`GET /api/items` lists public authored item views. Completing the current item
enables **Next item**, which starts a linked session for the next item without
overwriting earlier responses or logs. See [SEASONLENS_MVP.md](../../SEASONLENS_MVP.md)
for the full formative-study workflow, item schema, logging, checks, and limitations.
