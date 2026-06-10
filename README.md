# Basic Network Graph

This layer uses snapped topology output to create a NetworkX graph.

## Flow

1. Take snapped points:

   ```text
   (100,50)
   (250,50)
   (400,50)
   ```

2. Create nodes:

   ```text
   Node1
   Node2
   Node3
   ```

3. Create edges:

   ```text
   Node1 ---- Node2
   Node2 ---- Node3
   ```

4. Attach symbols:

   ```text
   Node1 -> CB-23
   Node2 -> SP-12
   Node3 -> BM-5
   ```

5. Query relationships:

   ```text
   CB-23 connected to SP-12
   SP-12 connected to BM-5
   ```

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python3 network_graph.py
```

