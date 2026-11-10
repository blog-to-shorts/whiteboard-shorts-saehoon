# 외부 공유: 웹 서버(8000) + Cloudflare 무료 터널을 백그라운드로 켜고 공개 주소를 출력한다.
# 사용:  .\scripts\share.ps1          켜기 (이미 켜져 있으면 그대로 두고 주소만 다시 보여줌)
#        .\scripts\share.ps1 -Stop    끄기
# 주의: 이 PC 가 켜져 있는 동안만 접속된다. 터널을 다시 켜면 주소가 바뀐다.
#       .env 의 DEMO_PASSWORD 가 있으면 접속 시 로그인 창(아이디 DEMO_USER)이 뜬다.
param([switch]$Stop)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$logs = Join-Path $root "jobs\_share"
New-Item -ItemType Directory -Force $logs | Out-Null
$pidFile = Join-Path $logs "pids.json"

function Stop-Share {
  if (Test-Path $pidFile) {
    (Get-Content $pidFile -Raw | ConvertFrom-Json).PSObject.Properties | ForEach-Object {
      Stop-Process -Id $_.Value -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $pidFile
  }
  Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  # cmd 아래에서 뜬 uvicorn(python)까지 정리: 8000 포트를 잡은 프로세스
  Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}

if ($Stop) { Stop-Share; "공유를 껐어요."; exit 0 }

$cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cf) { $cf = "C:\Program Files (x86)\cloudflared\cloudflared.exe" }
if (-not (Test-Path $cf)) { throw "cloudflared 가 없어요: winget install --id Cloudflare.cloudflared -e" }
if (-not (Test-Path (Join-Path $root ".env")) -or -not (Select-String -Path (Join-Path $root ".env") -Pattern '^DEMO_PASSWORD=.+' -Quiet)) {
  Write-Warning ".env 에 DEMO_PASSWORD 가 없어요. 누구나 들어와 영상을 만들 수 있으니(비용 발생) 비밀번호를 먼저 정하세요."
}
if (-not (Test-Path (Join-Path $root "frontend\dist\index.html"))) {
  Push-Location (Join-Path $root "frontend"); npm install --no-audit --no-fund; npm run build; Pop-Location
}

$pids = @{}
$listening = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if (-not $listening) {
  # -Redirect* 를 쓰면 자식이 이 스크립트의 출력 핸들을 물려받아 스크립트가 끝나지 않는다 → cmd 로 따로 띄우고 cmd 안에서 로그로 보냄
  $uv = (Get-Command uv).Source
  $srvLog = Join-Path $logs "server.log"
  $cmdLine = "/c `"`"$uv`" run uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 > `"$srvLog`" 2>&1`""
  $srv = Start-Process -FilePath "cmd.exe" -WorkingDirectory $root -WindowStyle Hidden -PassThru -ArgumentList $cmdLine
  $pids.server = $srv.Id
  for ($i = 0; $i -lt 40 -and -not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue); $i++) { Start-Sleep -Milliseconds 500 }
}

$tunLog = Join-Path $logs "tunnel.log"
$url = $null
if (Get-Process cloudflared -ErrorAction SilentlyContinue) {
  $url = (Select-String -Path $tunLog -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue | Select-Object -Last 1).Matches.Value
}
if (-not $url) {
  Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  if (Test-Path $tunLog) { Remove-Item $tunLog }
  $tun = Start-Process -FilePath $cf -WindowStyle Hidden -PassThru `
    -ArgumentList "tunnel", "--no-autoupdate", "--url", "http://localhost:8000", "--logfile", $tunLog
  $pids.tunnel = $tun.Id
  for ($i = 0; $i -lt 60 -and -not $url; $i++) {
    Start-Sleep -Milliseconds 500
    $url = (Select-String -Path $tunLog -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue | Select-Object -Last 1).Matches.Value
  }
}
if ($pids.Count) {
  $old = if (Test-Path $pidFile) { Get-Content $pidFile -Raw | ConvertFrom-Json } else { $null }
  if ($old) { $old.PSObject.Properties | ForEach-Object { if (-not $pids.ContainsKey($_.Name)) { $pids[$_.Name] = $_.Value } } }
  $pids | ConvertTo-Json | Set-Content $pidFile -Encoding utf8
}
if (-not $url) { throw "터널 주소를 받지 못했어요. 로그: $tunLog" }
$url | Set-Content (Join-Path $logs "url.txt") -Encoding utf8
"공개 주소: $url"
"아이디: demo  /  비밀번호: .env 의 DEMO_PASSWORD"
