from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import networkx as nx

NODE_COLORS = {
    "file":     "#AED6F1",  # steel blue
    "function": "#A9DFBF",  # mint green
    "class":    "#F0B27A",  # amber
    "import":   "#D5D8DC",  # light gray
    "markdown": "#C39BD3",  # lavender
}

NODE_SIZES = {
    "file":     22,
    "class":    16,
    "function": 12,
    "import":   8,
    "markdown": 14,
}


def _tooltip(data: dict) -> str:
    lines = [f"<b>type:</b> {data.get('type', '?')}"]
    if data.get("name"):
        lines.append(f"<b>name:</b> {data['name']}")
    if data.get("path"):
        lines.append(f"<b>path:</b> {Path(data['path']).name}")
    if data.get("file_path"):
        lines.append(f"<b>file:</b> {Path(data['file_path']).name}")
    if data.get("start_line"):
        lines.append(f"<b>lines:</b> {data['start_line']}–{data.get('end_line', '?')}")
    if data.get("header"):
        lines.append(f"<b>header:</b> {data['header']}")
    content = data.get("content", "")
    if content:
        preview = content[:180].replace("<", "&lt;").replace(">", "&gt;")
        if len(content) > 180:
            preview += "…"
        lines.append(f"<br><code>{preview}</code>")
    return "<br>".join(lines)


def _short_label(node_id: str, data: dict) -> str:
    if data.get("name"):
        return data["name"]
    if data.get("path"):
        return Path(data["path"]).name
    if data.get("header"):
        h = data["header"]
        return h[:30] + "…" if len(h) > 30 else h
    return node_id.split(":")[-1][:25]


# Above this many nodes, in-browser force-directed physics never stabilises and
# pins the CPU, so we disable it and render a static layout instead.
_PHYSICS_NODE_LIMIT = 2000

# Hard caps on what we hand the browser. A 400k-edge canvas is unusable even
# with physics off, so we render the most-connected core and note the rest.
_MAX_NODES = 3000
_MAX_EDGES = 8000


def _cap_graph(graph: nx.DiGraph, max_nodes: int, max_edges: int):
    """Return a subgraph of the most-connected nodes, plus a summary dict.

    Selecting highest-degree nodes keeps the structurally important hubs
    (heavily-called programs, shared copybooks) rather than an arbitrary slice.
    """
    n, e = graph.number_of_nodes(), graph.number_of_edges()
    if n <= max_nodes and e <= max_edges:
        return graph, None

    # Keep the top-degree nodes.
    degrees = sorted(graph.degree, key=lambda kv: kv[1], reverse=True)
    keep = {node for node, _ in degrees[:max_nodes]}
    sub = graph.subgraph(keep).copy()

    # If still over the edge cap, drop lowest-weight/oldest edges deterministically.
    if sub.number_of_edges() > max_edges:
        edges = list(sub.edges())[max_edges:]
        sub.remove_edges_from(edges)

    return sub, {
        "total_nodes": n, "total_edges": e,
        "shown_nodes": sub.number_of_nodes(), "shown_edges": sub.number_of_edges(),
    }


