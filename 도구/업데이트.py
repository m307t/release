#!/usr/bin/env python3
"""Bring the newest release of the distribution into this office (your own private repository).

    python3 도구/업데이트.py                    show what comes in, ask, then merge
    python3 도구/업데이트.py --check            only show; changes nothing (safe in a practice copy)
    python3 도구/업데이트.py --yes              merge without asking (Claude, after showing you --check)
    python3 도구/업데이트.py --yes --leave-conflicts
                                                on a conflict, keep the merge open so Claude can resolve it
Windows: py -3 도구/업데이트.py (slashes work in cmd, PowerShell and Git Bash).
Wrappers: 업데이트.sh (macOS·Linux), 업데이트.cmd (Windows double-click).

How it works
- Reads the distribution repository from 배포판.md and fetches its main branch into
  refs/remotes/release/main. No remote is added and nothing is ever pushed there.
- A repository made with GitHub Import or by cloning shares history with the distribution, so git finds
  the common base itself and this is an ordinary merge.
- A repository started from a ZIP download or a template has no shared history. The first run finds the
  distribution commit the first commit of this repository came from (the one with the fewest differing
  files), records it as the base with a merge that keeps every file as it is, and then merges as usual.
- A repository made from the old layout (the office copied out of a vanilla/ folder, release 1.0) is
  merged with that release's vanilla/ folder as the base, and the result is recorded as a merge with the
  distribution. Later runs are ordinary merges.
- Files changed only by the distribution are taken, files changed only here are kept, and files changed
  on both sides are merged by git. If both sides changed the same lines the merge stops, nothing is
  changed (unless --leave-conflicts), and the conflicting files are listed.
- Only a folder linked to your own repository receives: a folder still linked to the public
  distribution repository, or with no remote at all (a practice folder), can only --check.
- It never pushes. Upload the result with the sync script (동기화.sh / 동기화.cmd) afterwards.

Exit code 0 = up to date, merged, or --check shown; 1 = stopped.
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INFO_NAME = "배포판.md"
REF = "refs/remotes/release/main"
# Same address as 배포판.md (used only when that file is missing). 구성점검 checks that they agree.
DEFAULT_URL = "https://github.com/m307t/release"
KIT = "도구/설치키트/"
LIST_LIMIT = 40

# A person at a terminal may be asked to sign in to their own repository; when Claude runs this there is
# nobody to answer, so prompts and sign-in windows are turned off (they would hang).
INTERACTIVE = sys.stdin.isatty()
BASE_ENV = dict(os.environ, GIT_MERGE_AUTOEDIT="no", LC_ALL="C", LANG="C")
QUIET_ENV = dict(BASE_ENV, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")


class Stop(Exception):
    """Stop with a message; nothing was changed unless the message says so."""


def git(*args, check=True, timeout=None, env=None):
    """Run git in the office folder and return stdout (text). Raise Stop on failure when check is set."""
    try:
        proc = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=str(ROOT),
                              env=env or QUIET_ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=timeout)
    except FileNotFoundError:
        raise Stop("git을 찾지 못했습니다. Git(Windows는 Git for Windows)을 설치한 뒤 다시 실행하세요.")
    except subprocess.TimeoutExpired:
        raise Stop("git " + args[0] + "이(가) 너무 오래 걸려 멈췄습니다. 네트워크를 확인하세요.")
    out = proc.stdout.decode("utf-8", "replace")
    err = proc.stderr.decode("utf-8", "replace")
    if check and proc.returncode != 0:
        raise Stop("git " + " ".join(args[:2]) + " 실패:\n" + (err or out).strip())
    return out if check else (proc.returncode, out, err)


def ok(*args):
    return git(*args, check=False)[0] == 0


def read_info(text):
    """The '| 항목 | 값 |' rows and the '판별 바뀐 것' rows of 배포판.md."""
    info, notes, section = {}, [], ""
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if len(cells) < 2 or set(cells[0]) <= set("-: "):
            continue
        if section == "판별 바뀐 것" and len(cells) >= 3:
            if cells[:2] != ["판", "배포일"]:  # the table head
                notes.append((cells[0], cells[1], cells[2]))
        elif not section and cells[:2] != ["항목", "값"]:
            info[cells[0]] = cells[1]
    return info, notes


def info_at(commit):
    """배포판.md as it was in a commit; None when the commit has no such file."""
    code, out, _ = git("show", commit + ":" + INFO_NAME, check=False)
    return read_info(out) if code == 0 else None


# 배포판.md started with release 1.1. A tree without it is the 1.0 release (the vanilla/ folder era).
BEFORE_INFO = ({"배포본": "vanilla", "판": "1.0 무렵(" + INFO_NAME + "가 없는 옛 판)"}, [("1.0", "", "")])


def slug(url):
    """owner/repo of a GitHub address (https or ssh), lower case; '' when it is not one."""
    m = re.search(r"github\.com[:/]+([^/\s]+)/([^/\s]+?)(?:\.git)?/*$", url.strip(), re.I)
    return (m.group(1) + "/" + m.group(2)).lower() if m else ""


def version_label(info):
    if not info.get("판"):
        return "알 수 없음"
    return " ".join(x for x in (info.get("배포본", ""), info["판"]) if x) + (
        " (" + info["배포일"] + ")" if info.get("배포일") else "")


def same_dir(a, b):
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def check_place():
    """Run only at the top of this folder's own repository, on a branch, with a first commit."""
    code, top, err = git("rev-parse", "--show-toplevel", check=False)
    if code != 0:
        if "dubious ownership" in err:
            raise Stop("git이 이 폴더를 다른 사용자의 저장소로 보고 막았습니다(폴더 소유자가 다름: 다른 계정·관리자 권한으로 "
                       "만든 폴더, 외장·네트워크 드라이브 등). 내 폴더가 맞는지 확인한 뒤 git이 알려 준 "
                       "'git config --global --add safe.directory …' 명령을 실행하고 다시 실행하세요. "
                       "아무것도 바꾸지 않았습니다.\n" + err.strip())
        raise Stop("이 폴더는 git 저장소가 아닙니다. README '처음 쓰는 PC'대로 내 저장소를 만든 뒤 다시 실행하세요.\n"
                   + err.strip())
    if not same_dir(top.strip(), ROOT) and git("rev-parse", "--show-prefix").strip():
        raise Stop("이 폴더가 git 저장소의 맨 위가 아닙니다(다른 저장소 안에 든 폴더). 아무것도 바꾸지 않았습니다.")
    if not ok("rev-parse", "-q", "--verify", "HEAD"):
        raise Stop("아직 첫 커밋이 없습니다. README '처음 쓰는 PC'대로 저장소를 만들어 첫 동기화를 한 뒤 다시 실행하세요.")
    branch = git("symbolic-ref", "-q", "--short", "HEAD", check=False)
    if branch[0] != 0:
        raise Stop("지금 브랜치가 없는 상태(detached HEAD)입니다. Claude에게 이 메시지를 보여 주세요.")
    return branch[1].strip()


