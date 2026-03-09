param(
    [string]$Target = "."
)

python -m archmap.cli.main analyze $Target --format both --out .codeatlas/local-graph.json --out-mermaid .codeatlas/local-graph.mmd --include-cytoscape
