$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
if (-not (Test-Path -LiteralPath (Join-Path $taskRoot 'dist\index.html')) -or -not (Test-Path -LiteralPath (Join-Path $taskRoot 'dist\server\api.mjs'))) { throw '먼저 이 폴더에서 npm install 및 npm run build를 실행하세요.' }
$taskNodeCommand = Get-Command node -ErrorAction SilentlyContinue
$taskNode = if ($taskNodeCommand) { $taskNodeCommand.Source } else { Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' }
if (-not (Test-Path -LiteralPath $taskNode)) { throw 'Node.js 20.19+ 또는 22.12+가 필요합니다. README.md의 실행 방법을 확인하세요.' }
$taskServer = Join-Path $taskRoot 'scripts\serve.mjs'
$taskPort = if ($env:SIGHTCHECK_PORT) { $env:SIGHTCHECK_PORT } else { '4173' }
$taskUrl = 'http://127.0.0.1:' + $taskPort + '/'
$taskReady = $false
try { $taskHealth = Invoke-RestMethod -Uri ($taskUrl + 'api/health') -TimeoutSec 2; $taskReply = Invoke-WebRequest -Uri $taskUrl -TimeoutSec 2; $taskReady = $taskHealth.engineVersion -eq '0.3.0' -and $taskReply.Content -match '시야체크' } catch { }
if (-not $taskReady) {
  if (-not $env:SIGHTCHECK_PORT) {
    $taskFreePort = $null
    foreach ($taskCandidate in 4173..4183) {
      $taskProbe = New-Object Net.Sockets.TcpClient
      try { $taskProbe.Connect('127.0.0.1', $taskCandidate); $taskOccupied = $true } catch { $taskOccupied = $false } finally { $taskProbe.Dispose() }
      if (-not $taskOccupied) { $taskFreePort = $taskCandidate; break }
    }
    if (-not $taskFreePort) { throw '4173~4183 포트를 사용할 수 없습니다. SIGHTCHECK_PORT로 다른 포트를 지정하세요.' }
    $taskPort = [string]$taskFreePort
    $taskUrl = 'http://127.0.0.1:' + $taskPort + '/'
    $env:SIGHTCHECK_PORT = $taskPort
  }
  Start-Process -FilePath $taskNode -ArgumentList @('"' + $taskServer + '"') -WorkingDirectory $taskRoot -WindowStyle Hidden
  for ($taskAttempt = 0; $taskAttempt -lt 20; $taskAttempt++) {
    Start-Sleep -Milliseconds 200
    try { $taskHealth = Invoke-RestMethod -Uri ($taskUrl + 'api/health') -TimeoutSec 1; $taskReply = Invoke-WebRequest -Uri $taskUrl -TimeoutSec 1; if ($taskHealth.engineVersion -eq '0.3.0' -and $taskReply.Content -match '시야체크') { $taskReady = $true; break } } catch { }
  }
}
if ($taskReady) { Start-Process ($taskUrl + 'operator.html') } else { throw "변환 API 서버를 시작하지 못했습니다. 다른 프로그램이 $taskPort 포트를 사용하면 SIGHTCHECK_PORT로 다른 포트를 지정하세요." }
