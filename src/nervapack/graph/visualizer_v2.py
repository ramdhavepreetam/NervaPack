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
    with open(output_path, "r", encoding="utf-8") as f:
        html = f.read()

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
  <button onclick="clearSearch()" style="
    background:#333366; border:none; border-radius:4px;
    padding:6px 12px; color:#e0e0e0; font-size:12px; margin-left:4px;
    cursor:pointer;">Clear</button>
  <div id="search-results" style="margin-top:8px; font-size:11px; color:#888;"></div>
</div>

<script>
// network variable is already declared by pyvis above

function searchNodes(event) {
  const searchTerm = document.getElementById('search-input').value.toLowerCase();
  const resultsDiv = document.getElementById('search-results');

  if (!searchTerm) {
    clearSearch();
    return;
  }

  // Get all nodes
  const allNodes = network.body.data.nodes.get();
  const matchingNodes = allNodes.filter(node => {
    const label = (node.label || '').toLowerCase();
    const type = (node.type || '').toLowerCase();
    return label.includes(searchTerm) || type.includes(searchTerm);
  });

  resultsDiv.innerHTML = `Found ${matchingNodes.length} nodes`;

  // Highlight matching nodes
  const allNodeIds = allNodes.map(n => n.id);
  const matchingIds = matchingNodes.map(n => n.id);

  // Update node visibility/opacity
  const updates = allNodes.map(node => {
    if (matchingIds.includes(node.id)) {
      return {
        id: node.id,
        opacity: 1.0,
        size: node.size * 1.5,  // Enlarge matching nodes
      };
    } else {
      return {
        id: node.id,
        opacity: 0.2,  // Dim non-matching nodes
      };
    }
  });

  network.body.data.nodes.update(updates);

  // Focus on first match if any
  if (matchingIds.length > 0) {
    network.focus(matchingIds[0], {
      scale: 1.5,
      animation: true
    });
  }
}

function clearSearch() {
  document.getElementById('search-input').value = '';
  document.getElementById('search-results').innerHTML = '';

  // Reset all nodes to normal
  const allNodes = network.body.data.nodes.get();
  const updates = allNodes.map(node => ({
    id: node.id,
    opacity: 1.0,
    size: node.size || 10,
  }));
  network.body.data.nodes.update(updates);

  network.fit();
}

// Capture network instance when vis.js creates it
document.addEventListener('DOMContentLoaded', function() {
  // Wait for network to be created
  setTimeout(function() {
    if (typeof network !== 'undefined') {
      console.log('NervaPack enhanced search ready');
    }
  }, 1000);
});
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
  <div style="font-weight:bold; margin-bottom:8px; color:#8888ff;">🔍 Path Finder</div>
  <div style="margin-bottom:8px;">
    <input type="text" id="path-source" placeholder="Click node or type ID..." style="
      background:#1a1a2e; border:1px solid #444; border-radius:4px;
      padding:4px 8px; color:#e0e0e0; font-size:11px; width:100%; margin-bottom:4px;">
    <input type="text" id="path-target" placeholder="Click another node..." style="
      background:#1a1a2e; border:1px solid #444; border-radius:4px;
      padding:4px 8px; color:#e0e0e0; font-size:11px; width:100%;">
  </div>
  <button onclick="findPath()" style="
    background:#4ECDC4; border:none; border-radius:4px;
    padding:6px 12px; color:#0f0f1a; font-size:12px; font-weight:bold;
    cursor:pointer; width:100%;">Find Path</button>
  <button onclick="clearPath()" style="
    background:#333366; border:none; border-radius:4px;
    padding:4px 8px; color:#e0e0e0; font-size:11px; margin-top:4px;
    cursor:pointer; width:100%;">Clear Path</button>
  <div id="path-results" style="margin-top:8px; font-size:11px; color:#888;"></div>
</div>

<script>
let originalNodeColors = {};
let originalEdgeColors = {};

