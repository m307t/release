#!/usr/bin/env python3
"""Consistency check for the legal team office.

Run after editing skills, agents, or rules:
    python3 도구/구성점검.py        (Windows: py -3 도구\\구성점검.py)
Exit code 0 = no errors, 1 = errors found.

Checked files: the .md files git syncs (tracked, or new and not ignored by .gitignore), so work
files that stay on one PC are not checked. The third-party plugin source under
도구/설치키트/payload/ is not checked either. Without git, every .md except .git/ and 산출물/.
Paths are checked in backticked spans (every token, so `python3 도구/…` commands too) and on
the lines of ``` code blocks. 변경이력.md and the table rows of the 라운지/ record tables are not
checked (old rows keep old names).
Also warns about files git still tracks although .gitignore now leaves them out (a rule added after
they were committed does not untrack them, so they keep syncing).
Also checks 배포판.md (the release this office came from): its rows can be read, and the distribution
repository address in it is the one the sync scripts refuse to upload to and the update tool uses.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".claude" / "skills"
AGENTS = ROOT / ".claude" / "agents"

# Paths (backticked or in code blocks) starting with these prefixes must exist, unless they contain
# placeholders or the backticked span is followed by "(있으면)" (optional files that appear later).
CHECKED_PREFIXES = ("자료실/", "라운지/", "상황실/", "안내실/", "발송실/", "도구/", ".claude/")
PLACEHOLDER = re.compile(r"[<>*○{}…]|YYYY|\.\.\.")
# Settings that belong only in CLAUDE.md; a hard-coded copy elsewhere drifts when the setting changes.
DUPLICATED_SETTING = re.compile(r"보완[^\n|]{0,12}\d+\s*회")
BUILTIN_COMMANDS = {"loop", "mcp", "help", "config", "init", "agents", "plugin"}
SKIP_DIRS = {".git", "산출물"}
# Third-party plugin source (도구/설치키트/README.md); its own documents are not this office's references.
SKIP_PREFIX = "도구/설치키트/payload/"
# Change log rows keep old names on purpose; renaming a team or file must not turn old rows into errors.
HISTORY_FILES = {"변경이력.md"}
# Record tables in 라운지/ work the same way: their rows keep the names of their day (an 오류노트 row may name
# a checklist that does not exist yet). Only the rows (lines starting with "|") are skipped; the head is checked.
RECORD_TABLE_FILES = {"라운지/오류노트.md", "라운지/훈련기록.md", "라운지/개선안.md"}

errors = []
warnings = []


def rel(path):
    return path.relative_to(ROOT).as_posix()


def read(path):
    return path.read_text(encoding="utf-8", errors="replace")


def frontmatter(text):
    """Return simple key/value pairs from a leading --- block."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    data = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return data
        m = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if m:
            data[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return None


def md_files():
    """The .md files git syncs; every .md when git is missing or this is not a git folder."""
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "*.md"],
            capture_output=True, check=True).stdout.decode("utf-8")
        # A set, because an unmerged file is listed once per conflict stage.
        paths = [ROOT / p for p in sorted({p for p in out.split("\0") if p})]
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError):
        paths = sorted(ROOT.rglob("*.md"))
    for path in paths:
        if not path.is_file():
            continue  # deleted or moved in the working tree but still in the git index
        name = rel(path)
        if name.split("/")[0] in SKIP_DIRS or name.startswith(SKIP_PREFIX):
            continue
        yield path


def check_skills():
    teams = []
    if not SKILLS.is_dir():
        errors.append(".claude/skills 폴더가 없습니다.")
        return teams
    for d in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
        skill = d / "SKILL.md"
        if not skill.is_file():
            errors.append(f"{rel(d)}: SKILL.md가 없습니다.")
            continue
        text = read(skill)
        fm = frontmatter(text)
        if fm is None:
            errors.append(f"{rel(skill)}: 맨 위 --- 머리말이 없거나 닫히지 않았습니다.")
            continue
        name = fm.get("name", "")
        if name != d.name:
            errors.append(f"{rel(skill)}: name 값({name})과 폴더 이름({d.name})이 다릅니다.")
        if not re.fullmatch(r"[a-z0-9-]+", d.name):
            errors.append(f"{rel(d)}: 팀 ID는 영문 소문자·숫자·하이픈만 씁니다.")
        if not fm.get("description"):
            errors.append(f"{rel(skill)}: description이 비어 있습니다.")
        if "## 팀 설정" not in text:
            continue  # not a team skill
        teams.append(d.name)
        for role in ("writer", "checker"):
            agent = f"{d.name}-{role}"
            if not (AGENTS / f"{agent}.md").is_file():
                errors.append(f"{rel(skill)}: 에이전트 파일 .claude/agents/{agent}.md가 없습니다.")
            if agent not in text:
                errors.append(f"{rel(skill)}: 본문에서 {agent}를 부르지 않습니다.")
    return teams


