"""
NervaPack Memory MCP Server

Exposes 17 agent memory tools via MCP so any MCP-compatible client (Claude Code,
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
    from mcp.types import CallToolResult, TextContent
except ImportError:
    raise ImportError(
        "MCP SDK is not installed. Run: pip install nervapack[mcp]"
    )

from .consolidate import RuleBasedConsolidator
from .pack import get_token_counter, pack
from .recall import recall as _recall_pipeline, recall_timeline
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
_namespace: str = "default"
_namespace_explicit: bool = False  # True when set via memory_switch_namespace tool
_code_graph: "Any" = None  # NetworkX graph, False (tried+failed), or None (not tried)


def _get_code_graph() -> "Any":
    global _code_graph
    if _code_graph is None:
        try:
            from nervapack.graph.builder import GraphBuilder
            _code_graph = GraphBuilder().load_graph()
        except Exception:
            _code_graph = False
    return _code_graph if _code_graph is not False else None


def _get_store() -> MemoryStore:
    global _store, _namespace, _namespace_explicit
    if _store is None:
        if not _namespace_explicit:
            # External reset (e.g. test fixture): revert to default namespace
            _namespace = "default"
        _namespace_explicit = False
        _store = MemoryStore(namespace=_namespace)
    elif _store.namespace != _namespace:
        _store = MemoryStore(namespace=_namespace)
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


# ── Tool 1: memory_store ──────────────────────────────────────────────────────

@mcp.tool()
def memory_store(
    content: str,
    kind: str = "fact",
    entities: list[str] | None = None,
    confidence: float = 1.0,
    rationale: str | None = None,
    alternatives_rejected: list[str] | None = None,
    touches: list[str] | None = None,
) -> dict:
    """
    Persist a new memory node.

    Args:
        content: The core knowledge to store.
        kind: One of fact, decision, procedure, preference, outcome, action.
        entities: Code entity names to link via ABOUT edges (auto-created if not found).
        confidence: How confident this memory is (0.0–1.0).
        rationale: Why this decision was made (stored in data, surfaced by memory_why).
        alternatives_rejected: Options that were considered and rejected.
        touches: File paths this memory directly relates to (TOUCHES edges).
    """
    store = _get_store()
    session_id = _get_or_create_session()

    valid_kinds = {"fact", "decision", "procedure", "preference", "outcome", "action"}
    if kind not in valid_kinds:
        return {"error": f"Invalid kind '{kind}'. Must be one of: {sorted(valid_kinds)}"}

    data: dict[str, Any] = {}
    if rationale:
        data["rationale"] = rationale
    if alternatives_rejected:
        data["alternatives_rejected"] = alternatives_rejected

    node_id = store.add_node(
        kind=kind,
        content=content,
        data=data or None,
        confidence=confidence,
        session_id=session_id,
    )

    # Resolve entities → ABOUT edges
    linked_entity_ids: list[str] = []
    created_entity_ids: list[str] = []
    if entities:
        linked, created = resolve_entities(store, entities, session_id=session_id)
        linked_entity_ids = linked
        created_entity_ids = created
        for eid in linked:
            try:
                store.add_edge(node_id, eid, "ABOUT")
            except Exception:
                pass

    # Resolve entity names to code graph file paths → TOUCHES edges
    all_touches = list(touches or [])
    graph = _get_code_graph()
    if graph and entities:
        for name in entities:
            match = match_code_entity(graph, name)
            if match and match.get("file_path"):
                fp = match["file_path"]
                if fp not in all_touches:
                    all_touches.append(fp)
                # Also create a precise TOUCHES edge with line info
                entity_node = store.add_node(
                    kind="entity",
                    content=name.strip(),
                    data={"entity_type": match.get("code_type", "unknown")},
                    session_id=session_id,
                ) if not linked_entity_ids else None
                target_eid = entity_node or (linked_entity_ids[0] if linked_entity_ids else None)
                if target_eid:
                    try:
                        store.add_edge(node_id, target_eid, "TOUCHES", data={
                            "file_path": fp,
                            "start_line": match.get("start_line"),
                            "end_line": match.get("end_line"),
                            "graph_node_id": match.get("graph_node_id"),
                        })
                    except Exception:
                        pass

    if all_touches:
        store.add_touches_edges(node_id, all_touches)

    return {
        "node_id": node_id,
        "kind": kind,
        "linked_entity_ids": linked_entity_ids,
        "created_entity_ids": created_entity_ids,
    }


# ── Tool 2: memory_recall ─────────────────────────────────────────────────────

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
    Retrieve the most relevant memories for a query within a token budget.

    Args:
        query: Natural-language description of what to look for.
        budget_tokens: Hard token cap on the returned context block.
        kinds: Filter to specific node kinds (fact, decision, procedure, etc.).
        as_of: ISO timestamp or commit hash — retrieve memories as they were then.
        hops: Graph expansion hops (0–2).
        min_confidence: Exclude nodes below this confidence threshold.
        namespace: Read from this namespace without switching the active one.
    """
    if namespace:
        tmp_store = MemoryStore(namespace=namespace)
    else:
        tmp_store = _get_store()
    try:
        return _recall_pipeline(
            tmp_store, query,
            budget_tokens=budget_tokens,
            kinds=kinds,
            as_of=as_of,
            hops=hops,
            min_confidence=min_confidence,
        )
    except Exception as e:
        return f"Recall failed: {e}"