// Wait for network to be initialized before attaching handlers
function initPathFinder() {
  if (typeof network === 'undefined' || !network) {
    setTimeout(initPathFinder, 100);
    return;
  }

  // Click handler to select nodes for path finding
  network.on("click", function(params) {
  if (params.nodes.length > 0) {
    const nodeId = params.nodes[0];
    const sourceInput = document.getElementById('path-source');
    const targetInput = document.getElementById('path-target');

    if (!sourceInput.value) {
      sourceInput.value = nodeId;
      sourceInput.style.borderColor = '#4ECDC4';
    } else if (!targetInput.value) {
      targetInput.value = nodeId;
      targetInput.style.borderColor = '#4ECDC4';
    } else {
      // Both filled, replace target
      targetInput.value = nodeId;
    }
  }
});

function findPath() {
  const sourceId = document.getElementById('path-source').value;
  const targetId = document.getElementById('path-target').value;
  const resultsDiv = document.getElementById('path-results');

  if (!sourceId || !targetId) {
    resultsDiv.innerHTML = '<span style="color:#FF6B6B;">Please select both source and target nodes</span>';
    return;
  }

  // Simple BFS to find shortest path
  const path = findShortestPath(sourceId, targetId);

  if (!path) {
    resultsDiv.innerHTML = '<span style="color:#FF6B6B;">No path found between nodes</span>';
    return;
  }

  // Highlight the path
  highlightPath(path);

  resultsDiv.innerHTML = `
    <span style="color:#4ECDC4;">✓ Path found!</span><br>
    <span style="color:#888;">Length: ${path.length - 1} edges</span><br>
    <span style="color:#888;">Nodes: ${path.length}</span>
  `;
}

function findShortestPath(sourceId, targetId) {
  const edges = network.body.data.edges.get();

  // Build adjacency list
  const graph = {};
  edges.forEach(edge => {
    if (!graph[edge.from]) graph[edge.from] = [];
    graph[edge.from].push(edge.to);
    // For undirected search, uncomment:
    // if (!graph[edge.to]) graph[edge.to] = [];
    // graph[edge.to].push(edge.from);
  });

  // BFS
  const queue = [[sourceId]];
  const visited = new Set([sourceId]);

  while (queue.length > 0) {
    const path = queue.shift();
    const node = path[path.length - 1];

    if (node === targetId) {
      return path;
    }

    const neighbors = graph[node] || [];
    for (const neighbor of neighbors) {
      if (!visited.has(neighbor)) {
        visited.add(neighbor);
        queue.push([...path, neighbor]);
      }
    }
  }

  return null;
}

function highlightPath(path) {
  const allNodes = network.body.data.nodes.get();
  const allEdges = network.body.data.edges.get();

  // Store original colors
  allNodes.forEach(node => {
    originalNodeColors[node.id] = node.color;
  });
  allEdges.forEach(edge => {
    originalEdgeColors[edge.id] = edge.color;
  });

  // Dim all nodes and edges
  const nodeUpdates = allNodes.map(node => ({
    id: node.id,
    opacity: path.includes(node.id) ? 1.0 : 0.15,
    size: path.includes(node.id) ? (node.size || 10) * 1.5 : node.size,
    color: path.includes(node.id) ? {
      background: '#FF6B6B',
      border: '#FF0000',
      highlight: {background: '#FF8888', border: '#FF0000'}
    } : node.color
  }));

  // Highlight edges in path
  const pathEdges = [];
  for (let i = 0; i < path.length - 1; i++) {
    const from = path[i];
    const to = path[i + 1];
    const edge = allEdges.find(e => e.from === from && e.to === to);
    if (edge) pathEdges.push(edge.id);
  }

  const edgeUpdates = allEdges.map(edge => ({
    id: edge.id,
    color: pathEdges.includes(edge.id) ? '#FF6B6B' : edge.color,
    width: pathEdges.includes(edge.id) ? 4 : (edge.width || 1),
    opacity: pathEdges.includes(edge.id) ? 1.0 : 0.15
  }));

  network.body.data.nodes.update(nodeUpdates);
  network.body.data.edges.update(edgeUpdates);

  // Focus on path
  network.fit({
    nodes: path,
    animation: true
  });
}

function clearPath() {
  document.getElementById('path-source').value = '';
  document.getElementById('path-target').value = '';
  document.getElementById('path-results').innerHTML = '';
  document.getElementById('path-source').style.borderColor = '#444';
  document.getElementById('path-target').style.borderColor = '#444';

  // Restore original appearance
  const allNodes = network.body.data.nodes.get();
  const allEdges = network.body.data.edges.get();

  const nodeUpdates = allNodes.map(node => ({
    id: node.id,
    opacity: 1.0,
    size: node.size || 10,
    color: originalNodeColors[node.id] || node.color
  }));

  const edgeUpdates = allEdges.map(edge => ({
    id: edge.id,
    color: originalEdgeColors[edge.id] || edge.color,
    width: edge.width || 1,
    opacity: 1.0
  }));

  network.body.data.nodes.update(nodeUpdates);
  network.body.data.edges.update(edgeUpdates);

  network.fit();
}
}

// Initialize path finder when page loads
initPathFinder();
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
