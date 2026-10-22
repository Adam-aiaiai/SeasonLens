from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Iterator
from uuid import uuid4

from shared_platform import Actor, ActorType, EventEnvelope, StateSnapshot


LEGACY_STUDY_CONFIG = {
    "instrument_id": "SeasonLens_Formative_Participant_Questionnaire_v3_Bilingual",
    "questionnaire_version": 3,
    "material_set_version": 3,
    "study_mode": "researcher_assisted",
    "enable_prototype_stage": True,
}


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class PersistentRepository:
    """Small transactional repository supporting SQLite and Railway PostgreSQL.

    The PostgreSQL driver is imported only when a postgres URL is configured so the
    standard-library-only local test environment remains usable.
    """

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._lock = RLock()
        self._postgres = database_url.startswith(("postgres://", "postgresql://"))
        if self._postgres:
            try:
                import psycopg  # type: ignore
            except ImportError as error:  # pragma: no cover - production dependency
                raise RuntimeError("psycopg is required when DATABASE_URL uses PostgreSQL.") from error
            self._connection = psycopg.connect(database_url)
        else:
            path = self._sqlite_path(database_url)
            if str(path) != ":memory:":
                path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(str(path), check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA journal_mode = WAL")
        self.migrate()

    @staticmethod
    def _sqlite_path(database_url: str) -> Path:
        if database_url in {"sqlite:///:memory:", ":memory:"}:
            return Path(":memory:")
        if database_url.startswith("sqlite:///"):
            return Path(database_url.removeprefix("sqlite:///")).resolve()
        return Path(database_url).resolve()

    def _sql(self, statement: str) -> str:
        return statement.replace("?", "%s") if self._postgres else statement

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        with self._lock:
            cursor = self._connection.cursor()
            try:
                yield cursor
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
            finally:
                cursor.close()

    def migrate(self) -> None:
        statements = [
            "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)",
            """CREATE TABLE IF NOT EXISTS prototype_sessions (
                session_id TEXT PRIMARY KEY, snapshot_json TEXT NOT NULL,
                events_json TEXT NOT NULL, updated_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS studies (
                study_id TEXT PRIMARY KEY, participant_id TEXT NOT NULL,
                resume_token_hash TEXT NOT NULL, stage TEXT NOT NULL,
                version INTEGER NOT NULL, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, completed_at TEXT,
                researcher_metadata_json TEXT NOT NULL,
                config_json TEXT NOT NULL DEFAULT '{}'
            )""",
            """CREATE TABLE IF NOT EXISTS study_responses (
                study_id TEXT NOT NULL, section_id TEXT NOT NULL,
                task_index INTEGER NOT NULL DEFAULT 0, draft_json TEXT NOT NULL,
                response_json TEXT, started_at TEXT NOT NULL, submitted_at TEXT,
                PRIMARY KEY (study_id, section_id, task_index),
                FOREIGN KEY (study_id) REFERENCES studies(study_id) ON DELETE RESTRICT
            )""",
            """CREATE TABLE IF NOT EXISTS study_materials (
                study_id TEXT NOT NULL, section_id TEXT NOT NULL,
                task_index INTEGER NOT NULL DEFAULT 0, config_json TEXT NOT NULL,
                PRIMARY KEY (study_id, section_id, task_index),
                FOREIGN KEY (study_id) REFERENCES studies(study_id) ON DELETE RESTRICT
            )""",
            """CREATE TABLE IF NOT EXISTS study_events (
                event_id TEXT PRIMARY KEY, study_id TEXT NOT NULL,
                event_type TEXT NOT NULL, actor_id TEXT NOT NULL,
                payload_json TEXT NOT NULL, recorded_at TEXT NOT NULL,
                FOREIGN KEY (study_id) REFERENCES studies(study_id) ON DELETE RESTRICT
            )""",
            """CREATE TABLE IF NOT EXISTS study_prototype_sessions (
                study_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
                session_id TEXT NOT NULL UNIQUE, item_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (study_id, ordinal),
                FOREIGN KEY (study_id) REFERENCES studies(study_id) ON DELETE RESTRICT
            )""",
            """CREATE TABLE IF NOT EXISTS researcher_sessions (
                token_hash TEXT PRIMARY KEY, username TEXT NOT NULL,
                csrf_token TEXT NOT NULL, created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS study_deletion_audit (
                audit_id TEXT PRIMARY KEY, study_id TEXT NOT NULL,
                actor_id TEXT NOT NULL, stage TEXT NOT NULL,
                deleted_at TEXT NOT NULL, child_counts_json TEXT NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_study_events_study ON study_events(study_id, recorded_at)",
            "CREATE INDEX IF NOT EXISTS idx_study_sessions_study ON study_prototype_sessions(study_id, ordinal)",
            "CREATE INDEX IF NOT EXISTS idx_researcher_session_expiry ON researcher_sessions(expires_at)",
        ]
        with self.transaction() as cursor:
            for statement in statements:
                cursor.execute(statement)
            if self._postgres:
                cursor.execute("""SELECT 1 FROM information_schema.columns
                    WHERE table_name='studies' AND column_name='config_json'""")
                has_config = cursor.fetchone() is not None
            else:
                cursor.execute("PRAGMA table_info(studies)")
                has_config = any(row[1] == "config_json" for row in cursor.fetchall())
            if not has_config:
                cursor.execute("ALTER TABLE studies ADD COLUMN config_json TEXT NOT NULL DEFAULT '{}'")
            cursor.execute(self._sql(
                "UPDATE studies SET config_json=? WHERE config_json IS NULL OR config_json='' OR config_json='{}'"
            ), (_json(LEGACY_STUDY_CONFIG),))
            cursor.execute(self._sql(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?) "
                "ON CONFLICT(version) DO NOTHING"
            ), (1, datetime.now(timezone.utc).isoformat()))
            cursor.execute(self._sql(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?) "
                "ON CONFLICT(version) DO NOTHING"
            ), (2, datetime.now(timezone.utc).isoformat()))
            cursor.execute(self._sql(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?) "
                "ON CONFLICT(version) DO NOTHING"
            ), (3, datetime.now(timezone.utc).isoformat()))

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @staticmethod
    def _row(cursor: Any) -> dict[str, Any] | None:
        row = cursor.fetchone()
        if row is None:
            return None
        if isinstance(row, sqlite3.Row):
            return dict(row)
        names = [entry.name if hasattr(entry, "name") else entry[0] for entry in cursor.description]
        return dict(zip(names, row, strict=True))

    @staticmethod
    def _rows(cursor: Any) -> list[dict[str, Any]]:
        rows = cursor.fetchall()
        if not rows:
            return []
        if isinstance(rows[0], sqlite3.Row):
            return [dict(row) for row in rows]
        names = [entry.name if hasattr(entry, "name") else entry[0] for entry in cursor.description]
        return [dict(zip(names, row, strict=True)) for row in rows]

    def save_prototype_session(self, snapshot: StateSnapshot, events: list[dict[str, Any]], updated_at: str) -> None:
        value = {"extension_id": snapshot.extension_id, "aggregate_id": snapshot.aggregate_id,
                 "version": snapshot.version, "data": snapshot.data}
        with self.transaction() as cursor:
            cursor.execute(self._sql("""INSERT INTO prototype_sessions
                (session_id, snapshot_json, events_json, updated_at) VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET snapshot_json=excluded.snapshot_json,
                events_json=excluded.events_json, updated_at=excluded.updated_at"""),
                (snapshot.aggregate_id, _json(value), _json(events), updated_at))

    def load_prototype_session(self, session_id: str) -> tuple[StateSnapshot, list[EventEnvelope]] | None:
        with self.transaction() as cursor:
            cursor.execute(self._sql("SELECT snapshot_json, events_json FROM prototype_sessions WHERE session_id=?"),
                           (session_id,))
            row = self._row(cursor)
        if not row:
            return None
        raw = json.loads(row["snapshot_json"])
        snapshot = StateSnapshot(raw["extension_id"], raw["aggregate_id"], raw["version"], raw["data"])
        events = []
        for value in json.loads(row["events_json"]):
            events.append(EventEnvelope(
                session_id=value["session_id"], extension_id=value["extension_id"],
                aggregate_id=value["aggregate_id"], aggregate_version=value["aggregate_version"],
                actor=Actor(ActorType(value["actor"]["actor_type"]), value["actor"]["actor_id"]),
                event_type=value["event_type"], payload=value["payload"],
                correlation_id=value["correlation_id"], causation_id=value.get("causation_id"),
                event_id=value["event_id"], recorded_at=datetime.fromisoformat(value["recorded_at"]),
            ))
        return snapshot, events

    def create_study(self, study: dict[str, Any], materials: dict[str, Any], event: dict[str, Any]) -> None:
        with self.transaction() as cursor:
            cursor.execute(self._sql("""INSERT INTO studies
                (study_id, participant_id, resume_token_hash, stage, version, created_at,
                 updated_at, completed_at, researcher_metadata_json, config_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""),
                (study["study_id"], study["participant_id"], study["resume_token_hash"], study["stage"],
                 study["version"], study["created_at"], study["updated_at"], None, _json({}),
                 _json(study["config"])))
            cursor.execute(self._sql("""INSERT INTO study_responses
                (study_id, section_id, task_index, draft_json, response_json, started_at, submitted_at)
                VALUES (?, 'A', 0, '{}', NULL, ?, NULL)"""), (study["study_id"], study["created_at"]))
            for section_id, config in materials.items():
                cursor.execute(self._sql("""INSERT INTO study_materials
                    (study_id, section_id, task_index, config_json) VALUES (?, ?, 0, ?)"""),
                    (study["study_id"], section_id, _json(config)))
            self._insert_event(cursor, event)

    def get_study(self, study_id: str) -> dict[str, Any] | None:
        with self.transaction() as cursor:
            cursor.execute(self._sql("SELECT * FROM studies WHERE study_id=?"), (study_id,))
            study = self._row(cursor)
            if not study:
                return None
            cursor.execute(self._sql("SELECT * FROM study_responses WHERE study_id=? ORDER BY section_id, task_index"),
                           (study_id,))
            responses = self._rows(cursor)
            cursor.execute(self._sql("SELECT * FROM study_materials WHERE study_id=? ORDER BY section_id, task_index"),
                           (study_id,))
            materials = self._rows(cursor)
            cursor.execute(self._sql("SELECT * FROM study_prototype_sessions WHERE study_id=? ORDER BY ordinal"),
                           (study_id,))
            sessions = self._rows(cursor)
        study["researcher_metadata"] = json.loads(study.pop("researcher_metadata_json"))
        study["config"] = json.loads(study.pop("config_json"))
        study["responses"] = [{**row, "draft": json.loads(row.pop("draft_json")),
                               "response": json.loads(row.pop("response_json")) if row["response_json"] else None}
                              for row in responses]
        study["materials"] = [{**row, "config": json.loads(row.pop("config_json"))} for row in materials]
        study["prototype_sessions"] = sessions
        return study

    def list_studies(self) -> list[dict[str, Any]]:
        with self.transaction() as cursor:
            cursor.execute("""SELECT s.study_id, s.participant_id, s.stage, s.version, s.created_at,
                s.updated_at, s.completed_at, COUNT(p.session_id) AS prototype_session_count
                FROM studies s LEFT JOIN study_prototype_sessions p ON p.study_id=s.study_id
                GROUP BY s.study_id, s.participant_id, s.stage, s.version, s.created_at,
                s.updated_at, s.completed_at ORDER BY s.created_at DESC""")
            return self._rows(cursor)

    def delete_study(self, study_id: str, actor_id: str, deleted_at: str) -> dict[str, Any]:
        """Hard-delete one study and its linked research data in one transaction."""
        with self.transaction() as cursor:
            cursor.execute(self._sql("SELECT stage FROM studies WHERE study_id=?"), (study_id,))
            study = self._row(cursor)
            if not study:
                raise ValueError("Study not found or already deleted.")

            cursor.execute(self._sql(
                "SELECT session_id FROM study_prototype_sessions WHERE study_id=? ORDER BY ordinal"
            ), (study_id,))
            session_ids = [row["session_id"] for row in self._rows(cursor)]
            counts: dict[str, int] = {"prototype_sessions": len(session_ids)}
            for table, key in (("study_responses", "responses"), ("study_materials", "materials"),
                               ("study_events", "events")):
                cursor.execute(self._sql(f"SELECT COUNT(*) AS total FROM {table} WHERE study_id=?"),
                               (study_id,))
                counts[key] = int(self._row(cursor)["total"])

            cursor.execute(self._sql("DELETE FROM study_prototype_sessions WHERE study_id=?"), (study_id,))
            for session_id in session_ids:
                cursor.execute(self._sql("DELETE FROM prototype_sessions WHERE session_id=?"), (session_id,))
            cursor.execute(self._sql("DELETE FROM study_events WHERE study_id=?"), (study_id,))
            cursor.execute(self._sql("DELETE FROM study_responses WHERE study_id=?"), (study_id,))
            cursor.execute(self._sql("DELETE FROM study_materials WHERE study_id=?"), (study_id,))
            cursor.execute(self._sql("DELETE FROM studies WHERE study_id=?"), (study_id,))
            if cursor.rowcount != 1:
                raise ValueError("Study not found or already deleted.")
            cursor.execute(self._sql("""INSERT INTO study_deletion_audit
                (audit_id, study_id, actor_id, stage, deleted_at, child_counts_json)
                VALUES (?, ?, ?, ?, ?, ?)"""),
                (str(uuid4()), study_id, actor_id, study["stage"], deleted_at, _json(counts)))
            return {"study_id": study_id, "deleted": True, "deleted_at": deleted_at,
                    "deleted_records": counts}

    def update_draft(self, study_id: str, section_id: str, draft: dict[str, Any],
                     expected_version: int, updated_at: str, event: dict[str, Any]) -> bool:
        with self.transaction() as cursor:
            cursor.execute(self._sql("""UPDATE studies SET version=version+1, updated_at=?
                WHERE study_id=? AND version=? AND stage=?"""),
                (updated_at, study_id, expected_version, section_id))
            if cursor.rowcount != 1:
                return False
            cursor.execute(self._sql("""UPDATE study_responses SET draft_json=?
                WHERE study_id=? AND section_id=? AND task_index=0"""),
                (_json(draft), study_id, section_id))
            self._insert_event(cursor, event)
            return True

    def submit_section(self, study_id: str, section_id: str, response: dict[str, Any],
                       next_stage: str, expected_version: int, submitted_at: str,
                       event: dict[str, Any]) -> bool:
        with self.transaction() as cursor:
            cursor.execute(self._sql("""UPDATE studies SET stage=?, version=version+1, updated_at=?,
                completed_at=CASE WHEN ?='COMPLETE' THEN ? ELSE completed_at END
                WHERE study_id=? AND version=? AND stage=?"""),
                (next_stage, submitted_at, next_stage, submitted_at, study_id, expected_version, section_id))
            if cursor.rowcount != 1:
                return False
            cursor.execute(self._sql("""UPDATE study_responses SET draft_json=?, response_json=?, submitted_at=?
                WHERE study_id=? AND section_id=? AND task_index=0"""),
                (_json(response), _json(response), submitted_at, study_id, section_id))
            if next_stage in {"B", "C", "D", "E"}:
                cursor.execute(self._sql("""INSERT INTO study_responses
                    (study_id, section_id, task_index, draft_json, response_json, started_at, submitted_at)
                    VALUES (?, ?, 0, '{}', NULL, ?, NULL)
                    ON CONFLICT(study_id, section_id, task_index) DO NOTHING"""),
                    (study_id, next_stage, submitted_at))
            self._insert_event(cursor, event)
            return True

    def release_stage(self, study_id: str, wait_stage: str, section_id: str,
                      expected_version: int, released_at: str, event: dict[str, Any]) -> bool:
        with self.transaction() as cursor:
            cursor.execute(self._sql("""UPDATE studies SET stage=?, version=version+1, updated_at=?
                WHERE study_id=? AND version=? AND stage=?"""),
                (section_id, released_at, study_id, expected_version, wait_stage))
            if cursor.rowcount != 1:
                return False
            if section_id in {"B", "C", "D", "E"}:
                cursor.execute(self._sql("""INSERT INTO study_responses
                    (study_id, section_id, task_index, draft_json, response_json, started_at, submitted_at)
                    VALUES (?, ?, 0, '{}', NULL, ?, NULL) ON CONFLICT(study_id, section_id, task_index) DO NOTHING"""),
                    (study_id, section_id, released_at))
            self._insert_event(cursor, event)
            return True

    def add_prototype_session(self, study_id: str, ordinal: int, session_id: str,
                              item_id: str, created_at: str, event: dict[str, Any]) -> None:
        with self.transaction() as cursor:
            cursor.execute(self._sql("""INSERT INTO study_prototype_sessions
                (study_id, ordinal, session_id, item_id, created_at) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(study_id, ordinal) DO NOTHING"""),
                (study_id, ordinal, session_id, item_id, created_at))
            self._insert_event(cursor, event)

    def study_for_session(self, session_id: str) -> dict[str, Any] | None:
        with self.transaction() as cursor:
            cursor.execute(self._sql("""SELECT p.study_id, p.ordinal, s.stage, s.version
                FROM study_prototype_sessions p JOIN studies s ON s.study_id=p.study_id
                WHERE p.session_id=?"""), (session_id,))
            return self._row(cursor)

    def transition_study(self, study_id: str, from_stage: str, to_stage: str,
                         expected_version: int, at: str, event: dict[str, Any]) -> bool:
        with self.transaction() as cursor:
            cursor.execute(self._sql("""UPDATE studies SET stage=?, version=version+1, updated_at=?
                WHERE study_id=? AND stage=? AND version=?"""),
                (to_stage, at, study_id, from_stage, expected_version))
            if cursor.rowcount != 1:
                return False
            if to_stage == "E":
                cursor.execute(self._sql("""INSERT INTO study_responses
                    (study_id, section_id, task_index, draft_json, response_json, started_at, submitted_at)
                    VALUES (?, 'E', 0, '{}', NULL, ?, NULL)
                    ON CONFLICT(study_id, section_id, task_index) DO NOTHING"""), (study_id, at))
            self._insert_event(cursor, event)
            return True

    def update_researcher_metadata(self, study_id: str, metadata: dict[str, Any],
                                   expected_version: int, at: str, event: dict[str, Any]) -> bool:
        with self.transaction() as cursor:
            cursor.execute(self._sql("""UPDATE studies SET researcher_metadata_json=?, version=version+1,
                updated_at=? WHERE study_id=? AND version=?"""),
                (_json(metadata), at, study_id, expected_version))
            if cursor.rowcount != 1:
                return False
            self._insert_event(cursor, event)
            return True

    def update_material(self, study_id: str, section_id: str, config: dict[str, Any],
                        expected_version: int, at: str, event: dict[str, Any]) -> bool:
        with self.transaction() as cursor:
            cursor.execute(self._sql("""UPDATE studies SET version=version+1, updated_at=?
                WHERE study_id=? AND version=?"""), (at, study_id, expected_version))
            if cursor.rowcount != 1:
                return False
            cursor.execute(self._sql("""UPDATE study_materials SET config_json=?
                WHERE study_id=? AND section_id=? AND task_index=0"""),
                (_json(config), study_id, section_id))
            self._insert_event(cursor, event)
            return True

    def events_for_study(self, study_id: str) -> list[dict[str, Any]]:
        with self.transaction() as cursor:
            cursor.execute(self._sql("SELECT * FROM study_events WHERE study_id=? ORDER BY recorded_at, event_id"),
                           (study_id,))
            rows = self._rows(cursor)
        return [{**row, "payload": json.loads(row.pop("payload_json"))} for row in rows]

    def create_researcher_session(self, token_hash: str, username: str, csrf_token: str,
                                  created_at: str, expires_at: str) -> None:
        with self.transaction() as cursor:
            cursor.execute(self._sql("""INSERT INTO researcher_sessions
                (token_hash, username, csrf_token, created_at, expires_at) VALUES (?, ?, ?, ?, ?)"""),
                (token_hash, username, csrf_token, created_at, expires_at))

    def researcher_session(self, token_hash: str, now: str) -> dict[str, Any] | None:
        with self.transaction() as cursor:
            cursor.execute(self._sql("DELETE FROM researcher_sessions WHERE expires_at <= ?"), (now,))
            cursor.execute(self._sql("SELECT * FROM researcher_sessions WHERE token_hash=? AND expires_at>?"),
                           (token_hash, now))
            return self._row(cursor)

    def delete_researcher_session(self, token_hash: str) -> None:
        with self.transaction() as cursor:
            cursor.execute(self._sql("DELETE FROM researcher_sessions WHERE token_hash=?"), (token_hash,))

    def _insert_event(self, cursor: Any, event: dict[str, Any]) -> None:
        cursor.execute(self._sql("""INSERT INTO study_events
            (event_id, study_id, event_type, actor_id, payload_json, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?)"""),
            (event["event_id"], event["study_id"], event["event_type"], event["actor_id"],
             _json(event.get("payload", {})), event["recorded_at"]))
