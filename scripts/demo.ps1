param(
    [string]$Target = "examples/sample-project",
    [string]$OutDir = ".codeatlas/demo"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$env:PYTHONPATH = "$RepoRoot\src$([System.IO.Path]::PathSeparator)$($env:PYTHONPATH)"

Write-Host "[demo] Running ArchMAP demo against: $Target"

python -m archmap.cli.main analyze `
    $Target `
    --format both `
    --out "$OutDir/graph.json" `
    --out-mermaid "$OutDir/graph.mmd" `
    --include-cytoscape `
    --out-cytoscape "$OutDir/graph-cytoscape.json"

if ($LASTEXITCODE -ne 0) {
    throw "Demo analyze command failed."
}

Write-Host "[demo] Outputs generated in $OutDir"
Write-Host "[demo] To open UI, run: archmap serve $Target"
