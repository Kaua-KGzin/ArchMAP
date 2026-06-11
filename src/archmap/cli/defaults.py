from __future__ import annotations

DEFAULT_JSON_OUTPUT_PATH = ".codeatlas/graph.json"
DEFAULT_MERMAID_OUTPUT_PATH = ".codeatlas/graph.mmd"
DEFAULT_CYTOSCAPE_OUTPUT_PATH = ".codeatlas/graph-cytoscape.json"
DEFAULT_SARIF_OUTPUT_PATH = ".codeatlas/archmap.sarif"
DEFAULT_PORT = 3000
# Bind to loopback by default. The serve command exposes endpoints that switch
# the analyzed directory and trigger outbound LLM calls; binding to 0.0.0.0
# would expose those to anyone on the network. Opt in explicitly with --host.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_TOP_ITEMS = 5
