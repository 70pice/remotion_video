. (Join-Path $PSScriptRoot 'studio-common.ps1')
if (-not (Test-Path -LiteralPath $StudioManifest)) { Write-Host 'No studio process manifest found.'; exit 0 }
$saved = Get-Content -LiteralPath $StudioManifest -Raw | ConvertFrom-Json
if ($saved.root -ne $StudioRoot) { throw 'Manifest belongs to a different workspace.' }
foreach ($service in $saved.services) { Stop-OwnedStudioProcess $service }
Remove-Item -LiteralPath $StudioManifest
Write-Host 'VideoAgents stopped.'
