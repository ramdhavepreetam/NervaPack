"""
Regex / line-based extractors for languages without a tree-sitter grammar.

RPG, CL, and COBOL (the IBM i / mainframe stack) have no usable tree-sitter
grammar on PyPI, so they cannot go through the AST path in ``ast_parser``.
These are column- and keyword-oriented languages, which makes reliable
line-based symbol extraction practical.

Each ``extract_*`` function takes the file text plus its path and returns a
list of :class:`~nervapack.parser.ast_parser.ParsedEntity`, using the same
entity vocabulary as the tree-sitter path (``class`` / ``function`` /
``import``) so the graph builder wires them up with no special-casing.

``ParsedEntity`` is imported lazily inside each function to avoid an import
cycle (ast_parser -> language_registry -> regex_extractors -> ast_parser).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List


# ── Shared helpers ───────────────────────────────────────────────────────────

def _mk(name, kind, file_path, start_line, end_line, content, lang, ref_kind=None):
    """Build a ParsedEntity (lazy import breaks the ast_parser cycle).

    ``ref_kind`` labels *import* entities with the relationship they represent
    ("call", "copy", or "file") so the graph builder can emit a typed edge
    (CALLS / COPIES / DECLARES_FILE) instead of a generic REFERENCES edge.
    """
    from nervapack.parser.ast_parser import ParsedEntity
    metadata = {"parser": "regex", "lang": lang}
    if ref_kind is not None:
        metadata["ref_kind"] = ref_kind
    return ParsedEntity(
        name=name,
        type=kind,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        content=content,
        metadata=metadata,
    )


def _clean_name(raw: str) -> str:
    """Strip quotes/parens/whitespace and trailing punctuation from a symbol."""
    return raw.strip().strip("'\"();:.").strip()


def _valid(name: str) -> bool:
    return bool(name) and len(name) >= 2


def _ensure_module_entity(entities, content, file_path, lang):
    """Guarantee a linkable definition named after the file/member.

    Copybooks and includes (e.g. a bare `.cpy` with only data items, or an RPG
    `/copy` member) often define no program or procedure, so a `COPY MEMBER`
    elsewhere would have nothing to point at. When the file defines no
    program/class and no procedure/paragraph, prepend a module-level `class`
    entity named after the file stem so member references resolve. Idempotent
    per file.
    """
    # Only synthesize for files that define nothing linkable (pure copybooks /
    # data members). A file that already defines a program or a procedure has a
    # real target — adding a stem-named class would create a duplicate.
    if any(e.type in ("class", "function") for e in entities):
        return entities
    stem = Path(file_path).stem
    if not _valid(stem):
        return entities
    module = _mk(stem, "class", file_path, 1, 1,
                 content.splitlines()[0] if content.strip() else stem, lang)
    module.metadata["module"] = True
    return [module] + entities


# ── RPG (.rpgle .rpg .sqlrpgle) ──────────────────────────────────────────────
#
# Handles both free-form (dcl-proc / dcl-pr) and fixed-form (P/C specs).
# Fixed-form RPG puts a spec letter in column 6 (0-indexed 5).

_RPG_FREE_PROC = re.compile(r"^\s*dcl-proc\s+([A-Za-z0-9_]+)", re.IGNORECASE)
_RPG_FREE_END = re.compile(r"^\s*end-proc\b", re.IGNORECASE)
_RPG_FREE_PR = re.compile(r"^\s*dcl-pr\s+([A-Za-z0-9_]+)", re.IGNORECASE)
_RPG_COPY = re.compile(r"^\s*/(?:copy|include)\s+([^\s]+)", re.IGNORECASE)
# Fixed-form P spec: col 6 = 'P', a name, then 'B' (begin) / 'E' (end).
_RPG_FIXED_P = re.compile(r"^.{5}P\s*([A-Za-z0-9_]+)\s+B", re.IGNORECASE)
# CALL 'PGM' (free-form or C spec).
_RPG_CALL = re.compile(r"\bcall(?:p|b)?\s*\(?\s*'?([A-Za-z0-9_./]+)'?", re.IGNORECASE)


def extract_rpg(content: str, file_path: str) -> List["object"]:
    entities: List[object] = []
    lines = content.splitlines()
    n = len(lines)

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # Full-line comments: free-form '//' or fixed-form '*' in col 7 (idx 6).
        if stripped.startswith("//") or (len(line) > 6 and line[6:7] == "*"):
            continue

        m = _RPG_FREE_PROC.match(line)
        if m and _valid(m.group(1)):
            end = i
            for j in range(i + 1, n):
                if _RPG_FREE_END.match(lines[j]):
                    end = j
                    break
            entities.append(_mk(
                m.group(1), "function", file_path, i + 1, end + 1,
                "\n".join(lines[i:end + 1]), "rpg"))
            continue

        m = _RPG_FIXED_P.match(line)
        if m and _valid(m.group(1)):
            entities.append(_mk(
                m.group(1), "function", file_path, i + 1, i + 1, line, "rpg"))
            continue

        m = _RPG_FREE_PR.match(line)
        if m and _valid(m.group(1)):
            entities.append(_mk(
                m.group(1), "function", file_path, i + 1, i + 1, line, "rpg"))
            continue

        m = _RPG_COPY.match(line)
        if m:
            name = _clean_name(m.group(1))
            if _valid(name):
                entities.append(_mk(
                    name, "import", file_path, i + 1, i + 1, stripped, "rpg",
                    ref_kind="copy"))
            continue

        m = _RPG_CALL.search(line)
        if m:
            name = _clean_name(m.group(1))
            if _valid(name):
                entities.append(_mk(
                    name, "import", file_path, i + 1, i + 1, stripped, "rpg",
                    ref_kind="call"))

    return _ensure_module_entity(entities, content, file_path, "rpg")


# ── CL (.clle .clp .cl) ──────────────────────────────────────────────────────

_CL_PGM = re.compile(r"^\s*(?:[A-Za-z0-9_#]+:\s*)?PGM\b", re.IGNORECASE)
_CL_SUBR = re.compile(r"^\s*SUBR\s+SUBR\s*\(\s*([A-Za-z0-9_#]+)", re.IGNORECASE)
_CL_LABEL = re.compile(r"^\s*([A-Za-z0-9_#]+):\s*(?:$|[A-Za-z])")
_CL_CALL = re.compile(r"\bCALL(?:PRC)?\s+(?:PGM|PRC)?\s*\(?\s*([A-Za-z0-9_#/]+)", re.IGNORECASE)
_CL_DCLF = re.compile(r"\bDCLF\s+FILE\s*\(\s*([A-Za-z0-9_#/]+)", re.IGNORECASE)


def extract_cl(content: str, file_path: str) -> List["object"]:
    entities: List[object] = []
    lines = content.splitlines()
    stem = Path(file_path).stem

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("/*"):
            continue

        if _CL_PGM.match(line):
            entities.append(_mk(
                stem, "class", file_path, i + 1, i + 1, stripped, "cl"))
            continue

        m = _CL_SUBR.match(line)
        if m and _valid(m.group(1)):
            entities.append(_mk(
                m.group(1), "function", file_path, i + 1, i + 1, stripped, "cl"))
            continue

        m = _CL_CALL.search(line)
        if m:
            name = _clean_name(m.group(1))
            if _valid(name):
                entities.append(_mk(
                    name, "import", file_path, i + 1, i + 1, stripped, "cl",
                    ref_kind="call"))
            continue

        m = _CL_DCLF.search(line)
        if m:
            name = _clean_name(m.group(1))
            if _valid(name):
                entities.append(_mk(
                    name, "import", file_path, i + 1, i + 1, stripped, "cl",
                    ref_kind="file"))
            continue

        m = _CL_LABEL.match(line)
        if m and _valid(m.group(1)) and m.group(1).upper() != "PGM":
            entities.append(_mk(
                m.group(1), "function", file_path, i + 1, i + 1, stripped, "cl"))

    return entities


# ── COBOL (.cbl .cob .cobol .cpy) ────────────────────────────────────────────
#
# Fixed-form COBOL reserves cols 1-6 for sequence numbers and col 7 as an
# indicator ('*' = comment, '/' = page eject).  Free-form has no such columns.
# We normalise by stripping a fixed-form prefix when present, then match on the
# resulting text.

_COBOL_PROG_ID = re.compile(r"\bPROGRAM-ID\s*\.\s*([A-Za-z0-9_-]+)", re.IGNORECASE)
_COBOL_DIVISION = re.compile(r"^\s*([A-Za-z0-9-]+)\s+DIVISION\s*\.", re.IGNORECASE)
_COBOL_SECTION = re.compile(r"^\s*([A-Za-z0-9-]+)\s+SECTION\s*\.", re.IGNORECASE)
_COBOL_PARA = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9-]*)\s*\.\s*$")
_COBOL_COPY = re.compile(r"\bCOPY\s+([A-Za-z0-9_-]+)", re.IGNORECASE)
_COBOL_CALL = re.compile(r"\bCALL\s+'?\"?([A-Za-z0-9_-]+)", re.IGNORECASE)


def _cobol_strip_fixed(line: str):
    """Return (text, is_comment). Detects fixed-form indicator column."""
    if len(line) > 6:
        indicator = line[6:7]
        if indicator in ("*", "/"):
            return "", True
        # Heuristic: cols 1-6 are digits/blank on genuine fixed-form source.
        seq = line[:6]
        if seq.strip() == "" or seq.strip().isdigit():
            return line[7:], False
    # Free-form (or short line): treat '*>' and leading '*' as comment.
    s = line.lstrip()
    if s.startswith("*>") or s.startswith("*"):
        return "", True
    return line, False


def extract_cobol(content: str, file_path: str) -> List["object"]:
    entities: List[object] = []
    lines = content.splitlines()
    in_procedure = False

    for i, raw in enumerate(lines):
        text, is_comment = _cobol_strip_fixed(raw)
        if is_comment or not text.strip():
            continue
        stripped = text.strip()

        m = _COBOL_PROG_ID.search(text)
        if m and _valid(m.group(1)):
            entities.append(_mk(
                m.group(1), "class", file_path, i + 1, i + 1, stripped, "cobol"))
            continue

        m = _COBOL_DIVISION.match(text)
        if m:
            if m.group(1).upper() == "PROCEDURE":
                in_procedure = True
            entities.append(_mk(
                f"{m.group(1)}-DIVISION", "function", file_path,
                i + 1, i + 1, stripped, "cobol"))
            continue

        m = _COBOL_SECTION.match(text)
        if m and _valid(m.group(1)):
            entities.append(_mk(
                m.group(1), "function", file_path, i + 1, i + 1, stripped, "cobol"))
            continue

        m = _COBOL_COPY.search(text)
        if m:
            name = _clean_name(m.group(1))
            if _valid(name):
                entities.append(_mk(
                    name, "import", file_path, i + 1, i + 1, stripped, "cobol",
                    ref_kind="copy"))
            continue

        m = _COBOL_CALL.search(text)
        if m:
            name = _clean_name(m.group(1))
            if _valid(name):
                entities.append(_mk(
                    name, "import", file_path, i + 1, i + 1, stripped, "cobol",
                    ref_kind="call"))
            continue

        # Paragraph labels only count inside the PROCEDURE DIVISION, so we
        # don't turn DATA DIVISION level-01 items into functions.
        if in_procedure:
            m = _COBOL_PARA.match(text)
            if m and _valid(m.group(1)):
                entities.append(_mk(
                    m.group(1), "function", file_path, i + 1, i + 1, stripped, "cobol"))

    return _ensure_module_entity(entities, content, file_path, "cobol")