def export_html(graph: nx.DiGraph, output_path: str,
                max_nodes: int = _MAX_NODES, max_edges: int = _MAX_EDGES) -> Optional[dict]:
    """Render the graph to an interactive HTML file.

    For large graphs, physics is disabled (so the browser doesn't run an
    unbounded force simulation) and the view is capped to the most-connected
    core. Returns a summary dict when capping occurred, else None.
    """
    try:
        from pyvis.network import Network
    except ImportError:
        raise ImportError("pyvis is required for visualization. Run: pip install pyvis")

    os.makedirs(Path(output_path).parent, exist_ok=True)

    graph, cap_info = _cap_graph(graph, max_nodes, max_edges)
    physics_on = graph.number_of_nodes() <= _PHYSICS_NODE_LIMIT

    net = Network(
        height="92vh",
        width="100%",
        directed=True,
        bgcolor="#0f0f1a",
        font_color="#e0e0e0",
        # select_menu / filter_menu are intentionally OFF — they cause pyvis to
        # inject <script src="lib/tom-select/..."> and <script src="lib/bindings/utils.js">
        # which are relative paths that don't exist next to the output HTML file,
        # producing "TomSelect is not defined" and 404s in the browser.
        select_menu=False,
        filter_menu=False,
    )

    net.set_options(json.dumps({
        "physics": {
            # Disabled for large graphs: a live force simulation over thousands
            # of nodes / hundreds of thousands of edges never stabilises in the
            # browser and pins the CPU. With physics off, vis.js lays nodes out
            # once and renders immediately.
            "enabled": physics_on,
            "solver": "forceAtlas2Based",
            "forceAtlas2Based": {
                "gravitationalConstant": -60,
                "centralGravity": 0.005,
                "springLength": 120,
                "springConstant": 0.08,
                "damping": 0.6,
            },
            "stabilization": {"iterations": 200},
        },
        "edges": {
            "smooth": {"type": "curvedCW", "roundness": 0.2},
            "font": {"size": 9, "color": "#aaaaaa"},
            "color": {"color": "#444466", "highlight": "#8888ff"},
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.6}},
        },
        "nodes": {
            "font": {"size": 11},
            "borderWidth": 1,
            "borderWidthSelected": 2,
        },
        "interaction": {
            "hover": True,
            "tooltipDelay": 100,
            "navigationButtons": True,
            "keyboard": True,
        },
    }))

    for node_id, data in graph.nodes(data=True):
        node_type = data.get("type", "unknown")
        net.add_node(
            node_id,
            label=_short_label(node_id, data),
            color={
                "background": NODE_COLORS.get(node_type, "#888888"),
                "border": "#222244",
                "highlight": {"background": "#ffffff", "border": "#6666ff"},
            },
            size=NODE_SIZES.get(node_type, 10),
            title=_tooltip(data),
            shape="dot" if node_type != "file" else "diamond",
        )

    for u, v, edata in graph.edges(data=True):
        relation = edata.get("relation", "")
        net.add_edge(
            u, v,
            label=relation,
            color="#5555aa" if relation == "EXPLAINS" else "#336655",
            dashes=(relation == "EXPLAINS"),
        )

    # Legend HTML injected into the page
    legend_html = """
<div id="np-legend" style="
    position:fixed; top:12px; right:12px; z-index:9999;
    background:rgba(15,15,26,0.92); border:1px solid #333366;
    border-radius:8px; padding:12px 16px; font-family:monospace;
    font-size:12px; color:#ccc; min-width:160px;">
  <div style="font-weight:bold; margin-bottom:8px; color:#8888ff;">NervaPack Graph</div>
  <div><span style="display:inline-block;width:12px;height:12px;background:#AED6F1;border-radius:50%;margin-right:6px;"></span>file</div>
  <div><span style="display:inline-block;width:12px;height:12px;background:#A9DFBF;border-radius:50%;margin-right:6px;"></span>function</div>
  <div><span style="display:inline-block;width:12px;height:12px;background:#F0B27A;border-radius:50%;margin-right:6px;"></span>class</div>
  <div><span style="display:inline-block;width:12px;height:12px;background:#D5D8DC;border-radius:50%;margin-right:6px;"></span>import</div>
  <div><span style="display:inline-block;width:12px;height:12px;background:#C39BD3;border-radius:50%;margin-right:6px;"></span>markdown</div>
  <div style="margin-top:8px; font-size:11px; color:#888;">
    <span style="color:#336655;">━━</span> DEFINES &nbsp;
    <span style="color:#5555aa;">╌╌</span> EXPLAINS
  </div>
</div>
"""

    # Save, clean up pyvis artefacts, and inject legend
    net.save_graph(output_path)
    with open(output_path, "r", encoding="utf-8") as f:
        html = f.read()

    import re as _re

    # pyvis always emits <script src="lib/bindings/utils.js"> even when
    # select_menu=False — this is a relative path that 404s when the HTML is
    # opened from any location other than the pyvis package directory.
    html = _re.sub(r'<script\s+src=["\']lib/bindings/utils\.js["\']>\s*</script>', '', html)

    # pyvis template also contains a commented-out node_modules vis block;
    # strip it to avoid confusion and CSP noise.
    html = _re.sub(
        r'<!--\s*<link[^>]*node_modules[^>]*>.*?<script[^>]*node_modules[^>]*>.*?</script>\s*-->',
        '',
        html,
        flags=_re.DOTALL,
    )

    html = html.replace("</body>", legend_html + "\n</body>")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return cap_info