def check_agents(teams):
    count = 0
    if not AGENTS.is_dir():
        errors.append(".claude/agents 폴더가 없습니다.")
        return count
    for path in sorted(AGENTS.glob("*.md")):
        count += 1
        text = read(path)
        fm = frontmatter(text)
        if fm is None:
            errors.append(f"{rel(path)}: 맨 위 --- 머리말이 없거나 닫히지 않았습니다.")
            continue
        if fm.get("name") != path.stem:
            errors.append(f"{rel(path)}: name 값({fm.get('name')})과 파일 이름({path.stem})이 다릅니다.")
        if not fm.get("description"):
            errors.append(f"{rel(path)}: description이 비어 있습니다.")
        m = re.fullmatch(r"(.+)-(writer|checker)", path.stem)
        if not m:
            continue
        team, role = m.groups()
        if team not in teams:
            # Mode-specific agents (e.g. ops-desk-news-writer) belong to the team whose ID is a prefix.
            owner = next((t for t in sorted(teams, key=len, reverse=True) if team.startswith(t + "-")), None)
            if owner is None:
                warnings.append(f"{rel(path)}: 팀장 스킬 .claude/skills/{team}/가 없습니다.")
            elif path.stem not in read(SKILLS / owner / "SKILL.md"):
                errors.append(f".claude/skills/{owner}/SKILL.md: 본문에서 {path.stem}를 부르지 않습니다.")
        if role == "checker":
            denied = {t.strip() for t in fm.get("disallowedTools", "").split(",")}
            allowed = {t.strip() for t in fm.get("tools", "").split(",") if t.strip()}
            can_edit = ("Write" in allowed or "Edit" in allowed) if allowed else not {"Write", "Edit"} <= denied
            if can_edit:
                errors.append(f"{rel(path)}: 검증 에이전트가 파일을 고칠 수 있습니다(disallowedTools에 Write, Edit 필요).")
            bash_open = ("Bash" in allowed) if allowed else "Bash" not in denied
            if bash_open and "읽기 전용" not in text:
                warnings.append(f"{rel(path)}: 검증 에이전트에 Bash가 열려 있는데 '읽기 전용' 계산만 하라는 지시가 없습니다.")
            if "자료실/규칙/검증공통.md" not in text:
                warnings.append(f"{rel(path)}: 자료실/규칙/검증공통.md를 읽으라는 지시가 없습니다.")
        elif "자료실/규칙/실무공통.md" not in text:
            warnings.append(f"{rel(path)}: 자료실/규칙/실무공통.md를 읽으라는 지시가 없습니다.")
    return count


def missing_paths(text):
    """Tokens of text that are repository paths (CHECKED_PREFIXES, no placeholder) but do not exist."""
    return [t for t in text.replace("\\", "/").split()
            if t.startswith(CHECKED_PREFIXES) and not PLACEHOLDER.search(t) and not (ROOT / t).exists()]


def check_references():
    known_commands = ({p.name for p in SKILLS.iterdir() if p.is_dir()} if SKILLS.is_dir() else set()) | BUILTIN_COMMANDS
    for path in md_files():
        if rel(path) in HISTORY_FILES:
            continue
        text = read(path)
        if rel(path) in RECORD_TABLE_FILES:
            text = "\n".join("" if line.lstrip().startswith("|") else line for line in text.splitlines())
        in_template = rel(path).startswith("도구/새팀_템플릿/")
        for match in re.finditer(r"`([^`\n]+)`", text):
            span = match.group(1).strip()
            optional = text[match.end():match.end() + 8].lstrip().startswith("(있으면)")
            if not optional:
                for target in missing_paths(span):
                    errors.append(f"{rel(path)}: `{target}` 경로가 없습니다.")
            m = re.match(r"/([a-z0-9-]+)", span)
            if m and not in_template and m.group(1) not in known_commands:
                errors.append(f"{rel(path)}: 명령 `/{m.group(1)}`에 해당하는 스킬이 없습니다.")
        # Code block lines are run as written: check their paths too (backticked spans were checked above).
        in_fence = False
        for line in text.splitlines():
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
            elif in_fence:
                for target in missing_paths(re.sub(r"`[^`\n]+`", " ", line)):
                    errors.append(f"{rel(path)}: 코드 블록의 `{target}` 경로가 없습니다.")
        if SKILLS in path.parents or AGENTS in path.parents:
            for line in text.splitlines():
                if DUPLICATED_SETTING.search(line):
                    warnings.append(f"{rel(path)}: 보완 횟수를 직접 적었습니다. '운영 설정의 보완 한도'로 바꾸세요: {line.strip()[:60]}")


def check_index(teams):
    for doc in ("CLAUDE.md", "README.md"):
        path = ROOT / doc
        if not path.is_file():
            errors.append(f"{doc}가 없습니다.")
            continue
        text = read(path)
        for team in teams:
            if f"/{team}" not in text:
                errors.append(f"{doc}: 팀 명령 목록에 /{team} 항목이 없습니다.")
    claude = ROOT / "CLAUDE.md"
    if claude.is_file() and "## 운영 설정" not in read(claude):
        errors.append("CLAUDE.md: '## 운영 설정' 표가 없습니다.")