def unfinished():
    if ok("rev-parse", "-q", "--verify", "MERGE_HEAD"):
        return True
    for name in ("rebase-merge", "rebase-apply"):
        if (ROOT / git("rev-parse", "--git-path", name).strip()).is_dir():
            return True
    return False


def remotes_of(branch):
    """(pull remote, push remote) of this branch, as git pull and git push pick them."""
    def cfg(key):
        code, out, _ = git("config", "--get", key, check=False)
        return out.strip() if code == 0 else ""
    pull = cfg("branch." + branch + ".remote") or "origin"
    push = cfg("branch." + branch + ".pushRemote") or cfg("remote.pushDefault") or pull
    return pull, push


def points_to_release(remote, release_slug):
    """The remote's address as written in the config, and as git uses it (after url.*.insteadOf)."""
    for args in (("config", "--get-all", "remote." + remote + ".url"),
                 ("config", "--get-all", "remote." + remote + ".pushurl"),
                 ("remote", "get-url", remote), ("remote", "get-url", "--push", remote)):
        code, out, _ = git(*args, check=False)
        if code == 0 and any(slug(u) == release_slug for u in out.split()):
            return True
    return False


def root_commit():
    """The oldest commit with no parent (the first commit of this repository)."""
    roots = git("rev-list", "--max-parents=0", "HEAD").split()
    if len(roots) == 1:
        return roots[0]
    return min(roots, key=lambda c: int(git("log", "-1", "--format=%ct", c).strip() or 0))