# ── Tool 3: memory_about ──────────────────────────────────────────────────────

@mcp.tool()
def memory_about(entity: str) -> str:
    """
    Return all current memories linked to a named entity.

    Args:
        entity: Entity name (case-insensitive, supports CamelCase → snake_case).
    """
    from .resolve import _find_entity
    store = _get_store()

    eid = _find_entity(store, entity)
    if not eid:
        return f"No entity found matching '{entity}'."

    nodes = store.nodes_about_entity(eid)
    if not nodes:
        return f"Entity '{entity}' exists but has no linked memories."

    lines = [f"## Entity: {entity}\n"]
    for n in nodes:
        data = {}
        try:
            data = json.loads(n.get("data") or "{}")
        except Exception:
            pass
        lines.append(
            f"- [{n['id']}] {n['recorded_at'][:10]} · {n['kind']} · conf {n.get('confidence', 1.0):.2f} — {n['content']}"
        )
        if data.get("rationale"):
            lines.append(f"  **Rationale:** {data['rationale']}")
    return "\n".join(lines)


# ── Tool 4: memory_why ────────────────────────────────────────────────────────

@mcp.tool()
def memory_why(decision_ref: str) -> str:
    """
    Explain a decision: show rationale, rejected alternatives, and caused outcomes.

    Args:
        decision_ref: Node ID (d_...) or search phrase matching the decision content.
    """
    store = _get_store()

    node = store.get_node(decision_ref)
    if not node:
        # Try FTS search
        hits = store.fts_search(decision_ref, limit=3, kinds=["decision"])
        if not hits:
            return f"No decision found matching '{decision_ref}'."
        node = hits[0]

    data = {}
    try:
        data = json.loads(node.get("data") or "{}")
    except Exception:
        pass

    lines = [
        f"## Decision: {node['id']}",
        f"**Recorded:** {node.get('recorded_at', '')[:10]}",
        f"**Confidence:** {node.get('confidence', 1.0):.2f}",
        f"\n**Decision:** {node['content']}",
    ]
    if data.get("rationale"):
        lines.append(f"\n**Rationale:** {data['rationale']}")
    if data.get("alternatives_rejected"):
        alts = data["alternatives_rejected"]
        if isinstance(alts, list):
            lines.append("\n**Alternatives rejected:**")
            for a in alts:
                lines.append(f"  - {a}")
        else:
            lines.append(f"\n**Alternatives rejected:** {alts}")

    # Outcomes caused by this decision
    caused = [e for e in store.get_edges(src=node["id"]) if e["kind"] == "CAUSED"]
    if caused:
        lines.append("\n**Caused outcomes:**")
        for e in caused:
            out = store.get_node(e["dst"])
            if out:
                lines.append(f"  - [{out['id']}] {out['content']}")

    return "\n".join(lines)


