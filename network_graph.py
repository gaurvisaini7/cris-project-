from __future__ import annotations

import json
from pathlib import Path
from typing import Any


try:
    import networkx as nx
except ImportError:  # Helpful message when running before pip install.
    nx = None


def build_network_graph(topology: dict[str, Any]):
    """Create a NetworkX graph from snapped topology output."""

    if nx is None:
        raise RuntimeError("NetworkX is not installed. Run: pip install networkx")

    graph = nx.Graph()

    for node in topology.get("nodes", []):
        graph.add_node(
            node["id"],
            x=node["x"],
            y=node["y"],
            symbols=node.get("attached_symbols", []),
        )

    for edge in topology.get("edges", []):
        graph.add_edge(
            edge["from_node"],
            edge["to_node"],
            id=edge["id"],
            length=edge.get("length"),
            source_line_id=edge.get("source_line_id"),
        )

    return graph


def node_symbols(graph, node_id: str) -> list[dict[str, Any]]:
    return graph.nodes[node_id].get("symbols", [])


def symbol_to_node(graph) -> dict[str, str]:
    lookup = {}
    for node_id, data in graph.nodes(data=True):
        for symbol in data.get("symbols", []):
            label = symbol.get("label")
            if label:
                lookup[label] = node_id
    return lookup


def connected_symbols(graph) -> list[dict[str, Any]]:
    """Return symbol-to-symbol relationships across graph edges."""

    relationships = []
    for from_node, to_node, edge_data in graph.edges(data=True):
        from_symbols = node_symbols(graph, from_node)
        to_symbols = node_symbols(graph, to_node)

        for source_symbol in from_symbols:
            for target_symbol in to_symbols:
                relationships.append(
                    {
                        "from_symbol": source_symbol.get("label"),
                        "from_type": source_symbol.get("symbol_type"),
                        "to_symbol": target_symbol.get("label"),
                        "to_type": target_symbol.get("symbol_type"),
                        "via_edge": edge_data.get("id"),
                        "from_node": from_node,
                        "to_node": to_node,
                    }
                )

    return relationships


def shortest_symbol_path(graph, start_symbol: str, end_symbol: str) -> list[str]:
    lookup = symbol_to_node(graph)
    start_node = lookup[start_symbol]
    end_node = lookup[end_symbol]
    return nx.shortest_path(graph, start_node, end_node)


def graph_summary(graph) -> dict[str, Any]:
    return {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "nodes": [
            {
                "id": node_id,
                "x": data["x"],
                "y": data["y"],
                "symbols": data.get("symbols", []),
                "neighbors": list(graph.neighbors(node_id)),
            }
            for node_id, data in graph.nodes(data=True)
        ],
        "edges": [
            {
                "from_node": from_node,
                "to_node": to_node,
                **edge_data,
            }
            for from_node, to_node, edge_data in graph.edges(data=True)
        ],
        "symbol_relationships": connected_symbols(graph),
    }


def main() -> None:
    base_dir = Path(__file__).parent
    topology = json.loads((base_dir / "sample_topology.json").read_text())
    graph = build_network_graph(topology)

    summary = graph_summary(graph)
    print(json.dumps(summary, indent=2))

    print("\nRelationship example:")
    print("CB-23 connected path to BM-5:", " -> ".join(shortest_symbol_path(graph, "CB-23", "BM-5")))


if __name__ == "__main__":
    main()
