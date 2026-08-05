import networkx as nx
import re
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Set
from nervapack.parser.ast_parser import ParsedEntity

_WORD_RE = re.compile(r'[a-zA-Z_]\w*')

class GraphBuilder:
    def __init__(self):
        self.graph = nx.DiGraph()
        self._file_index: Dict[str, Set[str]] = defaultdict(set)

    def build_from_entities(self, entities: List[ParsedEntity]) -> nx.DiGraph:
        """
        Takes a list of ParsedEntity and constructs a directed graph.
        Files are nodes, entities are nodes. Contains/Defines edges connect them.
        """
        for entity in entities:
            # File Node
            file_node_id = f"file:{entity.file_path}"
            if not self.graph.has_node(file_node_id):
                self.graph.add_node(file_node_id, type="file", path=entity.file_path)

            # Entity Node
            # Unique ID for the entity
            entity_node_id = f"{entity.type}:{entity.file_path}:{entity.name}:{entity.start_line}"
            self.graph.add_node(
                entity_node_id,
                type=entity.type,
                name=entity.name,
                file_path=entity.file_path,
                start_line=entity.start_line,
                end_line=entity.end_line,
                content=entity.content
            )
            self._file_index[entity.file_path].add(entity_node_id)

            # Edge from File -> Entity
            self.graph.add_edge(file_node_id, entity_node_id, relation="DEFINES", source="ast", confidence=1.0)

        # ── Typed edges from regex-parsed import entities ─────────────────────
        # Regex extractors (RPG/CL/COBOL) emit `import` entities tagged with a
        # ref_kind ("call"/"copy"/"file"). Turn each into a precise, typed edge
        # to the matching definition — no length floor, since IBM i program and
        # file names are frequently <= 4 chars (AR100, INV, ORD, PAY).
        self._add_typed_reference_edges(entities)

        # ── Heuristic cross-file name resolution (all languages) ──────────────
        # Group entities by their *definition* names. A short-name floor guards
        # against false positives from common tokens in normal source, but it is
        # relaxed for regex-parsed (IBM i) entities whose names are short by
        # convention.
        entity_nodes_by_name: Dict[str, List[str]] = defaultdict(list)
        for entity in entities:
            if not entity.name or entity.type == "import":
                continue
            if len(entity.name) >= 4 or self._is_regex_parsed(entity):
                entity_node_id = f"{entity.type}:{entity.file_path}:{entity.name}:{entity.start_line}"
                entity_nodes_by_name[entity.name].append(entity_node_id)

        name_set: Set[str] = set(entity_nodes_by_name.keys())

        # For each entity, tokenize its content and find overlaps.
        # Intersect words with name_set first — reduces inner iterations by ~95%.
        for entity in entities:
            if not entity.content:
                continue

            entity_node_id = f"{entity.type}:{entity.file_path}:{entity.name}:{entity.start_line}"
            words = set(_WORD_RE.findall(entity.content)) & name_set
            for word in words:
                if word == entity.name:
                    continue
                for target_id in entity_nodes_by_name[word]:
                    if target_id != entity_node_id:
                        # Don't overwrite a precise typed edge with a generic one.
                        if self.graph.has_edge(entity_node_id, target_id):
                            continue
                        self.graph.add_edge(
                            entity_node_id,
                            target_id,
                            relation="REFERENCES",
                            source="heuristic",
                            confidence=0.7
                        )

        return self.graph

    @staticmethod
    def _is_regex_parsed(entity) -> bool:
        return bool(getattr(entity, "metadata", None)) and entity.metadata.get("parser") == "regex"

    # ref_kind on the import entity -> edge relation on the graph
    _REF_KIND_RELATION = {"call": "CALLS", "copy": "COPIES", "file": "DECLARES_FILE"}

    def _add_typed_reference_edges(self, entities: List[ParsedEntity]) -> None:
        """Emit CALLS / COPIES / DECLARES_FILE edges from tagged import entities.

        Source of the edge is the enclosing program/definition in the same file
        when one exists (e.g. the PROGRAM-ID class, or the sole procedure),
        otherwise the file node. Target is every same-named definition anywhere
        in the graph — this is what produces cross-file / cross-language edges.
        """
        # Index definitions (call/copy targets) by name — no length floor.
        defs_by_name: Dict[str, List[str]] = defaultdict(list)
        for e in entities:
            if e.name and e.type in ("class", "function"):
                node_id = f"{e.type}:{e.file_path}:{e.name}:{e.start_line}"
                defs_by_name[e.name].append(node_id)

        # Index files by their stem (uppercased). IBM i COPY/CALL/DCLF frequently
        # target a *member* — e.g. `COPY EMPREC` -> EMPREC.cpy, `CALL PGM(ORD)` ->
        # ORD.rpgle, `DCLF FILE(CUSTF)` -> CUSTF.* — so we resolve against file
        # stems in addition to in-source definition symbols.
        files_by_stem: Dict[str, str] = {}
        for e in entities:
            stem = Path(e.file_path).stem.upper()
            files_by_stem.setdefault(stem, f"file:{e.file_path}")

        # For each file, pick a representative source node: prefer a class
        # (PROGRAM-ID / CL PGM), else the first function, else the file node.
        source_by_file: Dict[str, str] = {}
        for e in entities:
            if e.type == "class":
                source_by_file[e.file_path] = f"class:{e.file_path}:{e.name}:{e.start_line}"
        for e in entities:
            if e.file_path not in source_by_file and e.type == "function":
                source_by_file[e.file_path] = f"function:{e.file_path}:{e.name}:{e.start_line}"

        for e in entities:
            if e.type != "import":
                continue
            ref_kind = (getattr(e, "metadata", None) or {}).get("ref_kind")
            relation = self._REF_KIND_RELATION.get(ref_kind)
            if relation is None:
                continue

            source_id = source_by_file.get(e.file_path, f"file:{e.file_path}")

            # Resolve targets: same-named definitions first, then a file-stem
            # fallback (member reference). De-dup so a symbol whose file also
            # matches the stem doesn't create two edges to effectively the same
            # place.
            targets = list(defs_by_name.get(e.name, []))
            if not targets:
                stem_target = files_by_stem.get(e.name.upper())
                if stem_target is not None:
                    targets.append(stem_target)

            for target_id in targets:
                if target_id == source_id or not self.graph.has_node(target_id):
                    continue
                self.graph.add_edge(
                    source_id,
                    target_id,
                    relation=relation,
                    source="regex",
                    confidence=0.9,
                    ref_line=e.start_line,
                )

    # XML 1.0 forbids C0 control characters except tab/LF/CR. Legacy source
    # (notably fixed-form RPG/COBOL and copybooks) can carry NUL bytes,
    # form-feeds, and other control chars that would make write_graphml raise
    # "All strings must be XML compatible". This is the last line of defense —
    # it protects every language, whatever produced the attribute.
    _XML_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

    def _sanitize_for_graphml(self) -> None:
        for _, data in self.graph.nodes(data=True):
            for key, value in data.items():
                if isinstance(value, str) and self._XML_ILLEGAL.search(value):
                    data[key] = self._XML_ILLEGAL.sub("", value)
        for _, _, data in self.graph.edges(data=True):
            for key, value in data.items():
                if isinstance(value, str) and self._XML_ILLEGAL.search(value):
                    data[key] = self._XML_ILLEGAL.sub("", value)

    def save_graph(self, path: str = ".nervapack/graph.graphml"):
        import os
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._sanitize_for_graphml()
        nx.write_graphml(self.graph, path)

    def load_graph(self, path: str = ".nervapack/graph.graphml"):
        self.graph = nx.read_graphml(path)
        return self.graph

    def remove_nodes_for_file(self, file_path: str):
        """Removes the file node and all entities associated with it."""
        nodes_to_remove = list(self._file_index.pop(file_path, set()))
        file_node_id = f"file:{file_path}"
        if self.graph.has_node(file_node_id):
            nodes_to_remove.append(file_node_id)
        self.graph.remove_nodes_from(nodes_to_remove)


