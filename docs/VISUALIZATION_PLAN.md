# NervaPack Data Visualization Enhancement Plan

> **Created:** 2026-06-16
> **Status:** Planning Phase
> **Owner:** NervaPack Development Team

---

## Executive Summary

This document outlines a comprehensive plan to enhance NervaPack's data visualization capabilities. While NervaPack currently provides basic graph visualization and token efficiency metrics, there's significant opportunity to add rich, interactive visualizations that help users understand their codebase structure, query patterns, and knowledge graph health.

---

## Current State Analysis

### Existing Visualizations

#### 1. Interactive Graph Visualization (pyvis-based)
**Location:** `src/nervapack/graph/visualizer.py`
**Command:** `nervapack visualize`

**Features:**
- Color-coded nodes by type (file, function, class, import, markdown)
- Diamond shapes for files, dots for other entities
- Solid edges for DEFINES, dashed for EXPLAINS
- Hover tooltips with code previews
- Physics-based force-directed layout
- Interactive (drag, zoom, pan)
- Navigation buttons and keyboard controls
- Legend overlay

**Strengths:**
- Beautiful dark theme
- Fully self-contained HTML (no external dependencies)
- Good for exploring relationships

**Limitations:**
- No clustering or community detection
- Performance degrades with 1000+ nodes
- No search/filter functionality
- No path highlighting or subgraph isolation
- No directory/module grouping
- Can't compare different graph states
- No export options (beyond HTML)

#### 2. Token Efficiency Dashboard (Rich-based)
**Location:** `src/nervapack/graph/token_meter.py`
**Context:** Shown during `nervapack query` command

**Features:**
- Side-by-side comparison: Naive RAG vs NervaPack
- Visual progress bars (█ and ░ characters)
- Token counts (exact with tiktoken, estimated fallback)
- Percentage reduction calculation
- Cost savings for GPT-4o and Claude Sonnet
- File count display

**Strengths:**
- Clear, actionable metrics
- Beautiful Rich formatting
- Immediate value demonstration

**Limitations:**
- Only shows single query metrics
- No historical trends
- No aggregated analytics
- No query pattern analysis
- Can't compare multiple queries

#### 3. Status Output (Rich-based)
**Location:** `src/nervapack/cli.py` (status command)

**Features:**
- Graph loaded status
- Node and edge counts
- Git repo detection
- Unsynced file list

**Strengths:**
- Quick health check
- Git integration awareness

**Limitations:**
- Text-only output
- No visual charts
- Missing detailed breakdowns (by type, language, etc.)
- No trends or historical data

---

## Visualization Gaps & Opportunities

### Category 1: Graph Analytics & Insights

**Missing:**
1. **Graph Statistics Dashboard**
   - Node/edge count by type
   - Language distribution pie chart
   - Degree distribution histogram
   - Most connected files/classes
   - Orphaned nodes detection
   - Clustering coefficient
   - Average path length

2. **Community Detection Visualization**
   - Module/package clustering
   - Color-coded communities
   - Inter-community vs intra-community edges
   - Modularity score

3. **Code Dependency Flow**
   - Import dependency graph (separate view)
   - Call graph visualization (future)
   - Circular dependency detection
   - Dependency depth tree

4. **Documentation Coverage**
   - Heatmap: which code has EXPLAINS edges
   - Undocumented functions/classes
   - Documentation quality score per module

### Category 2: Query Analytics

**Missing:**
1. **Query History Dashboard**
   - Recent queries list
   - Token savings trends over time
   - Most queried topics/nodes
   - Query response time metrics
   - Average context size per query

2. **Query Result Visualization**
   - Highlight retrieved subgraph in interactive view
   - Show BFS traversal path
   - Seed nodes vs neighbor nodes (different colors)
   - Query similarity clustering

3. **Efficiency Metrics Timeline**
   - Token savings over time (line chart)
   - Cost savings accumulation
   - Average reduction percentage trend
   - Comparison across different projects

