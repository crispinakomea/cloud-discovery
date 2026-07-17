#!/usr/bin/env pwsh
# build-and-push.ps1
# Builds all service containers and pushes them to ACR.
# Usage: .\build-and-push.ps1 [-Registry <acr>] [-Tag <tag>] [-NoPush]

param(
    [string]$Registry = "uks5e2e7acr.azurecr.io",
    [string]$Tag = "v1.0.0",
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"

$services = @(
    @{ Name = "countries-api-flask";      Context = ".\countries-api\flask" },
    #@{ Name = "countries-api-function";   Context = ".\countries-api\function" },
    @{ Name = "currency-api-flask";       Context = ".\currency-api\flask" },
    #@{ Name = "currency-api-function";    Context = ".\currency-api\function" },
    @{ Name = "weather-api-flask";        Context = ".\weather-api\flask" },
    #@{ Name = "weather-api-function";     Context = ".\weather-api\function" },
    @{ Name = "holiday-planner-flask";     Context = ".\holiday-planner\flask" },
    #@{ Name = "holiday-planner-function";  Context = ".\holiday-planner\function" },
    @{ Name = "otel-collector-standard";  Context = ".\otel-collector\standard" }
    #@{ Name = "otel-collector-dynatrace"; Context = ".\otel-collector\dynatrace" }
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "`n=== Logging in to ACR: $Registry ===" -ForegroundColor Cyan
az acr login --name ($Registry -split '\.')[0]

foreach ($svc in $services) {
    $image = "$Registry/$($svc.Name):$Tag"
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

Write-Host "`n=== All services built and pushed successfully ===" -ForegroundColor Green
