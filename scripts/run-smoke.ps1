param(
    [string]$Target = "."
)

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$env:PYTHONPATH = "$RepoRoot\src$([System.IO.Path]::PathSeparator)$($env:PYTHONPATH)"

python -m archmap.cli.main analyze `
    $Target `
    --format both `
    --out .codeatlas/local-graph.json `
    --out-mermaid .codeatlas/local-graph.mmd `
    --include-cytoscape