### Category 3: Temporal & Change Tracking

**Missing:**
1. **Graph Evolution Timeline**
   - Node/edge count growth over time
   - Commits that caused major graph changes
   - Before/after sync comparison
   - File churn vs graph churn correlation

2. **Sync History Visualization**
   - Files modified per sync
   - Nodes added/removed per sync
   - LLM binding time per sync
   - Sync performance trends

3. **Code Hotspot Analysis**
   - Files that change most frequently
   - Nodes that get re-synced often
   - Stability score per module

### Category 4: Interactive Exploration

**Missing:**
1. **Advanced Graph Filtering**
   - Filter by file type/language
   - Filter by directory/module
   - Show only EXPLAINS edges
   - Show only specific node types
   - Regex-based node name search

2. **Path Finding & Highlighting**
   - Find shortest path between two nodes
   - Highlight all paths from docs to code
   - Show ego network (N-hop neighborhood of a node)
   - Trace import chains

3. **Comparison Views**
   - Diff two graph states (before/after refactoring)
   - Compare graphs from different branches
   - Show added/removed/modified nodes

### Category 5: Reporting & Exports

**Missing:**
1. **Static Reports**
   - PDF graph analysis report
   - Markdown summary report
   - CSV export of nodes/edges
   - GraphML export (already have this)
   - JSON export for custom tooling

2. **Dashboards**
   - Web-based live dashboard (Flask/FastAPI)
   - Real-time graph metrics
   - Query analytics panel
   - Health monitoring

---

## Proposed Visualization Enhancements

### Phase 1: Enhanced CLI Visualizations (Quick Wins)

#### 1.1 Enhanced Status Command
**Priority:** HIGH
**Effort:** LOW
**Impact:** MEDIUM

```bash
nervapack status --detailed
```

**Features:**
- Rich panels with graph statistics
- Language distribution table
- Node type breakdown (bar chart using Rich)
- Edge type breakdown
- Top 10 most connected files
- Documentation coverage percentage
- Health score (0-100)

**Technical Approach:**
- Use Rich library (already a dependency)
- Add `--detailed` flag for extended stats
- Implement helper functions in `graph/analytics.py`

**Mockup Output:**
```
╭─────────────────── NervaPack Status ───────────────────╮
│ Graph Health: ●●●●●●●●○○ 85/100                        │
│                                                         │
│ Nodes: 1,247        Edges: 3,821                       │
│ Files: 156          Functions: 892                     │
│ Classes: 142        Imports: 57                        │
│                                                         │
│ Language Distribution:                                 │
│   Python        ████████████░░░░░░░░  62% (97 files)  │
│   TypeScript    ███████░░░░░░░░░░░░░  35% (54 files)  │
│   Markdown      ██░░░░░░░░░░░░░░░░░░   3% (5 files)   │
│                                                         │
│ Documentation Coverage: 67% (845/1,247 nodes)          │
│ Most Connected: src/graph/builder.py (42 edges)        │
│ Git Status: ✓ Synced (0 changed files)                 │
╰─────────────────────────────────────────────────────────╯
```

#### 1.2 Interactive Query Result Preview
**Priority:** HIGH
**Effort:** LOW
**Impact:** HIGH

**Features:**
- Show seed nodes vs expanded nodes
- Display traversal path
- Highlight which edges were followed
- Show node retrieval reasoning

**Technical Approach:**
- Enhance `GraphRetriever.retrieve_context()` to return metadata
- Add visualization to `nervapack query` output
- Use Rich tree/table for structure