def check_types(teams):
    """Each team needs a checklist type in the coaching team settings (CLAUDE.md 관문 규칙 uses it)."""
    if "coaching" not in teams:
        return
    skill = SKILLS / "coaching" / "SKILL.md"
    row = next((l for l in read(skill).splitlines() if l.startswith("| 팀 → 유형 |")), None)
    if row is None:
        warnings.append(f"{rel(skill)}: 팀 설정에 '팀 → 유형' 행이 없습니다.")
        return
    for team in teams:
        if not re.search(rf"(?<![a-z0-9-]){re.escape(team)} →", row):
            warnings.append(f"{rel(skill)}: 팀 설정 '팀 → 유형'에 {team}가 없습니다(검증에 넘길 체크리스트 유형).")


def check_ignored_tracked():
    """Files .gitignore leaves out but git still tracks: they were committed before the rule (or on a PC
    that had not pulled it yet), and .gitignore does not untrack them. Skipped without git."""
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z", "--cached", "--ignored", "--exclude-standard"],
            capture_output=True, check=True).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError):
        return
    for name in sorted({p for p in out.split("\0") if p}):
        warnings.append(f"{name}: 동기화에서 빼기로 한 파일이 이미 git에 올라가 있습니다. "
                        "사람에게 묻고 git rm --cached로 뺍니다.")


def check_release_info():
    """배포판.md rows that the update tool reads, and the same distribution address in the scripts."""
    info_path = ROOT / "배포판.md"
    if not info_path.is_file():
        errors.append("배포판.md가 없습니다(새 판 받기가 읽는 파일).")
        return
    rows = {}
    for line in read(info_path).splitlines():
        if line.startswith("## "):
            break
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if len(cells) >= 2:
            rows[cells[0]] = cells[1]
    for key in ("배포본", "판", "배포일", "배포 저장소"):
        if not rows.get(key):
            errors.append(f"배포판.md: 맨 위 표에 '{key}' 줄이 없습니다.")
    m = re.search(r"github\.com[:/]+([^/\s]+/[^/\s]+?)(?:\.git)?/*$", rows.get("배포 저장소", ""), re.I)
    if not m:
        if rows.get("배포 저장소"):
            errors.append("배포판.md: 배포 저장소가 GitHub 주소가 아닙니다.")
        return
    repo = m.group(1)
    for name, needle in (("동기화.sh", f"RELEASE_REPO='{repo}'"), ("동기화.cmd", f'set "RELEASE_REPO={repo}"'),
                         ("도구/업데이트.py", f'DEFAULT_URL = "https://github.com/{repo}"')):
        path = ROOT / name
        if path.is_file() and needle not in read(path):
            errors.append(f"{name}: 배포 저장소 주소가 배포판.md({repo})와 다릅니다. 함께 고칩니다(배포판.md 머리).")


def check_git_files():
    """.gitignore and .gitattributes are hidden files that a copy (ZIP, drag and drop) can leave behind.
    Without .gitignore the first sync uploads 산출물/ case folders and .env keys; without .gitattributes
    the add-only tables stop syncing with a conflict. Also warns when a tracked .sh lost its executable
    bit (a ZIP unpacked on Windows), which makes ./동기화.sh fail on macOS and Linux."""
    needed = {".gitignore": ("산출물/**", ".env"), ".gitattributes": ("merge=union",)}
    for name, lines in needed.items():
        path = ROOT / name
        if not path.is_file():
            errors.append(f"{name}가 없습니다. 숨김 파일이라 복사할 때 빠지기 쉽습니다. 받은 배포본에서 다시 넣습니다.")
            continue
        text = read(path)
        for line in lines:
            if line not in text:
                errors.append(f"{name}: '{line}' 줄이 없습니다. 동기화가 지켜야 할 규칙이 빠졌습니다.")
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-s", "-z", "--", "*.sh"],
                             capture_output=True, check=True).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError):
        return
    for entry in filter(None, out.split("\0")):
        meta, _, name = entry.partition("\t")
        if meta.startswith("100644"):
            warnings.append(f"{name}: 실행 권한이 없이 올라가 있습니다(Windows에서 압축을 푼 경우). "
                            f"git update-index --chmod=+x \"{name}\" 뒤 동기화합니다.")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    teams = check_skills()
    agent_count = check_agents(teams)
    check_references()
    check_index(teams)
    check_types(teams)
    check_ignored_tracked()
    check_git_files()
    check_release_info()
    print(f"구성 점검: 팀 {len(teams)}개, 에이전트 {agent_count}개")
    for e in errors:
        print(f"[오류] {e}")
    for w in warnings:
        print(f"[주의] {w}")
    print(f"결과: 오류 {len(errors)}건, 주의 {len(warnings)}건")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