# ── Tool 5: memory_timeline ───────────────────────────────────────────────────

@mcp.tool()
def memory_timeline(
    topic: str,
    since: str | None = None,
    as_of: str | None = None,
) -> str:
    """
    Chronological trace of all memories matching a topic, including superseded ones.

    Args:
        topic: Search phrase.
        since: ISO timestamp — only show memories recorded after this date.
        as_of: ISO timestamp — show memories as they existed at this point in time.
    """
    store = _get_store()
    return recall_timeline(store, topic, since=since, as_of=as_of)


# ── Tool 6: memory_end_session ────────────────────────────────────────────────

@mcp.tool()
def memory_end_session(summary: str) -> dict:
    """
    Close the current session with an outcome summary and queue consolidation.

    Args:
        summary: One-paragraph summary of what was done in this session.
    """
    global _session_id
    store = _get_store()
    sid = _session_id or _get_or_create_session()

    outcome_id = store.add_node(
        kind="outcome",
        content=summary,
        session_id=sid,
    )
    store.add_edge(outcome_id, sid, "OCCURRED_IN")
    store.update_node(sid, valid_until=_now_iso())

    job_id = store.queue_consolidation(sid, summary)

    _session_id = None
    return {
        "closed_session_id": sid,
        "outcome_id": outcome_id,
        "consolidation_job_id": job_id,
    }


# ── Tool 7: memory_forget ─────────────────────────────────────────────────────

@mcp.tool()
def memory_forget(
    node_id: str | None = None,
    entity: str | None = None,
    before: str | None = None,
    purge: bool = False,
) -> dict:
    """
    Tombstone (soft-delete) or hard-purge memory nodes.

    Args:
        node_id: Specific node ID to forget.
        entity: Entity name — forget all nodes linked to this entity.
        before: ISO timestamp — forget all nodes recorded before this date.
        purge: If True, hard-delete (irreversible). Default: tombstone.
    """
    store = _get_store()
    ids_to_delete: list[str] = []

    if node_id:
        ids_to_delete.append(node_id)

    if entity or before:
        eid = None
        if entity:
            from .resolve import _find_entity
            eid = _find_entity(store, entity)
        candidates = store.find_nodes(before=before, entity_id=eid)
        ids_to_delete.extend(n["id"] for n in candidates)

    ids_to_delete = list(dict.fromkeys(ids_to_delete))  # dedupe

    if not ids_to_delete:
        return {"count": 0, "mode": "purge" if purge else "tombstone", "ids": []}

    if purge:
        count = store.purge(ids_to_delete)
    else:
        count = store.tombstone(ids_to_delete)

    return {"count": count, "mode": "purge" if purge else "tombstone", "ids": ids_to_delete}


# ── Tool 8: memory_verify ─────────────────────────────────────────────────────

@mcp.tool()
def memory_verify(node_id: str, status: str) -> dict:
    """
    Confirm or refute a memory node, adjusting its confidence.

    Args:
        node_id: The node to verify.
        status: 'confirm' (confidence +0.1, capped at 1.0) or 'refute' (confidence ×0.5, closes valid_until).
    """
    store = _get_store()
    node = store.get_node(node_id)
    if not node:
        return {"error": f"Node '{node_id}' not found."}

    conf = float(node.get("confidence") or 1.0)
    if status == "confirm":
        new_conf = min(1.0, conf + 0.1)
        store.update_node(node_id, confidence=new_conf)
        return {"node_id": node_id, "status": "confirmed", "confidence": new_conf}
    elif status == "refute":
        new_conf = conf * 0.5
        store.update_node(node_id, confidence=new_conf, valid_until=_now_iso())
        return {"node_id": node_id, "status": "refuted", "confidence": new_conf}
    else:
        return {"error": f"Unknown status '{status}'. Use 'confirm' or 'refute'."}


