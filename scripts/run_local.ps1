# 로컬 실행 (Windows PowerShell): 의존성 설치 확인 후 블로그 1건 → final.mp4
# 사용: .\scripts\run_local.ps1 -Url https://blog.naver.com/<id>/<logNo> [-Image placeholder]
param(
  [Parameter(Mandatory = $true)][string]$Url,
  [string]$Image = ""
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
uv sync | Out-Null
if (-not (Test-Path remotion\node_modules)) { Push-Location remotion; npm install --no-audit --no-fund; Pop-Location }
$cmdArgs = @("run", "wbs", "run", "--url", $Url)
if ($Image) { $cmdArgs += @("--image", $Image) }
uv @cmdArgs
