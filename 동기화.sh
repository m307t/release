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
# repository (for example a copy of it placed inside another project), git would commit and push
# that outer repository instead, so stop before touching anything.
TOP="$(git rev-parse --show-toplevel 2>/dev/null || true)"
TOPERR="$(git rev-parse --show-toplevel 2>&1 >/dev/null || true)"
if [ -z "$TOP" ] && case "$TOPERR" in *"dubious ownership"*) true ;; *) false ;; esac; then
  printf '%s\n' "$TOPERR"
  stop "git이 이 폴더를 다른 사용자의 저장소로 보고 막았습니다(폴더 소유자가 다름). 아무것도 올리거나 받지 않았습니다." \
       "내 폴더가 맞는지 확인한 뒤 위에 나온 git config --global --add safe.directory 명령을 실행하고 다시 실행하세요."
fi
if [ "$TOP" != "$(pwd -P)" ]; then
  # Git for Windows prints C:/... where Git Bash prints /c/..., so ask git for the prefix as well.
  PREFIX="$(git rev-parse --show-prefix 2>/dev/null || echo "?")"
  if [ -z "$TOP" ] || [ -n "$PREFIX" ]; then
    stop "이 폴더가 git 저장소의 맨 위가 아닙니다(다른 저장소 안에 든 폴더이거나 git 저장소가 아님). 아무것도 올리거나 받지 않았습니다." \
         "README '처음 쓰는 PC'대로 받은 내 저장소 폴더에서 다시 실행하세요."
  fi
fi

# Never sync with the public distribution repository. A folder cloned straight from it keeps pointing
# there until it is linked to your own private repository (README '처음 쓰는 PC'). Check the remotes
# this branch pulls from and pushes to, before anything is committed.
# Keep this address the same as 배포판.md and 동기화.cmd (구성점검 compares them).
RELEASE_REPO='m307t/release'
BRANCH_NOW="$(git symbolic-ref -q --short HEAD || true)"
PULL_REMOTE="$(git config --get "branch.$BRANCH_NOW.remote" 2>/dev/null || echo origin)"
PUSH_REMOTE="$(git config --get "branch.$BRANCH_NOW.pushRemote" 2>/dev/null || git config --get remote.pushDefault 2>/dev/null || echo "$PULL_REMOTE")"
for r in "$PULL_REMOTE" "$PUSH_REMOTE"; do
  # The address as written in the config and as git uses it (url.*.insteadOf rules can rewrite it).
  for url in $(git config --get-all "remote.$r.url" 2>/dev/null; git config --get-all "remote.$r.pushurl" 2>/dev/null;
               git remote get-url "$r" 2>/dev/null; git remote get-url --push "$r" 2>/dev/null); do
    if printf '%s\n' "$url" | grep -Eiq "github\.com[:/]+${RELEASE_REPO}(\.git)?/*\$"; then
      stop "이 폴더는 공개 배포 저장소($RELEASE_REPO)에 연결되어 있어 동기화하지 않습니다. 아무것도 올리거나 받지 않았습니다." \
           "README '처음 쓰는 PC'대로 내 비공개 저장소를 만들어 연결한 뒤 다시 실행하세요. 연습 폴더는 동기화하지 않습니다."
    fi
  done
done
# A folder with no remote to upload to (a practice folder) is not synced: stop before committing.
if ! git remote get-url "$PUSH_REMOTE" >/dev/null 2>&1; then
  stop "이 폴더에는 올릴 곳(원격 $PUSH_REMOTE)이 없어 동기화하지 않습니다. 아무것도 올리거나 받지 않았습니다." \
       "연습 폴더라면 동기화하지 않습니다. 내 저장소라면 README '처음 쓰는 PC'의 내 저장소 만들기대로 연결한 뒤 다시 실행하세요."
fi
# A public upload target (a fork of the distribution, or a repository made Public) would publish the
# office's records. Ask GitHub whether it is public, without signing in (a private repository answers
# "not found"). When there is no answer (offline, rate limit, no curl, not GitHub) carry on.
public_on_github() {  # $1 = remote address
  local s
  s="$(printf '%s\n' "$1" | sed -nE 's#^.*github\.com[:/]+([^/[:space:]]+)/([^/[:space:]]+)/*$#\1/\2#p' | sed -E 's#\.git$##')"
  [ -n "$s" ] && command -v curl >/dev/null 2>&1 || return 1
  local body
  body="$(curl -fsS --max-time 10 -H 'Accept: application/vnd.github+json' "https://api.github.com/repos/$s" 2>/dev/null)" || return 1
  case "$body" in
    *'"private": false'*|*'"private":false'*) return 0 ;;
  esac
  return 1
}
for url in $(git config --get-all "remote.$PUSH_REMOTE.pushurl" 2>/dev/null || git config --get-all "remote.$PUSH_REMOTE.url" 2>/dev/null); do
  if public_on_github "$url"; then
    stop "올리는 곳(원격 $PUSH_REMOTE)이 누구나 볼 수 있는 공개(Public) 저장소입니다(배포 저장소의 포크이거나 Public으로 바꾼 저장소). 선례·오류노트·일정이 공개되므로 동기화하지 않습니다. 아무것도 올리거나 받지 않았습니다." \
         "GitHub에서 그 저장소를 Private으로 바꾸거나(포크는 바꿀 수 없습니다), README '처음 쓰는 PC' 3대로 Private 저장소를 새로 만들어 연결한 뒤 다시 실행하세요."
  fi
