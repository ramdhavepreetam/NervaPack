"""
NervaPack Dashboard - Main Streamlit Application

Launch with: streamlit run app.py
Or via CLI: nervapack serve
"""

import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from nervapack.graph.builder import GraphBuilder
from nervapack.graph.analytics import GraphAnalytics
from nervapack.graph.query_history import QueryHistory

# Page configuration
st.set_page_config(
    page_title="NervaPack Dashboard",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #4ECDC4;
        margin-bottom: 0.5rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .health-score {
        font-size: 3rem;
        font-weight: bold;
        color: #4ECDC4;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
    }
    .stTabs [data-baseweb="tab"] {
        height: 3rem;
        padding-left: 1.5rem;
        padding-right: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_graph():
    """Load the NervaPack graph with caching."""
    try:
        builder = GraphBuilder()
        graph = builder.load_graph()
        return graph, None
    except Exception as e:
        return None, str(e)


@st.cache_resource
def load_analytics(_graph):
    """Load graph analytics with caching."""
    return GraphAnalytics(_graph)


@st.cache_resource
def load_query_history():
    """Load query history with caching."""
    return QueryHistory()


def main():
    # Sidebar
    with st.sidebar:
        st.markdown("# 🧠 NervaPack")
        st.markdown("**Privacy-First Knowledge Graph**")
        st.markdown("---")

        # Load graph
        graph, error = load_graph()

        if error:
            st.error("⚠️ No graph found")
            st.info("Run `nervapack ingest .` to create a graph first.")
            st.stop()

        analytics = load_analytics(graph)
        stats = analytics.get_summary_stats()

        # Quick stats in sidebar
        st.markdown("### 📊 Quick Stats")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Nodes", f"{stats['total_nodes']:,}")
        with col2:
            st.metric("Edges", f"{stats['total_edges']:,}")

        health_score = stats['health_score']
        st.metric("Health Score", f"{health_score}/100")

        st.markdown("---")
        st.markdown("### 🔗 Navigation")
        st.page_link("app.py", label="🏠 Home", icon="🏠")

        st.markdown("---")
        st.markdown("### ⚙️ Actions")
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_resource.clear()
            st.rerun()

        st.markdown("---")
        st.caption("NervaPack v0.3.0")

    # Main content
    st.markdown('<div class="main-header">🧠 NervaPack Dashboard</div>', unsafe_allow_html=True)
    st.markdown("**Real-time analytics for your knowledge graph**")

    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "📈 Analytics", "🔍 Query History", "🌐 Graph Explorer"])

    with tab1:
        render_overview(graph, analytics, stats)

    with tab2:
        render_analytics(graph, analytics, stats)

    with tab3:
        render_query_history()

    with tab4:
        render_graph_explorer(graph, analytics)


