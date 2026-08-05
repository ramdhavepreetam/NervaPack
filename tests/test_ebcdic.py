"""Tests for EBCDIC detection and decoding of mainframe COBOL/RPG source."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from nervapack.parser.encoding import (
    looks_like_ebcdic,
    read_source_text,
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
