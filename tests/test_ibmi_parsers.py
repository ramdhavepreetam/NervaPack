"""Tests for the regex-based RPG / CL / COBOL extractors (IBM i / mainframe).

These languages have no tree-sitter grammar, so they go through the pure-Python
regex path in `nervapack.parser.regex_extractors`, wired into the parser via
`LANGUAGE_REGISTRY`.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from nervapack.parser.ast_parser import (
    ASTParser,
    scan_directory,
    _SUPPORTED_EXTENSIONS,
)
from nervapack.parser.regex_extractors import (
    extract_cl,
    extract_cobol,
    extract_rpg,
)
from nervapack.graph.builder import GraphBuilder


def _by_type(entities, kind):
    return sorted(e.name for e in entities if e.type == kind)


def _typed_edges(graph):
    """Return {(source_name, target_name, relation)} for typed IBM i edges."""
    out = set()
    for u, v, d in graph.edges(data=True):
        if d.get("relation") in ("CALLS", "COPIES", "DECLARES_FILE"):
            out.add((graph.nodes[u].get("name"),
                     graph.nodes[v].get("name"),
                     d["relation"]))
    return out


class TestExtensionRegistration(unittest.TestCase):
    def test_all_new_extensions_registered(self):
        for ext in (".rpgle", ".rpg", ".sqlrpgle",
                    ".clle", ".clp", ".cl",
                    ".cbl", ".cob", ".cobol", ".cpy"):
            self.assertIn(ext, _SUPPORTED_EXTENSIONS, ext)


class TestRPG(unittest.TestCase):
    SRC = "\n".join([
        "**free",
        "/copy qrpglesrc,constants",
        "dcl-proc CalcTotal export;",
        "  dcl-pi *n packed(9:2);",
        "  end-pi;",
        "  callp WriteLog('done');",
        "end-proc;",
        "dcl-pr ExternalProc extproc('EXT');",
        "end-pr;",
    ])

    def test_procedures_functions(self):
        ents = extract_rpg(self.SRC, "x.rpgle")
        funcs = _by_type(ents, "function")
        self.assertIn("CalcTotal", funcs)
        self.assertIn("ExternalProc", funcs)

    def test_proc_spans_to_end_proc(self):
        ents = extract_rpg(self.SRC, "x.rpgle")
        proc = next(e for e in ents if e.name == "CalcTotal")
        self.assertEqual(proc.start_line, 3)
        self.assertEqual(proc.end_line, 7)

    def test_copy_and_call_are_imports(self):
        ents = extract_rpg(self.SRC, "x.rpgle")
        imports = _by_type(ents, "import")
        self.assertTrue(any("qrpglesrc" in i for i in imports))
        self.assertIn("WriteLog", imports)

    def test_fixed_form_p_spec(self):
        fixed = "     P CalcNet         B\n     P CalcNet         E"
        ents = extract_rpg(fixed, "x.rpg")
        self.assertIn("CalcNet", _by_type(ents, "function"))

    def test_comment_lines_ignored(self):
        src = "// dcl-proc ShouldNotAppear;\n      * fixed comment"
        ents = extract_rpg(src, "x.rpgle")
        self.assertNotIn("ShouldNotAppear", _by_type(ents, "function"))


class TestCL(unittest.TestCase):
    SRC = "\n".join([
        "PGM PARM(&IN)",
        "  DCLF FILE(MYLIB/CUSTFILE)",
        "  CALL PGM(PROCESS) PARM(&IN)",
        "  CALLPRC PRC(HELPER)",
        "ENDPGM",
    ])

    def test_pgm_is_class_named_after_file(self):
        ents = extract_cl(self.SRC, "/src/MYPGM.clle")
        classes = _by_type(ents, "class")
        self.assertEqual(classes, ["MYPGM"])

    def test_call_and_dclf_imports(self):
        ents = extract_cl(self.SRC, "/src/MYPGM.clle")
        imports = _by_type(ents, "import")
        self.assertIn("PROCESS", imports)
        self.assertIn("HELPER", imports)
        self.assertTrue(any("CUSTFILE" in i for i in imports))

    def test_comment_ignored(self):
        ents = extract_cl("/* a comment */\nPGM", "/src/P.clle")
        # only the PGM class, no bogus entities from the comment
        self.assertEqual(_by_type(ents, "import"), [])


class TestCOBOL(unittest.TestCase):
    SRC = "\n".join([
        "       IDENTIFICATION DIVISION.",
        "       PROGRAM-ID. PAYROLL.",
        "       DATA DIVISION.",
        "       WORKING-STORAGE SECTION.",
        "       01 WS-TOTAL PIC 9(5).",
        "       COPY EMPREC.",
        "       PROCEDURE DIVISION.",
        "       MAIN-PARA.",
        "           CALL 'CALCTAX'.",
        "           PERFORM PRINT-PARA.",
        "       PRINT-PARA.",
        "           DISPLAY WS-TOTAL.",
    ])

    def test_program_id_is_class(self):
        ents = extract_cobol(self.SRC, "PAYROLL.cbl")
        self.assertEqual(_by_type(ents, "class"), ["PAYROLL"])

    def test_copy_and_call_imports(self):
        ents = extract_cobol(self.SRC, "PAYROLL.cbl")
        imports = _by_type(ents, "import")
        self.assertIn("EMPREC", imports)
        self.assertIn("CALCTAX", imports)

    def test_paragraphs_only_in_procedure_division(self):
        funcs = _by_type(extract_cobol(self.SRC, "PAYROLL.cbl"), "function")
        self.assertIn("MAIN-PARA", funcs)
        self.assertIn("PRINT-PARA", funcs)
        # DATA DIVISION level items must NOT become functions
        self.assertNotIn("01", funcs)
        self.assertNotIn("WS-TOTAL", funcs)

    def test_fixed_form_comment_indicator(self):
        # '*' in column 7 marks a comment line
        src = "      * PROGRAM-ID. HIDDEN.\n       PROGRAM-ID. REAL."
        ents = extract_cobol(src, "x.cbl")
        self.assertEqual(_by_type(ents, "class"), ["REAL"])


class TestScanDirectory(unittest.TestCase):
    def test_scan_directory_picks_up_ibmi_files(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.rpgle").write_text(
                "dcl-proc Foo;\nend-proc;\n")
            Path(d, "b.clle").write_text("PGM\n  CALL PGM(BAR)\nENDPGM\n")
            Path(d, "c.cbl").write_text(
                "       PROGRAM-ID. BAZ.\n")
            ents = scan_directory(d)
            names = {e.name for e in ents}
            self.assertIn("Foo", names)
            self.assertIn("BAR", names)
            self.assertIn("BAZ", names)

    def test_garbage_does_not_crash(self):
        parser = ASTParser()
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "junk.rpgle")
            p.write_text("!@#$%^&*()\n\x00\x01 random bytes\nzzz")
            # Should return a (possibly empty) list, never raise.
            self.assertIsInstance(parser.parse_file(str(p)), list)


class TestRefKindMetadata(unittest.TestCase):
    """Import entities carry a ref_kind so the builder can type the edge."""

    def _kinds(self, entities):
        return {e.name: e.metadata.get("ref_kind")
                for e in entities if e.type == "import"}

    def test_rpg_call_vs_copy(self):
        k = self._kinds(extract_rpg(
            "/copy lib,mbr\ndcl-proc P;\n  callp DoThing();\nend-proc;\n", "x.rpgle"))
        self.assertEqual(k.get("DoThing"), "call")
        self.assertTrue(any(v == "copy" for v in k.values()))

    def test_cl_call_vs_file(self):
        k = self._kinds(extract_cl(
            "PGM\n  DCLF FILE(CUSTF)\n  CALL PGM(SUB)\nENDPGM\n", "P.clle"))
        self.assertEqual(k.get("SUB"), "call")
        self.assertEqual(k.get("CUSTF"), "file")

    def test_cobol_call_vs_copy(self):
        k = self._kinds(extract_cobol(
            "       PROGRAM-ID. P.\n       PROCEDURE DIVISION.\n"
            "       M.\n           COPY REC.\n           CALL 'SUB'.\n", "P.cbl"))
        self.assertEqual(k.get("SUB"), "call")
        self.assertEqual(k.get("REC"), "copy")


class TestCopybookModuleEntity(unittest.TestCase):
    """A copybook with no program/procedure still yields a linkable module."""

    def test_bare_copybook_gets_module_class(self):
        ents = extract_cobol(
            "       01 EMPREC.\n          05 EMP-ID PIC 9(5).\n", "/s/EMPREC.cpy")
        classes = [e for e in ents if e.type == "class"]
        self.assertEqual([c.name for c in classes], ["EMPREC"])
        self.assertTrue(classes[0].metadata.get("module"))

    def test_program_file_gets_no_synthetic_module(self):
        # A file that defines a procedure must NOT also get a stem-named class.
        ents = extract_rpg("dcl-proc Foo;\nend-proc;\n", "/s/BAR.rpgle")
        self.assertEqual([e.name for e in ents if e.type == "class"], [])


class TestTypedGraphEdges(unittest.TestCase):
    def _graph_for(self, files):
        with tempfile.TemporaryDirectory() as d:
            for name, body in files.items():
                Path(d, name).write_text(body)
            ents = scan_directory(d)
        return GraphBuilder().build_from_entities(ents)

    def test_call_copy_and_short_names(self):
        g = self._graph_for({
            # 3-char names exercise the removed length floor.
            "RUN.clle": "PGM\n  CALL PGM(ORD)\nENDPGM\n",
            "ORD.rpgle": "**free\ndcl-proc ORD export;\n  callp TAX(1);\nend-proc;\n",
            "TAX.cbl": ("       PROGRAM-ID. TAX.\n       PROCEDURE DIVISION.\n"
                        "       M.\n           COPY EMPREC.\n           STOP RUN.\n"),
            "EMPREC.cpy": "       01 EMPREC.\n          05 X PIC 9(5).\n",
        })
        edges = _typed_edges(g)
        self.assertIn(("RUN", "ORD", "CALLS"), edges)      # CL -> RPG, short names
        self.assertIn(("ORD", "TAX", "CALLS"), edges)      # RPG -> COBOL, cross-language
        self.assertIn(("TAX", "EMPREC", "COPIES"), edges)  # COBOL -> copybook module

    def test_no_duplicate_edges(self):
        g = self._graph_for({
            "RUN.clle": "PGM\n  CALL PGM(ORD)\nENDPGM\n",
            "ORD.rpgle": "**free\ndcl-proc ORD export;\nend-proc;\n",
        })
        calls = [(u, v) for u, v, d in g.edges(data=True)
                 if d.get("relation") == "CALLS"]
        self.assertEqual(len(calls), len(set(calls)))

    def test_dangling_reference_makes_no_edge(self):
        # DCLF to a file not present in the tree must not fabricate an edge.
        g = self._graph_for({"P.clle": "PGM\n  DCLF FILE(NOSUCH)\nENDPGM\n"})
        self.assertNotIn("DECLARES_FILE",
                         {d.get("relation") for _, _, d in g.edges(data=True)})


class TestXmlIncompatibleCharacters(unittest.TestCase):
    """Legacy COBOL/RPG source with NUL bytes, form-feeds, and other control
    characters must not break GraphML serialization."""

    def test_control_chars_stripped_from_entities(self):
        # Interior control chars in a paragraph name and a COPY target.
        src = ("       PROGRAM-ID. PAY.\n"
               "       PROCEDURE DIVISION.\n"
               "       MAIN\x01PARA.\n"
               "           COPY EMP\x00REC.\n")
        ents = extract_cobol(src, "PAY.cbl")
        for e in ents:
            self.assertNotRegex(e.name, r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
            self.assertNotRegex(e.content, r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

    def test_form_feed_page_eject_saves(self):
        # 0x0C (form-feed) is a common mainframe page-eject and is XML-illegal.
        with tempfile.TemporaryDirectory() as d:
            Path(d, "PAY.cbl").write_text(
                "       PROGRAM-ID. PAY.\x0c\n"
                "       PROCEDURE DIVISION.\n"
                "       MAIN-PARA.\x00\n"
                "           STOP RUN.\n")
            b = GraphBuilder()
            b.build_from_entities(scan_directory(d))
            out = os.path.join(d, "g.graphml")
            b.save_graph(out)  # must not raise
            import networkx as nx
            g2 = nx.read_graphml(out)  # must be valid, re-readable GraphML
            self.assertGreater(g2.number_of_nodes(), 0)


if __name__ == "__main__":
    unittest.main()
