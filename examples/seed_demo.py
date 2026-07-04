"""
Seed demo: two-session demonstration of nervapack.memory cross-process recall.

Session A (run first):
    Stores a decision "Chose JWT over session cookies for auth_service" with
    rationale and entity, then ends the session.

Session B (run after):
    Recalls "why JWT for auth" and prints the packed result.

Usage:
    python examples/seed_demo.py session_a
    python examples/seed_demo.py session_b

Or run both automatically:
    python examples/seed_demo.py demo
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def session_a(db_path: str | None = None) -> None:
    """Store a JWT decision and end the session."""
    from nervapack.memory.store import MemoryStore
    from nervapack.memory.resolve import resolve_entities

    store = MemoryStore(db_path=db_path)

    # Create a session node
    sid = store.add_node(
        kind="session",
        content="Auth architecture session",
        data={"agent_id": "demo_agent", "task": "Choose auth mechanism"},
    )

    # Store the decision with rationale
    decision_id = store.add_node(
        kind="decision",
        content="Chose JWT over session cookies for auth_service",
        data={
            "rationale": "JWT is stateless and enables horizontal scaling without shared session store.",
            "alternatives_rejected": ["server-side sessions", "PASETO"],
        },
        confidence=0.9,
        session_id=sid,
    )

    # Resolve / create the entity
    linked, created = resolve_entities(store, ["auth_service"], session_id=sid)
    entity_id = linked[0]

    # Link decision → entity and → session
    store.add_edge(decision_id, entity_id, "ABOUT")
    store.add_edge(decision_id, sid, "OCCURRED_IN")

    # Also store a supporting fact
    fact_id = store.add_node(
        kind="fact",
        content="auth_service issues 15-minute access tokens with rotating refresh tokens",
        confidence=1.0,
        session_id=sid,
    )
    store.add_edge(fact_id, entity_id, "ABOUT")
    store.add_edge(fact_id, sid, "OCCURRED_IN")

    # Close the session
    from nervapack.memory.store import _now_iso
    store.update_node(sid, valid_until=_now_iso())

    print(f"[session_a] Stored decision: {decision_id}")
    print(f"[session_a] Stored fact: {fact_id}")
    print(f"[session_a] Closed session: {sid}")
    print(f"[session_a] DB: {store.db_path}")


def session_b(db_path: str | None = None) -> None:
    """Recall why JWT was chosen."""
    from nervapack.memory.store import MemoryStore
    from nervapack.memory.recall import recall

    store = MemoryStore(db_path=db_path)
    result = recall(store, "why JWT for auth", budget_tokens=500)
    print("\n" + "=" * 60)
    print("SESSION B — RECALL RESULT")
    print("=" * 60)
    print(result)
    print("=" * 60)

    # Verify budget
    from nervapack.memory.pack import CharTokenCounter
    tc = CharTokenCounter()
    tokens = tc.count(result)
    print(f"\nToken count: {tokens}/500  ✓" if tokens <= 500 else f"\nToken count: {tokens}/500  ✗ EXCEEDS BUDGET")


def run_demo(db_path: str | None = None) -> None:
    print("=== NervaPack Memory Demo ===\n")
    print("--- Running Session A (store) ---")
    session_a(db_path)
    print("\n--- Running Session B (recall, same process) ---")
    session_b(db_path)


if __name__ == "__main__":
    import os
    db = os.environ.get("NERVAPACK_MEMORY_DB")

    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
    if cmd == "session_a":
        session_a(db)
    elif cmd == "session_b":
        session_b(db)
    else:
        run_demo(db)
