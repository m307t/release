#!/usr/bin/env bash
# Installer for macOS / Linux: kordoc (CLI + MCP) and the bill-review Claude Code plugin.
set -euo pipefail

KIT="$(cd "$(dirname "$0")" && pwd)"
DEST="${AI_TOOLS_HOME:-$HOME/.ai-tools}"
KORDOC_VERSION="4.24.8"

say()  { printf '\n\033[1;34m==> %s\033[0m\n' "$1"; }
warn() { printf '\033[1;33m[주의] %s\033[0m\n' "$1"; }

# 1. Node.js 20+
say "1/4 Node.js 확인"
if ! command -v node >/dev/null 2>&1 || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 20 ]; then
  if [ "$(uname)" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
    brew install node
  else
    warn "Node.js 20 이상이 필요합니다. https://nodejs.org 에서 LTS를 설치한 뒤 다시 실행하세요."
    exit 1
  fi
fi
echo "node $(node -v)"

# 2. kordoc
say "2/4 kordoc $KORDOC_VERSION 설치"
if ! npm install -g "kordoc@$KORDOC_VERSION"; then
  # Fall back to a user-level prefix only when the global node_modules is not writable.
  # Any other failure (network etc.) stops here and leaves the npm settings as they were.
  if [ -w "$(npm root -g)" ]; then
    warn "kordoc 설치에 실패했습니다(위 npm 메시지 참고). npm 설정은 바꾸지 않았습니다."
    exit 1
  fi
  npm config set prefix "$HOME/.npm-global"
  warn "전역 npm 폴더에 쓸 수 없어 npm 설치 위치(prefix)를 \$HOME/.npm-global 로 바꿨습니다(~/.npmrc)."
  warn "PATH에 \$HOME/.npm-global/bin 을 추가하세요 (예: ~/.zshrc 에 export PATH=\"\$HOME/.npm-global/bin:\$PATH\")"
  export PATH="$HOME/.npm-global/bin:$PATH"
  npm install -g "kordoc@$KORDOC_VERSION"
fi
kordoc --version || true

# 3. Copy plugin source to a stable location
say "3/4 AI-Assembly(bill-review) 복사 → $DEST"
mkdir -p "$DEST"
rm -rf "$DEST/AI-Assembly"
cp -R "$KIT/payload/AI-Assembly" "$DEST/AI-Assembly"
cp "$KIT/payload/register-mcp.mjs" "$DEST/register-mcp.mjs"

# 4. Register with Claude Code / Claude Desktop
say "4/4 Claude 연결"
NODE_BIN="$(node "$DEST/register-mcp.mjs" --print | sed -n 1p)"
MCP_JS="$(node "$DEST/register-mcp.mjs" --print | sed -n 2p)"
if command -v claude >/dev/null 2>&1; then
  claude mcp remove --scope user kordoc >/dev/null 2>&1 || true
  claude mcp add --scope user kordoc -- "$NODE_BIN" "$MCP_JS"
  claude plugin marketplace remove ai-assembly >/dev/null 2>&1 || true
  claude plugin marketplace add "$DEST/AI-Assembly"
  claude plugin install bill-review@ai-assembly
else
  warn "Claude Code(claude) 가 없어 kordoc·플러그인의 Claude Code 등록을 건너뜁니다. 설치 후 이 스크립트를 다시 실행하세요."
fi
node "$DEST/register-mcp.mjs" || warn "Claude Desktop 등록 실패(수동 등록은 README 참고)"

say "완료"
echo "- KISA 범피스는 Windows 전용 프로그램이라 macOS/Linux에는 설치하지 않았습니다."
echo "- Claude 앱을 재시작한 뒤 확인하세요: claude mcp list / claude plugin list"