def find_matching_nodes(graph: nx.DiGraph, target: str) -> List[str]:
    """Return node IDs matching `target` by file path, name, or node ID.

    Case-insensitive substring match — the same matching used by `explore`.
    """
    t = target.lower()
    matches: List[str] = []
    for node_id, data in graph.nodes(data=True):
        file_path = data.get("file_path") or data.get("path", "")
        if target in file_path:
            matches.append(node_id)
            continue
        if t in (data.get("name", "") or "").lower():
            matches.append(node_id)
            continue
        if target in node_id:
            matches.append(node_id)
    return matches


def scoped_subgraph(graph: nx.DiGraph, target: str, hops: int = 2):
    """Extract the N-hop neighbourhood around nodes matching `target`.

    Returns (subgraph, matched_node_ids). The subgraph is an undirected-style
    ego network — it follows both successors (callees/definitions) and
    predecessors (callers) so you see what a program calls *and* who calls it.
    Returns (empty_graph, []) when nothing matches.
    """
    from collections import deque

    seeds = find_matching_nodes(graph, target)
    if not seeds:
        return nx.DiGraph(), []

    keep: Set[str] = set(seeds)
    for seed in seeds:
        visited: Set[str] = set()
        queue = deque([(seed, 0)])
        while queue:
            current, depth = queue.popleft()
            if current in visited or depth > hops:
                continue
            visited.add(current)
            keep.add(current)
            if depth < hops:
                for nb in graph.successors(current):
                    if nb not in visited:
                        queue.append((nb, depth + 1))
                for nb in graph.predecessors(current):
                    if nb not in visited:
                        queue.append((nb, depth + 1))

    return graph.subgraph(keep).copy(), seeds
