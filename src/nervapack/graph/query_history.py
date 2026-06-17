"""
Query history tracking and analytics for NervaPack.

Stores query history in JSONL format for easy appending and reading.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class QueryRecord:
    """A single query execution record."""
    timestamp: str
    query: str
    seed_nodes_count: int
    expanded_nodes_count: int
    total_nodes_retrieved: int
    edges_followed: int
    traversal_depth: int
    nervapack_tokens: int
    naive_tokens: int
    token_savings_pct: float
    source_files_count: int
    execution_time_ms: float


class QueryHistory:
    """Manages query history storage and retrieval."""

    def __init__(self, history_file: Optional[str] = None):
        """
        Initialize query history manager.

        Args:
            history_file: Path to history file. Defaults to .nervapack/query_history.jsonl
        """
        if history_file is None:
            history_file = os.path.join(".nervapack", "query_history.jsonl")

        self.history_file = Path(history_file)
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Ensure the history file and parent directory exist."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.history_file.exists():
            self.history_file.touch()

    def add_query(
        self,
        query: str,
        seed_nodes_count: int,
        expanded_nodes_count: int,
        total_nodes_retrieved: int,
        edges_followed: int,
        traversal_depth: int,
        nervapack_tokens: int,
        naive_tokens: int,
        source_files_count: int,
        execution_time_ms: float,
    ) -> None:
        """
        Add a query record to history.

        Args:
            query: The query string
            seed_nodes_count: Number of seed nodes from vector search
            expanded_nodes_count: Number of nodes expanded from seeds
            total_nodes_retrieved: Total nodes in subgraph
            edges_followed: Number of edges traversed
            traversal_depth: Maximum BFS depth reached
            nervapack_tokens: Token count for NervaPack context
            naive_tokens: Token count for naive RAG approach
            source_files_count: Number of source files in result
            execution_time_ms: Query execution time in milliseconds
        """
        token_savings_pct = 0.0
        if naive_tokens > 0:
            token_savings_pct = ((naive_tokens - nervapack_tokens) / naive_tokens) * 100

        record = QueryRecord(
            timestamp=datetime.now().isoformat(),
            query=query,
            seed_nodes_count=seed_nodes_count,
            expanded_nodes_count=expanded_nodes_count,
            total_nodes_retrieved=total_nodes_retrieved,
            edges_followed=edges_followed,
            traversal_depth=traversal_depth,
            nervapack_tokens=nervapack_tokens,
            naive_tokens=naive_tokens,
            token_savings_pct=token_savings_pct,
            source_files_count=source_files_count,
            execution_time_ms=execution_time_ms,
        )

        # Append to JSONL file
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record)) + "\n")

    def get_recent_queries(self, limit: int = 10) -> List[QueryRecord]:
        """
        Get the most recent N queries.

        Args:
            limit: Maximum number of queries to return

        Returns:
            List of QueryRecord objects, most recent first
        """
        records = []

        if not self.history_file.exists():
            return records

        # Read all records
        with open(self.history_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        records.append(QueryRecord(**data))
                    except (json.JSONDecodeError, TypeError):
                        # Skip malformed lines
                        continue

        # Return most recent N, reversed (newest first)
        return list(reversed(records[-limit:]))

    def get_all_queries(self) -> List[QueryRecord]:
        """
        Get all query records.

        Returns:
            List of all QueryRecord objects
        """
        return self.get_recent_queries(limit=999999)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Calculate aggregate statistics across all queries.

        Returns:
            Dictionary containing:
                - total_queries: Total number of queries
                - avg_token_savings_pct: Average token savings percentage
                - total_tokens_saved: Total tokens saved across all queries
                - avg_execution_time_ms: Average query execution time
                - total_cost_saved_gpt4: Total cost saved (GPT-4o rates)
                - total_cost_saved_sonnet: Total cost saved (Claude Sonnet rates)
                - avg_nodes_retrieved: Average nodes retrieved per query
                - most_common_words: Top 10 most common words in queries
        """
        queries = self.get_all_queries()

        if not queries:
            return {
                "total_queries": 0,
                "avg_token_savings_pct": 0.0,
                "total_tokens_saved": 0,
                "avg_execution_time_ms": 0.0,
                "total_cost_saved_gpt4": 0.0,
                "total_cost_saved_sonnet": 0.0,
                "avg_nodes_retrieved": 0.0,
                "most_common_words": [],
            }

        total_queries = len(queries)
        total_savings_pct = sum(q.token_savings_pct for q in queries)
        total_tokens_saved = sum(q.naive_tokens - q.nervapack_tokens for q in queries)
        total_execution_time = sum(q.execution_time_ms for q in queries)
        total_nodes_retrieved = sum(q.total_nodes_retrieved for q in queries)

        # Cost calculations (rates per million tokens)
        GPT4_RATE = 2.50 / 1_000_000
        SONNET_RATE = 3.00 / 1_000_000
        total_cost_saved_gpt4 = total_tokens_saved * GPT4_RATE
        total_cost_saved_sonnet = total_tokens_saved * SONNET_RATE

        # Word frequency analysis
        word_counts: Dict[str, int] = {}
        for q in queries:
            words = q.query.lower().split()
            for word in words:
                # Remove common punctuation
                word = word.strip(".,!?;:")
                if len(word) > 3:  # Skip very short words
                    word_counts[word] = word_counts.get(word, 0) + 1

        # Sort by frequency
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        most_common_words = sorted_words[:10]

        return {
            "total_queries": total_queries,
            "avg_token_savings_pct": total_savings_pct / total_queries,
            "total_tokens_saved": total_tokens_saved,
            "avg_execution_time_ms": total_execution_time / total_queries,
            "total_cost_saved_gpt4": total_cost_saved_gpt4,
            "total_cost_saved_sonnet": total_cost_saved_sonnet,
            "avg_nodes_retrieved": total_nodes_retrieved / total_queries,
            "most_common_words": most_common_words,
        }

    def clear_history(self) -> None:
        """Clear all query history."""
        if self.history_file.exists():
            self.history_file.unlink()
        self._ensure_file_exists()

    def prune_old_queries(self, keep_last_n: int = 100) -> int:
        """
        Keep only the most recent N queries, delete older ones.

        Args:
            keep_last_n: Number of recent queries to keep

        Returns:
            Number of queries deleted
        """
        all_queries = self.get_all_queries()

        if len(all_queries) <= keep_last_n:
            return 0

        # Keep only the last N
        queries_to_keep = all_queries[-keep_last_n:]
        deleted_count = len(all_queries) - len(queries_to_keep)

        # Rewrite file with only recent queries
        with open(self.history_file, "w", encoding="utf-8") as f:
            for record in queries_to_keep:
                f.write(json.dumps(asdict(record)) + "\n")

        return deleted_count
