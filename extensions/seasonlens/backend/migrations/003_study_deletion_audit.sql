CREATE TABLE IF NOT EXISTS study_deletion_audit (
    audit_id TEXT PRIMARY KEY,
    study_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    deleted_at TEXT NOT NULL,
    child_counts_json TEXT NOT NULL
);