done

has_upstream() { git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; }
rebase_in_progress() {
  [ -d "$(git rev-parse --git-path rebase-merge)" ] || [ -d "$(git rev-parse --git-path rebase-apply)" ]
}

# 0. Do not start on top of an unfinished merge or rebase.
if rebase_in_progress || git rev-parse -q --verify MERGE_HEAD >/dev/null; then
  stop "끝나지 않은 병합·리베이스가 있습니다."
fi

# 1. Commit local changes first, after showing every file (new folders are listed file by file).
ASKED=0
if [ -n "$(git status --porcelain)" ]; then
  echo "올릴 변경:"
  git -c core.quotepath=false status --short --untracked-files=all
  if [ "$YES" -ne 1 ]; then
    if [ ! -t 0 ]; then
      stop "변경 목록을 확인받을 수 없는 환경입니다." "목록을 사람에게 보여 주고 승인받았으면 --yes를 붙여 다시 실행하세요."
    fi
    read -r -p "이 변경을 올릴까요? [y/N] " ans || ans=""
    case "$ans" in
      y|Y|yes|YES) ASKED=1 ;;
      *) echo "동기화 취소: 아무것도 올리거나 받지 않았습니다."; exit 0 ;;
    esac
  fi
  # core.safecrlf=false: no line-ending warning per file on Windows (they flood the first sync).
  git -c core.safecrlf=false add -A || stop "변경을 담지 못했습니다(git add)."
  git commit -q -m "sync: $(hostname) $(date '+%Y-%m-%d %H:%M')" || stop "커밋하지 못했습니다(git commit). Git 사용자 등록(README 처음 쓰는 PC 2)을 확인하세요."
fi

# 2. Pull others' changes. On a real conflict, undo the pull and stop.
#    Usually rebase on top of them. When a merge commit is waiting to be uploaded (a new release received
#    with 업데이트.sh), merge instead: a rebase would redo that merge and can conflict, and the merge must
#    stay as it is so the next update still finds where this office and the distribution meet.
if has_upstream; then
  if [ -n "$(git rev-list --merges '@{u}..HEAD' 2>/dev/null)" ]; then
    PULL_HOW="--no-rebase --ff --no-edit"
  else
    PULL_HOW="--rebase"
  fi
  # shellcheck disable=SC2086
  if ! git pull $PULL_HOW -q; then
    if rebase_in_progress; then
      git rebase --abort >/dev/null 2>&1 || true
      stop "다른 PC의 변경과 충돌했습니다. 아무것도 올리지 않았고, 내 변경은 이 PC에 커밋으로 남아 있습니다."
    fi
    if git rev-parse -q --verify MERGE_HEAD >/dev/null; then
      git merge --abort >/dev/null 2>&1 || true
      stop "다른 PC의 변경과 충돌했습니다. 아무것도 올리지 않았고, 내 변경은 이 PC에 커밋으로 남아 있습니다."
    fi
    stop "받기(pull)에 실패했습니다. 네트워크·GitHub 로그인·원격 브랜치를 확인하세요. 아무것도 올리지 않았습니다." \
         "원인을 모르겠으면 위 메시지를 Claude에게 보여 주세요."
  fi
fi

# 3. Never upload conflict markers.
MARKERS='^(<<<<<<<|>>>>>>>)( |$)'
if git grep -I -q -E "$MARKERS" -- .; then
  git --no-pager -c core.quotepath=false grep -I -n -E "$MARKERS" -- . | head -20 || true
  stop "충돌 표지(<<<<<<<)가 남은 파일이 있어 올리지 않았습니다."
fi

# 4. Upload. Commits that were already made (a received release, or commits Claude made after your
#    approval) are listed first, and asked about unless the changes were already approved in step 1.
confirm_commits() {
  if [ "$YES" -eq 1 ] || [ "$ASKED" -eq 1 ]; then return 0; fi
  if [ ! -t 0 ]; then
    stop "올릴 커밋을 확인받을 수 없는 환경입니다. 아무것도 올리지 않았습니다." "목록을 사람에게 보여 주고 승인받았으면 --yes를 붙여 다시 실행하세요."
  fi
  read -r -p "이 커밋을 올릴까요? [y/N] " ans || ans=""
  case "$ans" in
    y|Y|yes|YES) ;;
    *) echo "동기화 취소: 올리지 않았습니다(다른 PC의 변경이 있었으면 받아 두었습니다)."; exit 0 ;;
  esac
}
if has_upstream; then
  if [ -n "$(git log --oneline '@{u}..HEAD')" ]; then
    echo "올릴 커밋:"
    git -c core.quotepath=false log --oneline --stat '@{u}..HEAD' | head -40 || true
    confirm_commits
  fi
  git push -q || stop "올리기(push)에 실패했습니다." "원인을 모르겠으면 위 메시지를 Claude에게 보여 주세요."
else
  echo "올릴 커밋(이 브랜치를 처음 올림, 최근 10개):"
  git -c core.quotepath=false log --oneline -10 || true
  confirm_commits
  git push -q -u "$PUSH_REMOTE" HEAD || stop "올리기(push)에 실패했습니다." "원인을 모르겠으면 위 메시지를 Claude에게 보여 주세요."
fi
echo "동기화 완료"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$BRANCH" != "main" ]; then
  echo "참고: 지금 브랜치($BRANCH)는 main이 아닙니다. 다른 PC에서 받으려면 이 브랜치를 main에 병합해야 합니다."
fi
