PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS mem_nodes (
    id            TEXT PRIMARY KEY,
    kind          TEXT NOT NULL CHECK (kind IN
                    ('session','fact','decision','action','outcome',
                     'entity','procedure','preference')),
    content       TEXT NOT NULL,
    data          TEXT,                             -- JSON, kind-specific
    confidence    REAL NOT NULL DEFAULT 1.0,
    valid_from    TEXT,                             -- ISO-8601 UTC
    valid_until   TEXT,                             -- NULL = currently valid
    recorded_at   TEXT NOT NULL,
    session_id    TEXT REFERENCES mem_nodes(id),
    namespace     TEXT NOT NULL DEFAULT 'default',
    tombstoned    INTEGER NOT NULL DEFAULT 0,
    access_count  INTEGER NOT NULL DEFAULT 0,
    last_accessed TEXT
);

CREATE TABLE IF NOT EXISTS mem_edges (
    id          TEXT PRIMARY KEY,
    src         TEXT NOT NULL REFERENCES mem_nodes(id),
    dst         TEXT NOT NULL REFERENCES mem_nodes(id),
    kind        TEXT NOT NULL CHECK (kind IN
                  ('ABOUT','OCCURRED_IN','SUPERSEDES','CONTRADICTS',
                   'CAUSED','DERIVED_FROM','TOUCHES')),
    recorded_at TEXT NOT NULL,
    data        TEXT                                -- JSON
);

CREATE TABLE IF NOT EXISTS mem_aliases (
    entity_id TEXT NOT NULL REFERENCES mem_nodes(id),
    alias     TEXT NOT NULL COLLATE NOCASE,
    PRIMARY KEY (entity_id, alias)
);

-- Phase 2: entity merge review queue (schema present now, no migration later)
CREATE TABLE IF NOT EXISTS mem_review_queue (
    id          TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    kind        TEXT NOT NULL,
    payload     TEXT NOT NULL,
    resolved    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS mem_audit (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id   TEXT NOT NULL REFERENCES mem_nodes(id),
    accessed_at TEXT NOT NULL,
    query       TEXT NOT NULL,
    score       REAL
);

CREATE INDEX IF NOT EXISTS idx_nodes_kind      ON mem_nodes(kind);
CREATE INDEX IF NOT EXISTS idx_nodes_validity  ON mem_nodes(valid_until, tombstoned);
CREATE INDEX IF NOT EXISTS idx_nodes_namespace ON mem_nodes(namespace);
CREATE INDEX IF NOT EXISTS idx_edges_src       ON mem_edges(src, kind);
CREATE INDEX IF NOT EXISTS idx_edges_dst       ON mem_edges(dst, kind);

-- FTS5 external-content table. Triggers below keep it in sync with mem_nodes.
-- content_rowid maps to the hidden integer rowid of mem_nodes (not the TEXT id).
CREATE VIRTUAL TABLE IF NOT EXISTS mem_fts USING fts5(
    content,
    content='mem_nodes',
    content_rowid='rowid'
);

-- Sync triggers: INSERT, UPDATE(content), DELETE
CREATE TRIGGER IF NOT EXISTS mem_nodes_ai AFTER INSERT ON mem_nodes BEGIN
    INSERT INTO mem_fts(rowid, content) VALUES (new.rowid, new.content);
END;

CREATE TRIGGER IF NOT EXISTS mem_nodes_au AFTER UPDATE OF content ON mem_nodes BEGIN
    INSERT INTO mem_fts(mem_fts, rowid, content) VALUES ('delete', old.rowid, old.content);
    INSERT INTO mem_fts(rowid, content) VALUES (new.rowid, new.content);
END;

CREATE TRIGGER IF NOT EXISTS mem_nodes_ad AFTER DELETE ON mem_nodes BEGIN
    INSERT INTO mem_fts(mem_fts, rowid, content) VALUES ('delete', old.rowid, old.content);
END;
