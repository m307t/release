# release

법제업무 AI 에이전트 팀의 배포용 프로젝트를 모아 두는 저장소입니다. 각 폴더가 하나의 배포본이며, 쓰는 사람은 원하는 폴더를 자기 비공개 저장소로 옮겨 씁니다.

> **목적과 면책**: 이 저장소의 에이전트는 법제업무, 검토보고서 작성 업무, 예결산 검토 업무를 보조하고 그를 위한 일정관리와 자료조사를 하는 도구입니다. 사용자와 함께 시행착오를 겪으며 성장하도록 설계해, 배포 시점에는 미숙할 수 있습니다. 결과물은 법률 자문이나 기관의 공식 의견이 아니며, 원문 대조와 사용 여부의 최종 판단·책임은 사람(최종 검수자)과 그 소속 기관에 있습니다. 자세한 내용은 각 배포본의 `면책고지.md`를 보세요.

만든 사람: 백현민 · 문의: bhm0307@naver.com

> **처음이면** 아래 [처음 쓰는 분: 내려받기부터 Claude 연결까지](#처음-쓰는-분-내려받기부터-claude-연결까지)를 0단계부터 차례로 따라 하세요. 배포본 내려받기 → 내 Private 저장소에 올리기 → Claude와 GitHub 연결 → 그다음 설정까지 이 페이지에 모두 있습니다.

## 배포본
| 폴더 | 판 | 무엇 | 시작 문서 |
|---|---|---|---|
| `vanilla/` | vanilla 1.0 (2026. 11. 5.) | 법제업무팀 에이전트 기본판: 8개 팀(상황실·법제·법안검토·예결산·조사·심사지원·뉴스레터·역량강화) + 진행 현황 대시보드. 기관 고유 자료를 모두 뺀 빈 사무실 | 이 페이지의 '처음 쓰는 분' → `vanilla/README.md` → `vanilla/튜토리얼.md` |

배포본의 바뀐 기록은 각 배포본의 `변경이력.md`(예: `vanilla/변경이력.md`)에 있습니다.

## 처음 쓰는 분: 내려받기부터 Claude 연결까지
배포본(`vanilla`)을 내려받아 **내 Private(비공개) 저장소**에 올리고, Claude와 GitHub를 연결하는 순서입니다. 계정 준비를 빼면 처음에 30~40분쯤 걸립니다.

| 단계 | 하는 일 | 어디서 |
|---|---|---|
| [0](#0-준비) | 계정과 프로그램 준비 | 브라우저, PC |
| [1](#1-배포본-내려받기) | 배포본을 내려받아 `법제업무팀` 폴더 만들기 | 이 페이지, PC |
| [2](#2-내-private-저장소-만들기) | GitHub에 빈 Private 저장소 만들기 | github.com |
| [3](#3-내-저장소에-올리기) | `법제업무팀` 폴더를 내 저장소에 올리기 | PC (Git Bash·터미널) |
| [4](#4-claude와-github-연결) | Claude와 GitHub 연결 | PC 또는 claude.ai/code |
| [5](#5-그다음-설정) | 도구 설치, 구성 점검, 법령 MCP, 실습 | 내 저장소 폴더 |

막히면 맨 아래 [자주 막히는 곳](#자주-막히는-곳)을 봅니다.

### 0. 준비
| 준비물 | 받는 곳 | 비고 |
|---|---|---|
| GitHub 계정 | https://github.com/signup | 무료 계정이면 됩니다 |
| claude.ai 계정 | https://claude.ai | Claude Code와 클라우드 세션은 Pro·Max·Ultra·Team·Enterprise 플랜에서 씁니다. Team·Enterprise는 조직 관리자가 Claude Code를 허용해야 합니다 |
| Git | Windows: [Git for Windows](https://git-scm.com/downloads/win) — 설치 화면은 기본값 그대로 **Next** · macOS: 터미널에서 `git --version`을 치면 설치 창이 뜹니다 | Windows는 함께 설치되는 **Git Bash**에서 아래 명령을 칩니다 |
| Claude Code 또는 Claude 데스크톱 앱 | 데스크톱 앱: https://claude.ai/download · Claude Code: 아래 명령 | 둘 중 하나만 있어도 됩니다 |

- 터미널 여는 법: Windows는 시작 메뉴에서 **Git Bash**(Claude Code 설치만은 **PowerShell**), macOS는 **응용 프로그램 → 유틸리티 → 터미널**.
- Claude Code 설치 명령(2026. 11. 6. 공식 안내 https://code.claude.com/docs/en/quickstart 기준):
  ```bash
  # macOS / Linux (Terminal)
  curl -fsSL https://claude.ai/install.sh | bash
  ```
  ```powershell
  # Windows (PowerShell)
  irm https://claude.ai/install.ps1 | iex
  ```
  설치한 뒤 새 터미널 창에서 `claude --version`으로 확인합니다.
- Python·Node.js처럼 업무 도구에 필요한 것은 [5단계](#5-그다음-설정)에서 설치합니다.

### 1. 배포본 내려받기
둘 중 편한 방법으로 받습니다. 받은 뒤 `vanilla` 폴더를 **폴더째** 복사해 `법제업무팀`이라는 새 폴더로 만듭니다.

**방법 A — ZIP으로 받기 (명령 없이)**
1. 이 페이지 위쪽의 초록색 **Code** 버튼 → **Download ZIP**을 누릅니다.
2. 받은 `release-main.zip`의 압축을 풉니다.
3. 풀린 폴더 안에서 `vanilla` 폴더를 찾아 복사하고, 작업할 곳(예: 내 사용자 폴더)에 붙여 넣은 뒤 이름을 `법제업무팀`으로 바꿉니다.

**방법 B — git으로 받기**

Git Bash(Windows)나 터미널(macOS)에서 칩니다.
```bash
cd ~                                             # your home folder
git clone https://github.com/m307t/release.git
cp -R release/vanilla 법제업무팀                    # copy the folder itself (hidden files included)
```

> **꼭 지킬 것**
> - `vanilla` 안의 파일을 골라 복사하지 말고 **폴더째** 복사합니다. 이름이 점(.)으로 시작하는 숨김 항목(`.claude` 폴더, `.gitignore`, `.gitattributes`)이 빠지면 팀이 동작하지 않습니다. 숨김 항목은 Windows 탐색기 **보기**에서 **숨긴 항목**을 켜면, macOS Finder에서는 `Cmd + Shift + .`을 누르면 보입니다.
> - 받은 `release`(또는 `release-main`) 폴더 안의 `vanilla`에서 바로 Claude를 열거나 동기화(`동기화.sh`·`동기화.cmd`)를 돌리지 않습니다. 팀 설정(`.claude/`)이 읽히지 않고, git으로 받았으면 연습 기록이 배포 저장소에 커밋될 수 있습니다. 동기화 스크립트도 자기 폴더가 git 저장소의 맨 위가 아니면 아무것도 올리지 않고 멈춥니다.
> - `법제업무팀` 폴더는 OneDrive·iCloud Drive처럼 자동으로 동기화되는 폴더 밖에 둡니다. 두 동기화가 겹치면 git 파일이 꼬일 수 있습니다.
> - 압축을 푼 뒤 한글 파일 이름이 깨져 보이면 반디집·7-Zip 같은 압축 프로그램으로 다시 풀거나 방법 B를 씁니다.

### 2. 내 Private 저장소 만들기
1. GitHub에 로그인하고 오른쪽 위 **+** → **New repository**를 누릅니다(바로 가기: https://github.com/new).
2. **Repository name**에 영문·숫자·하이픈으로 이름을 넣습니다(예: `legal-team`). 한글은 쓸 수 없습니다.
3. 공개 범위에서 **Private**을 고릅니다. 일을 할수록 선례·오류노트·일정이 쌓이므로 Public으로 만들지 않습니다.
4. README, .gitignore, license는 **추가하지 않습니다**(모두 끔·None). 배포본에 이미 들어 있고, 추가하면 3단계의 첫 올리기가 거절됩니다.
5. **Create repository**를 누릅니다. 다음 화면의 HTTPS 주소(`https://github.com/<내 계정>/<저장소 이름>.git`)를 복사해 둡니다.

### 3. 내 저장소에 올리기
1. `법제업무팀` 폴더에서 Git Bash나 터미널을 엽니다.
   - Windows: 탐색기에서 `법제업무팀` 폴더를 열고 빈 곳을 오른쪽 클릭 → **Open Git Bash here**(Windows 11은 **추가 옵션 표시** 안에 있습니다)
   - macOS: 터미널에 `cd `(cd와 빈칸 한 칸)를 친 뒤 `법제업무팀` 폴더를 터미널 창에 끌어다 놓고 Enter
2. 아래 명령을 차례로 붙여 넣습니다. 이름·메일과 마지막 주소는 내 것으로 바꿉니다.
   ```bash
   # once per PC: who makes the commits
   git config --global user.name "이름"
   git config --global user.email "GitHub에 등록한 메일 주소"
   git config --global core.quotepath false      # show Korean file names as-is

   # make this folder a repository and upload it
   git init -b main
   git add .
   git commit -m "법제업무팀 배포본으로 시작"
   git remote add origin https://github.com/<내 계정>/<저장소 이름>.git
   git push -u origin main
   ```
3. 처음 `git push`를 하면 GitHub 로그인을 묻습니다. 한 번 로그인하면 그 PC가 기억합니다.

   | PC | 뜨는 것 | 할 일 |
   |---|---|---|
   | Windows | **Connect to GitHub** 창 | **Sign in with your browser** → 브라우저에서 승인(**Authorize**) |
   | macOS | 터미널의 `Username`·`Password` 질문 | Username에는 GitHub 아이디, Password에는 GitHub 비밀번호가 아니라 아래에서 만든 **토큰**을 붙여 넣습니다. 입력해도 화면에 보이지 않는 것이 정상입니다 |

   - macOS 토큰 만들기: GitHub 오른쪽 위 프로필 사진 → **Settings** → 왼쪽 맨 아래 **Developer settings** → **Personal access tokens** → **Fine-grained tokens** → **Generate new token**. **Repository access**는 **Only select repositories**로 2단계 저장소만 고르고, 권한(Permissions)에서 **Contents**를 **Read and write**로 한 뒤 **Generate token**을 누릅니다. 토큰은 그 화면에서만 보이니 바로 복사합니다. 토큰의 만료일이 지나면 새로 만들어 같은 방법으로 넣습니다.
   - macOS에 Homebrew가 있으면 토큰 대신 `brew install gh` → `gh auth login`(GitHub.com → HTTPS → Git 인증 **Yes** → **Login with a web browser**)으로 브라우저 로그인을 해도 됩니다.
4. 브라우저에서 내 저장소 페이지를 새로 고칩니다. 파일 목록에 `.claude` 폴더와 `README.md`가 보이고 저장소 이름 옆에 **Private** 표시가 있으면 끝입니다.

- 명령이 낯설면 Claude에게 맡겨도 됩니다. `법제업무팀` 폴더에서 `claude`를 실행하고 "이 폴더를 git 저장소로 만들어 `https://github.com/<내 계정>/<저장소 이름>.git`의 main으로 올려 줘"라고 요청합니다. Claude가 명령마다 허락을 구하고, 로그인 창은 위와 같이 직접 처리합니다.
- GitHub 웹 화면의 파일 끌어다 놓기(**uploading an existing file**)로는 올리지 않습니다. 한 번에 100개까지만 올라가 배포본(파일 120여 개)이 다 들어가지 않고, 숨김 폴더가 빠지기 쉬우며, 이후 매일 동기화도 Git으로 하기 때문입니다.
- 둘째 PC부터는 올리지 않고 받아서 씁니다: `git clone https://github.com/<내 계정>/<저장소 이름>.git 법제업무팀`. 로그인 창은 위와 같습니다.

### 4. Claude와 GitHub 연결
어디서 Claude를 쓰느냐에 따라 할 일이 다릅니다.

| 쓰는 곳 | GitHub 연결 | 여는 법 |
|---|---|---|
| PC의 Claude Code(터미널) | 따로 하지 않습니다. 3단계에서 PC에 한 Git 로그인을 그대로 씁니다 | `법제업무팀` 폴더에서 `claude` 실행 |
| PC의 Claude 데스크톱 앱 | 따로 하지 않습니다 | **Code** 탭 → 입력창 아래 환경 선택에서 **Local**(내 컴퓨터) → 폴더 선택에서 `법제업무팀` |
| 클라우드: [claude.ai/code](https://claude.ai/code), 모바일 앱 **Code** 탭, 데스크톱 앱의 **Cloud** | **필요합니다**: GitHub 계정 연결 + Claude GitHub App 설치 | 아래 '클라우드에서 쓰기' |

**PC에서 처음 열기**
```bash
cd ~/법제업무팀      # the folder from step 1
claude              # the first run opens the browser to sign in to claude.ai
```
열리면 "구성 점검해 줘"라고 요청합니다. 마지막 줄이 `결과: 오류 0건`이면 됩니다.

**클라우드에서 쓰기 (claude.ai/code, 처음 한 번)**
1. https://claude.ai/code 에 들어가 claude.ai 계정으로 로그인합니다.
2. GitHub 연결 안내가 나오면 따라가 GitHub 승인 화면에서 **Authorize**를 누릅니다. 끝나면 claude.ai/code로 돌아옵니다. 나중에 다시 연결할 때는 https://claude.ai/connect-github 를 엽니다.
3. **Claude GitHub App을 내 저장소에 설치합니다.** Private 저장소는 이 앱이 설치된 것만 클라우드 세션에서 열립니다.
   1. https://github.com/apps/claude/installations/new 를 엽니다(2의 연결 도중 설치 화면이 나오면 거기서 해도 됩니다).
   2. 내 GitHub 계정을 고릅니다.
   3. **Repository access**에서 **Only select repositories**를 고르고 2단계 저장소를 선택합니다. Claude가 이 저장소만 열도록 **All repositories**는 고르지 않기를 권합니다.
   4. **Install**을 누릅니다.
4. 환경: Pro·Max·Ultra는 **Default** 환경이 저절로 생깁니다. Team·Enterprise는 **Create your first cloud environment** 화면이 나오면 값을 그대로 두고 **Create & finish**를 누릅니다.
5. claude.ai/code 입력창 아래의 저장소 선택에서 내 저장소를 고르고 "구성 점검해 줘"를 보냅니다.

클라우드에서 알아 둘 것:
- 클라우드 세션이 고친 내용은 세션 브랜치(`claude/…`, `ccr-…` 등)에 올라가고 main에는 바로 들어가지 않습니다. 다른 PC에서 받으려면 GitHub에서 PR을 만들어 main에 병합합니다.
- 클라우드에는 kordoc·검토보고서 플러그인·`.env`가 없습니다. HWP는 PDF로 바꿔 넣습니다.
- 국회 사이트가 막히면 세션 제목 줄의 환경 메뉴 → 편집 → 네트워크 접근에서 허용 도메인에 넣습니다.
- 자세한 내용은 사용설명서의 [Claude와 GitHub 연결](vanilla/사용설명서.md#claude와-github-연결)과 [동기화와 클라우드 세션](vanilla/사용설명서.md#동기화와-클라우드-세션)에 있습니다.

연결이 안 될 때:
- 저장소 목록에 내 저장소가 없으면: GitHub 프로필 사진 → **Settings** → **Applications** → **Installed GitHub Apps** → **Claude** 옆 **Configure** → **Repository access**에 내 저장소가 들어 있는지 봅니다.
- Team·Enterprise 플랜에서 GitHub 로그인 버튼 대신 "GitHub access is required…"가 보이면, 조직 Owner가 claude.ai 조직 설정의 Connectors에서 GitHub 커넥터를 켜야 합니다.
- GitHub CLI(`gh`)를 이미 쓰고 있으면 Claude Code에서 `/web-setup`을 실행해 연결해도 됩니다(Team·Enterprise는 Owner가 Quick setup을 켠 경우).
- claude.ai 일반 채팅의 GitHub 파일 첨부로는 이 팀이 돌지 않습니다. 팀 설정(`.claude/`)은 Claude Code(터미널, 데스크톱 앱 Code 탭, claude.ai/code)에서 저장소를 열 때 읽힙니다.
- 화면 이름은 2026. 11. 6.에 [Claude Code 문서](https://code.claude.com/docs/en/web-quickstart)로 확인한 것입니다. 바뀌었으면 그 문서를 따릅니다.

### 5. 그다음 설정
여기부터는 내 저장소의 `README.md`(이 저장소의 `vanilla/README.md`와 같은 파일)와 사용설명서가 안내합니다.

| 할 일 | 안내 |
|---|---|
| 도구 설치(kordoc, 검토보고서 플러그인) — PC마다 한 번 | [README '처음 쓰는 PC' 4](vanilla/README.md#처음-쓰는-pc), [설치키트 README](vanilla/도구/설치키트/README.md) |
| Python 3.8 이상 설치(구성점검·대시보드·조문 대조에 씀) | [README 'PC마다 확인할 것'](vanilla/README.md#pc마다-확인할-것) |
| 구성 점검 — "구성 점검해 줘" → 오류 0건 | [README '처음 쓰는 PC' 6](vanilla/README.md#처음-쓰는-pc) |
| 국가법령정보 MCP 연결(법령 원문 확인) | [사용설명서 '국가법령정보 MCP 연결'](vanilla/사용설명서.md#국가법령정보-mcp-연결) |
| 메일·Google Calendar 커넥터, 문서 스킬, 열린국회정보 API 키 | [사용설명서 '연결할 것 확인'](vanilla/사용설명서.md#연결할-것-확인-pc세션마다) |
| 기관·부서 등 운영 설정 채우기 | [사용설명서 '처음 채울 것'](vanilla/사용설명서.md#처음-채울-것) |
| 가상 예제로 한 건 끝까지 실습(60~90분) | [튜토리얼](vanilla/튜토리얼.md) |
| 매일 동기화(작업 전후 한 번씩) | [README '매일 동기화'](vanilla/README.md#매일-동기화) |
| 아침 뉴스 예약(선택) | [사용설명서 '아침 뉴스 예약'](vanilla/사용설명서.md#아침-뉴스-예약) |

### 자주 막히는 곳
| 증상 | 까닭과 해결 |
|---|---|
| `git push`가 `rejected … (fetch first)`로 거절됨 | 2단계에서 README 등을 추가해 저장소가 비어 있지 않은 것입니다. 아직 올린 것이 없으면 GitHub에서 그 저장소를 지우고(저장소 **Settings** → 맨 아래 **Delete this repository**) 같은 이름의 빈 저장소로 다시 만든 뒤 `git push -u origin main`을 다시 실행합니다 |
| `remote origin already exists` | 주소를 한 번 넣은 뒤 다시 넣은 것입니다. `git remote set-url origin https://github.com/<내 계정>/<저장소 이름>.git`으로 바꿉니다 |
| `Repository not found` 또는 `403` | 주소 오타이거나, 그 저장소가 없는 다른 계정으로 로그인한 것입니다. 저장된 로그인을 지우고(Windows **자격 증명 관리자** → **Windows 자격 증명**의 `git:https://github.com`, macOS **키체인 접근**의 `github.com`) 다시 `git push` 합니다 |
| macOS에서 비밀번호가 거절됨 | GitHub 비밀번호 대신 3단계의 토큰을 넣습니다 |
| `Author identity unknown` | 3단계의 `git config --global user.name`·`user.email`을 먼저 실행합니다 |
| GitHub에 `.claude` 폴더가 없음 | 숨김 항목이 빠진 채 복사된 것입니다. 숨김 항목을 보이게 한 뒤(1단계 '꼭 지킬 것') `vanilla`의 `.claude` 폴더와 `.gitignore`·`.gitattributes`를 `법제업무팀`에 복사하고 `git add . && git commit -m "숨김 파일 추가" && git push`를 실행합니다 |
| 동기화가 "이 폴더가 git 저장소의 맨 위가 아닙니다"로 멈춤 | `release/vanilla` 안에서 돌린 것입니다. 1단계대로 밖으로 복사한 `법제업무팀`에서 돌립니다 |
| claude.ai/code 저장소 목록에 내 저장소가 없음 | Claude GitHub App이 그 저장소에 설치되지 않은 것입니다. 4단계 '연결이 안 될 때'를 봅니다 |

## 정리 원칙
- 의안 원문, 선례 원문, 작성자·의원 실명, 계정·세션 정보, 운영 기록은 넣지 않습니다.
- 배포본이 쓴 안내 문서·서식·예제의 예시는 모두 가상 자료(○○법, 홍길동, `XXXXXXX`)로 씁니다.
- 예외: 제3자 구성요소인 검토보고서 플러그인(`vanilla/도구/설치키트/payload/AI-Assembly/`)은 `vanilla/제3자고지.md`에 적은 곳만 고치고 원본대로 두었습니다. 그래서 그 착안점 파일의 검토사례 색인에는 원저작자가 「법률안검토 표준교재」의 사례에서 옮긴 실제 법률안의 이름·대표발의 의원 이름·의안번호가, README와 LICENSE에는 원저작자의 저작권 표시·연락처가 들어 있습니다.
- 예외: 열린국회정보 점검 도구(`vanilla/도구/국회API점검.py`)의 기본 의안번호는 접속 확인용 공개 의안입니다.
- 제3자 구성요소의 라이선스는 각 배포본의 `제3자고지.md`에 적습니다.

## 라이선스
각 배포본 폴더의 `LICENSE`를 따릅니다. `vanilla/`는 내부 이용 허락입니다. 배포본을 받은 사람과 그 소속 기관은 자기 업무에 쓰려고 복제·수정해 비공개 저장소에 두고 쓸 수 있고, 기관 밖 제3자에게 넘기거나 공개하려면 배포자의 허락을 미리 받습니다. 제3자 구성요소는 각자의 라이선스를 따릅니다(`vanilla/제3자고지.md`).
