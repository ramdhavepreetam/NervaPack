"""
Enhanced graph visualization with search, filtering, and community detection.

Builds on pyvis but adds:
- Search functionality
- Advanced filtering (by type, language, directory)
- Community detection with color coding
- Path highlighting
- Minimap for large graphs
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Dict, List, Set

import networkx as nx

# Import community detection
try:
    from networkx.algorithms import community
    HAS_COMMUNITY = True
except ImportError:
    HAS_COMMUNITY = False

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

# Community colors (vibrant palette)
COMMUNITY_COLORS = [
    "#FF6B6B",  # Red
    "#4ECDC4",  # Teal
    "#FFE66D",  # Yellow
    "#95E1D3",  # Mint
    "#F38181",  # Pink
    "#AA96DA",  # Purple
    "#FCBAD3",  # Light pink
    "#A8D8EA",  # Light blue
    "#FFA07A",  # Light salmon
    "#98D8C8",  # Turquoise
]


def _tooltip(data: dict) -> str:
    """Generate HTML tooltip for a node."""
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

    # Add community info if present
    if data.get("community") is not None:
        lines.append(f"<b>community:</b> {data['community']}")

    content = data.get("content", "")
    if content:
        preview = content[:180].replace("<", "&lt;").replace(">", "&gt;")
        if len(content) > 180:
            preview += "…"
        lines.append(f"<br><code>{preview}</code>")
    return "<br>".join(lines)


def _short_label(node_id: str, data: dict) -> str:
    """Generate short display label for a node."""
    if data.get("name"):
        return data["name"]
    if data.get("path"):
        return Path(data["path"]).name
    if data.get("header"):
        h = data["header"]
        return h[:30] + "…" if len(h) > 30 else h
    return node_id.split(":")[-1][:25]


def detect_communities(graph: nx.DiGraph) -> Dict[str, int]:
    """
    Detect communities in the graph using the Louvain method.

    Returns:
        Dictionary mapping node_id to community_id
    """
    if not HAS_COMMUNITY:
        return {}

    # Convert to undirected for community detection
    undirected = graph.to_undirected()

    try:
        # Use Louvain method (greedy modularity optimization)
        communities = community.greedy_modularity_communities(undirected)

        # Map nodes to community IDs
        node_to_community = {}
        for i, comm in enumerate(communities):
            for node in comm:
                node_to_community[node] = i

        return node_to_community
    except Exception:
        # Fallback if community detection fails
        return {}


def export_html_enhanced(
    graph: nx.DiGraph,
    output_path: str,
    enable_search: bool = True,
    enable_community_detection: bool = True,
    enable_minimap: bool = False,
) -> None:
    """
    Export graph as enhanced interactive HTML visualization.

    Args:
        graph: NetworkX DiGraph to visualize
        output_path: Path to save HTML file
        enable_search: Add search bar and highlighting
        enable_community_detection: Color nodes by detected communities
        enable_minimap: Add minimap for navigation (experimental)
    """
    try:
        from pyvis.network import Network
    except ImportError:
        raise ImportError("pyvis is required for visualization. Run: pip install pyvis")

    os.makedirs(Path(output_path).parent, exist_ok=True)

    # Detect communities if enabled
    node_to_community = {}
    if enable_community_detection:
        node_to_community = detect_communities(graph)

    # Create network
    net = Network(
        height="92vh",
        width="100%",
        directed=True,
        bgcolor="#0f0f1a",
        font_color="#e0e0e0",
        select_menu=False,  # Disabled - using custom search instead
        filter_menu=False,  # Disabled - using custom search instead
    )

    net.set_options(json.dumps({
        "physics": {
            "enabled": True,
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

    # Add nodes with community colors if available
    for node_id, data in graph.nodes(data=True):
        node_type = data.get("type", "unknown")

        # Determine color
        if enable_community_detection and node_id in node_to_community:
            community_id = node_to_community[node_id]
            background_color = COMMUNITY_COLORS[community_id % len(COMMUNITY_COLORS)]
            # Store community in node data for tooltip
            data["community"] = community_id
        else:
            background_color = NODE_COLORS.get(node_type, "#888888")

        net.add_node(
            node_id,
            label=_short_label(node_id, data),
            color={
                "background": background_color,
                "border": "#222244",
                "highlight": {"background": "#ffffff", "border": "#6666ff"},
            },
            size=NODE_SIZES.get(node_type, 10),
            title=_tooltip(data),
            shape="dot" if node_type != "file" else "diamond",
            # Add metadata for filtering
            type=node_type,
            file_path=data.get("file_path", ""),
        )

    # Add edges
    for u, v, edata in graph.edges(data=True):
        relation = edata.get("relation", "")
        net.add_edge(
            u, v,
            label=relation,
            color="#5555aa" if relation == "EXPLAINS" else "#336655",
            dashes=(relation == "EXPLAINS"),
        )

    # Save graph
    net.save_graph(output_path)

    # Enhance HTML with custom controls
    import re as _re
    with open(output_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Strip pyvis relative-path artefacts that 404 in the browser
    html = _re.sub(r'<script\s+src=["\']lib/bindings/utils\.js["\']>\s*</script>', '', html)
    html = _re.sub(
        r'<!--\s*<link[^>]*node_modules[^>]*>.*?<script[^>]*node_modules[^>]*>.*?</script>\s*-->',
        '', html, flags=_re.DOTALL,
    )

    # Build enhanced UI
    enhanced_ui = _build_enhanced_ui(
        enable_search=enable_search,
        enable_community=enable_community_detection,
        num_communities=len(set(node_to_community.values())) if node_to_community else 0,
    )

    # Inject enhanced UI before </body>
    html = html.replace("</body>", enhanced_ui + "\n</body>")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def _build_enhanced_ui(enable_search: bool, enable_community: bool, num_communities: int, enable_path_finder: bool = True) -> str:
    """Build HTML for enhanced UI controls."""

    components = []

    # Legend
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
  </div>"""

    if enable_community and num_communities > 0:
        legend_html += f"""
  <div style="margin-top:8px; padding-top:8px; border-top:1px solid #333;">
    <div style="font-weight:bold; margin-bottom:4px; color:#8888ff;">Communities</div>
    <div style="font-size:10px; color:#999;">{num_communities} detected</div>
  </div>"""

    legend_html += "\n</div>"
    components.append(legend_html)

    # Search bar
    if enable_search:
        search_html = """
<div id="np-search" style="
    position:fixed; top:12px; left:12px; z-index:9999;
    background:rgba(15,15,26,0.92); border:1px solid #333366;
    border-radius:8px; padding:12px; font-family:monospace;">
  <input type="text" id="search-input" placeholder="Search nodes..." style="
    background:#1a1a2e; border:1px solid #444; border-radius:4px;
    padding:6px 10px; color:#e0e0e0; font-size:12px; width:200px;"
    onkeyup="searchNodes(event)">
  <button onclick="npClearSearch()" style="
    background:#333366; border:none; border-radius:4px;
    padding:6px 12px; color:#e0e0e0; font-size:12px; margin-left:4px;
    cursor:pointer;">Clear</button>
  <div id="search-results" style="margin-top:8px; font-size:11px; color:#888;"></div>
</div>

<script>
// Search uses the same npOriginalNodeState snapshot as the path finder.
// We snapshot on first search so we always restore to unmodified sizes/colors.
var npSearchSnapshotTaken = false;

function searchNodes(event) {
  var searchTerm = document.getElementById('search-input').value.toLowerCase();
  var resultsDiv = document.getElementById('search-results');

  if (!searchTerm) {
    npClearSearch();
    return;
  }

  // Snapshot original state once (before any modification)
  if (!npSearchSnapshotTaken && Object.keys(npOriginalNodeState).length === 0) {
    npSnapshot();
    npSearchSnapshotTaken = true;
  }

  var allNodes = network.body.data.nodes.get();
  var matchingIds = [];
  allNodes.forEach(function(node) {
    var label = (node.label || '').toLowerCase();
    var type  = (node.type  || '').toLowerCase();
    if (label.includes(searchTerm) || type.includes(searchTerm)) {
      matchingIds.push(node.id);
    }
  });

  resultsDiv.innerHTML = 'Found ' + matchingIds.length + ' node(s)';

  var updates = allNodes.map(function(node) {
    var isMatch = matchingIds.indexOf(node.id) !== -1;
    var origSize = npOriginalNodeState[node.id] ? npOriginalNodeState[node.id].size : node.size;
    return {
      id: node.id,
      opacity: isMatch ? 1.0 : 0.15,
      size: isMatch ? origSize * 1.5 : origSize
    };
  });
  network.body.data.nodes.update(updates);

  if (matchingIds.length > 0) {
    network.focus(matchingIds[0], { scale: 1.5, animation: true });
  }
}

function npClearSearch() {
  document.getElementById('search-input').value = '';
  document.getElementById('search-results').innerHTML = '';
  npSearchSnapshotTaken = false;
  // Only restore if path finder hasn't taken over the state
  if (!npPathActive) {
    if (Object.keys(npOriginalNodeState).length > 0) {
      npRestore();
    } else {
      // Fallback: just reset opacity without size changes
      var updates = network.body.data.nodes.get().map(function(n) {
        return { id: n.id, opacity: 1.0 };
      });
      network.body.data.nodes.update(updates);
      network.fit();
    }
  }
}
</script>
"""
        components.append(search_html)

    # Path finder
    if enable_path_finder:
        path_finder_html = """
<div id="np-path-finder" style="
    position:fixed; bottom:12px; left:12px; z-index:9999;
    background:rgba(15,15,26,0.92); border:1px solid #333366;
    border-radius:8px; padding:12px; font-family:monospace; max-width:400px;">
  <div style="font-weight:bold; margin-bottom:8px; color:#8888ff;">Path Finder</div>
  <div style="margin-bottom:8px;">
    <input type="text" id="path-source" placeholder="Click a node (source)..." style="
      background:#1a1a2e; border:1px solid #444; border-radius:4px;
      padding:4px 8px; color:#e0e0e0; font-size:11px; width:100%; margin-bottom:4px;">
    <input type="text" id="path-target" placeholder="Click a node (target)..." style="
      background:#1a1a2e; border:1px solid #444; border-radius:4px;
      padding:4px 8px; color:#e0e0e0; font-size:11px; width:100%;">
  </div>
  <button onclick="npFindPath()" style="
    background:#4ECDC4; border:none; border-radius:4px;
    padding:6px 12px; color:#0f0f1a; font-size:12px; font-weight:bold;
    cursor:pointer; width:100%;">Find Path</button>
  <button onclick="npClearPath()" style="
    background:#333366; border:none; border-radius:4px;
    padding:4px 8px; color:#e0e0e0; font-size:11px; margin-top:4px;
    cursor:pointer; width:100%;">Clear Path</button>
  <div id="path-results" style="margin-top:8px; font-size:11px; color:#888;"></div>
</div>

<script>
// Global state for path finder and search
// Keyed by node id, stores {color, size} before any highlighting
var npOriginalNodeState = {};
var npOriginalEdgeColors = {};
var npPathActive = false;
var npSearchActive = false;
var npClickMode = 'path';  // always filling path source/target on click

// Snapshot current node/edge appearance before modifying
function npSnapshot() {
  npOriginalNodeState = {};
  npOriginalEdgeColors = {};
  network.body.data.nodes.get().forEach(function(node) {
    npOriginalNodeState[node.id] = { color: node.color, size: node.size };
  });
  network.body.data.edges.get().forEach(function(edge) {
    npOriginalEdgeColors[edge.id] = edge.color;
  });
}

// Restore every node/edge to the snapshot state and fit view
function npRestore() {
  var nodeUpdates = network.body.data.nodes.get().map(function(node) {
    var orig = npOriginalNodeState[node.id];
    return {
      id: node.id,
      opacity: 1.0,
      size: orig ? orig.size : node.size,
      color: orig ? orig.color : node.color
    };
  });
  var edgeUpdates = network.body.data.edges.get().map(function(edge) {
    return {
      id: edge.id,
      color: npOriginalEdgeColors[edge.id] || edge.color,
      width: 1,
      opacity: 1.0
    };
  });
  network.body.data.nodes.update(nodeUpdates);
  network.body.data.edges.update(edgeUpdates);
  network.fit();
}

// ---- Path Finder ----

function npFindPath() {
  var sourceId = document.getElementById('path-source').value.trim();
  var targetId = document.getElementById('path-target').value.trim();
  var resultsDiv = document.getElementById('path-results');

  if (!sourceId || !targetId) {
    resultsDiv.innerHTML = '<span style="color:#FF6B6B;">Select both source and target nodes first</span>';
    return;
  }

  var path = npBFS(sourceId, targetId);

  if (!path) {
    resultsDiv.innerHTML = '<span style="color:#FF6B6B;">No path found between these nodes</span>';
    return;
  }

  npSnapshot();
  npPathActive = true;
  npHighlightPath(path);

  resultsDiv.innerHTML =
    '<span style="color:#4ECDC4;">Path found!</span><br>' +
    '<span style="color:#888;">Edges: ' + (path.length - 1) + ' &nbsp; Nodes: ' + path.length + '</span>';
}

function npBFS(sourceId, targetId) {
  var edges = network.body.data.edges.get();
  var adj = {};
  edges.forEach(function(edge) {
    if (!adj[edge.from]) adj[edge.from] = [];
    adj[edge.from].push(edge.to);
    // also traverse backwards so path finder works in both directions
    if (!adj[edge.to]) adj[edge.to] = [];
    adj[edge.to].push(edge.from);
  });

  var queue = [[sourceId]];
  var visited = {};
  visited[sourceId] = true;

  while (queue.length > 0) {
    var current = queue.shift();
    var node = current[current.length - 1];
    if (node === targetId) return current;
    var neighbors = adj[node] || [];
    for (var i = 0; i < neighbors.length; i++) {
      var nb = neighbors[i];
      if (!visited[nb]) {
        visited[nb] = true;
        queue.push(current.concat([nb]));
      }
    }
  }
  return null;
}

function npHighlightPath(path) {
  var allNodes = network.body.data.nodes.get();
  var allEdges = network.body.data.edges.get();
  var pathSet = {};
  path.forEach(function(id) { pathSet[id] = true; });

  var pathEdgeIds = {};
  for (var i = 0; i < path.length - 1; i++) {
    var from = path[i], to = path[i + 1];
    allEdges.forEach(function(e) {
      if ((e.from === from && e.to === to) || (e.from === to && e.to === from)) {
        pathEdgeIds[e.id] = true;
      }
    });
  }

  var nodeUpdates = allNodes.map(function(node) {
    var inPath = pathSet[node.id];
    return {
      id: node.id,
      opacity: inPath ? 1.0 : 0.1,
      size: inPath ? (npOriginalNodeState[node.id] ? npOriginalNodeState[node.id].size * 1.5 : 15) : node.size,
      color: inPath ? { background: '#FF6B6B', border: '#FF0000',
                        highlight: { background: '#FF8888', border: '#FF0000' } }
                    : node.color
    };
  });

  var edgeUpdates = allEdges.map(function(edge) {
    var inPath = pathEdgeIds[edge.id];
    return {
      id: edge.id,
      color: inPath ? '#FF6B6B' : edge.color,
      width: inPath ? 4 : 1,
      opacity: inPath ? 1.0 : 0.1
    };
  });

  network.body.data.nodes.update(nodeUpdates);
  network.body.data.edges.update(edgeUpdates);
  network.fit({ nodes: path, animation: true });
}

function npClearPath() {
  document.getElementById('path-source').value = '';
  document.getElementById('path-target').value = '';
  document.getElementById('path-results').innerHTML = '';
  document.getElementById('path-source').style.borderColor = '#444';
  document.getElementById('path-target').style.borderColor = '#444';
  npPathActive = false;
  if (Object.keys(npOriginalNodeState).length > 0) {
    npRestore();
  }
}

// ---- Wire up click-to-fill ----
function npInitClickHandler() {
  if (typeof network === 'undefined' || !network) {
    setTimeout(npInitClickHandler, 100);
    return;
  }
  network.on('click', function(params) {
    if (params.nodes.length === 0) return;
    var nodeId = params.nodes[0];
    var src = document.getElementById('path-source');
    var tgt = document.getElementById('path-target');
    if (!src.value) {
      src.value = nodeId;
      src.style.borderColor = '#4ECDC4';
    } else if (!tgt.value) {
      tgt.value = nodeId;
      tgt.style.borderColor = '#4ECDC4';
    } else {
      tgt.value = nodeId;
    }
  });
}
npInitClickHandler();
</script>
"""
        components.append(path_finder_html)

    # Node list panel
    node_list_html = """
<div id="np-node-list" style="
    position:fixed; top:80px; left:12px; z-index:9998;
    background:rgba(15,15,26,0.95); border:1px solid #333366;
    border-radius:8px; padding:12px; font-family:monospace;
    max-height:calc(100vh - 100px); width:280px;
    display:none;">
  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
    <div style="font-weight:bold; color:#8888ff;">📋 Node List</div>
    <button onclick="toggleNodeList()" style="
      background:#444; border:none; border-radius:4px;
      padding:2px 8px; color:#e0e0e0; font-size:10px; cursor:pointer;">✕</button>
  </div>
  <input type="text" id="node-list-filter" placeholder="Filter nodes..." style="
    background:#1a1a2e; border:1px solid #444; border-radius:4px;
    padding:4px 8px; color:#e0e0e0; font-size:11px; width:100%; margin-bottom:8px;"
    onkeyup="filterNodeList()">
  <div id="node-list-content" style="
    overflow-y:auto; max-height:calc(100vh - 200px); font-size:11px;">
    <div style="color:#888; text-align:center; padding:20px;">Loading nodes...</div>
  </div>
</div>

<button id="toggle-node-list-btn" onclick="toggleNodeList()" style="
    position:fixed; top:80px; left:12px; z-index:9998;
    background:rgba(15,15,26,0.92); border:1px solid #333366;
    border-radius:8px; padding:8px 12px; font-family:monospace;
    color:#8888ff; font-size:11px; cursor:pointer; font-weight:bold;">
  📋 Show Nodes
</button>

<script>
function toggleNodeList() {
  const panel = document.getElementById('np-node-list');
  const btn = document.getElementById('toggle-node-list-btn');
  if (panel.style.display === 'none') {
    panel.style.display = 'block';
    btn.style.display = 'none';
    if (!window.nodeListPopulated) {
      populateNodeList();
    }
  } else {
    panel.style.display = 'none';
    btn.style.display = 'block';
  }
}

function populateNodeList() {
  if (typeof network === 'undefined' || !network) {
    setTimeout(populateNodeList, 100);
    return;
  }

  const allNodes = network.body.data.nodes.get();

  // Group nodes by type
  const nodesByType = {};
  allNodes.forEach(node => {
    const type = node.type || 'unknown';
    if (!nodesByType[type]) nodesByType[type] = [];
    nodesByType[type].push(node);
  });

  // Sort types
  const sortedTypes = Object.keys(nodesByType).sort();

  // Build HTML
  let html = '';
  sortedTypes.forEach(type => {
    const nodes = nodesByType[type];
    const color = nodes[0].color?.background || '#888';

    html += `<div class="node-type-group" style="margin-bottom:12px;">
      <div style="color:#8888ff; font-weight:bold; margin-bottom:4px; font-size:10px; text-transform:uppercase;">
        <span style="display:inline-block;width:8px;height:8px;background:${color};border-radius:50%;margin-right:4px;"></span>
        ${type} (${nodes.length})
      </div>`;

    nodes.slice(0, 50).forEach(node => {  // Limit to 50 per type for performance
      const label = node.label || node.id;
      const shortLabel = label.length > 35 ? label.substring(0, 35) + '...' : label;
      html += `<div class="node-item" data-node-id="${node.id}" data-label="${label.toLowerCase()}"
        onclick="focusNode('${node.id}')" style="
        padding:4px 6px; margin:2px 0; background:#1a1a2e; border-radius:4px;
        cursor:pointer; color:#ccc; transition:all 0.2s;"
        onmouseover="this.style.background='#2a2a3e'; this.style.color='#fff';"
        onmouseout="this.style.background='#1a1a2e'; this.style.color='#ccc';">
        ${shortLabel}
      </div>`;
    });

    if (nodes.length > 50) {
      html += `<div style="color:#666; font-size:10px; padding:4px;">...and ${nodes.length - 50} more</div>`;
    }

    html += `</div>`;
  });

  document.getElementById('node-list-content').innerHTML = html;
  window.nodeListPopulated = true;
}

function filterNodeList() {
  const filter = document.getElementById('node-list-filter').value.toLowerCase();
  const items = document.querySelectorAll('.node-item');
  const groups = document.querySelectorAll('.node-type-group');

  if (!filter) {
    items.forEach(item => item.style.display = 'block');
    groups.forEach(group => group.style.display = 'block');
    return;
  }

  groups.forEach(group => {
    let hasVisibleItems = false;
    const groupItems = group.querySelectorAll('.node-item');
    groupItems.forEach(item => {
      const label = item.getAttribute('data-label');
      if (label.includes(filter)) {
        item.style.display = 'block';
        hasVisibleItems = true;
      } else {
        item.style.display = 'none';
      }
    });
    group.style.display = hasVisibleItems ? 'block' : 'none';
  });
}

function focusNode(nodeId) {
  if (typeof network === 'undefined' || !network) return;

  network.focus(nodeId, {
    scale: 1.5,
    animation: {
      duration: 500,
      easingFunction: 'easeInOutQuad'
    }
  });

  // Highlight the node temporarily
  network.selectNodes([nodeId]);
  setTimeout(() => {
    network.unselectAll();
  }, 2000);
}

// Initialize node list when network is ready
setTimeout(() => {
  if (typeof network !== 'undefined' && network) {
    // Prepopulate in background for faster first open
    populateNodeList();
  }
}, 2000);
</script>
"""
    components.append(node_list_html)

    return "\n".join(components)


# Backward compatibility - keep old function name
def export_html(graph: nx.DiGraph, output_path: str) -> None:
    """
    Basic export function for backward compatibility.
    Uses enhanced version with default settings.
    """
    export_html_enhanced(
        graph,
        output_path,
        enable_search=True,
        enable_community_detection=False,  # Keep simple by default
        enable_minimap=False,
    )