**Mockup Output:**
```bash
$ nervapack query "How does sync work?"

Query: "How does sync work?"
Vector Search: Found 3 seed nodes
  ✓ function:src/cli.py:sync:89 (relevance: 0.92)
  ✓ class:src/git/tracker.py:GitTracker:12 (relevance: 0.87)
  ✓ function:src/graph/builder.py:remove_nodes_for_file:82 (relevance: 0.81)

Graph Traversal (max_hops=1):
  3 seed nodes → expanded to 18 nodes

Retrieved Subgraph:
src/
├─ cli.py (1 file)
│  └─ sync() [seed]
│     └─ EXPLAINS: docs/architecture.md:L110
├─ git/
│  └─ tracker.py (1 file)
│     └─ GitTracker [seed]
│        ├─ get_changed_files()
│        └─ EXPLAINS: README.md:L193
└─ graph/
   └─ builder.py (1 file)
      └─ remove_nodes_for_file() [seed]
         └─ EXPLAINS: docs/architecture.md:L114

--- Retrieved Context ---
[context markdown here...]
--- End Context ---

[Token efficiency panel...]
```

#### 1.3 Query History Command
**Priority:** MEDIUM
**Effort:** LOW
**Impact:** MEDIUM

```bash
nervapack history
nervapack history --stats
```

**Features:**
- Store query history in `.nervapack/query_history.jsonl`
- Show recent queries with token savings
- Aggregate statistics (total queries, avg savings, etc.)
- Trend visualization using Rich bar charts

**Technical Approach:**
- Add query logging to `query` command
- Create new `history` command
- Use Rich tables for display

### Phase 2: Advanced Graph Visualization (Medium Effort)

#### 2.1 Enhanced Interactive Graph
**Priority:** HIGH
**Effort:** MEDIUM
**Impact:** HIGH

**Features to Add:**
- Search bar to find and highlight nodes
- Filter controls (by type, language, directory)
- Community detection with color coding
- Path highlighting (show shortest path between two nodes)
- Node grouping by directory/module
- Expand/collapse file nodes
- Minimap for large graphs
- Export view as PNG/SVG

**Technical Approach:**
- Consider migrating from pyvis to:
  - **Option A:** Plotly + Dash (interactive, Python-native)
  - **Option B:** D3.js + custom HTML template (most flexible)
  - **Option C:** vis.js (similar to pyvis but more features)
- Add community detection using NetworkX algorithms
- Implement client-side search/filter in JavaScript

**Recommendation:** Start with vis.js (Option C) as it's closest to current pyvis implementation

#### 2.2 Subgraph Explorer
**Priority:** MEDIUM
**Effort:** MEDIUM
**Impact:** HIGH

```bash
nervapack explore [FILE_OR_NODE]
nervapack explore src/graph/builder.py
nervapack explore --type function --name sync
```

**Features:**
- Focus on specific file or node
- Show N-hop ego network
- Interactive drill-down
- Export focused subgraph

**Technical Approach:**
- Use `nx.ego_graph()` for N-hop extraction
- Reuse enhanced visualization from 2.1
- Add CLI arguments for filtering

#### 2.3 Dependency Graph Visualizer
**Priority:** MEDIUM
**Effort:** MEDIUM
**Impact:** MEDIUM

```bash
nervapack dependencies [FILE]
nervapack dependencies --circular
```

**Features:**
- Show import dependency graph
- Detect circular dependencies
- Highlight critical paths
- Layered layout (dependency levels)

**Technical Approach:**
- Extract import edges from graph
- Use NetworkX topological sort
- Detect cycles with `nx.simple_cycles()`
- Use Graphviz dot layout for hierarchical view

### Phase 3: Web Dashboard (High Effort)

#### 3.1 Live Web Dashboard
**Priority:** MEDIUM
**Effort:** HIGH
**Impact:** HIGH

```bash
nervapack serve
# Opens dashboard at http://localhost:8080
```

**Features:**
- **Home:** Graph overview stats, health metrics
- **Graph:** Interactive visualization (from Phase 2.1)
- **Analytics:** Charts and metrics
  - Language distribution pie chart
  - Node type breakdown
  - Degree distribution histogram
  - Documentation coverage progress bar