def tree_diff(a, b):
    """Paths whose content differs between two trees (mode-only changes do not count)."""
    paths = []
    for line in git("diff-tree", "-r", "--no-renames", a, b).splitlines():
        meta, _, path = line.partition("\t")
        fields = meta.split()
        if len(fields) >= 4 and fields[2] != fields[3]:
            paths.append(path)
    return paths


def find_base():
    """For a repository without shared history: the distribution commit its first commit came from.
    Returns (commit, tree spec, differing paths, layout)."""
    first = root_commit() + "^{tree}"
    best = None
    for commit in git("rev-list", REF).split():  # newest first, so ties keep the newer commit
        for spec, layout in ((commit + "^{tree}", "맨 위"), (commit + ":vanilla", "vanilla/ 폴더")):
            if not ok("rev-parse", "-q", "--verify", spec):
                continue
            diff = tree_diff(first, spec)
            if best is None or len(diff) < len(best[2]):
                best = (commit, spec, diff, layout)
    if best is None:
        raise Stop("배포 저장소에서 기준이 될 기록을 찾지 못했습니다. 아무것도 바꾸지 않았습니다.")
    return best


def write_git_file(name, text):
    path = Path(git("rev-parse", "--git-path", name).strip())
    if not path.is_absolute():
        path = ROOT / path
    path.write_text(text, encoding="utf-8")


def merge_with_base(base_spec, message, start, leave_conflicts):
    """Merge REF into HEAD taking the tree base_spec as the common base; for the old vanilla/ layout,
    where no distribution commit has the same shape as this office. The result is a merge commit with
    parents HEAD and REF, so later runs are ordinary merges. Returns the conflicting paths ([] = merged).
    First tries git merge-tree --write-tree (git 2.38+, honours .gitattributes such as merge=union); on
    a conflict or an older git it merges in the index with read-tree and merge-one-file."""
    def commit(tree, *parents):
        args = ["commit-tree", tree, "-m", message]
        for parent in parents:
            args += ["-p", parent]
        return git(*args).strip()
    base_tree = git("rev-parse", base_spec).strip()
    base = commit(base_tree)
    ours = commit(git("rev-parse", "HEAD^{tree}").strip(), base)
    theirs = commit(git("rev-parse", REF + "^{tree}").strip(), base)
    code, out, _ = git("merge-tree", "--write-tree", ours, theirs, check=False)
    if code == 0 and out.split():
        merged = commit(out.split()[0], "HEAD", REF)
        if ok("merge", "--ff-only", "-q", merged):
            return []
    # Three-way merge in the index with the explicit base, as git merge does but without rename handling
    # (the two trees have the same shape here).
    code, out, err = git("read-tree", "-m", "-u", base_tree, "HEAD", REF, check=False)
    if code != 0:
        git("reset", "-q", "--hard", start, check=False)
        raise Stop("배포본을 합치지 못했습니다. 아무것도 바꾸지 않았습니다.\n" + (err or out).strip())
    git("merge-index", "-o", "-q", "git-merge-one-file", "-a", check=False)
    conflicts = [c for c in git("diff", "--name-only", "--diff-filter=U").split("\n") if c]
    conflicts = [c for c in conflicts if not union_merged(c)]
    write_git_file("MERGE_HEAD", git("rev-parse", REF).strip() + "\n")
    write_git_file("MERGE_MSG", message + "\n")
    if not conflicts:
        git("commit", "-q", "--no-edit")
        return []
    if not leave_conflicts:
        git("reset", "-q", "--hard", start, check=False)  # the tree was clean before (checked), so this only undoes the merge
    return conflicts


