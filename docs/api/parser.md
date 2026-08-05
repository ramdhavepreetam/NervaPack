# Parser API

The parser layer turns source files into `ParsedEntity` objects. Most languages
go through the tree-sitter path in `ast_parser`; the IBM i / mainframe stack
(RPG, CL, COBOL), which has no tree-sitter grammar, is handled by the
pure-Python `regex_extractors` module. See
[IBM i Languages](../user-guide/concepts/ibm-i-languages.md) for the
higher-level overview.

::: nervapack.parser.ast_parser
    options:
      show_source: true

::: nervapack.parser.regex_extractors
    options:
      show_source: true

::: nervapack.parser.encoding
    options:
      show_source: true

::: nervapack.parser.md_chunker
    options:
      show_source: true
