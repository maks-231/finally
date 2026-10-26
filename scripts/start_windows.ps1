<#
.SYNOPSIS
    Start the FinAlly Docker container (Windows PowerShell).

.DESCRIPTION
    Builds the Docker image if it doesn't already exist (or if -Build is
    passed to force a rebuild), then runs the container with the volume
    mount and port mapping, using the project's .env file.

    Idempotent: safe to run multiple times. If the container is already
    running, this just prints the URL. If it exists but is stopped, it is
    started rather than recreated.

.PARAMETER Build
    Force a rebuild of the Docker image before starting.

.EXAMPLE
    ./scripts/start_windows.ps1
    ./scripts/start_windows.ps1 -Build
#>

param(
    [switch]$Build
)

$ErrorActionPreference = "Stop"

$ImageName = "finally"
$ImageTag = "latest"
$ContainerName = "finally"
$VolumeName = "finally-data"
$HostPort = 8000
$ContainerPort = 8000

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$EnvFile = Join-Path $ProjectRoot ".env"

if (-not (Test-Path $EnvFile)) {
    Write-Warning "$EnvFile not found. Copy .env.example to .env and fill in values first."
}

Push-Location $ProjectRoot
try {
    $imageExists = $false
    docker image inspect "${ImageName}:${ImageTag}" *> $null
    if ($LASTEXITCODE -eq 0) {
        $imageExists = $true
    }

    if ($Build -or -not $imageExists) {
        Write-Host "Building Docker image ${ImageName}:${ImageTag}..."
        docker build -t "${ImageName}:${ImageTag}" -f (Join-Path $ProjectRoot "Dockerfile") $ProjectRoot
        if ($LASTEXITCODE -ne 0) { throw "docker build failed" }
    }

    # Ensure the named volume exists (idempotent — no-op if already present)
    docker volume create $VolumeName *> $null

    $containerState = (docker inspect -f '{{.State.Status}}' $ContainerName 2>$null)
    if (-not $containerState) {
        $containerState = "missing"
    }

    switch ($containerState) {
        "running" {
            Write-Host "Container '$ContainerName' is already running."
        }
        "missing" {
            Write-Host "Starting new container '$ContainerName'..."
            $runArgs = @(
                "run", "-d", "--name", $ContainerName,
                "-p", "${HostPort}:${ContainerPort}",
                "-v", "${VolumeName}:/app/db",
                "--restart", "unless-stopped"
            )
            if (Test-Path $EnvFile) {
                $runArgs += @("--env-file", $EnvFile)
            }
            $runArgs += "${ImageName}:${ImageTag}"
            docker @runArgs
            if ($LASTEXITCODE -ne 0) { throw "docker run failed" }
        }
        default {
            Write-Host "Container '$ContainerName' exists (state: $containerState). Starting it..."
            docker start $ContainerName *> $null
        }
    }

    $url = "http://localhost:$HostPort"
    Write-Host ""
    Write-Host "FinAlly is available at: $url"

    # Best-effort browser open; never fail the script if it's unavailable.
    try {
        Start-Process $url -ErrorAction Stop | Out-Null
    } catch {
        # Ignore — no default browser handler available in this environment.
    }
}
finally {
    Pop-Location
}
