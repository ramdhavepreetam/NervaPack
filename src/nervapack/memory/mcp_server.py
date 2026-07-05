"""
NervaPack Memory MCP Server

Exposes agent memory tools via MCP so any MCP-compatible client (Claude Code,
Cursor, etc.) can persist and recall structured facts across sessions.

Run via:  nervapack-memory-mcp
Or add to .mcp.json:
  { "mcpServers": { "nervapack-memory": { "command": "nervapack-memory-mcp" } } }
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    raise ImportError(
        "MCP SDK is not installed. Run: pip install nervapack[mcp]"
    )

from .consolidate import RuleBasedConsolidator
from .pack import get_token_counter, pack
from .recall import recall, recall_timeline
from .resolve import match_code_entity, resolve_entities
from .store import MemoryStore, _now_iso

mcp = FastMCP(
    "nervapack-memory",
    instructions=(
        "NervaPack Memory stores and retrieves structured agent memory — facts, "
        "decisions, outcomes, and procedures — across sessions. "
        "Call memory_recall before answering questions that depend on prior context. "
        "Call memory_store to persist any decision, fact, or outcome worth remembering. "
        "Call memory_end_session when a task is complete."
    ),
)

_store: MemoryStore | None = None
_session_id: str | None = None
_code_graph: "Any" = None  # NetworkX graph or False (tried+failed) or None (not yet tried)


def _get_code_graph() -> "Any":
    global _code_graph
    if _code_graph is None:
        try:
            from nervapack.graph.builder import GraphBuilder
            _code_graph = GraphBuilder().load_graph()
        except Exception:
            _code_graph = False  # sentinel: don't retry
    return _code_graph if _code_graph is not False else None


def _get_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store


def _get_or_create_session() -> str:
    global _session_id
    if _session_id is None:
        store = _get_store()
        _session_id = store.add_node(
            kind="session",
            content="Active session",
            data={"started_at": _now_iso(), "agent_id": "default"},
        )
    return _session_id


# ── Tool 0: memory_start_session ──────────────────────────────────────────────

@mcp.tool()
def memory_start_session(name: str, namespace: str | None = None) -> dict[str, Any]:
    """
    Explicitly open a named session and return its ID.

    Call this at the start of a task to give the session a meaningful name
    (e.g. "JWT auth refactor", "Debugging payment flow"). The returned
    session_id can be passed to memory_store to group nodes under this session.

    If a session is already open for this server process, the existing session
    is returned unchanged (use memory_end_session first to close it).
    Use `namespace` to switch the active namespace before opening the session.

    Example: memory_start_session("JWT auth refactor")
    """
    global _session_id
    store = _get_store()
    if namespace is not None:
        ns = namespace.strip() or "default"
        if ns != store.namespace:
            store.namespace = ns
            _session_id = None
    if _session_id is not None:
        return {"session_id": _session_id, "created": False, "note": "existing session returned"}
    _session_id = store.add_node(
        kind="session",
        content=name.strip(),
        data={"started_at": _now_iso(), "agent_id": "default"},
    )
    return {"session_id": _session_id, "created": True, "namespace": store.namespace}


# ── Tool 1: memory_store ────────────────────────────────────────────────────────

@mcp.tool()
def memory_store(
    content: str,
    kind: str,
    entities: list[str] | None = None,
    confidence: float = 1.0,
    valid_from: str | None = None,
    supersedes: str | None = None,
    session_id: str | None = None,
    rationale: str | None = None,
    alternatives_rejected: list[str] | None = None,
    namespace: str | None = None,
) -> dict[str, Any]:
    """
    Persist a memory node (fact, decision, outcome, procedure, preference, or action).

    Resolves each entity string to an existing node via alias (case-insensitive),
    or creates a new entity node. Links them via ABOUT edges. If `supersedes`
    is provided, closes the old node's valid window and adds a SUPERSEDES edge.

    Use `rationale` to record *why* the decision was made (shows in memory_why).
    Use `alternatives_rejected` to record options that were considered but dropped.
    Use `namespace` to switch the active namespace and write into it (resets session).

    Example: memory_store("Chose JWT for auth — stateless scaling",
                          kind="decision", entities=["auth_service"],
                          confidence=0.9, rationale="Stateless, scales horizontally",
                          alternatives_rejected=["session cookies", "API keys"])

    Returns: {node_id, linked_entity_ids, created_entity_ids}
    """
    global _session_id
    store = _get_store()
    if namespace is not None:
        ns = namespace.strip() or "default"
        if ns != store.namespace:
            store.namespace = ns
            _session_id = None
    sid = session_id or _get_or_create_session()

    valid_kinds = {"session", "fact", "decision", "action", "outcome",
                   "entity", "procedure", "preference"}
    if kind not in valid_kinds:
        return {"error": f"Unknown kind {kind!r}. Valid: {sorted(valid_kinds)}"}

    data: dict[str, Any] = {}
    if rationale:
        data["rationale"] = rationale
    if alternatives_rejected:
        data["alternatives_rejected"] = alternatives_rejected

    node_id = store.add_node(
        kind=kind,
        content=content,
        confidence=confidence,
        valid_from=valid_from,
        session_id=sid,
        data=data if data else None,
    )

    linked, created = resolve_entities(store, entities or [], session_id=sid)

    for eid in linked:
        store.add_edge(node_id, eid, "ABOUT")

    store.add_edge(node_id, sid, "OCCURRED_IN")

    # TOUCHES bridge: link memory node to code graph nodes when graph is available
    graph = _get_code_graph()
    if graph is not None:
        for eid in linked:
            entity_node = store.get_node(eid)
            if entity_node:
                code_match = match_code_entity(graph, entity_node["content"])
                if code_match:
                    existing = json.loads(entity_node.get("data") or "{}")
                    existing.update(code_match)
                    store.update_node(eid, data=json.dumps(existing))
                    store.add_edge(node_id, eid, "TOUCHES", data=code_match)

    if supersedes:
        node = store.get_node(supersedes)
        if node:
            store.supersede(node_id, supersedes)

    return {
        "node_id": node_id,
        "linked_entity_ids": linked,
        "created_entity_ids": created,
    }


# ── Tool 2: memory_recall ───────────────────────────────────────────────────────

@mcp.tool()
def memory_recall(
    query: str,
    budget_tokens: int = 500,
    kinds: list[str] | None = None,
    as_of: str | None = None,
    hops: int = 1,
    min_confidence: float = 0.0,
    namespace: str | None = None,
) -> str:
    """
    Retrieve the most relevant memories for a query, packed into a token budget.

    Runs FTS5 search, expands neighbours, applies temporal mask, scores by
    relevance × recency × frequency × connectivity, and returns a markdown block
    guaranteed to stay within `budget_tokens`.

    Use `min_confidence` (0.0–1.0) to filter out low-confidence nodes.
    Use `namespace` to read from a specific namespace without switching the active one.
    Example: memory_recall("why JWT for auth", budget_tokens=500, min_confidence=0.7)
    """
    store = _get_store()
    if namespace is not None:
        prev_ns = store.namespace
        store.namespace = namespace.strip() or "default"
        try:
            return recall(store, query, budget_tokens=budget_tokens,
                          kinds=kinds, as_of=as_of, hops=hops, min_confidence=min_confidence)
        finally:
            store.namespace = prev_ns
    return recall(store, query, budget_tokens=budget_tokens,
                  kinds=kinds, as_of=as_of, hops=hops, min_confidence=min_confidence)


# ── Tool 3: memory_about ───────────────────────────────────────────────────────

@mcp.tool()
def memory_about(entity: str, budget_tokens: int = 500) -> str:
    """
    Dossier on one entity: all currently valid facts, decisions, and outcomes
    linked to it via ABOUT edges, newest first, packed within budget_tokens.

    Example: memory_about("auth_service", budget_tokens=500)
    """
    store = _get_store()
    tc = get_token_counter()

    # Resolve entity
    from .resolve import _find_entity
    entity_id = _find_entity(store, entity)
    if not entity_id:
        return f"No entity found matching {entity!r}."

    nodes = store.nodes_about_entity(entity_id)
    return pack(nodes, f"about:{entity}", budget_tokens, None, counter=tc)


# ── Tool 4: memory_why ─────────────────────────────────────────────────────────

@mcp.tool()
def memory_why(decision_ref: str) -> str:
    """
    Explain why a decision was made.

    Accepts a node id (e.g. "d_01J...") or a search phrase (best FTS match
    among decision nodes). Returns the decision content, rationale, rejected
    alternatives, any CAUSED outcomes, and the supersession chain if applicable.

    Example: memory_why("JWT auth decision")
    """
    store = _get_store()

    node = store.get_node(decision_ref)
    if node is None:
        # Try FTS match among decisions
        results = store.search_by_kind(decision_ref, kind="decision", limit=1)
        node = dict(results[0]) if results else None

    if node is None:
        return f"No decision found matching {decision_ref!r}."

    node = dict(node)
    data = json.loads(node.get("data") or "{}")
    lines = [
        f"## Decision: {node['id']}",
        f"**{node['content']}**",
        f"Date: {node.get('valid_from', 'unknown')}  ·  Confidence: {node.get('confidence', 1.0):.2f}",
    ]
    if data.get("rationale"):
        lines.append(f"\n**Rationale:** {data['rationale']}")
    if data.get("alternatives_rejected"):
        alts = ", ".join(data["alternatives_rejected"])
        lines.append(f"**Rejected alternatives:** {alts}")

    # CAUSED outcomes
    edges = store.get_edges(src=node["id"], kind="CAUSED")
    if edges:
        lines.append("\n**Outcomes:**")
        for e in edges:
            outcome = store.get_node(e["dst"])
            if outcome:
                outcome = dict(outcome)
                lines.append(f"- [{outcome['id']}] {outcome['content']}")

    # Supersession chain
    sup_edges = store.get_edges(src=node["id"], kind="SUPERSEDES")
    if sup_edges:
        lines.append("\n**Supersedes:**")
        for e in sup_edges:
            old = store.get_node(e["dst"])
            if old:
                old = dict(old)
                lines.append(f"- [{old['id']}] {old['content']}")

    incoming_sup = store.get_edges(dst=node["id"], kind="SUPERSEDES")
    if incoming_sup:
        lines.append("\n**Superseded by:**")
        for e in incoming_sup:
            newer = store.get_node(e["src"])
            if newer:
                newer = dict(newer)
                lines.append(f"- [{newer['id']}] {newer['content']}")

    return "\n".join(lines)


# ── Tool 5: memory_timeline ────────────────────────────────────────────────────

@mcp.tool()
def memory_timeline(topic: str, since: str | None = None) -> str:
    """
    Chronological trace of all memories matching `topic`, including superseded
    nodes (each marked [superseded by <id>]).

    Example: memory_timeline("auth_service", since="2026-01-01T00:00:00")
    """
    store = _get_store()
    return recall_timeline(store, topic, since=since)


# ── Tool 6: memory_end_session ─────────────────────────────────────────────────

@mcp.tool()
def memory_end_session(summary: str) -> dict[str, Any]:
    """
    Close the current session node with an outcome summary.

    Creates a session node if none is open, stores the summary as an outcome
    node, and queues consolidation (Phase 2 — no LLM call in Phase 1).

    Example: memory_end_session("Implemented JWT auth; chose refresh-token rotation")
    """
    global _session_id
    store = _get_store()
    sid = _get_or_create_session()

    now = _now_iso()
    store.update_node(sid, valid_until=now)

    # Store summary as an outcome node
    outcome_id = store.add_node(
        kind="outcome",
        content=summary,
        data={"status": "success", "detail": summary},
        session_id=sid,
    )
    store.add_edge(outcome_id, sid, "OCCURRED_IN")

    consolidator = RuleBasedConsolidator(store)
    consolidator.consolidate(sid, summary)

    closed_id = _session_id
    _session_id = None  # Reset for next session
    return {"closed_session_id": closed_id, "outcome_id": outcome_id}


# ── Tool 7: memory_forget ──────────────────────────────────────────────────────

@mcp.tool()
def memory_forget(
    node_id: str | None = None,
    entity: str | None = None,
    before: str | None = None,
    purge: bool = False,
) -> dict[str, Any]:
    """
    Tombstone (soft-delete) or hard-delete matching nodes.

    node_id: specific node to forget.
    entity: forget all nodes linked to this entity.
    before: forget all nodes recorded before this ISO-8601 timestamp.
    purge=True: hard-delete rows and remove from FTS (the only sanctioned hard delete).

    Example: memory_forget(node_id="f_01J...", purge=False)
    """
    store = _get_store()
    ids: list[str] = []

    if node_id:
        ids.append(node_id)
    if entity:
        from .resolve import _find_entity
        eid = _find_entity(store, entity)
        if eid:
            linked = store.find_nodes(entity_id=eid)
            ids.extend(r["id"] for r in linked)
    if before:
        old = store.find_nodes(before=before)
        ids.extend(r["id"] for r in old)

    ids = list(set(ids))
    if not ids:
        return {"count": 0, "mode": "purge" if purge else "tombstone"}

    if purge:
        count = store.purge(ids)
        return {"count": count, "mode": "purge", "ids": ids}
    else:
        count = store.tombstone(ids)
        return {"count": count, "mode": "tombstone", "ids": ids}


# ── Tool 8: memory_verify ──────────────────────────────────────────────────────

@mcp.tool()
def memory_verify(node_id: str, status: str) -> dict[str, Any]:
    """
    Update the confidence of a memory node.

    status='confirm': confidence = min(1.0, confidence + 0.1)
    status='refute': close valid_until = now, confidence = confidence × 0.5

    Example: memory_verify("f_01J...", "confirm")
    """
    store = _get_store()
    node = store.get_node(node_id)
    if node is None:
        return {"error": f"Node {node_id!r} not found"}

    node = dict(node)
    conf = node.get("confidence", 1.0)

    if status == "confirm":
        new_conf = min(1.0, conf + 0.1)
        store.update_node(node_id, confidence=new_conf)
        return {"node_id": node_id, "confidence": new_conf, "status": "confirmed"}
    elif status == "refute":
        new_conf = conf * 0.5
        store.update_node(node_id, confidence=new_conf, valid_until=_now_iso())
        return {"node_id": node_id, "confidence": new_conf, "status": "refuted"}
    else:
        return {"error": f"Unknown status {status!r}. Use 'confirm' or 'refute'."}


# ── Tool 9: memory_list_sessions ──────────────────────────────────────────────

@mcp.tool()
def memory_list_sessions(limit: int = 50) -> list[dict[str, Any]]:
    """
    List all sessions, newest first.

    Returns id, content, recorded_at, node_count, and status
    (open / closed / tombstoned) for each session.

    Example: memory_list_sessions()
    """
    store = _get_store()
    return store.list_sessions(limit=limit)


# ── Tool 10: memory_clear_session ─────────────────────────────────────────────

@mcp.tool()
def memory_clear_session(
    session_id: str,
    purge: bool = False,
) -> dict[str, Any]:
    """
    Delete a session and every node that belongs to it.

    purge=False (default): tombstones all nodes — they disappear from recall
    but remain in the database for audit / timeline purposes.
    purge=True: hard-deletes all rows and removes them from FTS (irreversible).

    Example: memory_clear_session("s_0019f2...", purge=False)
    """
    store = _get_store()
    return store.delete_session(session_id, purge=purge)


# ── Tool 11: memory_stats ─────────────────────────────────────────────────────

@mcp.tool()
def memory_stats(namespace: str | None = None) -> dict[str, Any]:
    """
    Summary statistics for the memory store.

    Returns node counts by kind, database size, top-10 entities by degree,
    and list of namespaces.
    Use `namespace` to get stats for a specific namespace without switching the active one.

    Example: memory_stats()
    """
    store = _get_store()
    if namespace is not None:
        prev_ns = store.namespace
        store.namespace = namespace.strip() or "default"
        try:
            return store.stats()
        finally:
            store.namespace = prev_ns
    return store.stats()


# ── Tool 12: memory_switch_namespace ──────────────────────────────────────────

@mcp.tool()
def memory_switch_namespace(namespace: str) -> dict[str, Any]:
    """
    Switch the active namespace for this server process.

    All subsequent memory_store, memory_recall, memory_start_session, and
    memory_stats calls will operate in `namespace`. Resets the active session
    so the next memory_store opens a fresh session in the new namespace.

    Use namespaces to isolate memory for separate projects or agents in the
    same database file. The "default" namespace is used when none is set.

    Example: memory_switch_namespace("project_b")
    """
    global _session_id
    store = _get_store()
    prev = store.namespace
    store.namespace = namespace.strip() or "default"
    _session_id = None
    return {"previous_namespace": prev, "active_namespace": store.namespace}


# ── Tool 13: memory_for_code ──────────────────────────────────────────────────

@mcp.tool()
def memory_for_code(
    file_path: str,
    line: int | None = None,
) -> str:
    """
    Return memories that TOUCH a given source file (optionally at a specific line).

    Use this to answer "what decisions were made about this file or function?"
    Requires the code graph to have been built (nervapack build) and memory_store
    to have been called with matching entity names.

    Example: memory_for_code("src/nervapack/memory/store.py", line=172)
    """
    store = _get_store()
    nodes = store.get_touches_for_file(file_path, line=line)
    if not nodes:
        return f"No memories touch {file_path}" + (f":{line}" if line else "")
    lines = [f"## Memories touching `{file_path}`" + (f":{line}" if line else "")]
    for n in nodes:
        kind = n.get("kind", "node")
        content = n.get("content", "")
        conf = n.get("confidence", 1.0)
        lines.append(f"- [{kind}] ({conf:.0%}) {content}")
    return "\n".join(lines)


# ── Tool 14: memory_to_code ───────────────────────────────────────────────────

@mcp.tool()
def memory_to_code(memory_id: str) -> list[dict[str, Any]]:
    """
    Return code-graph locations that a memory node TOUCHES.

    Provides file_path, start_line, end_line, and code_type for each match.
    Returns an empty list if the node has no TOUCHES edges.

    Example: memory_to_code("d_01J...")
    """
    store = _get_store()
    return store.get_touches_from_node(memory_id)


# ── Tool 15: memory_import ────────────────────────────────────────────────────

@mcp.tool()
def memory_import(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Bulk-import memory nodes from a list of dicts.

    Each dict must have: content (str), kind (str).
    Optional: entities (list[str]), confidence (float), valid_from (str),
              rationale (str), alternatives_rejected (list[str]), session_id (str).

    Also accepts the full export format: {"nodes": [...], "edges": [...]} —
    pass the "nodes" array only (edges are rebuilt via entity resolution).

    Example:
      memory_import([
        {"content": "Chose JWT for auth", "kind": "decision",
         "entities": ["auth_service"], "confidence": 0.9}
      ])
    """
    store = _get_store()
    node_ids: list[str] = []
    all_created: list[str] = []
    errors: list[str] = []

    valid_kinds = {"session", "fact", "decision", "action", "outcome",
                   "entity", "procedure", "preference"}

    for i, spec in enumerate(nodes):
        content = spec.get("content", "")
        kind = spec.get("kind", "fact")
        if not content:
            errors.append(f"[{i}] missing content")
            continue
        if kind not in valid_kinds:
            errors.append(f"[{i}] unknown kind {kind!r}")
            continue

        data: dict[str, Any] = {}
        if spec.get("rationale"):
            data["rationale"] = spec["rationale"]
        if spec.get("alternatives_rejected"):
            data["alternatives_rejected"] = spec["alternatives_rejected"]

        sid = spec.get("session_id") or _get_or_create_session()
        node_id = store.add_node(
            kind=kind,
            content=content,
            confidence=float(spec.get("confidence", 1.0)),
            valid_from=spec.get("valid_from"),
            session_id=sid,
            data=data if data else None,
        )
        node_ids.append(node_id)

        entity_names: list[str] = spec.get("entities") or []
        linked, created = resolve_entities(store, entity_names, session_id=sid)
        all_created.extend(created)
        for eid in linked:
            store.add_edge(node_id, eid, "ABOUT")
        store.add_edge(node_id, sid, "OCCURRED_IN")

    return {
        "imported": len(node_ids),
        "node_ids": node_ids,
        "created_entity_ids": all_created,
        "errors": errors,
    }


