"""Tests for EBCDIC detection and decoding of mainframe COBOL/RPG source."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from nervapack.parser.encoding import (
    looks_like_ebcdic,
    read_source_text,
    _best_ebcdic_codec,
    _EBCDIC_CANDIDATE_CODECS,
    DEFAULT_EBCDIC_CODEC,
)
from nervapack.parser.ast_parser import scan_directory

_COBOL = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. PAYROLL.\n"
    "       PROCEDURE DIVISION.\n"
    "       MAIN-PARA.\n"
    "           COPY EMPREC.\n"
    "           CALL 'CALCTAX'.\n"
    "           STOP RUN.\n"
)


def _write(dir_, name, text, codec):
    p = Path(dir_, name)
    p.write_bytes(text.encode(codec))
    return str(p)


class TestDetection(unittest.TestCase):
    def test_ebcdic_bytes_detected(self):
        self.assertTrue(looks_like_ebcdic(_COBOL.encode("cp037")))

    def test_ascii_not_detected(self):
        self.assertFalse(looks_like_ebcdic(_COBOL.encode("utf-8")))

    def test_empty_not_detected(self):
        self.assertFalse(looks_like_ebcdic(b""))


class TestReadSourceText(unittest.TestCase):
    def test_ebcdic_roundtrips_to_readable_text(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write(d, "PAY.cbl", _COBOL, "cp037")
            text = read_source_text(p)
            self.assertIn("PROGRAM-ID. PAYROLL.", text)
            self.assertIn("CALL 'CALCTAX'.", text)
            # newlines normalized so the file is multi-line
            self.assertGreater(len(text.splitlines()), 5)

    def test_ascii_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write(d, "A.cbl", _COBOL, "utf-8")
            self.assertEqual(read_source_text(p).splitlines()[1].strip(),
                             "PROGRAM-ID. PAYROLL.")

    def test_default_codec_is_cp037(self):
        self.assertEqual(DEFAULT_EBCDIC_CODEC, "cp037")


class TestCandidateCodecs(unittest.TestCase):
    def test_candidate_set_includes_cp500_and_cp1140(self):
        self.assertIn("cp500", _EBCDIC_CANDIDATE_CODECS)
        self.assertIn("cp1140", _EBCDIC_CANDIDATE_CODECS)

    def test_cp037_is_first_and_default(self):
        self.assertEqual(_EBCDIC_CANDIDATE_CODECS[0], "cp037")
        self.assertEqual(DEFAULT_EBCDIC_CODEC, "cp037")

    def test_plain_source_defaults_to_cp037_on_tie(self):
        # A/Z/0-9/space/common punctuation coincide across the pages, so plain
        # COBOL is indistinguishable and must fall back to the first candidate.
        for codec in _EBCDIC_CANDIDATE_CODECS:
            self.assertEqual(_best_ebcdic_codec(_COBOL.encode(codec)), "cp037")

    def test_cp500_chosen_when_its_operators_present(self):
        # Bytes 0x4A/0x4F/0x5A decode to '[' '!' ']' in cp500 but to non-ASCII
        # symbols in cp037; a bracket/operator-heavy member should pick cp500.
        line = ("       IF X[1] = Y | Z THEN\n" * 4) + "       PROGRAM-ID. T.\n"
        self.assertEqual(_best_ebcdic_codec(line.encode("cp500")), "cp500")


class TestEndToEnd(unittest.TestCase):
    EXPECTED = {"IDENTIFICATION-DIVISION", "PAYROLL", "PROCEDURE-DIVISION",
                "MAIN-PARA", "EMPREC", "CALCTAX"}

    def test_ebcdic_cobol_extracts_all_symbols(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "PAYROLL.cbl", _COBOL, "cp037")
            names = {e.name for e in scan_directory(d)}
            self.assertTrue(self.EXPECTED.issubset(names), names)


class TestOverride(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("NERVAPACK_EBCDIC")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("NERVAPACK_EBCDIC", None)
        else:
            os.environ["NERVAPACK_EBCDIC"] = self._saved

    def test_off_disables_detection(self):
        os.environ["NERVAPACK_EBCDIC"] = "off"
        with tempfile.TemporaryDirectory() as d:
            p = _write(d, "PAY.cbl", _COBOL, "cp037")
            # Read as UTF-8 → should NOT contain the clean program id.
            self.assertNotIn("PROGRAM-ID. PAYROLL.", read_source_text(p))

    def test_forced_codec(self):
        os.environ["NERVAPACK_EBCDIC"] = "cp037"
        with tempfile.TemporaryDirectory() as d:
            p = _write(d, "PAY.cbl", _COBOL, "cp037")
            self.assertIn("PROGRAM-ID. PAYROLL.", read_source_text(p))

    def test_unknown_codec_falls_back_gracefully(self):
        os.environ["NERVAPACK_EBCDIC"] = "not-a-real-codec"
        with tempfile.TemporaryDirectory() as d:
            p = _write(d, "PAY.cbl", _COBOL, "utf-8")
            # Must not raise; falls back to utf-8.
            self.assertIn("PROGRAM-ID. PAYROLL.", read_source_text(p))


if __name__ == "__main__":
    unittest.main()
