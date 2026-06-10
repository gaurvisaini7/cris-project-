# Topology Snap Algorithm

This is the topology layer after:

1. PDF parsing
2. Rule-based symbol classification

It reads parsed line geometry and creates a snapped topology graph.

## Steps

1. Extract all line endpoints from parser output.
2. Compare endpoint distances.
3. Merge endpoints within `SNAP_TOLERANCE = 5`.
4. Create snapped topology nodes.
5. Create graph edges between snapped nodes.
6. Attach classified symbols to nearest nodes.
7. Report validation information such as dangling nodes.

## Example

Before snapping:

```text
(100, 50)
(250, 50)
(252, 51)
(400, 50)
```

Distance between `(250, 50)` and `(252, 51)` is less than 5, so they are merged.

After snapping:

```text
N1 = (100, 50)
N2 = average of (250, 50), (252, 51)
N3 = (400, 50)
```

Edges:

```text
N1 -> N2
N2 -> N3
```

## Run

```bash
python3 topology_snap.py
```

## Expected Parser Shape

```json
{
  "symbols": [
    { "label": "CB-23", "x": 100, "y": 50 }
  ],
  "lines": [
    { "x1": 100, "y1": 50, "x2": 250, "y2": 50 }
  ],
  "classifications": [
    { "label": "CB-23", "symbol_type": "CB" }
  ]
}
```

