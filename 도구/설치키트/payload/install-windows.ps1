# Installer for Windows: kordoc (CLI + MCP), bill-review Claude Code plugin, optional KISA program shortcut.
$ErrorActionPreference = "Stop"

$Kit  = Split-Path -Parent $PSScriptRoot
$Dest = Join-Path $env:LOCALAPPDATA "ai-tools"
$KordocVersion = "4.24.8"

function Say($m)  { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "[주의] $m" -ForegroundColor Yellow }
function Refresh-Path {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
              [Environment]::GetEnvironmentVariable("Path", "User")
}
function Has($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

# 1. Node.js 20+
Say "1/5 Node.js 확인"
$needNode = $true
if (Has node) { $needNode = [int](node -p "process.versions.node.split('.')[0]") -lt 20 }
if ($needNode) {
  if (Has winget) {
    winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
    Refresh-Path
  } else {
    Warn "Node.js 20 이상이 필요합니다. https://nodejs.org 에서 LTS를 설치한 뒤 다시 실행하세요."
    exit 1
  }
}
Write-Host "node $(node -v)"

# 2. kordoc
Say "2/5 kordoc $KordocVersion 설치"
npm install -g "kordoc@$KordocVersion"
if ($LASTEXITCODE -ne 0) { throw "kordoc 설치 실패" }
Refresh-Path

# 3. Copy plugin source and KISA program to a stable location
Say "3/5 파일 복사 → $Dest"
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
$asm = Join-Path $Dest "AI-Assembly"
if (Test-Path $asm) { Remove-Item -Recurse -Force $asm }
Copy-Item -Recurse (Join-Path $Kit "payload\AI-Assembly") $asm
Copy-Item (Join-Path $Kit "payload\register-mcp.mjs") $Dest -Force

# 4. KISA program (optional): the distribution does not bundle it. Copy and create shortcuts only
#    when the user has placed the .exe under payload\windows\ themselves.
Say "4/5 KISA 범피스 설치 (선택)"
$exe = Get-ChildItem (Join-Path $Kit "payload\windows") -Filter *.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -eq $exe) {
  Write-Host "KISA 범피스 .exe가 없어 이 단계는 건너뜁니다(배포본에 없는 선택 프로그램). 기관에서 받은 파일이 있을 때만 payload\windows\에 넣고 다시 실행합니다."
} else {
  $kisaDir = Join-Path $Dest "KISA"
  New-Item -ItemType Directory -Force -Path $kisaDir | Out-Null
  Copy-Item $exe.FullName $kisaDir -Force
  $target = Join-Path $kisaDir $exe.Name
  $shell = New-Object -ComObject WScript.Shell
  foreach ($dir in @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("Programs"))) {
    $lnk = $shell.CreateShortcut((Join-Path $dir "KISA 범피스.lnk"))
    $lnk.TargetPath = $target
    $lnk.WorkingDirectory = $kisaDir
    $lnk.Save()
  }
  Write-Host "바탕화면·시작 메뉴에 'KISA 범피스' 바로가기를 만들었습니다."
}

# 5. Register with Claude Code / Claude Desktop
Say "5/5 Claude 연결"
$reg = Join-Path $Dest "register-mcp.mjs"
$paths = node $reg --print
if (Has claude) {
  cmd /c "claude mcp remove --scope user kordoc >nul 2>&1"
  claude mcp add --scope user kordoc -- $paths[0] $paths[1]
  if ($LASTEXITCODE -ne 0) { Warn "kordoc의 Claude Code 등록 실패(수동 등록은 README 참고)" }
  cmd /c "claude plugin marketplace remove ai-assembly >nul 2>&1"
  claude plugin marketplace add $asm
  if ($LASTEXITCODE -ne 0) { Warn "플러그인 마켓플레이스 등록 실패(수동 등록은 README 참고)" }
  claude plugin install bill-review@ai-assembly
  if ($LASTEXITCODE -ne 0) { Warn "bill-review 플러그인 설치 실패(수동 등록은 README 참고)" }
} else {
  Warn "Claude Code(claude)가 없어 kordoc·플러그인의 Claude Code 등록을 건너뜁니다. 설치 후 이 파일을 다시 실행하세요."
}
node $reg
if ($LASTEXITCODE -ne 0) { Warn "Claude Desktop 등록 실패(수동 등록은 README 참고)" }

Say "완료 — Claude 앱을 재시작한 뒤 'claude mcp list', 'claude plugin list'로 확인하세요."
