# Live Demo

This demo is reproducible in a fresh clone.

## Step 1: run the demo script

```powershell
powershell -ExecutionPolicy Bypass -File scripts/demo.ps1
```

## Step 2: inspect generated files

The script writes outputs to `.codeatlas/demo/`:

- `graph.json`
- `graph.mmd`
- `graph-cytoscape.json`

## Step 3: open interactive UI

```bash
archmap serve examples/sample-project
```

## Step 4: verify API endpoints

```bash
curl http://localhost:3000/api/health
curl http://localhost:3000/api/project
curl http://localhost:3000/api/graph
```

## Expected behaviors

- Circular dependency is detected in the sample project.
- Risk panel highlights architectural hotspots.
- `POST /api/reanalyze` refreshes graph data without restarting the server.
