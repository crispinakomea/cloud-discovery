#!/usr/bin/env pwsh
# gcp-build-and-push.ps1
# Builds all service containers and pushes them to Google Artifact Registry.
# Usage: .\gcp-build-and-push.ps1 [-ProjectId <project>] [-Repository <repo>] [-Location <region>] [-Tag <tag>] [-NoPush]

param(
    [string]$ProjectId = "work-playpen-env",
    [string]$Repository = "eur-78085-acr",
    [string]$Location = "",
    [string]$Tag = "v1.0.0",
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"

$services = @(
    #@{ Name = "countries-api-flask";       Context = ".\countries-api\flask" },
    #@{ Name = "countries-api-function";    Context = ".\countries-api\function" },
    #@{ Name = "currency-api-flask";        Context = ".\currency-api\flask" },
    #@{ Name = "currency-api-function";     Context = ".\currency-api\function" },
    #@{ Name = "weather-api-flask";         Context = ".\weather-api\flask" },
    #@{ Name = "weather-api-function";      Context = ".\weather-api\function" },
    #@{ Name = "holiday-planner-flask";     Context = ".\holiday-planner\flask" },
    #@{ Name = "holiday-planner-function";  Context = ".\holiday-planner\function" },
    @{ Name = "otel-collector-standard";   Context = ".\otel-collector\standard" },
    @{ Name = "otel-collector-dynatrace";  Context = ".\otel-collector\dynatrace" }
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if ([string]::IsNullOrWhiteSpace($Location)) {
    Write-Host "`n=== Resolving location for repository '$Repository' in project '$ProjectId' ===" -ForegroundColor Cyan
    $reposJson = gcloud artifacts repositories list --project="$ProjectId" --format="json"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to list Artifact Registry repositories for project '$ProjectId'."
        exit 1
    }

    $repos = $reposJson | ConvertFrom-Json
    $repo = $repos | Where-Object { ($_.name -split '/')[-1] -eq $Repository } | Select-Object -First 1

    if (-not $repo) {
        Write-Error "Repository '$Repository' not found in project '$ProjectId'."
        exit 1
    }

    $Location = ($repo.name -split '/')[3]
    if ([string]::IsNullOrWhiteSpace($Location)) {
        Write-Error "Could not determine repository location from '$($repo.name)'."
        exit 1
    }
}

$registryHost = "$Location-docker.pkg.dev"

if (-not $NoPush) {
    Write-Host "`n=== Configuring Docker auth for: $registryHost ===" -ForegroundColor Cyan
    gcloud auth configure-docker $registryHost --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to configure Docker authentication for '$registryHost'."
        exit 1
    }
}

foreach ($svc in $services) {
    if (-not (Test-Path $svc.Context)) {
        Write-Error "Build context not found: $($svc.Context)"
        exit 1
    }

    $image = "$registryHost/$ProjectId/$Repository/$($svc.Name):$Tag"
    Write-Host "`n=== Building $image ===" -ForegroundColor Cyan

    docker build -t $image $svc.Context
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Build failed for $($svc.Name)"
        exit 1
    }

    if (-not $NoPush) {
        Write-Host "=== Pushing $image ===" -ForegroundColor Cyan
        docker push $image
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Push failed for $($svc.Name)"
            exit 1
        }
    }
}

if ($NoPush) {
    Write-Host "`n=== All services built successfully (push skipped) ===" -ForegroundColor Green
} else {
    Write-Host "`n=== All services built and pushed successfully ===" -ForegroundColor Green
}