- **Queries:** Query history table, trend charts
- **Explorer:** Search and filter interface
- **Sync:** Git change tracking, sync history

**Technical Stack Options:**

**Option A: Streamlit** (Fastest)
```python
# Pros: Rapid development, Python-native, auto-refresh
# Cons: Limited customization, heavier weight
import streamlit as st
```

**Option B: FastAPI + React** (Most Flexible)
```python
# Pros: Full control, modern stack, API reusable
# Cons: More code, frontend expertise needed
from fastapi import FastAPI
```

**Option C: Flask + Plotly Dash** (Balanced)
```python
# Pros: Python-heavy, good for data apps, moderate complexity
# Cons: Less modern than FastAPI+React
from dash import Dash, dcc, html
```

**Recommendation:** Start with **Streamlit** for MVP, migrate to FastAPI+React if needed

**Architecture:**
```
nervapack serve
    ↓
FastAPI/Streamlit Backend
    ↓
Serves:
    - Graph data (JSON API)
    - Analytics metrics
    - Query history
    - Real-time status
    ↓
Frontend (React or Streamlit components)
    - Interactive charts (Plotly/Recharts)
    - Graph visualization (vis.js/D3.js)
    - Tables and filters
```

#### 3.2 Analytics Dashboard Panels

**Panel 1: Graph Health**
- Overall health score (0-100)
- Node/edge counts over time (line chart)
- Language distribution (pie chart)
- Documentation coverage (gauge chart)

**Panel 2: Query Analytics**
- Total queries count
- Average token savings percentage
- Cost savings accumulation (line chart)
- Most queried topics (word cloud or bar chart)

**Panel 3: Code Insights**
- Most connected files (bar chart)
- Orphaned nodes (table)
- Circular dependencies (list)
- Code hotspots (files changed frequently)

**Panel 4: Temporal Analysis**
- Graph growth over time
- Sync frequency
- LLM binding time per sync
- Performance metrics

### Phase 4: Export & Reporting (Medium Effort)

#### 4.1 Static Report Generation
**Priority:** LOW
**Effort:** MEDIUM
**Impact:** LOW

```bash
nervapack report --format pdf
nervapack report --format markdown
nervapack report --format html
```

**Features:**
- Comprehensive graph analysis report
- Charts and visualizations (static)
- Executive summary
- Detailed statistics
- Recommendations (e.g., "Add docs for 23 undocumented functions")

**Technical Approach:**
- Use Jinja2 templates
- Generate charts with Plotly (static mode)
- PDF generation with WeasyPrint or ReportLab
- Markdown with embedded images

#### 4.2 Data Export Formats
**Priority:** LOW
**Effort:** LOW
**Impact:** LOW

```bash
nervapack export --format json
nervapack export --format csv
nervapack export --format graphml  # Already supported
```

**Features:**
- Export nodes/edges as JSON
- CSV tables for spreadsheet analysis
- Integration with external tools

---

## Implementation Roadmap

### Sprint 1: Enhanced CLI (2-3 weeks)
- [ ] Enhanced `status` command with Rich panels
- [ ] Query result preview with traversal visualization
- [ ] Query history storage and `history` command
- [ ] Node type and language analytics helpers

**Deliverables:**
- `src/nervapack/graph/analytics.py` - Analytics helper functions
- Enhanced CLI commands with Rich formatting
- Query history persistence (`.nervapack/query_history.jsonl`)

### Sprint 2: Interactive Graph v2 (3-4 weeks)
- [ ] Migrate from pyvis to vis.js or keep pyvis and enhance
- [ ] Add search and filter functionality
- [ ] Implement community detection
- [ ] Add path highlighting
- [ ] Create minimap for large graphs
- [ ] Subgraph explorer command

**Deliverables:**
- `src/nervapack/graph/visualizer_v2.py` - Enhanced visualizer
- Updated `visualize` command with new features
- New `explore` command for focused exploration

