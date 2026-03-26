param(
    [string]$Python = "python",
    [switch]$Clean,
    [switch]$SkipSmoke
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$SpecPath = Join-Path $RepoRoot "archmap.spec"
$DistDir = Join-Path $RepoRoot "dist"
$ExePath = Join-Path $DistDir "archmap.exe"

Push-Location $RepoRoot
try {
    $version = & $Python -c "import sys; sys.path.insert(0, 'src'); from archmap import __version__; print(__version__)"
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($version)) {
        throw "Failed to resolve ArchMAP version from src/archmap/__init__.py"
    }
    $version = $version.Trim()

    $args = @("-m", "PyInstaller", $SpecPath, "--noconfirm")
    if ($Clean) {
        $args += "--clean"
    }

    Write-Host "[build] Building ArchMAP EXE (version $version)..."
    & $Python @args
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed."
    }

    if (-not (Test-Path $ExePath)) {
        throw "EXE not found after build: $ExePath"
    }

    $staleProcesses = Get-Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Path -and
            $_.Path.StartsWith($DistDir, [System.StringComparison]::OrdinalIgnoreCase) -and
            $_.ProcessName -like "archmap*"
        }
    if ($staleProcesses) {
        $staleProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500
    }

    $versionedExe = Join-Path $DistDir "archmap-$version.exe"
    Get-ChildItem -Path $DistDir -Filter "archmap-*.exe" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -ne $versionedExe } |
        Remove-Item -Force
    Copy-Item $ExePath $versionedExe -Force

    $sha = (Get-FileHash $ExePath -Algorithm SHA256).Hash
    $manifest = @{
        version      = $version
        builtAtUtc   = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        exePath      = $ExePath
        versionedExe = $versionedExe
        sha256       = $sha
    } | ConvertTo-Json -Depth 4
    $manifestPath = Join-Path $DistDir "archmap-build-info.json"
    Set-Content -Path $manifestPath -Value $manifest -Encoding UTF8

    if (-not $SkipSmoke) {
        Write-Host "[smoke] Running EXE smoke test (version command)..."
        & $ExePath version
        if ($LASTEXITCODE -ne 0) {
            throw "Smoke test failed for $ExePath"
        }
    }

    $distAnalysisCache = Join-Path $DistDir ".codeatlas"
    if (Test-Path $distAnalysisCache) {
        Remove-Item $distAnalysisCache -Recurse -Force -ErrorAction SilentlyContinue
    }

    Write-Host "[ok] EXE built successfully."
    Write-Host "[ok] Main EXE: $ExePath"
    Write-Host "[ok] Versioned EXE: $versionedExe"
    Write-Host "[ok] Older versioned EXEs removed."
    Write-Host "[ok] Build info: $manifestPath"
}
finally {
    Pop-Location
}
