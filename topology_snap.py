from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


SNAP_TOLERANCE = 5.0
SYMBOL_ATTACH_TOLERANCE = 20.0


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass
class TopologyNode:
    id: str
    x: float
    y: float
    original_points: list[Point] = field(default_factory=list)
    attached_symbols: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class TopologyEdge:
    id: str
    from_node: str
    to_node: str
    length: float
    source_line_id: str


class UnionFind:
    def __init__(self, size: int):
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a: int, b: int) -> None:
        root_a = self.find(a)
        root_b = self.find(b)
        if root_a != root_b:
            self.parent[root_b] = root_a


def build_topology(
    parsed_diagram: dict[str, Any],
    classifications: list[dict[str, Any]] | None = None,
    snap_tolerance: float = SNAP_TOLERANCE,
    symbol_attach_tolerance: float = SYMBOL_ATTACH_TOLERANCE,
) -> dict[str, Any]:
    """Build snapped topology graph from parsed line geometry.

    Input expected from parser:

    {
      "symbols": [{"label": "CB-23", "x": 100, "y": 50}],
      "lines": [{"x1": 100, "y1": 50, "x2": 250, "y2": 50}]
    }

    Optional classifications are the output of the rule-based classifier.
    """

    lines = extract_lines(parsed_diagram)
    endpoints = extract_endpoints(lines)
    nodes, point_to_node = snap_points(endpoints, snap_tolerance)
    edges = build_edges(lines, point_to_node)
    attach_symbols_to_nodes(
        nodes=nodes,
        symbols=parsed_diagram.get("symbols", []),
        classifications=classifications or parsed_diagram.get("classifications", []),
        attach_tolerance=symbol_attach_tolerance,
    )

    dangling_nodes = find_dangling_nodes(nodes, edges)

    return {
        "snap_tolerance": snap_tolerance,
        "symbol_attach_tolerance": symbol_attach_tolerance,
        "nodes": [serialize_node(node) for node in nodes],
        "edges": [asdict(edge) for edge in edges],
        "validation": {
            "line_count": len(lines),
            "raw_endpoint_count": len(endpoints),
            "snapped_node_count": len(nodes),
            "edge_count": len(edges),
            "dangling_node_ids": dangling_nodes,
        },
    }


def extract_lines(parsed_diagram: dict[str, Any]) -> list[dict[str, Any]]:
    lines = []
    for index, line in enumerate(parsed_diagram.get("lines", []), start=1):
        normalized = normalize_line(line, index)
        if normalized:
            lines.append(normalized)
    return lines


def normalize_line(line: dict[str, Any], index: int) -> dict[str, Any] | None:
    if all(key in line for key in ("x1", "y1", "x2", "y2")):
        return {
            "id": str(line.get("id", f"L{index}")),
            "start": Point(float(line["x1"]), float(line["y1"])),
            "end": Point(float(line["x2"]), float(line["y2"])),
        }

    if "start" in line and "end" in line:
        start = line["start"]
        end = line["end"]
        return {
            "id": str(line.get("id", f"L{index}")),
            "start": Point(float(start["x"]), float(start["y"])),
            "end": Point(float(end["x"]), float(end["y"])),
        }

    points = line.get("points")
    if isinstance(points, list) and len(points) >= 2:
        start = points[0]
        end = points[-1]
        return {
            "id": str(line.get("id", f"L{index}")),
            "start": Point(float(start["x"]), float(start["y"])),
            "end": Point(float(end["x"]), float(end["y"])),
        }

    return None


def extract_endpoints(lines: list[dict[str, Any]]) -> list[Point]:
    endpoints = []
    for line in lines:
        endpoints.append(line["start"])
        endpoints.append(line["end"])
    return endpoints


def snap_points(points: list[Point], tolerance: float) -> tuple[list[TopologyNode], dict[Point, str]]:
    union_find = UnionFind(len(points))

    for i, first in enumerate(points):
        for j in range(i + 1, len(points)):
            second = points[j]
            if distance(first, second) <= tolerance:
                union_find.union(i, j)

    clusters: dict[int, list[Point]] = {}
    for index, point in enumerate(points):
        root = union_find.find(index)
        clusters.setdefault(root, []).append(point)

    nodes: list[TopologyNode] = []
    point_to_node: dict[Point, str] = {}

    for node_index, cluster_points in enumerate(clusters.values(), start=1):
        node_id = f"N{node_index}"
        avg_x = sum(point.x for point in cluster_points) / len(cluster_points)
        avg_y = sum(point.y for point in cluster_points) / len(cluster_points)
        node = TopologyNode(id=node_id, x=avg_x, y=avg_y, original_points=cluster_points)
        nodes.append(node)

        for point in cluster_points:
            point_to_node[point] = node_id

    return nodes, point_to_node


def build_edges(lines: list[dict[str, Any]], point_to_node: dict[Point, str]) -> list[TopologyEdge]:
    edges = []
    seen = set()

    for index, line in enumerate(lines, start=1):
        from_node = point_to_node[line["start"]]
        to_node = point_to_node[line["end"]]

        if from_node == to_node:
            continue

        edge_key = tuple(sorted((from_node, to_node)) + [line["id"]])
        if edge_key in seen:
            continue
        seen.add(edge_key)

        edges.append(
            TopologyEdge(
                id=f"E{index}",
                from_node=from_node,
                to_node=to_node,
                length=distance(line["start"], line["end"]),
                source_line_id=line["id"],
            )
        )

    return edges


def attach_symbols_to_nodes(
    nodes: list[TopologyNode],
    symbols: list[dict[str, Any]],
    classifications: list[dict[str, Any]],
    attach_tolerance: float,
) -> None:
    classification_by_label = {
        item.get("label") or item.get("raw_label"): item
        for item in classifications
        if item.get("label") or item.get("raw_label")
    }

    for symbol in symbols:
        if symbol.get("x") is None or symbol.get("y") is None:
            continue

        symbol_point = Point(float(symbol["x"]), float(symbol["y"]))
        nearest_node = min(nodes, key=lambda node: distance(symbol_point, Point(node.x, node.y)), default=None)
        if not nearest_node:
            continue

        nearest_distance = distance(symbol_point, Point(nearest_node.x, nearest_node.y))
        if nearest_distance <= attach_tolerance:
            label = symbol.get("label") or symbol.get("id")
            nearest_node.attached_symbols.append(
                {
                    "label": label,
                    "symbol_type": classification_by_label.get(label, {}).get("symbol_type"),
                    "distance": nearest_distance,
                }
            )


def find_dangling_nodes(nodes: list[TopologyNode], edges: list[TopologyEdge]) -> list[str]:
    degree = {node.id: 0 for node in nodes}
    for edge in edges:
        degree[edge.from_node] += 1
        degree[edge.to_node] += 1
    return [node_id for node_id, count in degree.items() if count <= 1]


def serialize_node(node: TopologyNode) -> dict[str, Any]:
    return {
        "id": node.id,
        "x": node.x,
        "y": node.y,
        "original_points": [asdict(point) for point in node.original_points],
        "attached_symbols": node.attached_symbols,
    }


def distance(a: Point, b: Point) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def main() -> None:
    base_dir = Path(__file__).parent
    parsed = json.loads((base_dir / "sample_parsed_classified_diagram.json").read_text())
    topology = build_topology(parsed, snap_tolerance=SNAP_TOLERANCE)
    print(json.dumps(topology, indent=2))


if __name__ == "__main__":
    main()