### Sprint 3: Web Dashboard MVP (4-6 weeks)
- [ ] Set up Streamlit or FastAPI+React project
- [ ] Implement Graph Health panel
- [ ] Implement Query Analytics panel
- [ ] Implement interactive graph viewer
- [ ] Add search and filter UI
- [ ] Deploy `serve` command

**Deliverables:**
- `src/nervapack/dashboard/` - Dashboard application
- New `serve` command
- Documentation for dashboard features

### Sprint 4: Advanced Analytics (3-4 weeks)
- [ ] Dependency graph visualization
- [ ] Circular dependency detection
- [ ] Code hotspot analysis
- [ ] Temporal graph evolution tracking
- [ ] Sync history visualization

**Deliverables:**
- `src/nervapack/graph/dependency_analyzer.py`
- `src/nervapack/graph/temporal_tracker.py`
- New analytics commands and dashboard panels

### Sprint 5: Reporting & Export (2-3 weeks)
- [ ] Report template system (Jinja2)
- [ ] PDF report generation
- [ ] Markdown report generation
- [ ] JSON/CSV export formats
- [ ] Customizable report configs

**Deliverables:**
- `src/nervapack/reports/` - Report generation module
- New `report` and `export` commands
- Report templates

---

## Technical Specifications

### New Dependencies

**Phase 1 (CLI Enhancements):**
- None (uses existing Rich)

**Phase 2 (Advanced Graphs):**
```toml
vis-js = "^9.1.0"  # If migrating from pyvis
plotly = "^5.18.0"  # For advanced charts
networkx[all] = "^3.2"  # For community detection algorithms
```

**Phase 3 (Web Dashboard):**

**Option A: Streamlit**
```toml
streamlit = "^1.29.0"
plotly = "^5.18.0"
```

**Option B: FastAPI + React**
```toml
fastapi = "^0.109.0"
uvicorn = "^0.27.0"
# Frontend: React, Recharts, vis.js (in package.json)
```

**Phase 4 (Reporting):**
```toml
jinja2 = "^3.1.3"  # Already a transitive dep
weasyprint = "^60.2"  # PDF generation
pillow = "^10.2.0"  # Image handling
```

### File Structure Changes

```
src/nervapack/
├── graph/
│   ├── analytics.py           # [NEW] Graph analytics helpers
│   ├── dependency_analyzer.py # [NEW] Import dependency analysis
│   ├── temporal_tracker.py    # [NEW] Track graph evolution
│   ├── visualizer_v2.py       # [NEW] Enhanced visualization
│   └── ...
├── dashboard/                 # [NEW] Web dashboard
│   ├── __init__.py
│   ├── app.py                # Streamlit or FastAPI app
│   ├── components/           # Dashboard panels/components
│   │   ├── graph_health.py
│   │   ├── query_analytics.py
│   │   └── ...
│   └── templates/            # HTML templates if using FastAPI
├── reports/                  # [NEW] Report generation
│   ├── __init__.py
│   ├── generator.py
│   └── templates/
│       ├── report.md.j2
│       ├── report.html.j2
│       └── ...
└── ...

.nervapack/
├── query_history.jsonl       # [NEW] Query logs
├── sync_history.jsonl        # [NEW] Sync logs
├── analytics_cache.json      # [NEW] Cached metrics
└── ...
```

### API Design (for Web Dashboard)

```python
# FastAPI endpoints (if using Option B)
@app.get("/api/graph/stats")
def get_graph_stats() -> GraphStats:
    """Return overall graph statistics"""

@app.get("/api/graph/nodes")
def get_nodes(filter: Optional[str] = None) -> List[Node]:
    """Get all nodes with optional filtering"""

@app.get("/api/graph/subgraph/{node_id}")
def get_subgraph(node_id: str, max_hops: int = 1) -> Subgraph:
    """Get ego network around a node"""

@app.get("/api/queries/history")
def get_query_history(limit: int = 50) -> List[QueryRecord]:
    """Get recent queries"""

@app.get("/api/queries/analytics")
def get_query_analytics() -> QueryAnalytics:
    """Get aggregated query metrics"""

@app.post("/api/queries/search")
def search_query(query: QueryRequest) -> QueryResult:
    """Perform a new query"""
```