# ── Tool 9: memory_start_session ──────────────────────────────────────────────

@mcp.tool()
def memory_start_session(name: str, namespace: str | None = None) -> dict:
    """
    Open a named session. Returns the session ID and whether it was newly created.

    Args:
        name: Human-readable session name (e.g. "JWT auth refactor").
        namespace: Switch to this namespace before opening the session.
    """
    global _session_id, _namespace, _store
    if namespace and namespace != _namespace:
        _namespace = namespace
        _store = None
        _session_id = None

    if _session_id is not None:
        return {"session_id": _session_id, "created": False, "namespace": _namespace}

    store = _get_store()
    sid = store.add_node(
        kind="session",
        content=name,
        data={"started_at": _now_iso(), "agent_id": "default"},
    )
    _session_id = sid
    return {"session_id": sid, "created": True, "namespace": _namespace}


# ── Tool 10: memory_list_sessions ─────────────────────────────────────────────

@mcp.tool()
def memory_list_sessions(limit: int = 50) -> CallToolResult:
    """
    List all sessions with node counts, newest first.

    Args:
        limit: Maximum number of sessions to return.
    """
    store = _get_store()
    sessions = store.list_sessions(limit=limit)
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(sessions))])


# ── Tool 11: memory_clear_session ─────────────────────────────────────────────

@mcp.tool()
def memory_clear_session(session_id: str, purge: bool = False) -> dict:
    """
    Tombstone or hard-purge all nodes belonging to a session.

    Args:
        session_id: The session node ID to clear.
        purge: If True, hard-delete. Default: tombstone.
    """
    store = _get_store()
    return store.delete_session(session_id, purge=purge)


# ── Tool 12: memory_stats ─────────────────────────────────────────────────────

@mcp.tool()
def memory_stats(namespace: str | None = None) -> dict:
    """
    Return node counts by kind, DB size, top entities by degree, and all namespaces.

    Args:
        namespace: If provided, show stats for this namespace instead of the active one.
    """
    if namespace:
        store = MemoryStore(namespace=namespace)
    else:
        store = _get_store()
    return store.stats()


# ── Tool 13: memory_for_code ──────────────────────────────────────────────────

@mcp.tool()
def memory_for_code(file_path: str, line: int | None = None) -> str:
    """
    Return memories that TOUCH a given source file, optionally at a specific line.

    Args:
        file_path: Relative path to the source file (e.g. 'src/auth.py').
        line: Optional line number to narrow results to overlapping ranges.
    """
    store = _get_store()
    nodes = store.get_touches_for_file(file_path, line=line)
    if not nodes:
        return f"No memories TOUCH '{file_path}'" + (f" at line {line}" if line else "") + "."

    lines = [f"## Memories touching `{file_path}`" + (f" @ line {line}" if line else "") + "\n"]
    for n in nodes:
        td = {}
        try:
            td = json.loads(n.get("touches_data") or "{}")
        except Exception:
            pass
        loc = ""
        if td.get("start_line"):
            loc = f" (L{td['start_line']}–{td.get('end_line', '?')})"
        lines.append(f"- [{n['id']}] {n['kind']} · conf {n.get('confidence', 1.0):.2f}{loc} — {n['content']}")
    return "\n".join(lines)


# ── Tool 14: memory_to_code ───────────────────────────────────────────────────

@mcp.tool()
def memory_to_code(memory_id: str) -> CallToolResult:
    """
    Return code locations (file + line range) that a memory node TOUCHES.

    Args:
        memory_id: The memory node ID.
    """
    store = _get_store()
    locs = store.get_touches_from_node(memory_id)
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(locs))])


