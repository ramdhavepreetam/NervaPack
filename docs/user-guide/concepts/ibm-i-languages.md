# IBM i / Mainframe Languages (RPG, CL, COBOL)

> Added in **v0.7.0**

NervaPack indexes the IBM i / mainframe stack — **RPG**, **CL** (Control
Language), and **COBOL** — as first-class citizens of the knowledge graph:
symbols become nodes, and `CALL` / `COPY` / file declarations become typed
dependency edges that resolve across files and even across languages.

This support is **bundled and always on** — there is no extra to install and no
grammar to compile. It works offline and in air-gapped / corporate networks,
consistent with NervaPack's privacy-first design.

---

## Why these languages are handled differently

Every other language NervaPack supports is parsed with a
[tree-sitter](https://tree-sitter.github.io/) grammar. RPG, CL, and COBOL have
**no usable tree-sitter grammar on PyPI**, so they are parsed by a dedicated
pure-Python, line/column-based extractor (`nervapack.parser.regex_extractors`)
that runs alongside the tree-sitter path.

This is a deliberate, scoped fallback. RPG, CL, and COBOL are
column- and keyword-oriented by design, which makes line-based extraction
reliable — and it avoids vendoring and compiling C grammars in environments
that have no toolchain or no network access. Tree-sitter remains the default
for every language that has a grammar.

A file is routed to the regex path when its extension maps to a
`LanguageConfig` whose `regex_extractor` is set (and `grammar_loader` is
`None`) — see the [Parser API](../../api/parser.md).

---

## Supported extensions

| Language | Extensions |
|---|---|
| **RPG** | `.rpgle`, `.rpg`, `.sqlrpgle` |
| **CL** (Control Language) | `.clle`, `.clp`, `.cl` |
| **COBOL** | `.cbl`, `.cob`, `.cobol`, `.cpy` (copybooks) |

Both fixed-form and free-form source are handled. Fixed-form sequence columns
(1–6) and the indicator column (7) are recognised — comment lines (`*` / `/` in
column 7, or free-form `//` and `*>`) are skipped.

---

## What gets extracted

Each extractor emits the same `ParsedEntity` vocabulary as the tree-sitter path
(`class` / `function` / `import`), so the rest of the pipeline — graph builder,
vector store, retrieval — treats these languages identically to any other.

### RPG

| Source construct | Node |
|---|---|
| `dcl-proc NAME` … `end-proc` (free-form procedure) | `function` (spans to `end-proc`) |
| `dcl-pr NAME` (prototype) | `function` |
| Fixed-form `P` spec (`P NAME B`) | `function` |
| `/copy` and `/include` | `import` (ref_kind `copy`) |
| `CALL` / `CALLP` / `CALLB 'PGM'` | `import` (ref_kind `call`) |

### CL

| Source construct | Node |
|---|---|
| `PGM` | `class` (named after the source member) |
| `SUBR` label | `function` |
| `CALL PGM(NAME)` / `CALLPRC` | `import` (ref_kind `call`) |
| `DCLF FILE(NAME)` | `import` (ref_kind `file`) |

### COBOL

| Source construct | Node |
|---|---|
| `PROGRAM-ID. NAME` | `class` |
| `... DIVISION` | `function` (e.g. `PROCEDURE-DIVISION`) |
| `... SECTION` | `function` |
| Paragraph label (PROCEDURE DIVISION only) | `function` |
| `COPY NAME` | `import` (ref_kind `copy`) |
| `CALL 'NAME'` / `CALL NAME` | `import` (ref_kind `call`) |

!!! note "Paragraphs vs. data items"
    COBOL paragraph labels are only treated as functions inside the
    `PROCEDURE DIVISION`. Level-numbered data items in the `DATA DIVISION`
    (e.g. `01 WS-TOTAL`) are intentionally **not** turned into functions.

!!! note "Copybooks resolve to a module node"
    A copybook that defines no program or procedure (e.g. a bare `.cpy` of data
    items) yields a **module-level node named after the member**, so a
    `COPY MEMBER` from another program has something to point at.

---

## Typed dependency edges

Instead of collapsing every reference into a single generic edge, NervaPack
emits **typed** edges for IBM i so the call graph and the copybook-usage graph
are separately queryable:

| Source construct | Edge relation |
|---|---|
| `CALL` / `CALLP` / `CALLPRC` | `CALLS` |
| `/copy` / `COPY` | `COPIES` |
| CL `DCLF FILE(...)` | `DECLARES_FILE` |

Each typed edge carries the source line (`ref_line`) and a confidence of `0.9`
(`source="regex"`). Targets are resolved by:

1. **Symbol name** — a same-named `class`/`function` definition anywhere in the
   graph, then
2. **File-stem fallback** — a member reference to a file, e.g. `COPY EMPREC`
   → `EMPREC.cpy`, `CALL PGM(ORD)` → `ORD.rpgle`.

Because resolution spans all files, edges are **cross-file and
cross-language** — an RPG program that calls a COBOL program produces a real
`CALLS` edge between them.

!!! tip "Dangling references make no edge"
    If a `CALL` or `DCLF` target is not present anywhere in the indexed tree,
    **no edge is fabricated**. A missing edge means the target isn't in scope,
    not that the reference was ignored.

### Short names link correctly

IBM i program and file names are frequently ≤ 4 characters (`AR100`, `INV`,
`ORD`, `PAY`). The generic name-overlap heuristic normally ignores names
shorter than 4 characters to limit false positives; that floor is **relaxed for
IBM i (regex-parsed) entities** so short-named programs link. The floor still
applies to tree-sitter languages, and a generic reference never overwrites a
precise typed edge.

---

## Worked example

Given four members:

```rpg title="ORD.rpgle"
**free
/copy qrpglesrc,ordconst
dcl-proc ORD export;
  callp TAX(1);
end-proc;
```

```cl title="RUN.clle"
PGM
  CALL PGM(ORD)
ENDPGM
```

```cobol title="TAX.cbl"
       PROGRAM-ID. TAX.
       PROCEDURE DIVISION.
       MAIN-PARA.
           COPY EMPREC.
           STOP RUN.
```

```cobol title="EMPREC.cpy"
       01 EMPREC.
          05 EMP-ID PIC 9(5).
```

After `nervapack ingest .`, the graph contains these typed edges:

```
CALLS   RUN:RUN    → ORD:ORD       (CL → RPG, 3-char names)
CALLS   ORD:ORD    → TAX:TAX       (RPG → COBOL, cross-language)
COPIES  TAX:TAX    → EMPREC:EMPREC (copybook dependency)
```

You can now answer questions that are painful on a green-screen system:

- **"What calls `TAX`?"** → follow incoming `CALLS` edges.
- **"Which programs copy `EMPREC`?"** → follow incoming `COPIES` edges.
- **"What does `ORD` depend on?"** → follow outgoing edges from `ORD`.

…and feed that connected context to an LLM via `query_codebase` for
modernization, onboarding, or impact analysis — at a fraction of the tokens of
dumping raw fixed-form source.

---

## Limitations

The regex extractors are precise about program/procedure structure and
CALL/COPY/file dependencies, but they are **not** a full parser. Currently out
of scope:

- **Data-structure / field-level modeling** (RPG `dcl-ds` members, COBOL
  `DATA DIVISION` field layouts).
- **Dynamic calls** — `CALL` via a variable rather than a literal name is not
  resolvable and produces no edge.
- **Embedded SQL** inside `.sqlrpgle` is treated as RPG text, not parsed as SQL.
- Nested/conditional call structure is flattened — an edge records *that* a
  call exists and its line, not the control-flow path to it.

These are candidates for future refinement; the current scope targets the
inventory + dependency map that IBM i teams most need.

---

## See also

- [Architecture](architecture.md) — graph node and edge model
- [Parser API](../../api/parser.md) — `ast_parser` and `regex_extractors`
- [Changelog](../../changelog.md) — v0.7.0 release notes
