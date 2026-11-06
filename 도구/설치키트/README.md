# AI 도구 설치 키트

kordoc · AI-Assembly(bill-review 플러그인)를 한 번에 설치합니다. KISA 범피스(Windows)는 배포본에 들어 있지 않아, 파일을 직접 넣었을 때만 설치합니다.

## 설치 방법

| OS | 실행 |
|---|---|
| Windows | `install-windows.bat` 더블클릭 |
| macOS / Linux | 터미널에서 `bash install.sh` |

설치 후 Claude 앱(Claude Code·Claude Desktop)을 재시작하세요.

## 설치되는 것

| 구성요소 | Windows | macOS | Linux | 설치 위치 |
|---|---|---|---|---|
| Node.js 20+ (없을 때만) | winget 자동 | Homebrew 자동 | 수동 | 시스템 |
| kordoc 4.24.8 (CLI + MCP) | ○ | ○ | ○ | npm 전역 |
| bill-review 플러그인 | ○ | ○ | ○ | `%LOCALAPPDATA%\ai-tools` / `~/.ai-tools` |
| KISA 범피스 (선택, 배포본에 없음) | △ exe를 넣었을 때만 (바탕화면·시작메뉴 바로가기) | × | × | `%LOCALAPPDATA%\ai-tools\KISA` |

- kordoc MCP는 Claude Code(사용자 범위)와 Claude Desktop에 자동 등록됩니다. 등록 직전의 Desktop 설정은 `.bak`으로 백업됩니다.
- bill-review 플러그인은 Claude Code가 설치된 경우에만 등록됩니다. 나중에 Claude Code를 설치했다면 스크립트를 다시 실행하세요.
- 다시 실행해도 됩니다. 플러그인 폴더(`~/.ai-tools/AI-Assembly`, Windows는 `%LOCALAPPDATA%\ai-tools\AI-Assembly`)를 지우고 같은 판을 다시 복사·등록합니다. Desktop 설정 백업 `.bak`은 실행할 때마다 덮어쓰므로, 처음 설정을 보존하려면 첫 실행 뒤 `.bak`을 따로 복사해 둡니다.
- 새 판을 받았을 때(저장소 맨 위 `README.md`의 '새 판 받기') 배포본이 바꾼 파일에 `도구/설치키트/`가 있으면 PC마다 이 키트를 다시 실행합니다. 다른 PC는 동기화로 받은 뒤 실행합니다.
- 국가법령정보 MCP는 설치키트가 설치하지 않습니다. 연결 방법은 저장소 맨 위 `README.md`의 'PC마다 확인할 것'에 있습니다.
- kordoc는 인터넷(npm)에서 받습니다. 나머지는 키트 안의 파일을 씁니다.
- KISA 범피스: 제3자 프로그램이라 배포본에는 넣지 않았습니다(`제3자고지.md`). 이 배포본은 이 프로그램의 용도를 정하지 않으며 에이전트 팀도 쓰지 않으므로, 기관이 따로 정한 경우가 아니면 넣지 않아도 됩니다.
  - 기관에서 받은 .exe를 `도구/설치키트/payload/windows/`에 넣으면 Windows 설치 4단계(`payload/install-windows.ps1`의 4/5)가 `%LOCALAPPDATA%\ai-tools\KISA`에 복사하고 바탕화면·시작 메뉴에 'KISA 범피스' 바로가기를 만듭니다. 파일이 없으면 안내 한 줄만 띄우고 이 단계를 건너뜁니다. 설치 스크립트는 이 프로그램을 실행하지 않습니다.
  - 넣은 .exe는 재배포 조건이 따로 있어 동기화하지 않습니다(`.gitignore`). 여러 PC에서 쓰려면 PC마다 넣습니다.
- kordoc 버전을 바꿀 때는 `install.sh`의 `KORDOC_VERSION`, `payload/install-windows.ps1`의 `$KordocVersion`, 이 문서의 버전 숫자(위 표, 아래 확인·수동 등록 예시)를 함께 고칩니다.

## 확인

```bash
kordoc --version          # 4.24.8
claude mcp list           # kordoc ... Connected
claude plugin list        # bill-review@ai-assembly enabled
```

## 수동 등록(자동 등록 실패 시)

```bash
claude mcp add --scope user kordoc -- npx -y kordoc@4.24.8 mcp
claude plugin marketplace add ~/.ai-tools/AI-Assembly    # Windows: %LOCALAPPDATA%\ai-tools\AI-Assembly
claude plugin install bill-review@ai-assembly
```

마켓플레이스 경로는 설치 스크립트가 플러그인을 복사한 곳입니다(macOS·Linux에서 `AI_TOOLS_HOME`을 정했으면 그 아래 `AI-Assembly`).

## 이 저장소가 직접 쓰는 payload 파일

플러그인을 설치하지 않은 PC나 클라우드 세션에서도 조문 대조(법제팀·심사지원팀·법안검토팀 예비 경로, `자료실/규칙/조문대조.md`)는 아래 파일을 경로째 직접 씁니다. 원본을 새로 받아 덮어쓰거나 플러그인을 고친 뒤에는 두 명령을 돌려 둘 다 통과하는지 확인합니다.

| 파일 (`payload/AI-Assembly/plugins/bill-review/skills/` 아래) | 쓰는 곳 |
|---|---|
| `article-check/scripts/article_check.py` | 조문 대조 검사기 |
| `article-check/SKILL.md` §2 | 원장 전체 형식 |
| `review-writing/references/compare-table.md` | 대비표 전체 표기 약속 |

```bash
python3 도구/설치키트/payload/AI-Assembly/plugins/bill-review/skills/article-check/scripts/article_check.py --selftest
python3 도구/구성점검.py
```

## 이 저장소에서 고친 것

원본은 [parkjui92/AI-Assembly](https://github.com/parkjui92/AI-Assembly)(MIT)다. 아래만 고쳤다. 원본을 새로 받아 덮어쓰면 다시 적용한다.

| 파일 (`payload/AI-Assembly/` 아래) | 고친 내용 | 이유 |
|---|---|---|
| `plugins/bill-review/agents/bill-investigator.md` | `tools:` 목록을 지움 (모든 도구 상속) | 법령 커넥터 이름이 환경마다 달라(`mcp__mcp__…` 등) 고정 목록으로는 법령 도구를 쓰지 못함 |
| `plugins/bill-review/agents/bill-reviewer.md` | `tools:` 목록 → `disallowedTools: Write, Edit, NotebookEdit, Bash` | 같은 이유. 쓰기 금지는 그대로 |
| `plugins/bill-review/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | 버전 `0.1.0` → `0.1.0-vanilla.1` | 이미 설치한 PC가 고친 판을 새로 받도록 |
| `slides/`, `tools/`, `index.html`, `.nojekyll` | 지움 | 원본의 강의자료·소개 페이지(약 7MB)로, 설치 스크립트와 플러그인이 쓰지 않음. 원본 저장소에서 본다 |
| `README.md` | 1·2절(강의자료·도구 모음)을 원본 저장소를 가리키는 한 문단으로 줄임. 3절 설치 명령 앞에 이 사본은 설치키트로 설치한다는 한 줄을 넣음. '유의'의 강의자료 출처 문장을 원본 저장소의 강의자료로 한정함 | 지운 파일을 가리키지 않고, 원본 명령으로 고치지 않은 판(`0.1.0`)을 설치하지 않게 |

이미 설치키트를 실행한 PC는 한 번 더 실행해야 고친 내용이 적용된다.
