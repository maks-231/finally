<#
.SYNOPSIS
    Stop and remove the FinAlly Docker container (Windows PowerShell).

.DESCRIPTION
    Does NOT remove the named volume — portfolio/trade data persists.
    Idempotent: safe to run multiple times, including when the container
    doesn't exist or is already stopped.

.EXAMPLE
    ./scripts/stop_windows.ps1
#>

$ContainerName = "finally"

docker inspect $ContainerName *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Stopping container '$ContainerName'..."
    docker stop $ContainerName *> $null
    Write-Host "Removing container '$ContainerName'..."
    docker rm $ContainerName *> $null
    Write-Host "Container stopped and removed. Data volume 'finally-data' is preserved."
} else {
    Write-Host "Container '$ContainerName' does not exist. Nothing to do."
}