---

## Metrics & Success Criteria

### Phase 1 Success Metrics
- [ ] `status` command shows 10+ useful metrics
- [ ] Query visualization shows traversal path
- [ ] Query history stored and retrievable
- [ ] User feedback: "Much more informative"

### Phase 2 Success Metrics
- [ ] Can search and find nodes in <2 seconds
- [ ] Can highlight shortest path between any two nodes
- [ ] Community detection reveals 3-10 meaningful clusters
- [ ] Graph renders smoothly with 5000+ nodes

### Phase 3 Success Metrics
- [ ] Dashboard loads in <3 seconds
- [ ] Real-time updates work smoothly
- [ ] All analytics panels functional
- [ ] User feedback: "Game changer for understanding my codebase"

### Phase 4 Success Metrics
- [ ] PDF report generates in <10 seconds
- [ ] Reports are readable and actionable
- [ ] Export formats work with external tools (Neo4j, Gephi, etc.)

---

## Design Mockups

### Enhanced Status Command
```
╭──────────────────────── NervaPack Status ────────────────────────╮
│                                                                   │
│  Graph Health Score: 85/100 ●●●●●●●●○○                          │
│                                                                   │
│  📊 Overview                                                      │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Nodes:     1,247    Edges:      3,821                       │ │
│  │ Files:       156    Defined:    3,621                       │ │
│  │ Functions:   892    Explained:    200                       │ │
│  │ Classes:     142                                             │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  📚 Language Distribution                                         │
│  Python      ████████████░░░░░░░░  62%  (97 files)              │
│  TypeScript  ███████░░░░░░░░░░░░░  35%  (54 files)              │
│  Markdown    ██░░░░░░░░░░░░░░░░░░   3%  (5 files)               │
│                                                                   │
│  📖 Documentation Coverage                                        │
│  Documented: 67% ██████████████░░░░░ (845/1,247 entities)       │
│                                                                   │
│  🔗 Most Connected Files                                          │
│  1. src/graph/builder.py          (42 edges)                    │
│  2. src/cli.py                    (38 edges)                    │
│  3. src/parser/ast_parser.py      (31 edges)                    │
│                                                                   │
│  🔄 Git Sync Status                                               │
│  ✓ Graph is in sync (0 unsynced files)                          │
│  Last sync: 2 hours ago                                          │
│                                                                   │
╰───────────────────────────────────────────────────────────────────╯
```

