"""
Source-file text decoding, including EBCDIC support for mainframe COBOL/RPG.

Real IBM mainframe source members are frequently stored in **EBCDIC**, not
ASCII/UTF-8. EBCDIC has no byte-order mark or magic number, so this module
detects it heuristically and decodes with the appropriate code page, falling
back to UTF-8 for everything else.

Detection can be overridden with the ``NERVAPACK_EBCDIC`` environment variable:

- ``NERVAPACK_EBCDIC=auto`` (or unset) — heuristic detection (default).
- ``NERVAPACK_EBCDIC=cp037`` (or any codec name) — force this EBCDIC code page
  for every file, skipping detection. Useful for corporate / air-gapped shops
  that know their members are a specific code page.
- ``NERVAPACK_EBCDIC=off`` — disable EBCDIC entirely; always read as UTF-8.

Common EBCDIC code pages: ``cp037`` (US/Canada — the usual default),
``cp500`` (international), ``cp1140`` (US/Canada with euro), ``cp273``
(Germany/Austria).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# Default EBCDIC code page assumed when detection fires without an explicit
# override. cp037 is by far the most common for US/Canada mainframe source.
DEFAULT_EBCDIC_CODEC = "cp037"

# Extensions that may plausibly be EBCDIC. Detection is only attempted for these
# so we never mis-decode a modern UTF-8 file with unusual byte statistics.
_EBCDIC_CANDIDATE_EXTS = {
    ".cbl", ".cob", ".cobol", ".cpy",        # COBOL + copybooks
    ".rpgle", ".rpg", ".sqlrpgle",           # RPG
    ".clle", ".clp", ".cl",                  # CL
}

# How many bytes to sample for detection. Mainframe members are small; a few KB
# is plenty and keeps large-file scanning cheap.
_SAMPLE_BYTES = 4096

# EBCDIC space is 0x40. COBOL/RPG source is heavily space-indented, so genuine
# EBCDIC members are dominated by 0x40 and contain essentially no 0x20 (which is
# a control char, not space, in EBCDIC).
_EBCDIC_SPACE = 0x40
_ASCII_SPACE = 0x20


def _env_override() -> Optional[str]:
    val = os.environ.get("NERVAPACK_EBCDIC", "").strip()
    return val or None


def looks_like_ebcdic(sample: bytes) -> bool:
    """Heuristic: does this byte sample look like EBCDIC text?

    The robust signal is that EBCDIC source is space-indented with 0x40 (the
    EBCDIC space) and uses 0x20 as a control character, essentially never as a
    space. So genuine EBCDIC source has **many 0x40 bytes and (almost) no 0x20**
    — a combination that ASCII/UTF-8 text (which spaces with 0x20) does not
    produce. A byte-value "printable ASCII" test is *not* reliable here because
    many EBCDIC letter/digit/punctuation bytes coincidentally land in the
    0x20-0x7E range, so we do not use it.
    """
    if not sample:
        return False

    n = len(sample)
    ebcdic_space = sample.count(_EBCDIC_SPACE)
    ascii_space = sample.count(_ASCII_SPACE)

    # (1) EBCDIC spaces must be a non-trivial share of the file.
    if ebcdic_space < max(4, n * 0.05):
        return False

    # (2) 0x40 must overwhelmingly dominate 0x20. Indentation-heavy source in
    #     EBCDIC has many 0x40 and near-zero 0x20; ASCII text is the opposite.
    #     Require at least 4x more 0x40 than 0x20 (usually 0x20 is exactly 0).
    if ebcdic_space < ascii_space * 4 + 1:
        return False

    return True


def _resolve_codec(ext: str, raw: bytes) -> Optional[str]:
    """Return the EBCDIC codec to use, or None to read as UTF-8."""
    override = _env_override()
    if override:
        low = override.lower()
        if low in ("off", "none", "false", "0"):
            return None
        if low in ("auto", "detect", "1", "true"):
            pass  # fall through to detection
        else:
            return override  # explicit codec name, e.g. "cp037"

    if ext.lower() not in _EBCDIC_CANDIDATE_EXTS:
        return None
    if looks_like_ebcdic(raw[:_SAMPLE_BYTES]):
        return DEFAULT_EBCDIC_CODEC
    return None


def read_source_text(file_path: str) -> str:
    """Read a source file as text, decoding EBCDIC when detected/forced.

    Falls back to UTF-8 (errors replaced) for non-EBCDIC files, preserving the
    previous behaviour for every ASCII/UTF-8 source file.
    """
    with open(file_path, "rb") as f:
        raw = f.read()

    codec = _resolve_codec(Path(file_path).suffix, raw)
    if codec:
        try:
            text = raw.decode(codec)
            return _normalize_newlines(text)
        except (LookupError, UnicodeDecodeError):
            # Unknown codec name or bytes that don't fit it — fall back rather
            # than crash the whole ingest.
            pass
    return raw.decode("utf-8", errors="replace")


def _normalize_newlines(text: str) -> str:
    """Map EBCDIC/legacy line boundaries to ``\\n``.

    EBCDIC newline (0x25) already decodes to ``\\n``, but the NEL character
    (0x15 -> U+0085) and lone carriage returns do not. Normalising here means
    the line-based extractors and the GraphML sanitizer see consistent Unix
    line endings.
    """
    return text.replace("\r\n", "\n").replace("\x85", "\n").replace("\r", "\n")