def union_merged(path):
    """For a conflicted file marked merge=union in .gitattributes (add-only tables such as 변경이력.md),
    keep the lines of both sides as git merge does, and stage it. True when done."""
    if not git("check-attr", "merge", "--", path).strip().endswith(": union"):
        return False
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        files = []
        for stage in ("2", "1", "3"):  # ours, base, theirs
            code, out, _ = git("show", ":" + stage + ":" + path, check=False)
            name = os.path.join(tmp, stage)
            with open(name, "w", encoding="utf-8", newline="") as f:
                f.write(out if code == 0 else "")
            files.append(name)
        code, merged, _ = git("merge-file", "--union", "-p", *files, check=False)
    if code < 0:
        return False
    (ROOT / path).write_text(merged, encoding="utf-8", newline="")
    git("add", "--", path)
    return True


def describe(commit):
    return git("log", "-1", "--format=%h %cd %s", "--date=short", commit).strip()


def show_list(title, items):
    print(title)
    for item in items[:LIST_LIMIT]:
        print("  " + item)
    if len(items) > LIST_LIMIT:
        print("  … 외 " + str(len(items) - LIST_LIMIT) + "개")


def changed(base, tip):
    """'M path' style lines for what changed from base to tip (renames shown as such)."""
    lines = []
    for line in git("diff", "--name-status", "-M", base, tip).splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            lines.append(parts[0][0] + " " + parts[1] + " → " + parts[2])
        elif len(parts) == 2:
            lines.append(parts[0][0] + " " + parts[1])
    return lines


def fix_exec_bits(branch):
    """Give back the executable bit the distribution has (a ZIP unpacked on Windows loses it, and the
    merge would keep that). Makes one small commit when anything changed."""
    def modes(ref):
        result = {}
        for line in git("ls-tree", "-r", ref).splitlines():
            meta, _, path = line.partition("\t")
            result[path] = meta.split()[0]
        return result
    release, here = modes(REF), modes("HEAD")
    lost = sorted(p for p, m in release.items() if m == "100755" and here.get(p) == "100644")
    if not lost:
        return
    git("update-index", "--chmod=+x", "--", *lost)
    # Where git follows the file mode (macOS, Linux) the files themselves must be executable too, or the
    # next sync would record the old mode again.
    if git("config", "--bool", "core.filemode", check=False)[1].strip() != "false":
        for path in lost:
            full = ROOT / path
            if full.is_file():
                full.chmod(full.stat().st_mode | 0o111)
    git("commit", "-q", "-m", "실행 권한을 배포본과 같게 바로잡음: " + ", ".join(lost))
    print("실행 권한을 배포본과 같게 바로잡았습니다: " + ", ".join(lost))


def kit_notice(paths):
    if any(p.startswith(KIT) for p in paths):
        print("")
        print("참고: 설치키트(" + KIT + ")가 바뀌었습니다. 받은 뒤 PC마다 설치키트를 다시 실행합니다"
              "(Windows는 도구\\설치키트\\install-windows.bat, macOS·Linux는 bash 도구/설치키트/install.sh. "
              "다른 PC는 동기화로 받은 뒤).")


