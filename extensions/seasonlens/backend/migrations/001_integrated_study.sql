-- Reference PostgreSQL migration. The application applies the equivalent
-- idempotent migration at startup for both PostgreSQL and SQLite.
CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS prototype_sessions (session_id TEXT PRIMARY KEY, snapshot_json TEXT NOT NULL, events_json TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS studies (study_id TEXT PRIMARY KEY, participant_id TEXT NOT NULL, resume_token_hash TEXT NOT NULL, stage TEXT NOT NULL, version INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, completed_at TEXT, researcher_metadata_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS study_responses (study_id TEXT NOT NULL REFERENCES studies(study_id) ON DELETE RESTRICT, section_id TEXT NOT NULL, task_index INTEGER NOT NULL DEFAULT 0, draft_json TEXT NOT NULL, response_json TEXT, started_at TEXT NOT NULL, submitted_at TEXT, PRIMARY KEY (study_id, section_id, task_index));
CREATE TABLE IF NOT EXISTS study_materials (study_id TEXT NOT NULL REFERENCES studies(study_id) ON DELETE RESTRICT, section_id TEXT NOT NULL, task_index INTEGER NOT NULL DEFAULT 0, config_json TEXT NOT NULL, PRIMARY KEY (study_id, section_id, task_index));
CREATE TABLE IF NOT EXISTS study_events (event_id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(study_id) ON DELETE RESTRICT, event_type TEXT NOT NULL, actor_id TEXT NOT NULL, payload_json TEXT NOT NULL, recorded_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS study_prototype_sessions (study_id TEXT NOT NULL REFERENCES studies(study_id) ON DELETE RESTRICT, ordinal INTEGER NOT NULL, session_id TEXT NOT NULL UNIQUE, item_id TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (study_id, ordinal));
CREATE TABLE IF NOT EXISTS researcher_sessions (token_hash TEXT PRIMARY KEY, username TEXT NOT NULL, csrf_token TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_study_events_study ON study_events(study_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_study_sessions_study ON study_prototype_sessions(study_id, ordinal);
CREATE INDEX IF NOT EXISTS idx_researcher_session_expiry ON researcher_sessions(expires_at);
