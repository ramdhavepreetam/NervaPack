"""SQLite-backed memory store with bi-temporal semantics and FTS5 search."""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def _fts_variants(query: str) -> list[str]:
    """
    Return FTS5 query variants to try in order: exact phrase, prefix on each token,
    and individual tokens (OR). Handles partial matches like 'timeline_v'.
    """
    safe = query.replace('"', '""').strip()
    if not safe:
        return []
    tokens = safe.split()
    variants = [safe]
    # Prefix: append * to each token
    prefix_q = " ".join(t + "*" for t in tokens)
    if prefix_q != safe:
        variants.append(prefix_q)
    # OR fallback for multi-token queries
    if len(tokens) > 1:
        variants.append(" OR ".join(tokens))
    return variants


_KIND_PREFIXES: dict[str, str] = {
    "session": "s",
    "fact": "f",
    "decision": "d",
    "action": "a",
    "outcome": "o",
    "entity": "e",
    "procedure": "p",
    "preference": "pr",
}

_EDGE_KINDS = frozenset(
    {"ABOUT", "OCCURRED_IN", "SUPERSEDES", "CONTRADICTS", "CAUSED", "DERIVED_FROM", "TOUCHES"}
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _make_id(kind: str) -> str:
    """Generate a time-sortable prefixed id (ULID-compatible without external dep)."""
    prefix = _KIND_PREFIXES.get(kind, "n")
    # Encode millisecond timestamp (10 chars) + random hex (16 chars) to get ~26-char body
    ts_ms = int(time.time() * 1000)
    rand = uuid.uuid4().hex[:16]
    body = f"{ts_ms:013x}{rand}"
    return f"{prefix}_{body}"


def _resolve_db_path(db_path: str | None = None) -> Path:
    """Locate the memory DB: env var > explicit arg > project-local > home."""
    if db_path:
        return Path(db_path)
    env = os.environ.get("NERVAPACK_MEMORY_DB")
    if env:
        return Path(env)
    # Walk up from cwd looking for .nervapack/
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / ".nervapack"
        if candidate.is_dir():
            return candidate / "memory.db"
    home_dir = Path.home() / ".nervapack"
    home_dir.mkdir(parents=True, exist_ok=True)
    return home_dir / "memory.db"


# Canonical validity SQL fragment (reused everywhere to prevent drift)
_VALID_NOW = """
    tombstoned = 0
    AND valid_until IS NULL
    AND id NOT IN (
        SELECT dst FROM mem_edges WHERE kind = 'SUPERSEDES'
        AND src IN (
            SELECT id FROM mem_nodes WHERE tombstoned = 0 AND valid_until IS NULL
        )
    )
""".strip()


def _valid_at(alias: str = "n") -> str:
    """Validity predicate for a specific point in time (parametrized)."""
    return f"""
        {alias}.tombstoned = 0
        AND ({alias}.valid_from IS NULL OR {alias}.valid_from <= :as_of)
        AND ({alias}.valid_until IS NULL OR {alias}.valid_until > :as_of)
    """.strip()


class MemoryStore:
    """CRUD, supersede, temporal queries, and FTS sync over the memory SQLite db."""

    def __init__(self, db_path: str | None = None, namespace: str = "default") -> None:
        self.db_path = _resolve_db_path(db_path)
        self.namespace = namespace
        self._conn: sqlite3.Connection | None = None

    # ── Connection ─────────────────────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._apply_schema(conn)
            self._conn = conn
        return self._conn

    def _apply_schema(self, conn: sqlite3.Connection) -> None:
        schema_path = Path(__file__).parent / "schema.sql"
        sql = schema_path.read_text()
        # executescript handles multi-statement DDL including triggers (which contain
        # semicolons that would break naive split). It auto-commits first.
        conn.executescript(sql)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Core node operations ────────────────────────────────────────────────────

    def add_node(
        self,
        kind: str,
        content: str,
        data: dict[str, Any] | None = None,
        confidence: float = 1.0,
        valid_from: str | None = None,
        session_id: str | None = None,
        node_id: str | None = None,
    ) -> str:
        """Insert a new node; return its id."""
        conn = self._get_conn()
        nid = node_id or _make_id(kind)
        now = _now_iso()
        conn.execute(
            """
            INSERT INTO mem_nodes
                (id, kind, content, data, confidence, valid_from, recorded_at,
                 session_id, namespace)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                nid,
                kind,
                content,
                json.dumps(data) if data else None,
                confidence,
                valid_from or now,
                now,
                session_id,
                self.namespace,
            ),
        )
        conn.commit()
        return nid

    def add_edge(
        self,
        src: str,
        dst: str,
        kind: str,
        data: dict[str, Any] | None = None,
    ) -> str:
        """Insert an edge; return its id."""
        if kind not in _EDGE_KINDS:
            raise ValueError(f"Unknown edge kind: {kind!r}")
        conn = self._get_conn()
        eid = _make_id("action")  # edges share id space without a special prefix
        eid = f"edge_{uuid.uuid4().hex[:16]}"
        conn.execute(
            "INSERT INTO mem_edges (id, src, dst, kind, recorded_at, data) VALUES (?,?,?,?,?,?)",
            (eid, src, dst, kind, _now_iso(), json.dumps(data) if data else None),
        )
        conn.commit()
        return eid

    def supersede(self, new_id: str, old_id: str) -> None:
        """Close old node's valid_until and add a SUPERSEDES edge (new → old)."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE mem_nodes SET valid_until = ? WHERE id = ?",
            (_now_iso(), old_id),
        )
        self.add_edge(new_id, old_id, "SUPERSEDES")
        conn.commit()

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM mem_nodes WHERE id = ?", (node_id,)
        ).fetchone()
        return dict(row) if row is not None else None

    def update_node(self, node_id: str, **kwargs: Any) -> None:
        """Update arbitrary columns on a node."""
        conn = self._get_conn()
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        conn.execute(
            f"UPDATE mem_nodes SET {sets} WHERE id = ?",
            (*kwargs.values(), node_id),
        )
        conn.commit()

    def touch_nodes(self, node_ids: list[str]) -> None:
        """Increment access_count and set last_accessed for returned nodes."""
        if not node_ids:
            return
        conn = self._get_conn()
        now = _now_iso()
        placeholders = ",".join("?" * len(node_ids))
        conn.execute(
            f"""
            UPDATE mem_nodes
            SET access_count = access_count + 1, last_accessed = ?
            WHERE id IN ({placeholders})
            """,
            [now, *node_ids],
        )
        conn.commit()

    # ── FTS search ─────────────────────────────────────────────────────────────

    def fts_search(
        self,
        query: str,
        limit: int = 12,
        kinds: list[str] | None = None,
        as_of: str | None = None,
    ) -> list[dict[str, Any]]:
        """BM25 FTS5 search + alias lookup; returns up to `limit` node dicts."""
        conn = self._get_conn()

        kind_filter = ""
        params: list[Any] = []

        if kinds:
            placeholders = ",".join("?" * len(kinds))
            kind_filter = f"AND n.kind IN ({placeholders})"
            params.extend(kinds)

        if as_of:
            temporal_clause = """
                AND n.tombstoned = 0
                AND (n.valid_from IS NULL OR n.valid_from <= ?)
                AND (n.valid_until IS NULL OR n.valid_until > ?)
            """
            temporal_params: list[Any] = [as_of, as_of]
        else:
            temporal_clause = """
                AND n.tombstoned = 0
                AND n.valid_until IS NULL
                AND n.id NOT IN (
                    SELECT dst FROM mem_edges WHERE kind = 'SUPERSEDES'
                    AND src IN (
                        SELECT id FROM mem_nodes WHERE tombstoned = 0 AND valid_until IS NULL
                    )
                )
            """
            temporal_params = []

        fts_rows: list[Any] = []
        for safe_q in _fts_variants(query):
            try:
                fts_rows = conn.execute(
                    f"""
                    SELECT n.*, rank
                    FROM mem_fts
                    JOIN mem_nodes n ON mem_fts.rowid = n.rowid
                    WHERE mem_fts MATCH ?
                      AND n.namespace = ?
                      {kind_filter}
                      {temporal_clause}
                    ORDER BY rank
                    LIMIT ?
                    """,
                    [safe_q, self.namespace, *params, *temporal_params, limit],
                ).fetchall()
                if fts_rows:
                    break
            except sqlite3.OperationalError:
                continue

        # Alias search (case-insensitive): union in any additional matches
        alias_rows = conn.execute(
            f"""
            SELECT n.*, 0.0 as rank
            FROM mem_aliases a
            JOIN mem_nodes n ON a.entity_id = n.id
            WHERE a.alias = ?
              AND n.namespace = ?
              {kind_filter}
            ORDER BY n.recorded_at DESC
            LIMIT ?
            """,
            [query.strip(), self.namespace, *params, limit],
        ).fetchall()

        seen: set[str] = set()
        results: list[dict[str, Any]] = []
        for row in [*fts_rows, *alias_rows]:
            r = dict(row)
            if r["id"] not in seen:
                seen.add(r["id"])
                results.append(r)

        return results[:limit]

    # ── Alias operations ────────────────────────────────────────────────────────

    def add_alias(self, entity_id: str, alias: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR IGNORE INTO mem_aliases (entity_id, alias) VALUES (?,?)",
            (entity_id, alias.strip()),
        )
        conn.commit()

    def find_entity_by_alias(self, alias: str) -> str | None:
        """Return entity node id matching alias (case-insensitive), or None."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT entity_id FROM mem_aliases WHERE alias = ? LIMIT 1",
            (alias.strip(),),
        ).fetchone()
        return row["entity_id"] if row else None

    def find_entity_by_alias_normalised(self, norm: str) -> str | None:
        """Return entity id where the alias stripped of separators matches norm."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT entity_id, alias FROM mem_aliases"
        ).fetchall()
        for row in rows:
            candidate = row["alias"].lower().replace("_", "").replace(" ", "").replace("-", "")
            if candidate == norm.lower():
                return row["entity_id"]
        return None

    # ── Neighbor traversal ──────────────────────────────────────────────────────

    def neighbors(
        self,
        node_id: str,
        edge_kinds: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return all nodes 1 hop away (both directions) via specified edge kinds."""
        conn = self._get_conn()
        kinds = edge_kinds or ["ABOUT", "CAUSED", "SUPERSEDES", "OCCURRED_IN", "DERIVED_FROM"]
        placeholders = ",".join("?" * len(kinds))
        rows = conn.execute(
            f"""
            SELECT DISTINCT n.*
            FROM mem_edges e
            JOIN mem_nodes n ON (
                (e.src = ? AND e.dst = n.id) OR (e.dst = ? AND e.src = n.id)
            )
            WHERE e.kind IN ({placeholders})
              AND n.namespace = ?
            """,
            [node_id, node_id, *kinds, self.namespace],
        ).fetchall()
        return [dict(r) for r in rows]

    def get_edges(
        self,
        src: str | None = None,
        dst: str | None = None,
        kind: str | None = None,
    ) -> list[dict[str, Any]]:
        conn = self._get_conn()
        clauses = []
        params: list[Any] = []
        if src:
            clauses.append("src = ?")
            params.append(src)
        if dst:
            clauses.append("dst = ?")
            params.append(dst)
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(f"SELECT * FROM mem_edges {where}", params).fetchall()
        return [dict(r) for r in rows]

    # ── Temporal queries ────────────────────────────────────────────────────────

    def currently_valid(
        self,
        node_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return nodes that are currently valid (not tombstoned, not superseded, valid_until IS NULL)."""
        conn = self._get_conn()
        id_clause = ""
        params: list[Any] = [self.namespace]
        if node_ids:
            placeholders = ",".join("?" * len(node_ids))
            id_clause = f"AND id IN ({placeholders})"
            params.extend(node_ids)
        rows = conn.execute(
            f"""
            SELECT * FROM mem_nodes
            WHERE namespace = ?
              AND {_VALID_NOW}
              {id_clause}
            """,
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def nodes_about_entity(
        self, entity_id: str, as_of: str | None = None
    ) -> list[dict[str, Any]]:
        """Return all nodes linked to entity via ABOUT edge, newest first."""
        conn = self._get_conn()
        if as_of:
            temporal = f"AND {_valid_at('n')}"
            tparams = [as_of, as_of]
        else:
            # Rebuild _VALID_NOW with table alias
            temporal = "AND n.tombstoned = 0 AND n.valid_until IS NULL AND n.id NOT IN (SELECT dst FROM mem_edges WHERE kind = 'SUPERSEDES' AND src IN (SELECT id FROM mem_nodes WHERE tombstoned = 0 AND valid_until IS NULL))"
            tparams = []

        rows = conn.execute(
            f"""
            SELECT DISTINCT n.*
            FROM mem_edges e
            JOIN mem_nodes n ON e.src = n.id
            WHERE e.dst = ? AND e.kind = 'ABOUT'
              AND n.namespace = ?
              {temporal}
            ORDER BY n.recorded_at DESC
            """,
            [entity_id, self.namespace, *tparams],
        ).fetchall()
        return [dict(r) for r in rows]

    def timeline(
        self,
        query: str,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return all matching nodes (incl. superseded) chronologically."""
        conn = self._get_conn()
        since_clause = "AND n.recorded_at >= ?" if since else ""
        since_params = [since] if since else []

        rows: list[Any] = []
        for safe_q in _fts_variants(query):
            try:
                rows = conn.execute(
                    f"""
                    SELECT n.*, rank
                    FROM mem_fts
                    JOIN mem_nodes n ON mem_fts.rowid = n.rowid
                    WHERE mem_fts MATCH ?
                      AND n.namespace = ?
                      AND n.tombstoned = 0
                      {since_clause}
                    ORDER BY n.valid_from ASC
                    """,
                    [safe_q, self.namespace, *since_params],
                ).fetchall()
                if rows:
                    break
            except sqlite3.OperationalError:
                continue

        result = []
        for row in rows:
            r = dict(row)
            # Mark superseded: check for a live SUPERSEDES edge pointing at this node
            sup = conn.execute(
                """
                SELECT src FROM mem_edges
                WHERE dst = ? AND kind = 'SUPERSEDES'
                  AND src IN (SELECT id FROM mem_nodes WHERE tombstoned = 0)
                LIMIT 1
                """,
                (r["id"],),
            ).fetchone()
            r["_superseded_by"] = sup["src"] if sup else None
            result.append(r)
        return result

    # ── Tombstone / purge ───────────────────────────────────────────────────────

    def tombstone(self, node_ids: list[str]) -> int:
        """Soft-delete nodes. Returns count updated."""
        if not node_ids:
            return 0
        conn = self._get_conn()
        placeholders = ",".join("?" * len(node_ids))
        cur = conn.execute(
            f"UPDATE mem_nodes SET tombstoned = 1, valid_until = ? WHERE id IN ({placeholders})",
            [_now_iso(), *node_ids],
        )
        conn.commit()
        return cur.rowcount

    def purge(self, node_ids: list[str]) -> int:
        """Hard-delete nodes (DELETE trigger removes FTS entries). Returns count."""
        if not node_ids:
            return 0
        conn = self._get_conn()
        placeholders = ",".join("?" * len(node_ids))
        # Delete dependent edges first to satisfy FK constraints
        conn.execute(
            f"DELETE FROM mem_edges WHERE src IN ({placeholders}) OR dst IN ({placeholders})",
            [*node_ids, *node_ids],
        )
        conn.execute(
            f"DELETE FROM mem_aliases WHERE entity_id IN ({placeholders})",
            node_ids,
        )
        cur = conn.execute(
            f"DELETE FROM mem_nodes WHERE id IN ({placeholders})",
            node_ids,
        )
        conn.commit()
        return cur.rowcount

    # ── Stats ───────────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        conn = self._get_conn()
        kind_counts = dict(
            conn.execute(
                "SELECT kind, COUNT(*) FROM mem_nodes WHERE namespace = ? AND tombstoned = 0 GROUP BY kind",
                (self.namespace,),
            ).fetchall()
        )
        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
        top_entities = conn.execute(
            """
            SELECT n.id, n.content,
                   COUNT(DISTINCT e.src) + COUNT(DISTINCT e2.dst) AS degree
            FROM mem_nodes n
            LEFT JOIN mem_edges e ON e.dst = n.id
            LEFT JOIN mem_edges e2 ON e2.src = n.id
            WHERE n.kind = 'entity' AND n.namespace = ? AND n.tombstoned = 0
            GROUP BY n.id
            ORDER BY degree DESC
            LIMIT 10
            """,
            (self.namespace,),
        ).fetchall()
        namespaces = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT namespace FROM mem_nodes"
            ).fetchall()
        ]
        return {
            "kind_counts": kind_counts,
            "db_size_bytes": db_size,
            "top_entities": [dict(r) for r in top_entities],
            "namespaces": namespaces,
        }

    def search_by_kind(
        self, query: str, kind: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Best FTS match among nodes of a given kind."""
        return self.fts_search(query, limit=limit, kinds=[kind])

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return sessions newest-first with node counts."""
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT s.id, s.content, s.recorded_at, s.valid_until, s.tombstoned,
                   COUNT(n.id) AS node_count
            FROM mem_nodes s
            LEFT JOIN mem_nodes n ON n.session_id = s.id AND n.kind != 'session'
            WHERE s.kind = 'session' AND s.namespace = ?
            GROUP BY s.id
            ORDER BY s.recorded_at DESC
            LIMIT ?
            """,
            (self.namespace, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_session(self, session_id: str, purge: bool = False) -> dict[str, Any]:
        """Tombstone or hard-purge a session node and all nodes that belong to it."""
        conn = self._get_conn()
        # Collect the session node itself plus all nodes that occurred in it
        rows = conn.execute(
            "SELECT id FROM mem_nodes WHERE id = ? OR session_id = ?",
            (session_id, session_id),
        ).fetchall()
        ids = [r["id"] for r in rows]
        if not ids:
            return {"count": 0}
        if purge:
            count = self.purge(ids)
        else:
            count = self.tombstone(ids)
        return {"count": count, "mode": "purge" if purge else "tombstone", "ids": ids}

    def find_nodes(
        self,
        before: str | None = None,
        entity_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Find nodes for bulk tombstone/purge operations."""
        conn = self._get_conn()
        clauses = ["namespace = ?"]
        params: list[Any] = [self.namespace]
        if before:
            clauses.append("recorded_at < ?")
            params.append(before)
        if entity_id:
            # Nodes linked to this entity via ABOUT
            clauses.append(
                "id IN (SELECT src FROM mem_edges WHERE dst = ? AND kind = 'ABOUT')"
            )
            params.append(entity_id)
        where = " AND ".join(clauses)
        rows = conn.execute(
            f"SELECT id FROM mem_nodes WHERE {where}", params
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Consolidation queue ─────────────────────────────────────────────────────

    def queue_consolidation(self, session_id: str, summary: str) -> str:
        """Write a consolidation job to mem_review_queue; return its id."""
        conn = self._get_conn()
        jid = f"rq_{uuid.uuid4().hex[:16]}"
        conn.execute(
            "INSERT INTO mem_review_queue (id, created_at, kind, payload, resolved) VALUES (?,?,?,?,0)",
            (jid, _now_iso(), "session_close", json.dumps({"session_id": session_id, "summary": summary})),
        )
        conn.commit()
        return jid

    def get_pending_jobs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return unresolved consolidation jobs, oldest first."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM mem_review_queue WHERE resolved=0 ORDER BY created_at ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def resolve_job(self, job_id: str) -> None:
        """Mark a consolidation job as resolved."""
        conn = self._get_conn()
        conn.execute("UPDATE mem_review_queue SET resolved=1 WHERE id=?", (job_id,))
        conn.commit()

    def get_session_facts(self, session_id: str) -> list[dict[str, Any]]:
        """Return non-tombstoned fact/decision/procedure/preference nodes for a session."""
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT * FROM mem_nodes
            WHERE session_id = ?
              AND kind IN ('fact','decision','procedure','preference')
              AND tombstoned = 0
              AND namespace = ?
            ORDER BY recorded_at ASC
            """,
            (session_id, self.namespace),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── TOUCHES / code graph reverse lookup ──────────────────────────────────────

    def get_touches_for_file(
        self, file_path: str, line: int | None = None
    ) -> list[dict[str, Any]]:
        """Return memory nodes that TOUCHES a given file (optionally at a line)."""
        conn = self._get_conn()
        if line is None:
            rows = conn.execute(
                """
                SELECT n.*, e.data AS touches_data
                FROM mem_edges e
                JOIN mem_nodes n ON n.id = e.src
                WHERE e.kind = 'TOUCHES'
                  AND json_extract(e.data, '$.file_path') = ?
                  AND n.tombstoned = 0
                  AND n.namespace = ?
                """,
                (file_path, self.namespace),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT n.*, e.data AS touches_data
                FROM mem_edges e
                JOIN mem_nodes n ON n.id = e.src
                WHERE e.kind = 'TOUCHES'
                  AND json_extract(e.data, '$.file_path') = ?
                  AND CAST(json_extract(e.data, '$.start_line') AS INTEGER) <= ?
                  AND CAST(json_extract(e.data, '$.end_line') AS INTEGER) >= ?
                  AND n.tombstoned = 0
                  AND n.namespace = ?
                """,
                (file_path, line, line, self.namespace),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_touches_from_node(self, node_id: str) -> list[dict[str, Any]]:
        """Return code-graph locations that this memory node TOUCHES."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT data FROM mem_edges WHERE src = ? AND kind = 'TOUCHES'",
            (node_id,),
        ).fetchall()
        result = []
        for r in rows:
            try:
                result.append(json.loads(r["data"] or "{}"))
            except Exception:
                pass
        return result
