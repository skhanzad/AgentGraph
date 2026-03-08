#!/usr/bin/env python3
"""Plot the pipeline graph from graph.py and save as an image."""
import matplotlib.pyplot as plt
import networkx as nx


def get_pipeline_graph():
    """Return (nodes, edges with labels) matching graph.py structure."""
    nodes = [
        "orchestrator",
        "orchestrator_release",
        "pm",
        "architect",
        "planner",
        "coder",
        "reviewer",
        "tester",
        "debugger",
        "docs",
        "devops",
        "project_writer",
        "git",
    ]
    # (from, to, label) for conditional edges; label None = fixed edge
    edges = [
        ("orchestrator", "pm", None),
        ("orchestrator", "architect", None),
        ("pm", "planner", None),
        ("architect", "planner", None),
        ("planner", "coder", None),
        ("coder", "coder", "more tasks"),
        ("coder", "project_writer", "all done"),
        ("project_writer", "git", None),
        ("git", "reviewer", "code snapshot"),
        ("reviewer", "tester", "approved"),
        ("reviewer", "coder", "rework"),
        ("tester", "orchestrator_release", "passed"),
        ("tester", "coder", "failed"),
        ("debugger", "coder", None),
        ("orchestrator_release", "docs", None),
        ("orchestrator_release", "devops", None),
        ("docs", "project_writer", None),
        ("devops", "project_writer", None),
        ("git", "__end__", "release snapshot"),
    ]
    return nodes, edges


def plot_pipeline_graph(output_path: str = "pipeline_graph.png", dpi: int = 120):
    """Build and draw the pipeline graph, then save to output_path."""
    nodes, edges = get_pipeline_graph()
    G = nx.DiGraph()
    G.add_nodes_from(nodes)
    G.add_node("__start__")
    G.add_node("__end__")

    for u, v, label in edges:
        G.add_edge(u, v, label=label)

    # Layout: top-to-bottom (y decreases so start is at top)
    pos = {
        "__start__": (0, 0),
        "orchestrator": (0, -1),
        "pm": (-0.9, -2),
        "architect": (0.9, -2),
        "planner": (0, -3),
        "coder": (0.4, -4),
        "debugger": (-0.7, -4),
        "reviewer": (0.9, -5),
        "tester": (0.9, -6),
        "orchestrator_release": (0, -7),
        "docs": (-0.9, -8),
        "devops": (0.9, -8),
        "project_writer": (0, -9),
        "git": (0, -10),
        "__end__": (0, -11),
    }

    fig, ax = plt.subplots(figsize=(14, 8))
    ax.set_axis_off()

    # Node colors: start/end vs agents
    node_colors = []
    for n in G.nodes():
        if n == "__start__":
            node_colors.append("#c8e6c9")
        elif n == "__end__":
            node_colors.append("#ffccbc")
        else:
            node_colors.append("#bbdefb")

    nx.draw_networkx_nodes(
        G,
        pos,
        node_color=node_colors,
        node_size=2400,
        node_shape="s",
        edgecolors="#1565c0",
        linewidths=1.5,
        ax=ax,
    )
    nx.draw_networkx_labels(
        G,
        pos,
        font_size=8,
        font_weight="bold",
        ax=ax,
    )

    # Draw edges: fixed (black) and conditional (colored with label)
    fixed_edges = [(u, v) for u, v, lbl in edges if lbl is None]
    cond_edges = [(u, v) for u, v, lbl in edges if lbl is not None]
    edge_labels = {(u, v): lbl for u, v, lbl in edges if lbl is not None}

    nx.draw_networkx_edges(
        G,
        pos,
        edgelist=fixed_edges,
        edge_color="#37474f",
        arrows=True,
        arrowsize=18,
        width=1.2,
        connectionstyle="arc3,rad=0.1",
        ax=ax,
    )
    nx.draw_networkx_edges(
        G,
        pos,
        edgelist=cond_edges,
        edge_color="#6a1b9a",
        style="dashed",
        arrows=True,
        arrowsize=16,
        width=1,
        connectionstyle="arc3,rad=0.15",
        ax=ax,
    )
    nx.draw_networkx_edge_labels(
        G,
        pos,
        edge_labels=edge_labels,
        font_size=6,
        font_color="#6a1b9a",
        ax=ax,
    )

    ax.set_title("AgentGraph pipeline", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"Saved {output_path}")


if __name__ == "__main__":
    import os

    out = os.path.join(os.path.dirname(__file__) or ".", "pipeline_graph.png")
    plot_pipeline_graph(output_path=out)