# ── Tool 16: memory_verify_staleness ─────────────────────────────────────────

@mcp.tool()
def memory_verify_staleness(queue: bool = True) -> dict[str, Any]:
    """
    Scan all TOUCHES edges and flag memories whose source file has changed.

    For each TOUCHES edge, compares the file's mtime against the memory node's
    recorded_at. Nodes where the file was modified after the memory was stored
    are "stale" — the memory may no longer accurately describe the code.

    By default (queue=True), stale nodes are written to mem_review_queue
    (kind="staleness") for human review. They are NOT tombstoned automatically.

    Returns:
      {
        "checked": N,           # total TOUCHES edges inspected
        "stale": M,             # edges where file was modified after memory stored
        "missing": K,           # edges where file no longer exists
        "clean": J,             # edges that are current
        "stale_nodes": [...],   # list of {node_id, file_path, memory_date, file_mtime}
        "missing_nodes": [...], # list of {node_id, file_path}
        "queued": bool,         # whether stale/missing were written to review queue
      }

    Note: file_path in TOUCHES edges is repo-relative. This tool resolves it
    relative to the .nervapack/ parent directory. It cannot resolve paths when
    using the home-directory fallback DB (~/.nervapack/memory.db).

    Example: memory_verify_staleness()
    """
    store = _get_store()
    touches = store.get_all_touches()

    # Resolve repo root: parent of .nervapack/ dir, or cwd fallback
    db_path = store.db_path
    if db_path.parent.name == ".nervapack":
        repo_root = db_path.parent.parent
    else:
        repo_root = Path(os.getcwd())

    stale: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    clean = 0

    for t in touches:
        file_path_str = t.get("file_path", "")
        if not file_path_str:
            continue
        abs_path = repo_root / file_path_str
        recorded_at_str = t.get("recorded_at", "")

        try:
            mtime = abs_path.stat().st_mtime
        except FileNotFoundError:
            missing.append({"node_id": t["node_id"], "file_path": file_path_str})
            continue

        if not recorded_at_str:
            clean += 1
            continue

        try:
            recorded_at_dt = datetime.fromisoformat(recorded_at_str)
            if recorded_at_dt.tzinfo is None:
                recorded_at_dt = recorded_at_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            clean += 1
            continue

        mtime_dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
        if mtime_dt > recorded_at_dt:
            stale.append({
                "node_id": t["node_id"],
                "file_path": file_path_str,
                "memory_date": recorded_at_str,
                "file_mtime": mtime_dt.isoformat(),
            })
        else:
            clean += 1

    queued = False
    if queue and (stale or missing):
        payload = {
            "stale_node_ids": [s["node_id"] for s in stale],
            "missing_node_ids": [m["node_id"] for m in missing],
        }
        store.queue_staleness_job(payload)
        queued = True

    return {
        "checked": len(touches),
        "stale": len(stale),
        "missing": len(missing),
        "clean": clean,
        "stale_nodes": stale,
        "missing_nodes": missing,
        "queued": queued,
    }


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