def run_checker():
    checker = ROOT / "도구" / "구성점검.py"
    if not checker.is_file():
        return
    proc = subprocess.run([sys.executable, str(checker)], cwd=str(ROOT), stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    lines = proc.stdout.decode("utf-8", "replace").strip().splitlines()
    print("")
    print("구성점검:")
    for line in lines[-12:]:
        print("  " + line)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    parser = argparse.ArgumentParser(description="배포본의 새 판을 이 사무실에 받습니다.")
    parser.add_argument("--check", action="store_true", help="보여 주기만 하고 아무것도 바꾸지 않습니다")
    parser.add_argument("--yes", action="store_true", help="묻지 않고 받습니다(--check 결과를 승인받은 뒤)")
    parser.add_argument("--leave-conflicts", action="store_true", help="충돌이 나면 병합을 열어 둡니다(Claude가 풀 때)")
    args = parser.parse_args()

    branch = check_place()
    if git("rev-parse", "--is-shallow-repository").strip() == "true":
        raise Stop("이 저장소는 기록 일부만 받은 얕은 복제(shallow clone)라 배포본과 이어진 곳을 찾을 수 없습니다. "
                   "PC에서 전체를 받은 내 저장소(README '처음 쓰는 PC')에서 실행하거나, git fetch --unshallow로 "
                   "기록을 모두 받은 뒤 다시 실행하세요. 아무것도 바꾸지 않았습니다.")
    if unfinished():
        raise Stop("끝나지 않은 병합·리베이스가 있습니다. 아무것도 바꾸지 않았습니다. Claude에게 이 메시지를 보여 주세요.")
    has_info = (ROOT / INFO_NAME).is_file()
    mine, mine_notes = read_info((ROOT / INFO_NAME).read_text(encoding="utf-8", errors="replace")) \
        if has_info else BEFORE_INFO
    url = mine.get("배포 저장소") or DEFAULT_URL
    release_slug = slug(url)
    if not release_slug:
        raise Stop(INFO_NAME + "의 배포 저장소 주소를 읽지 못했습니다: " + url)

    pull_remote, push_remote = remotes_of(branch)
    on_release = any(points_to_release(r, release_slug) for r in {pull_remote, push_remote})
    no_remote = not ok("remote", "get-url", push_remote)
    practice = on_release or no_remote
    if practice and not args.check:
        if on_release:
            raise Stop("이 폴더는 공개 배포 저장소에 연결되어 있어(연습 폴더이거나 아직 내 저장소에 연결하지 않은 폴더) "
                       "확인(--check)만 됩니다. 실제로 쓸 폴더면 README '처음 쓰는 PC' 3대로 내 비공개 저장소에 "
                       "연결한 뒤 다시 실행하세요. 아무것도 바꾸지 않았습니다.")
        raise Stop("이 폴더에는 내 저장소(원격 " + push_remote + ")가 연결되어 있지 않아 확인(--check)만 됩니다"
                   "(연습 폴더). 내 저장소라면 README '처음 쓰는 PC' 3대로 연결한 뒤 다시 실행하세요. "
                   "아무것도 바꾸지 않았습니다.")
    dirty = git("status", "--porcelain").strip()
    if dirty and not args.check:
        raise Stop("고친 채 올리지 않은 파일이 있습니다. 먼저 동기화(동기화.sh, Windows는 동기화.cmd)로 올린 뒤 "
                   "다시 실행하세요. 아무것도 바꾸지 않았습니다.")

    behind = 0
    if not practice and ok("rev-parse", "-q", "--verify", "@{u}"):
        # Changes another PC already uploaded should come in first (sync), so the merge starts from them.
        code, _, err = git("fetch", "--quiet", pull_remote, check=False, timeout=180,
                           env=BASE_ENV if INTERACTIVE else QUIET_ENV)
        if code != 0:
            if not args.check:
                raise Stop("내 저장소(" + pull_remote + ")의 최신 상태를 확인하지 못했습니다(인터넷 연결, GitHub "
                           "로그인). 동기화가 되는지 먼저 확인한 뒤 다시 실행하세요. 아무것도 바꾸지 않았습니다.\n"
                           + err.strip())
            print("참고: 내 저장소(" + pull_remote + ")의 최신 상태를 확인하지 못했습니다.")
        behind = int(git("rev-list", "--count", "HEAD..@{u}").strip() or 0)
        if behind and not args.check:
            raise Stop("다른 PC에서 올린 변경 " + str(behind) + "개를 아직 받지 않았습니다. 먼저 동기화로 받은 뒤 다시 "
                       "실행하세요. 아무것도 바꾸지 않았습니다.")

    print("배포 저장소: " + url)
    print("배포본을 받는 중…")
    code, _, err = git("fetch", "--quiet", "--no-tags", url, "+refs/heads/main:" + REF, check=False, timeout=600)
    if code != 0:
        raise Stop("배포 저장소에서 받지 못했습니다. 인터넷 연결과 " + INFO_NAME + "의 배포 저장소 주소를 확인하세요. "
                   "클라우드 세션은 네트워크 설정에 따라 받지 못할 수 있으니 PC에서 실행합니다. 아무것도 바꾸지 "
                   "않았습니다.\n" + err.strip())
    theirs, theirs_notes = info_at(REF) or ({}, [])
    print("지금 판: " + version_label(mine))
    print("배포 저장소의 최신판: " + version_label(theirs))

    if ok("merge-base", "--is-ancestor", REF, "HEAD"):
        print("")
        print("이미 최신판입니다. 받을 것이 없습니다.")
        if not args.check and not practice and ok("var", "GIT_COMMITTER_IDENT"):
            fix_exec_bits(branch)  # e.g. after a conflict was resolved by hand, finish() did not run
        return 0

    graft, layout = None, "맨 위"
    code, base, _ = git("merge-base", "HEAD", REF, check=False)
    if code == 0:
        base_tree = base_commit = base.strip()
    else:
        graft, base_tree, diff, layout = find_base()
        if graft == git("rev-parse", REF).strip() and layout == "맨 위":
            print("")
            print("이미 최신판입니다. 받을 것이 없습니다(이 저장소는 ZIP·템플릿으로 시작해, 배포본과 기록을 잇는 일은 "
                  "다음 새 판을 받을 때 합니다).")
            return 0
        print("")
        print("이 저장소는 배포본과 git 기록이 이어져 있지 않습니다(ZIP·템플릿이나 옛 폴더판으로 시작).")
        print("처음 받은 판으로 보이는 배포 기록: " + describe(graft) + " (" + layout + ")")
        if diff:
            show_list("그 판과 이 저장소의 첫 기록이 다른 파일 " + str(len(diff)) + "개 "
                      "(이 저장소에서 고친 것으로 보고 그대로 둡니다):", diff)
        else:
            print("그 판과 이 저장소의 첫 기록은 내용이 같습니다.")
        if layout == "맨 위":
            print("받을 때 이 기록을 기준으로 연결하는 커밋을 하나 더 만듭니다(파일은 바뀌지 않습니다).")
        else:
            print("옛 폴더판에서 시작한 저장소라, 그 판의 vanilla/ 폴더 내용을 기준으로 합칩니다.")
        base_commit = graft

    # Releases already in: those noted here and those the base already had.
    have = {n[0] for n in mine_notes} | {n[0] for n in (info_at(base_commit) or BEFORE_INFO)[1]}
    new_notes = [n for n in theirs_notes if n[0] not in have]
    if new_notes:
        print("")
        print("새로 들어오는 판:")
        for ver, day, text in new_notes:
            print("  - " + ver + " (" + day + "): " + text)
    incoming = changed(base_tree, REF)
    print("")
    show_list("배포본이 바꾼 파일 " + str(len(incoming)) + "개:", incoming)
    release_paths = set(tree_diff(base_tree, REF))
    both = sorted(release_paths & set(tree_diff(base_tree, "HEAD")))
    if both:
        show_list("이 저장소에서도 고친 파일 " + str(len(both)) + "개 "
                  + ("(커밋한 것만 견줬습니다. 올리지 않은 변경은 동기화한 뒤 다시 확인하세요) " if dirty else "")
                  + "(git이 합쳐 보고, 같은 줄을 양쪽에서 고쳤으면 멈추고 알려 드립니다):", both)
    kit_notice(release_paths)
    if practice:
        print("")
        if on_release:
            print("참고: 이 폴더는 공개 배포 저장소에 연결되어 있어(연습 폴더이거나 아직 내 저장소에 연결하지 않은 폴더) "
                  "확인만 됩니다.")
        else:
            print("참고: 이 폴더에는 내 저장소가 연결되어 있지 않아(연습 폴더) 확인만 됩니다.")
    elif dirty or behind:
        print("")
        print("참고: 고친 채 올리지 않은 파일이나 아직 받지 않은 다른 PC의 변경이 있어, 실제로 받기 전에 먼저 "
              "동기화해야 합니다.")
    if args.check:
        print("")
        print("확인만 했습니다. 아무것도 바꾸지 않았습니다.")
        return 0

    if not args.yes:
        if not INTERACTIVE:
            if os.environ.get("MSYSTEM"):
                raise Stop("Git Bash 창에서는 받을지 물어볼 수 없습니다. Windows는 업데이트.cmd를 더블클릭하거나, "
                           "--check로 확인한 뒤 --yes를 붙여 실행하세요. 아무것도 바꾸지 않았습니다.")
            raise Stop("확인받을 수 없는 환경입니다. --check 결과를 사람에게 보여 주고 승인받았으면 --yes를 붙여 "
                       "다시 실행하세요.")
        try:
            answer = input("새 판을 받을까요? [y/N] ").strip().lower()
        except EOFError:
            answer = ""
        if answer not in ("y", "yes"):
            print("업데이트 취소: 아무것도 바꾸지 않았습니다.")
            return 0

    if not ok("var", "GIT_COMMITTER_IDENT"):
        raise Stop("Git 사용자 등록이 없어 병합 기록을 만들 수 없습니다. README '처음 쓰는 PC' 2를 한 뒤 다시 실행하세요. "
                   "아무것도 바꾸지 않았습니다.")
    start = git("rev-parse", "HEAD").strip()
    message = "배포판 업데이트: " + version_label(mine) + " → " + version_label(theirs)

    if graft and layout != "맨 위":
        conflicts = merge_with_base(base_tree, message, start, args.leave_conflicts)
        if not conflicts:
            return finish(theirs, branch, release_paths)
        return report_conflicts(conflicts, args.leave_conflicts, start, graft=False)

    if graft:
        code, out, err = git("merge", "-s", "ours", "--allow-unrelated-histories", "--no-edit", "-q",
                             "-m", "배포판 기준 연결: " + describe(graft), graft, check=False)
        if code != 0:
            git("merge", "--abort", check=False)
            git("reset", "-q", "--keep", start, check=False)
            raise Stop("배포본과 기록을 잇지 못했습니다. 아무것도 바꾸지 않았습니다.\n" + (err or out).strip())
    code, out, err = git("merge", "--no-ff", "--no-edit", "-m", message, REF, check=False)
    if code != 0:
        conflicts = [c for c in git("diff", "--name-only", "--diff-filter=U").split("\n") if c]
        merging = ok("rev-parse", "-q", "--verify", "MERGE_HEAD")
        if merging and conflicts and args.leave_conflicts:
            return report_conflicts(conflicts, True, start, graft=bool(graft))
        if merging:
            git("merge", "--abort", check=False)
        if graft:
            git("reset", "-q", "--keep", start, check=False)
        if conflicts:
            return report_conflicts(conflicts, False, start, graft=False)
        print("업데이트 중단: 병합하지 못했습니다. 아무것도 바꾸지 않았습니다.")
        print((err or out).strip())
        print("원인을 모르겠으면 위 메시지를 Claude에게 보여 주세요.")
        return 1
    return finish(theirs, branch, release_paths)


def report_conflicts(conflicts, left_open, start, graft):
    if left_open:
        show_list("충돌한 파일 " + str(len(conflicts)) + "개 (병합을 열어 두었습니다):", conflicts)
        print("충돌 표지(<<<<<<<)를 풀고 git add 한 뒤 git commit --no-edit 으로 마칩니다.")
        print("그만두려면 git merge --abort" + (" 다음 git reset --keep " + start[:12] if graft else "") + ".")
        return 1
    show_list("업데이트 중단: 이 저장소와 배포본이 같은 곳을 고쳐 자동으로 합치지 못했습니다. "
              "아무것도 바꾸지 않았습니다. 충돌한 파일:", conflicts)
    print("Claude에게 \"업데이트 충돌 해결해 줘\"라고 요청하세요.")
    return 1


def finish(theirs, branch, release_paths):
    fix_exec_bits(branch)
    print("")
    print("새 판을 받았습니다: " + version_label(theirs))
    kit_notice(release_paths)
    run_checker()
    print("")
    print("내 저장소(GitHub)에는 아직 올라가지 않았습니다. 곧바로 동기화(동기화.sh, Windows는 동기화.cmd)로 올리세요.")
    if branch != "main":
        print("참고: 지금 브랜치(" + branch + ")는 main이 아닙니다.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Stop as e:
        print("")
        print("업데이트 중단: " + str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        print("")
        print("업데이트 취소.")
        sys.exit(1)
