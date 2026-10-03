Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$StudioRoot = Split-Path -Parent $PSScriptRoot
$StudioRuntime = Join-Path $StudioRoot '.runtime\videoagents'
$StudioManifest = Join-Path $StudioRuntime 'processes.json'

function Get-OwnedStudioProcess($Service) {
    $process = Get-Process -Id $Service.pid -ErrorAction SilentlyContinue
    if ($null -eq $process) { return $null }
    # PowerShell 7 can deserialize ISO dates as DateTime; Windows PowerShell 5
    # leaves them as strings. Compare UTC ticks rather than culture conversion.
    $actualStart = $process.StartTime.ToUniversalTime().Ticks
    $expectedStart = ([DateTimeOffset]$Service.started_at).UtcDateTime.Ticks
    if ($actualStart -ne $expectedStart) { return $null }
    if ($process.Path -ne $Service.executable) { return $null }
    return $process
}

function Stop-OwnedStudioProcess($Service) {
    $process = Get-OwnedStudioProcess $Service
    if ($null -eq $process) { return }
    # Snapshot descendants before stopping the root; never stop a reused PID.
    $snapshot = @(Get-CimInstance Win32_Process)
    $ownedIds = [System.Collections.Generic.HashSet[int]]::new()
    $ownedProcesses = [System.Collections.Generic.List[object]]::new()
    [void]$ownedIds.Add([int]$process.Id)
    $ownedProcesses.Add($Service)
    do {
        $added = $false
        foreach ($entry in $snapshot) {
            if ($ownedIds.Contains([int]$entry.ParentProcessId) -and -not $ownedIds.Contains([int]$entry.ProcessId)) {
                $child = Get-Process -Id $entry.ProcessId -ErrorAction SilentlyContinue
                if ($null -ne $child -and $child.StartTime -ge $process.StartTime) {
                    [void]$ownedIds.Add([int]$entry.ProcessId)
                    $ownedProcesses.Add([pscustomobject]@{
                        pid = $child.Id; started_at = $child.StartTime.ToUniversalTime().ToString('o')
                        executable = $child.Path
                    })
                    $added = $true
                }
            }
        }
    } while ($added)
    foreach ($owned in $ownedProcesses | Sort-Object started_at -Descending) {
        $current = Get-OwnedStudioProcess $owned
        if ($null -ne $current) {
            Stop-Process -Id $current.Id -Force -ErrorAction SilentlyContinue
        }
    }
    if ($null -ne (Get-OwnedStudioProcess $Service)) { Stop-Process -Id $process.Id -Force }
}

function Assert-FreeStudioPort([int]$Port) {
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    if ($listeners.Count -gt 0) { throw "Port $Port is occupied. Run npm run studio:stop or choose another application port before starting." }
}

function Start-StudioService([string]$Name, [string]$Executable, [string[]]$Arguments, [string]$WorkingDirectory) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $stdout = Join-Path $StudioRuntime "$Name-$stamp.stdout.log"
    $stderr = Join-Path $StudioRuntime "$Name-$stamp.stderr.log"
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
    return [pscustomobject]@{
        name = $Name; pid = $process.Id; started_at = $process.StartTime.ToUniversalTime().ToString('o')
        executable = (Get-Item -LiteralPath $Executable).FullName; stdout = $stdout; stderr = $stderr
    }
}

function Start-VideoAgentsStudio([ValidateSet('development', 'production')][string]$Mode) {
    New-Item -ItemType Directory -Path $StudioRuntime -Force | Out-Null
    $existingServices = @()
    if (Test-Path -LiteralPath $StudioManifest) {
        $saved = Get-Content -LiteralPath $StudioManifest -Raw | ConvertFrom-Json
        if ($saved.root -ne $StudioRoot) { throw 'Manifest belongs to a different workspace.' }
        $running = @($saved.services | Where-Object { $null -ne (Get-OwnedStudioProcess $_) })
        if ($running.Count -gt 0) {
            if ($saved.mode -ne $Mode) { throw 'Another studio mode is running. Run npm run studio:stop first.' }
            $existingServices = $running
        }
    }
    $python = Join-Path $StudioRoot '.venv-videoagents\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw 'Missing Python environment. See docs/videoagents-setup.md for uv sync instructions.' }
    $node = (Get-Command node -ErrorAction Stop).Source
    $vite = Join-Path $StudioRoot 'node_modules\vite\bin\vite.js'
    if ($Mode -eq 'development' -and -not (Test-Path -LiteralPath $vite)) { throw 'Missing JavaScript dependencies. Run npm install first.' }
    if ($Mode -eq 'production' -and -not (Test-Path -LiteralPath (Join-Path $StudioRoot 'web\dist\index.html'))) {
        Push-Location $StudioRoot
        try { & npm run web:build; if ($LASTEXITCODE -ne 0) { throw 'React build failed.' } }
        finally { Pop-Location }
    }
    if (-not ($existingServices | Where-Object name -eq 'api')) { Assert-FreeStudioPort 8000 }
    if ($Mode -eq 'development' -and -not ($existingServices | Where-Object name -eq 'web')) { Assert-FreeStudioPort 5173 }
    $services = [System.Collections.Generic.List[object]]::new()
    foreach ($service in $existingServices) { $services.Add($service) }
    $newServices = [System.Collections.Generic.List[object]]::new()
    $url = if ($Mode -eq 'development') { 'http://127.0.0.1:5173' } else { 'http://127.0.0.1:8000' }
    try {
        if (-not ($existingServices | Where-Object name -eq 'api')) {
            $newServices.Add((Start-StudioService 'api' $python @('-m', 'server.main') $StudioRoot))
        }
        if (-not ($existingServices | Where-Object name -eq 'worker')) {
            $newServices.Add((Start-StudioService 'worker' $python @('-m', 'worker.main') $StudioRoot))
        }
        if ($Mode -eq 'development' -and -not ($existingServices | Where-Object name -eq 'web')) {
            $newServices.Add((Start-StudioService 'web' $node @(('"' + $vite + '"'), '--host', '127.0.0.1', '--port', '5173', '--strictPort') (Join-Path $StudioRoot 'web')))
        }
        foreach ($service in $newServices) { $services.Add($service) }
        [pscustomobject]@{ mode = $Mode; root = $StudioRoot; url = $url; services = $services.ToArray() } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $StudioManifest -Encoding UTF8
        $ready = $false
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            foreach ($service in $services) {
                if ($null -eq (Get-OwnedStudioProcess $service)) { throw "$($service.name) exited. Inspect $($service.stderr)" }
            }
            try {
                $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 1
                $web = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 1
                if ($health.status -eq 'ok' -and $health.worker_alive -and $web.StatusCode -eq 200) { $ready = $true; break }
            } catch { }
            Start-Sleep -Seconds 1
        }
        if (-not $ready) { throw "Studio did not become healthy. Inspect logs under $StudioRuntime" }
        Write-Host "VideoAgents ready: $url"
        Write-Host "Logs: $StudioRuntime"
        Write-Host 'Stop: npm run studio:stop'
    } catch {
        foreach ($service in $newServices) { Stop-OwnedStudioProcess $service }
        throw
    }
}