### Web Dashboard (Home Panel)
```
┌─────────────────────────────────────────────────────────────────┐
│  NervaPack Dashboard                              [Settings] [?] │
├─────────────────────────────────────────────────────────────────┤
│  [Home] [Graph] [Analytics] [Queries] [Explorer] [Sync]         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌───────────────────┐  ┌───────────────────┐                  │
│  │ Graph Health      │  │ Documentation     │                  │
│  │                   │  │ Coverage          │                  │
│  │      85/100       │  │                   │                  │
│  │   ●●●●●●●●○○      │  │       67%         │                  │
│  │                   │  │   ████████░░░     │                  │
│  └───────────────────┘  └───────────────────┘                  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Node Count Over Time                                     │   │
│  │                                              ╱           │   │
│  │                                            ╱             │   │
│  │                                     ╱----╱               │   │
│  │                              ╱----╱                      │   │
│  │  ────────────────────╱------╱                           │   │
│  │  Jan   Feb   Mar   Apr   May   Jun                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────┐  ┌──────────────────────────────┐   │
│  │ Language Distribution│  │ Recent Queries                │   │
│  │                      │  │                                │   │
│  │   Python    62% 🥧  │  │ • How does sync work?          │   │
│  │   TypeScript 35%    │  │   (saved 11,660 tokens)        │   │
│  │   Markdown   3%     │  │ • Authentication flow          │   │
│  │                      │  │   (saved 8,234 tokens)         │   │
│  └──────────────────────┘  └──────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Open Questions & Decisions Needed

1. **Web Dashboard Framework?**
   - Streamlit (fast MVP) vs FastAPI+React (production-grade)?
   - Recommendation: Start with Streamlit

2. **Graph Visualization Library?**
   - Keep pyvis, enhance with JavaScript?
   - Migrate to vis.js?
   - Use D3.js for full control?
   - Recommendation: vis.js (good balance)

3. **Query History Storage?**
   - JSONL files (simple)?
   - SQLite database (queryable)?
   - Recommendation: JSONL for v1, SQLite for v2

4. **Performance Optimization?**
   - When to implement graph sampling for large repos?
   - Lazy loading strategies for dashboard?
   - Recommendation: Implement when users report issues >10K nodes

5. **Export Formats Priority?**
   - Which formats are most valuable: JSON, CSV, GraphML, GEXF?
   - Recommendation: JSON first (most flexible)

---

## Alternative Approaches Considered

### Alternative 1: No Web Dashboard, CLI Only
**Pros:** Simpler, fewer dependencies, aligns with CLI-first philosophy
**Cons:** Limited visualization capabilities, harder to explore large graphs
**Decision:** Rejected. Users need interactive exploration for large codebases.

### Alternative 2: Jupyter Notebook Integration
**Pros:** Great for data science users, interactive Python environment
**Cons:** Requires Jupyter, not all users comfortable with notebooks
**Decision:** Consider as Phase 5 (optional integration)

### Alternative 3: VS Code Extension Instead of Web Dashboard
**Pros:** Integrated into developer workflow, native IDE experience
**Cons:** Much more complex, requires TypeScript/VS Code API expertise
**Decision:** Long-term goal (v1.0+), web dashboard first

---

## Risk Assessment

### High Risks
1. **Performance degradation** with large graphs (10K+ nodes)
   - Mitigation: Implement sampling, lazy loading, pagination

2. **Dependency bloat** from adding Streamlit/FastAPI
   - Mitigation: Make dashboard optional extra: `pip install nervapack[dashboard]`

3. **Maintenance burden** of web frontend
   - Mitigation: Keep it simple, use established frameworks, avoid custom code

### Medium Risks
1. **User learning curve** for new commands/features
   - Mitigation: Good documentation, progressive disclosure, sensible defaults

2. **Cross-platform compatibility** (Windows, macOS, Linux)
   - Mitigation: Test on all platforms, use platform-agnostic libraries

### Low Risks
1. **Breaking changes** to existing CLI
   - Mitigation: Only add new commands, don't modify existing ones

---

## Conclusion

This visualization plan transforms NervaPack from a powerful but text-heavy tool into a rich, interactive codebase intelligence platform. The phased approach allows for:

1. **Quick wins** (Phase 1) with immediate user value
2. **Meaningful improvements** (Phase 2) to core use cases
3. **Game-changing features** (Phase 3) for power users
4. **Professional polish** (Phase 4) for enterprise adoption

**Recommended Next Steps:**
1. Get stakeholder/user feedback on this plan
2. Prioritize phases based on user needs
3. Start Sprint 1 (Enhanced CLI) - low risk, high value
4. Prototype web dashboard (Streamlit) in parallel
5. Iterate based on user feedback

**Total Estimated Timeline:** 14-20 weeks for all phases
**Estimated LOC Addition:** ~3000-5000 lines
**New Dependencies:** 5-10 packages (mostly optional extras)