def render_overview(graph, analytics, stats):
    """Render the overview dashboard."""
    st.markdown("### 📊 Graph Health")

    # Health score with visual indicator
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        health_score = stats['health_score']
        color = "🟢" if health_score >= 70 else "🟡" if health_score >= 50 else "🔴"
        st.markdown(f"""
        <div class="metric-card">
            <div style="font-size: 0.9rem; opacity: 0.9;">Health Score</div>
            <div class="health-score">{color} {health_score}</div>
            <div style="font-size: 0.8rem; opacity: 0.7;">out of 100</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        node_counts = stats['node_counts']
        total_nodes = stats['total_nodes']
        st.markdown(f"""
        <div class="metric-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
            <div style="font-size: 0.9rem; opacity: 0.9;">Total Nodes</div>
            <div class="health-score">{total_nodes:,}</div>
            <div style="font-size: 0.8rem; opacity: 0.7;">{node_counts.get('file', 0)} files</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        total_edges = stats['total_edges']
        edge_counts = stats['edge_counts']
        st.markdown(f"""
        <div class="metric-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
            <div style="font-size: 0.9rem; opacity: 0.9;">Total Edges</div>
            <div class="health-score">{total_edges:,}</div>
            <div style="font-size: 0.8rem; opacity: 0.7;">{edge_counts.get('EXPLAINS', 0)} EXPLAINS</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        doc_cov = stats['documentation_coverage']
        doc_pct = doc_cov['percentage']
        st.markdown(f"""
        <div class="metric-card" style="background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);">
            <div style="font-size: 0.9rem; opacity: 0.9;">Doc Coverage</div>
            <div class="health-score">{doc_pct:.1f}%</div>
            <div style="font-size: 0.8rem; opacity: 0.7;">{doc_cov['documented']}/{doc_cov['total']}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Language distribution
    st.markdown("### 📚 Language Distribution")
    lang_dist = stats['languages']
    if lang_dist:
        import pandas as pd
        import plotly.express as px

        df = pd.DataFrame(list(lang_dist.items()), columns=['Language', 'Files'])
        df = df.sort_values('Files', ascending=False)

        fig = px.bar(
            df,
            x='Language',
            y='Files',
            color='Files',
            color_continuous_scale='viridis',
            title="Files by Language",
        )
        fig.update_layout(
            height=400,
            showlegend=False,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No language data available")

    st.markdown("---")

    # Most connected files
    st.markdown("### 🔗 Most Connected Files")
    most_connected = stats['most_connected']
    if most_connected:
        import pandas as pd

        df = pd.DataFrame(most_connected, columns=['Node ID', 'Degree'])
        df['File'] = df['Node ID'].apply(lambda x: analytics.get_file_display_name(x))
        df = df[['File', 'Degree']].head(10)

        st.dataframe(
            df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Degree": st.column_config.NumberColumn(
                    "Connections",
                    help="Number of edges connected to this file",
                    format="%d 🔗",
                )
            }
        )
    else:
        st.info("No connectivity data available")


def render_analytics(graph, analytics, stats):
    """Render detailed analytics."""
    st.markdown("### 📈 Detailed Analytics")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Node Type Breakdown")
        node_counts = stats['node_counts']
        import pandas as pd
        import plotly.express as px

        df = pd.DataFrame(list(node_counts.items()), columns=['Type', 'Count'])
        fig = px.pie(
            df,
            values='Count',
            names='Type',
            title="Nodes by Type",
            hole=0.4,
            color_discrete_sequence=px.colors.sequential.RdBu
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("#### Edge Type Breakdown")
        edge_counts = stats['edge_counts']
        df = pd.DataFrame(list(edge_counts.items()), columns=['Relation', 'Count'])
        fig = px.pie(
            df,
            values='Count',
            names='Relation',
            title="Edges by Relation",
            hole=0.4,
            color_discrete_sequence=px.colors.sequential.Teal
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Degree distribution
    st.markdown("#### 📊 Degree Distribution")
    degree_dist = stats['degree_distribution']
    if degree_dist['histogram']:
        import pandas as pd
        import plotly.express as px

        df = pd.DataFrame(list(degree_dist['histogram'].items()), columns=['Degree Range', 'Count'])
        fig = px.bar(
            df,
            x='Degree Range',
            y='Count',
            title="Node Connectivity Distribution",
            color='Count',
            color_continuous_scale='blues'
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

        col1, col2, col3 = st.columns(3)
        col1.metric("Min Degree", degree_dist['min'])
        col2.metric("Average Degree", f"{degree_dist['mean']:.1f}")
        col3.metric("Max Degree", degree_dist['max'])


def render_query_history():
    """Render query history analytics."""
    st.markdown("### 🔍 Query History & Analytics")

    history = load_query_history()
    stats_data = history.get_statistics()

    if stats_data['total_queries'] == 0:
        st.info("📭 No query history yet. Run some queries with `nervapack query` to see analytics here!")
        return

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Queries", stats_data['total_queries'])
    col2.metric("Avg Token Savings", f"{stats_data['avg_token_savings_pct']:.1f}%")
    col3.metric("Total Tokens Saved", f"{stats_data['total_tokens_saved']:,}")
    col4.metric("Avg Query Time", f"{stats_data['avg_execution_time_ms']:.0f}ms")

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 💰 Cost Savings")
        import pandas as pd
        import plotly.graph_objects as go

        cost_data = pd.DataFrame({
            'Model': ['GPT-4o', 'Claude Sonnet'],
            'Cost Saved': [stats_data['total_cost_saved_gpt4'], stats_data['total_cost_saved_sonnet']]
        })

        fig = go.Figure(data=[
            go.Bar(
                x=cost_data['Model'],
                y=cost_data['Cost Saved'],
                text=[f'${x:.4f}' for x in cost_data['Cost Saved']],
                textposition='auto',
                marker_color=['#4ECDC4', '#FF6B6B']
            )
        ])
        fig.update_layout(
            title="Total Cost Saved by Model",
            yaxis_title="USD",
            height=350
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("#### 🔥 Most Queried Topics")
        most_common = stats_data['most_common_words']
        if most_common:
            import pandas as pd

            df = pd.DataFrame(most_common[:10], columns=['Word', 'Count'])
            import plotly.express as px

            fig = px.bar(
                df,
                x='Count',
                y='Word',
                orientation='h',
                title="Top 10 Query Keywords",
                color='Count',
                color_continuous_scale='reds'
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No word frequency data available")

    st.markdown("---")

    # Recent queries
    st.markdown("#### 📝 Recent Queries")
    queries = history.get_recent_queries(limit=20)
    if queries:
        import pandas as pd
        from datetime import datetime

        data = []
        for q in queries:
            try:
                dt = datetime.fromisoformat(q.timestamp)
                time_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                time_str = q.timestamp[:16]

            data.append({
                'Time': time_str,
                'Query': q.query[:50] + "..." if len(q.query) > 50 else q.query,
                'Nodes': q.total_nodes_retrieved,
                'Savings': f"{q.token_savings_pct:.1f}%",
                'Duration': f"{q.execution_time_ms:.0f}ms" if q.execution_time_ms < 1000 else f"{q.execution_time_ms/1000:.1f}s"
            })

        df = pd.DataFrame(data)
        st.dataframe(df, hide_index=True, use_container_width=True)


def render_graph_explorer(graph, analytics):
    """Render interactive graph explorer."""
    st.markdown("### 🌐 Graph Explorer")

    st.info("💡 **Tip:** Use `nervapack visualize --enhanced --communities` for the full interactive visualization!")

    # Search functionality
    st.markdown("#### 🔍 Search Nodes")
    search_term = st.text_input("Search for nodes by name, type, or file path")

    if search_term:
        matching = []
        for node_id, data in graph.nodes(data=True):
            name = data.get("name", "")
            node_type = data.get("type", "")
            file_path = data.get("file_path") or data.get("path", "")

            if (search_term.lower() in name.lower() or
                search_term.lower() in node_type.lower() or
                search_term.lower() in file_path.lower()):
                matching.append({
                    'Node ID': node_id,
                    'Type': node_type,
                    'Name': name or Path(file_path).name,
                    'File': Path(file_path).name if file_path else 'N/A',
                    'Degree': graph.degree(node_id)
                })

        if matching:
            import pandas as pd
            df = pd.DataFrame(matching)
            st.success(f"Found {len(matching)} matching nodes")
            st.dataframe(df, hide_index=True, use_container_width=True)

            # Quick explore button
            if len(matching) == 1:
                if st.button("🔍 Explore this node"):
                    st.code(f"nervapack explore \"{matching[0]['Name']}\" --hops 2")
        else:
            st.warning("No matching nodes found")

    st.markdown("---")

    st.markdown("#### 📊 Graph Statistics")
    col1, col2, col3 = st.columns(3)

    orphaned = analytics.get_orphaned_nodes()
    col1.metric("Orphaned Nodes", len(orphaned))

    most_connected = analytics.get_most_connected_nodes(n=1)
    if most_connected:
        max_degree = most_connected[0][1]
        col2.metric("Max Connections", max_degree)

    col3.metric("Graph Density", f"{(graph.number_of_edges() / (graph.number_of_nodes() ** 2) * 100):.2f}%")


if __name__ == "__main__":
    main()
