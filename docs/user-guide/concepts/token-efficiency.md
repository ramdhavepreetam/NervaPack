# Token Efficiency

NervaPack reduces token usage by 90% compared to naive RAG. Here's how.

---

## The Token Problem

LLMs have limited context windows:
- GPT-4o: 128K tokens
- Claude Sonnet: 200K tokens

**Problem:** Traditional RAG sends entire files, wasting tokens on irrelevant code.

---

## Naive RAG Approach

```
Query: "How does authentication work?"

Naive RAG:
1. Vector search finds 3 relevant files
2. Send entire files to LLM
3. Total: 12,840 tokens (mostly irrelevant)
```

---

## NervaPack Approach

```
Query: "How does authentication work?"

NervaPack:
1. Vector search finds 3 seed entities
2. Graph traversal (BFS) finds related code
3. Extract only relevant classes/functions
4. Total: 1,180 tokens (90.8% reduction)
```

---

## Token Savings Dashboard

Every query shows savings:
```
╭──────────────  Token Efficiency  ──────────────╮
│  Naive RAG        12,840   ████████████████    │
│  NervaPack         1,180   █░░░░░░░░░░░░░░░    │
│                                                 │
│  Savings: 11,660 tokens (90.8%)                │
│  Cost saved: $0.0292/query (GPT-4o)            │
╰─────────────────────────────────────────────────╯
```

---

## Why This Matters

1. **Lower costs** — Less API spending
2. **Faster responses** — Smaller prompts
3. **Better quality** — LLM focuses on relevant code
4. **More context** — Fit more queries in same window
