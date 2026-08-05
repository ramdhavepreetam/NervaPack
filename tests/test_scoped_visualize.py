"""Tests for scoped subgraph extraction used by `visualize --scope`."""
from __future__ import annotations

import unittest

import networkx as nx

from nervapack.graph.builder import scoped_subgraph, find_matching_nodes


def _sample():
    g = nx.DiGraph()
    for n in ["PAYROLL", "CALCTAX", "DEDUCT", "TAXRATES", "RUNNER", "UNRELATED"]:
        g.add_node(f"function:{n}", type="function", name=n)
    g.add_edge("function:RUNNER", "function:PAYROLL", relation="CALLS")
    g.add_edge("function:PAYROLL", "function:CALCTAX", relation="CALLS")
    g.add_edge("function:PAYROLL", "function:DEDUCT", relation="CALLS")
    g.add_edge("function:CALCTAX", "function:TAXRATES", relation="COPIES")
    return g


def _names(graph):
    return sorted(d["name"] for _, d in graph.nodes(data=True))


class TestFindMatching(unittest.TestCase):
    def test_match_by_name_case_insensitive(self):
        self.assertEqual(find_matching_nodes(_sample(), "payroll"),
                         ["function:PAYROLL"])

    def test_no_match(self):
        self.assertEqual(find_matching_nodes(_sample(), "NOPE"), [])


class TestScopedSubgraph(unittest.TestCase):
    def test_one_hop_includes_callers_and_callees(self):
        sub, seeds = scoped_subgraph(_sample(), "PAYROLL", 1)
        self.assertEqual(seeds, ["function:PAYROLL"])
        # caller RUNNER + callees CALCTAX/DEDUCT + PAYROLL; not TAXRATES/UNRELATED
        self.assertEqual(_names(sub), ["CALCTAX", "DEDUCT", "PAYROLL", "RUNNER"])

    def test_two_hops_reaches_copybook(self):
        sub, _ = scoped_subgraph(_sample(), "PAYROLL", 2)
        self.assertIn("TAXRATES", _names(sub))
        self.assertNotIn("UNRELATED", _names(sub))

    def test_unrelated_never_included(self):
        sub, _ = scoped_subgraph(_sample(), "PAYROLL", 5)
        self.assertNotIn("UNRELATED", _names(sub))

    def test_no_match_returns_empty(self):
        sub, seeds = scoped_subgraph(_sample(), "NOPE", 2)
        self.assertEqual(seeds, [])
        self.assertEqual(sub.number_of_nodes(), 0)


if __name__ == "__main__":
    unittest.main()