# ── Tool 15: memory_import ────────────────────────────────────────────────────

@mcp.tool()
def memory_import(nodes: list[dict]) -> dict:
    """
    Bulk-seed memory from a list of node specs.

    Each spec: {content, kind, confidence?, entities?, rationale?, alternatives_rejected?}

    Args:
        nodes: List of node specification dicts.
    """
    store = _get_store()
    session_id = _get_or_create_session()
    valid_kinds = {"fact", "decision", "procedure", "preference", "outcome", "action"}

    imported = 0
    node_ids: list[str] = []
    created_entity_ids: list[str] = []
    errors: list[str] = []

    for i, spec in enumerate(nodes):
        kind = spec.get("kind", "fact")
        content = spec.get("content", "")
        if kind not in valid_kinds:
            errors.append(f"Node {i}: invalid kind '{kind}'")
            continue
        if not content:
            errors.append(f"Node {i}: missing content")
            continue

        data: dict[str, Any] = {}
        if spec.get("rationale"):
            data["rationale"] = spec["rationale"]
        if spec.get("alternatives_rejected"):
            data["alternatives_rejected"] = spec["alternatives_rejected"]

        nid = store.add_node(
            kind=kind,
            content=content,
            data=data or None,
            confidence=float(spec.get("confidence", 1.0)),
            session_id=session_id,
        )
        node_ids.append(nid)

        entities = spec.get("entities")
        if entities:
            linked, created = resolve_entities(store, entities, session_id=session_id)
            created_entity_ids.extend(created)
            for eid in linked:
                try:
                    store.add_edge(nid, eid, "ABOUT")
                except Exception:
                    pass

        imported += 1

    return {
        "imported": imported,
        "node_ids": node_ids,
        "created_entity_ids": created_entity_ids,
        "errors": errors,
    }


# ── Tool 16: memory_switch_namespace ─────────────────────────────────────────

@mcp.tool()
def memory_switch_namespace(namespace: str) -> dict:
    """
    Switch the active namespace. Resets the active session.

    Args:
        namespace: Target namespace name.
    """
    global _namespace, _namespace_explicit, _store, _session_id
    previous = _namespace
    _namespace = namespace
    _namespace_explicit = True  # signal that _store=None is an intentional switch
    _store = None
    _session_id = None
    return {"active_namespace": namespace, "previous_namespace": previous}


# ── Tool 17: memory_verify_staleness ─────────────────────────────────────────

@mcp.tool()
def memory_verify_staleness(queue: bool = True) -> dict:
    """
    Scan TOUCHES edges and flag memories whose source file changed since they were stored.

    Args:
        queue: If True, write a staleness job to the review queue.
    """
    store = _get_store()
    touches = store.get_all_touches()

    # Resolve repo root from the store's db path
    db_path = Path(store.db_path)
    repo_root = db_path.parent.parent  # .nervapack/ → project root

    checked = 0
    stale_ids: list[str] = []
    missing_ids: list[str] = []

    for t in touches:
        fp = t.get("file_path")
        if not fp:
            continue
        checked += 1
        node_recorded_at = t.get("recorded_at", "")
        abs_path = repo_root / fp
        if not abs_path.exists():
            missing_ids.append(t["node_id"])
            continue
        try:
            mtime = abs_path.stat().st_mtime
            mtime_iso = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(timespec="seconds")
            if node_recorded_at and mtime_iso > node_recorded_at:
                stale_ids.append(t["node_id"])
        except Exception:
            pass

    queued = False
    if queue and (stale_ids or missing_ids):
        store.queue_staleness_job({
            "stale_node_ids": stale_ids,
            "missing_node_ids": missing_ids,
        })
        queued = True

    return {
        "checked": checked,
        "stale": len(stale_ids),
        "missing": len(missing_ids),
        "stale_node_ids": stale_ids,
        "missing_node_ids": missing_ids,
        "queued": queued,
    }


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
