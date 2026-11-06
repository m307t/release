#!/usr/bin/env bash
# Sync this folder with the private GitHub repository (macOS / Linux / Git Bash on Windows).
#   ./동기화.sh         show the changes and ask before uploading
#   ./동기화.sh --yes   upload without asking (when Claude runs it after showing you the list)
# Order: commit local changes -> pull others' changes on top -> check for conflict markers -> push.
# A real conflict stops the script before anything is uploaded.
set -euo pipefail
cd "$(dirname "$0")"

HINT="Claude에게 \"동기화 충돌 해결해 줘\"라고 요청하세요."
stop() {
  echo ""
  echo "동기화 중단: $1"
  echo "${2:-$HINT}"
  exit 1
}

YES=0
if [ "${1:-}" = "--yes" ]; then YES=1; fi

# Run only at the top of this folder's own git repository. When this folder sits inside another
# repository (for example vanilla/ inside the distribution repository), git would commit and push
# that outer repository instead, so stop before touching anything.
TOP="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ "$TOP" != "$(pwd -P)" ]; then
  # Git for Windows prints C:/... where Git Bash prints /c/..., so ask git for the prefix as well.
  PREFIX="$(git rev-parse --show-prefix 2>/dev/null || echo "?")"
  if [ -z "$TOP" ] || [ -n "$PREFIX" ]; then
    stop "이 폴더가 git 저장소의 맨 위가 아닙니다(배포 저장소 안의 vanilla 폴더이거나 git 저장소가 아님). 아무것도 올리거나 받지 않았습니다." \
         "이 폴더를 밖으로 복사해 자기 저장소로 만든 뒤(README '처음 쓰는 PC' 3) 그 폴더에서 다시 실행하세요."
  fi
fi

has_upstream() { git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; }
rebase_in_progress() {
  [ -d "$(git rev-parse --git-path rebase-merge)" ] || [ -d "$(git rev-parse --git-path rebase-apply)" ]
}

# 0. Do not start on top of an unfinished merge or rebase.
if rebase_in_progress || git rev-parse -q --verify MERGE_HEAD >/dev/null; then
  stop "끝나지 않은 병합·리베이스가 있습니다."
fi

# 1. Commit local changes first, after showing every file (new folders are listed file by file).
if [ -n "$(git status --porcelain)" ]; then
  echo "올릴 변경:"
  git -c core.quotepath=false status --short --untracked-files=all
  if [ "$YES" -ne 1 ]; then
    if [ ! -t 0 ]; then
      stop "변경 목록을 확인받을 수 없는 환경입니다." "목록을 사람에게 보여 주고 승인받았으면 --yes를 붙여 다시 실행하세요."
    fi
    read -r -p "이 변경을 올릴까요? [y/N] " ans || ans=""
    case "$ans" in
      y|Y|yes|YES) ;;
      *) echo "동기화 취소: 아무것도 올리거나 받지 않았습니다."; exit 0 ;;
    esac
  fi
  git add -A || stop "변경을 담지 못했습니다(git add)."
  git commit -q -m "sync: $(hostname) $(date '+%Y-%m-%d %H:%M')" || stop "커밋하지 못했습니다(git commit). Git 사용자 등록(README 처음 쓰는 PC 2)을 확인하세요."
fi

# 2. Pull others' changes on top. On a real conflict, undo the pull and stop.
if has_upstream; then
  if ! git pull --rebase -q; then
    if rebase_in_progress; then
      git rebase --abort >/dev/null 2>&1 || true
      stop "다른 PC의 변경과 충돌했습니다. 아무것도 올리지 않았고, 내 변경은 이 PC에 커밋으로 남아 있습니다."
    fi
    stop "받기(pull)에 실패했습니다. 네트워크·GitHub 로그인·원격 브랜치를 확인하세요. 아무것도 올리지 않았습니다." \
         "원인을 모르겠으면 위 메시지를 Claude에게 보여 주세요."
  fi
fi

# 3. Never upload conflict markers.
MARKERS='^(<<<<<<<|>>>>>>>)( |$)'
if git grep -I -q -E "$MARKERS" -- .; then
  git -c core.quotepath=false grep -I -n -E "$MARKERS" -- . | head -20 || true
  stop "충돌 표지(<<<<<<<)가 남은 파일이 있어 올리지 않았습니다."
fi

# 4. Upload. Commits that were already made (for example by Claude after your approval) are listed first.
if has_upstream; then
  if [ -n "$(git log --oneline '@{u}..HEAD')" ]; then
    echo "올릴 커밋:"
    git -c core.quotepath=false log --oneline --stat '@{u}..HEAD' | head -40 || true
  fi
  git push -q || stop "올리기(push)에 실패했습니다." "원인을 모르겠으면 위 메시지를 Claude에게 보여 주세요."
else
  git push -q -u origin HEAD || stop "올리기(push)에 실패했습니다." "원인을 모르겠으면 위 메시지를 Claude에게 보여 주세요."
fi
echo "동기화 완료"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$BRANCH" != "main" ]; then
  echo "참고: 지금 브랜치($BRANCH)는 main이 아닙니다. 다른 PC에서 받으려면 이 브랜치를 main에 병합해야 합니다."
fi
