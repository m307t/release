#!/usr/bin/env python3
"""Build the data file for the progress dashboard (상황실/대시보드.html).

    python3 도구/대시보드갱신.py [--today YYYY-MM-DD] [--root PATH] [--out PATH]
    python3 도구/대시보드갱신.py --selftest
    (Windows: py -3 도구\\대시보드갱신.py ...)
Needs Python 3.8 or later, standard library only.

Reads these files under the project root. A missing or unreadable input becomes a
warning in the output, never a crash:
  - 산출물/*/_진행.md (format: 자료실/서식/진행기록.md). 상태 comes from 다음 할 일:
    "없음(종결)" = 종결, "[사람 확인]" = 사람 확인 대기, anything else = 진행 중.
    A case folder whose _진행.md is missing or unreadable is listed as 기록 없음 with a warning.
    마감 = the 일정 ID(s) S-YYYYMMDD-XXXX in the 마감 field, looked up in 통합일정표
    (the earliest row whose 상태 is not 완료/취소). A 취소 row is followed to the rows
    whose 역산 기준 says "S-… 대체" (chains too). An open case whose 마감 IDs lead to
    no open row gets a warning (취소·완료 / 날짜를 읽지 못함 / 표에 없음).
  - 상황실/통합일정표.md (rules in its head), 상황실/현안목록.md
  - 라운지/오류노트.md, 라운지/훈련기록.md (table rows)
  - 자료실/교본/검수체크리스트_*.md (rows counted by 상태; 사용 rows are listed)
  - CLAUDE.md (운영 설정 table, 건물 배치 lines)
  - .claude/skills/*/SKILL.md front matter and .claude/agents/*.md, for the 조직도.
    The "7일 안 마감" window is the ops desk team setting '다가오는 마감 표시' (7 if absent).

Writes 상황실/대시보드_데이터.js as "window.DASHBOARD_DATA = {...};". It holds case
content, so it is git-ignored and must never be synced or published. Open
상황실/대시보드.html (same folder as the data file) in a browser to see it.

Options:
  --today     base date for D-n and 이번 달 (default: today in Asia/Seoul)
  --root      project root (default: the folder above 도구/); must hold CLAUDE.md and .claude/
  --out       data file to write (default: <root>/상황실/대시보드_데이터.js). The name must stay
              대시보드_데이터.js; inside the project only the default path is allowed (the one
              .gitignore covers), and an existing file is replaced only if this tool made it.
  --selftest  build a temporary fictional project, check the results, print pass/fail
Exit code 0 = data file written (warnings are listed but do not fail the run),
1 = selftest failed, 2 = the data file was not written (bad arguments, refused --root/--out,
write error, tool error, Python older than 3.8); an existing data file is left unchanged.
"""
import argparse
import contextlib
import datetime as dt
import io
import json
import os
import re
import sys
import tempfile
import traceback
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KST = dt.timezone(dt.timedelta(hours=9))  # Korea has no DST; a fixed offset avoids needing tzdata on Windows
OUT_NAME = "대시보드_데이터.js"
MARK = "// Generated dashboard data."  # first line of every data file; only such files are overwritten
VERSION = 2             # 2: deadline.via, deadline_issues, no_open_deadline, summary.no_open_deadline
MIN_PYTHON = (3, 8)
WEEKDAYS = "월화수목금토일"
DATE = re.compile(r"(\d{4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})")
COMPACT_DATE = re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)")
ROW_ID = re.compile(r"S-\d{8}-[0-9A-F]{4}")
REPLACES = re.compile(r"(S-\d{8}-[0-9A-F]{4})\s*대체")  # 역산 기준 "S-… 대체" (통합일정표 head)
SCHEDULE_STATES = {"제안", "확정", "완료", "취소"}
CLOSED_STATES = {"완료", "취소"}
ISSUE_LABELS = {"closed": "취소·완료", "bad": "날짜를 읽지 못함", "missing": "표에 없음"}
STATUS_ORDER = ["사람 확인 대기", "진행 중", "기록 없음", "종결"]
VERDICTS = ("통과", "보완", "반려")
NEXT_DAYS = 14          # 일정 tab: "오늘부터 14일" = D-day .. D-13
DEFAULT_DUE_DAYS = 7    # fallback when the ops desk team setting cannot be read
LATEST_ROWS = 20        # 오류노트·훈련기록 rows kept for the "latest" tables
FIELDS = ["건", "익명 ID", "팀", "접수일", "대상", "넘겨받은 자료", "마감", "현재 단계", "다음 할 일"]


# ---------------------------------------------------------------------------
# Small helpers

def iso(day):
    return day.isoformat() if day else None


def date_label(day, weekday=True):
    """2026. 11. 5.(목) — 자료실/규칙/표기규칙.md."""
    text = f"{day.year}. {day.month}. {day.day}."
    return f"{text}({WEEKDAYS[day.weekday()]})" if weekday else text


def time_key(text):
    """Sortable "HH:MM" of the first time in a 시각 cell; all-day ("-") sorts first."""
    m = re.match(r"^\s*(\d{1,2}):(\d{2})", text or "")
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else "00:00"


def dday_label(n):
    return "D-day" if n == 0 else (f"D-{n}" if n > 0 else f"D+{-n}")


def parse_date(text, compact=False):
    """First date in text ("2026. 11. 5.", "2026-11-05", or with compact=True "20261105")."""
    text = text or ""
    m = DATE.search(text) or (COMPACT_DATE.search(text) if compact else None)
    if not m:
        return None
    try:
        return dt.date(*(int(x) for x in m.groups()))
    except ValueError:
        return None


def cells(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def is_separator(line):
    return bool(re.fullmatch(r"\|?(\s*:?-{3,}:?\s*\|)*\s*:?-{3,}:?\s*\|?", line.strip()))


def col_match(key, name):
    """True if the header key is name, or name followed by a space or parenthesis ("내용 (한 줄)",
    "날짜(요일)"). So "일" does not match "일정 ID"."""
    return key == name or bool(re.match(re.escape(name) + r"[\s(（]", key))


def pick(row, name):
    """Value of the column called name, or whose header is name plus a note ("내용 (한 줄)")."""
    if name in row:
        return row[name]
    for key, value in row.items():
        if not key.startswith("_") and col_match(key, name):
            return value
    return ""


def fs_is_dir(path):
    """Path.is_dir() that reports False instead of raising (pathlib raises PermissionError)."""
    try:
        return path.is_dir()
    except OSError:
        return False


def fs_is_file(path):
    try:
        return path.is_file()
    except OSError:
        return False


def same_path(a, b):
    return os.path.normcase(str(a)) == os.path.normcase(str(b))


def within(path, folder):
    """True if path is folder or inside it (both already resolved)."""
    p, f = os.path.normcase(str(path)), os.path.normcase(str(folder))
    try:
        return os.path.commonpath([p, f]) == f
    except ValueError:  # different drives on Windows
        return False


def section(lines, title):
    """(start, stop) of the lines under the heading that starts with title, or None."""
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if m and m.group(2).startswith(title):
            level = len(m.group(1))
            for j in range(i + 1, len(lines)):
                m2 = re.match(r"^(#{1,6})\s", lines[j])
                if m2 and len(m2.group(1)) <= level:
                    return i + 1, j
            return i + 1, len(lines)
    return None


def frontmatter(lines):
    """Simple key/value pairs of a leading --- block (same rule as 도구/구성점검.py)."""
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


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=\.)\s+", text or "") if s.strip()]


def split_top(text):
    """Split 'a(b, c), d' on commas that are outside parentheses and backticks."""
    parts, cur, depth, code = [], "", 0, False
    for ch in text:
        if ch == "`":
            code = not code
        elif not code and ch in "(（":
            depth += 1
        elif not code and ch in ")）":
            depth = max(0, depth - 1)
        if ch in ",，" and depth == 0 and not code:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts


# ---------------------------------------------------------------------------
# Reading context: file access, warnings and the list of sources read

class Reader:
    def __init__(self, root, today):
        self.root = root
        self.today = today
        self.warnings = []
        self.sources = []

    def rel(self, path):
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return path.as_posix()

    def warn(self, path, message):
        self.warnings.append({"path": self.rel(path) if isinstance(path, Path) else path, "message": message})

    def source(self, label, path, ok, detail):
        name = self.rel(path) + ("/" if fs_is_dir(path) else "")
        self.sources.append({"label": label, "path": name, "ok": ok, "detail": detail})

    def glob(self, folder, pattern):
        """Sorted matches, or [] with a warning when the folder cannot be listed."""
        try:
            return sorted(folder.glob(pattern))
        except OSError as e:
            self.warn(folder, f"폴더를 읽지 못했습니다({e.strerror or e}).")
            return []

    def read(self, path):
        """(lines, problem): problem is None, "missing", or why the file could not be read.
        Only the decoding fallback warns here; callers word the other warnings."""
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            return None, "missing"
        except OSError as e:  # PermissionError, IsADirectoryError (a folder with the file's name), ...
            return None, f"읽지 못했습니다({e.strerror or e})."
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            self.warn(path, "UTF-8이 아닌 글자가 있어 그 부분을 빼고 읽었습니다.")
            text = raw.decode("utf-8", errors="replace")
        return text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), None

    def lines(self, path, missing_ok=False):
        """The file's lines, or None (with a warning unless missing_ok) when it cannot be read."""
        lines, problem = self.read(path)
        if problem == "missing":
            if not missing_ok:
                self.warn(path, "파일이 없습니다.")
        elif problem:
            self.warn(path, problem)
        return lines

    def table(self, path, lines, must, start=0, stop=None):
        """(header, rows) of the first table in lines[start:stop] whose header has every column in must
        (see col_match). Rows are dicts plus "_line". None if not found."""
        stop = len(lines) if stop is None else stop
        i = start
        while i < stop:
            line = lines[i]
            if line.strip().startswith("|") and i + 1 < stop and is_separator(lines[i + 1]):
                header = cells(line)
                if all(any(col_match(h, m) for h in header) for m in must):
                    rows = []
                    for n in range(i + 2, stop):
                        if not lines[n].strip().startswith("|"):
                            break
                        values = cells(lines[n])
                        if not any(values):
                            continue
                        if len(values) != len(header):
                            self.warn(path, f"{n + 1}줄: 칸 수가 표 머리와 다릅니다({len(values)}/{len(header)}).")
                            values = (values + [""] * len(header))[:len(header)]
                        row = dict(zip(header, values))
                        row["_line"] = n + 1
                        rows.append(row)
                    return header, rows
            i += 1
        return None


# ---------------------------------------------------------------------------
# Inputs

def read_skills(rd):
    """Team lead skills and agents for the 조직도, plus the due-soon window from the ops desk settings."""
    teams, due_days = {}, DEFAULT_DUE_DAYS
    skills_dir = rd.root / ".claude" / "skills"
    for skill in rd.glob(skills_dir, "*/SKILL.md"):
        lines = rd.lines(skill)
        if lines is None:
            continue
        fm = frontmatter(lines)
        if fm is None:
            rd.warn(skill, "맨 위 --- 머리말을 읽지 못했습니다.")
            continue
        sid = fm.get("name") or skill.parent.name
        parts = sentences(fm.get("description", ""))
        title = parts[0].rstrip(".") if parts else sid
        teams[sid] = {
            "id": sid,
            "title": title,
            "name": re.sub(r"\s*팀장$", "", title),
            "summary": parts[1] if len(parts) > 1 else "",
            "hint": fm.get("argument-hint", ""),
            "is_team": any(l.startswith("## 팀 설정") for l in lines),
            "agents": [],
        }
        for line in lines:
            m = re.match(r"^\|\s*다가오는 마감 표시\s*\|\s*(\d+)\s*일", line)
            if m and sid == "ops-desk":
                due_days = int(m.group(1))
    agents_dir = rd.root / ".claude" / "agents"
    for path in rd.glob(agents_dir, "*.md"):
        lines = rd.lines(path)
        if lines is None:
            continue
        fm = frontmatter(lines) or {}
        name = fm.get("name") or path.stem
        owner = next((t for t in sorted(teams, key=len, reverse=True) if name.startswith(t + "-")), None)
        if owner is None:
            continue
        parts = sentences(fm.get("description", ""))
        role = "검증" if name.endswith("-checker") else ("실무" if name.endswith("-writer") else "기타")
        teams[owner]["agents"].append({
            "name": name, "role": role,
            "title": parts[0].rstrip(".") if parts else name,
            "summary": parts[1] if len(parts) > 1 else "",
        })
    for sid, team in teams.items():
        # writer before checker; the team's main agent (<id>-writer) before mode agents (<id>-news-writer)
        team["agents"].sort(key=lambda a: (["실무", "검증", "기타"].index(a["role"]),
                                           a["name"] not in (f"{sid}-writer", f"{sid}-checker"), a["name"]))
    rd.source("팀장 스킬·에이전트", skills_dir.parent, bool(teams),
              f"팀장 스킬 {len(teams)}개, 에이전트 {sum(len(t['agents']) for t in teams.values())}개")
    return teams, due_days


def read_claude(rd, teams):
    """운영 설정 rows and the 건물 배치 floors from CLAUDE.md."""
    path = rd.root / "CLAUDE.md"
    lines = rd.lines(path)
    settings, floors = [], []
    if lines is None:
        rd.source("운영 설정·건물 배치", path, False, "읽지 못함")
        return settings, floors
    span = section(lines, "운영 설정")
    found = rd.table(path, lines, ["항목", "값", "상태"], *span) if span else None
    if found is None:
        rd.warn(path, "'운영 설정' 표(항목·값·상태)를 찾지 못했습니다.")
    else:
        settings = [{"item": pick(r, "항목"), "value": pick(r, "값"), "state": pick(r, "상태")} for r in found[1]]
    span = section(lines, "건물 배치")
    placed = set()
    for line in (lines[span[0]:span[1]] if span else []):
        m = re.match(r"^\s*-\s*(\d+F)\s*([^:：]*)[:：]\s*(.+)$", line)
        if not m:
            continue
        rooms = []
        for part in split_top(m.group(3)):
            rm = re.match(r"^(.*?)\s*[(（](.*)[)）]\s*$", part)
            name, note = (rm.group(1), rm.group(2)) if rm else (part, "")
            spans = re.findall(r"`([^`]+)`", note)
            commands = [s for s in spans if s.startswith("/")]
            ids = []
            for c in commands:
                sid = c[1:].split()[0] if len(c) > 1 else ""
                if sid in teams and sid not in ids:
                    ids.append(sid)
            placed.update(ids)
            rooms.append({"name": name.strip(), "note": note.strip(), "commands": commands, "teams": ids})
        floors.append({"floor": m.group(1), "title": m.group(2).strip(), "rooms": rooms})
    if not floors:
        rd.warn(path, "'건물 배치' 줄(- 3F …: …)을 찾지 못했습니다.")
    unplaced = [t for t in teams if t not in placed and teams[t]["is_team"]]
    if unplaced:
        rd.warn(path, f"건물 배치에 없는 팀 스킬: {', '.join(unplaced)}")
        floors.append({"floor": "-", "title": "건물 배치에 없는 팀", "rooms": [
            {"name": teams[t]["name"], "note": f"`/{t}`", "commands": [f"/{t}"], "teams": [t]} for t in unplaced]})
    rd.source("운영 설정·건물 배치", path, bool(settings or floors),
              f"운영 설정 {len(settings)}줄, 층 {len([f for f in floors if f['floor'] != '-'])}개")
    return settings, floors


def read_schedule(rd):
    path = rd.root / "상황실" / "통합일정표.md"
    out = {"rows": [], "counts": {"past": 0, "next": 0, "later": 0, "closed": 0, "bad": 0},
           "next_end": iso(rd.today + dt.timedelta(days=NEXT_DAYS - 1)), "next_days": NEXT_DAYS}
    lines = rd.lines(path)
    found = rd.table(path, lines, ["날짜", "상태", "일정 ID"]) if lines is not None else None
    if lines is not None and found is None:
        rd.warn(path, "표 머리(날짜(요일)·상태·일정 ID 칸이 있는 줄)를 찾지 못했습니다.")
    if found:
        for col, effect in (("일", "일정 이름을 비워 둡니다"), ("역산 기준", "대체 줄(S-… 대체)을 따라가지 못합니다")):
            if not any(col_match(h, col) for h in found[0]):
                rd.warn(path, f"표 머리에 '{col}' 칸이 없습니다({effect}).")
    rows = found[1] if found else []
    ids = Counter(pick(r, "일정 ID") for r in rows)
    for r in rows:
        n, rid, state = r["_line"], pick(r, "일정 ID"), pick(r, "상태")
        date_text = pick(r, "날짜")
        where = f"{n}줄 {rid or '(일정 ID 없음)'}"
        if not ROW_ID.fullmatch(rid):
            rd.warn(path, f"{where}: 일정 ID 형식(S-YYYYMMDD-XXXX)이 아닙니다.")
        elif ids[rid] > 1:
            rd.warn(path, f"{where}: 같은 일정 ID가 {ids[rid]}줄에 있습니다.")
        if state not in SCHEDULE_STATES:
            rd.warn(path, f"{where}: 상태 값({state or '빈칸'})이 제안·확정·완료·취소가 아닙니다.")
        day = parse_date(date_text)
        if day is None:
            rd.warn(path, f"{where}: 날짜를 읽지 못했습니다({date_text or '빈칸'}).")
        else:
            if len(DATE.findall(date_text)) > 1:
                rd.warn(path, f"{where}: 날짜가 둘 이상입니다. 첫 날짜로 봅니다(여러 날 일정은 두 줄로 쓴다).")
            wd = re.search(r"\(([월화수목금토일])\)", date_text)
            if wd and wd.group(1) != WEEKDAYS[day.weekday()]:
                rd.warn(path, f"{where}: 요일이 날짜와 다릅니다({date_text}, 그날은 {WEEKDAYS[day.weekday()]}요일).")
        dday = (day - rd.today).days if day else None
        if state in CLOSED_STATES:
            bucket = "closed"
        elif day is None:
            bucket = "bad"
        elif dday < 0:
            bucket = "past"
        elif dday < NEXT_DAYS:
            bucket = "next"
        else:
            bucket = "later"
        out["counts"][bucket] += 1
        out["rows"].append({
            "id": rid, "date": iso(day), "date_text": date_text, "time": pick(r, "시각"),
            "what": pick(r, "일"), "kind": pick(r, "종류"), "case": pick(r, "건"), "origin": pick(r, "출처"),
            "basis": pick(r, "역산 기준"), "state": state, "calendar": pick(r, "캘린더"),
            "dday": dday, "bucket": bucket, "line": n,
        })
    out["rows"].sort(key=lambda x: (x["date"] or "9999-99-99", time_key(x["time"]), x["line"]))
    if lines is not None:
        c = out["counts"]
        rd.source("통합일정표", path, found is not None,
                  f"{len(rows)}줄 (지난 미완료 {c['past']} · 14일 {c['next']} · 그 뒤 {c['later']} · 완료·취소 {c['closed']})")
    else:
        rd.source("통합일정표", path, False, "읽지 못함")
    return out


def team_name(value, folder_team, teams):
    """Normalize the 팀 field ("법안검토", "법안검토팀", "bill-review") to the team name of its skill."""
    aliases = {}
    for sid, t in teams.items():
        for a in (sid, t["name"], re.sub(r"(팀|실)$", "", t["name"])):
            aliases[a] = t["name"]
    for v in (value, folder_team):
        v = (v or "").strip().strip("`")
        if v:
            return aliases.get(v, v)
    return ""


def replacements(rows):
    """{old 일정 ID: [IDs of the rows whose 역산 기준 says "<old> 대체"]}, in table order."""
    out = {}
    for r in rows:
        for old in REPLACES.findall((r.get("basis") or "").upper()):
            if r["id"] and old != r["id"] and r["id"] not in out.get(old, []):
                out.setdefault(old, []).append(r["id"])
    return out


def resolve_deadline(rid, by_id, replaced_by):
    """Follow one 마감 ID through 취소 rows to the rows that replace them (chains, cycles stop).
    Returns (found, problems): found = [(open row with a date, IDs passed on the way)],
    problems = [(kind, path)] with kind in ISSUE_LABELS and path = IDs from rid to the dead end."""
    found, problems, seen = [], [], set()
    queue = [(rid, [])]
    while queue:
        cur, via = queue.pop(0)
        if cur in seen:
            continue
        seen.add(cur)
        row, path = by_id.get(cur), via + [cur]
        nexts = [n for n in replaced_by.get(cur, []) if n not in seen]
        if row is None:
            problems.append(("missing", path))
        elif row["state"] == "취소" and nexts:
            queue.extend((n, path) for n in nexts)
        elif row["state"] in CLOSED_STATES:
            problems.append(("closed", path))
        elif not row["date"]:
            problems.append(("bad", path))
        else:
            found.append((row, via))
    return found, problems


def read_case(rd, folder, schedule_by_id, teams, replaced_by=None):
    path = folder / "_진행.md"
    parts = folder.name.split("_")
    folder_team = parts[1] if len(parts) > 1 else ""
    case = {
        "folder": folder.name, "path": rd.rel(folder) + "/", "team": team_name("", folder_team, teams),
        "received": iso(parse_date(parts[0], compact=True)), "stage": "", "next": "", "status": "기록 없음",
        "target": "", "handed": "", "deadline_text": "", "deadline": None, "deadline_note": "",
        "deadline_issues": None, "no_open_deadline": False,
        "last_check": None, "check_count": 0, "decision_count": 0, "last_decision": None,
        "approval_count": 0, "last_approval": None, "warnings": [],
    }
    lines, problem = rd.read(path)
    where = case["path"] if problem == "missing" else rd.rel(path)

    def warn(message):
        case["warnings"].append(message)
        rd.warn(where, message)

    if lines is None:
        warn("_진행.md가 없습니다(팀장이 건 폴더를 만들 때 함께 만든다)." if problem == "missing"
             else f"_진행.md를 {problem}")
        return case
    head_end = next((i for i, l in enumerate(lines) if l.startswith("## ")), len(lines))
    fields = {}
    for line in lines[:head_end]:
        m = re.match(r"^\s*[-*]\s*\**([^:：*]+?)\**\s*[:：]\s*(.*)$", line)
        if m and m.group(1).strip() in FIELDS and m.group(1).strip() not in fields:
            fields[m.group(1).strip()] = m.group(2).strip()
    case.update({
        "team": team_name(fields.get("팀", ""), folder_team, teams),
        "received": iso(parse_date(fields.get("접수일", ""), compact=True)) or case["received"],
        "stage": fields.get("현재 단계", ""), "next": fields.get("다음 할 일", ""),
        "target": fields.get("대상", ""), "handed": fields.get("넘겨받은 자료", ""),
        "deadline_text": fields.get("마감", ""),
    })
    if "다음 할 일" not in fields:
        warn("'다음 할 일' 칸이 없습니다(진행 중으로 봅니다).")
    nxt = case["next"].lstrip("`* ")
    if re.match(r"^없음\s*\(종결\)", nxt):
        case["status"] = "종결"
    elif re.match(r"^\[사람\s*확인\]", nxt):
        case["status"] = "사람 확인 대기"
    else:
        case["status"] = "진행 중"

    # Deadline: the earliest open schedule row among the 일정 IDs named in 마감, following
    # 취소 rows to the rows that replace them ("S-… 대체" in 역산 기준)
    ids = []
    for rid in ROW_ID.findall(case["deadline_text"].upper()):
        if rid not in ids:
            ids.append(rid)
    candidates, problems = {}, []
    for rid in ids:
        if rid not in schedule_by_id:
            warn(f"마감의 일정 ID {rid}가 통합일정표에 없습니다.")
        found, probs = resolve_deadline(rid, schedule_by_id, replaced_by or {})
        for row, via in found:
            if row["id"] not in candidates or len(via) < len(candidates[row["id"]][1]):
                candidates[row["id"]] = (row, via)
        problems += probs
    if candidates:
        row, via = min(candidates.values(), key=lambda x: (x[0]["date"], time_key(x[0]["time"])))
        case["deadline"] = {k: row[k] for k in ("id", "date", "time", "what", "kind", "state", "dday")}
        case["deadline"]["via"] = via
    elif ids:
        issues = {k: [] for k in ISSUE_LABELS}
        for kind, chain in problems:
            text = " → ".join(chain)
            if text not in issues[kind]:
                issues[kind].append(text)
        detail = "; ".join(f"{ISSUE_LABELS[k]}: {', '.join(v)}" for k, v in issues.items() if v)
        case["deadline_issues"] = issues
        case["deadline_note"] = f"마감 칸의 일정 가운데 열린 줄이 없습니다({detail})."
        if case["status"] in ("진행 중", "사람 확인 대기"):
            case["no_open_deadline"] = True
            if issues["closed"] or issues["bad"]:  # IDs missing from the table were warned above
                warn(f"열린 건인데 마감 칸의 일정 가운데 열린 줄이 없습니다({detail}). "
                     "다음 마감 줄을 통합일정표에 넣고 마감 칸에 그 일정 ID를 더합니다.")
    elif parse_date(case["deadline_text"]):
        warn("마감 칸에 날짜만 있고 일정 ID(S-YYYYMMDD-XXXX)가 없습니다. 날짜는 통합일정표에 둡니다.")

    # Tables: 사람 결정, 검증 회차, 승인
    def rows_under(title, must):
        span = section(lines, title)
        found = rd.table(path, lines, must, *span) if span else None
        return found[1] if found else []

    decisions = rows_under("사람 결정", ["일시"])
    case["decision_count"] = len(decisions)
    if decisions:
        d = decisions[-1]
        case["last_decision"] = {"when": pick(d, "일시"), "stage": pick(d, "단계"), "asked": pick(d, "물은 것")}
    checks = rows_under("검증 회차", ["회차", "판정"])
    case["check_count"] = len(checks)
    if checks:
        def round_no(r):
            m = re.search(r"\d+", pick(r, "회차"))
            return int(m.group()) if m else 0
        last = max(enumerate(checks), key=lambda x: (round_no(x[1]), x[0]))[1]
        verdict_text = pick(last, "판정")
        verdict = next((v for v in VERDICTS if v in verdict_text), verdict_text)
        case["last_check"] = {"round": round_no(last) or None, "verdict": verdict,
                              "when": pick(last, "일시"), "findings": pick(last, "지적 수")}
    approvals = rows_under("승인", ["일시", "승인자"])
    case["approval_count"] = len(approvals)
    if approvals:
        a = approvals[-1]
        case["last_approval"] = {"when": pick(a, "일시"), "who": pick(a, "승인자"), "file": pick(a, "승인한 파일")}
    return case


def read_cases(rd, schedule, teams):
    base = rd.root / "산출물"
    by_id = {r["id"]: r for r in schedule["rows"] if r["id"]}
    replaced_by = replacements(schedule["rows"])
    try:
        entries = sorted(base.iterdir())
    except (FileNotFoundError, NotADirectoryError):
        rd.warn(base, "산출물 폴더가 없습니다.")
        rd.source("건 폴더", base, False, "폴더 없음")
        return []
    except OSError as e:
        rd.warn(base, f"산출물 폴더를 읽지 못했습니다({e.strerror or e}).")
        rd.source("건 폴더", base, False, "읽지 못함")
        return []
    folders = []
    for f in entries:
        if f.name.startswith((".", "_")):
            continue
        try:
            if f.is_dir():
                folders.append(f)
        except OSError as e:
            rd.warn(f, f"건 폴더인지 확인하지 못했습니다({e.strerror or e}).")
    cases = [read_case(rd, f, by_id, teams, replaced_by) for f in folders]
    # Waiting-for-person first, then nearest deadline, then newest 접수일 (two stable sorts)
    cases.sort(key=lambda c: c["received"] or "", reverse=True)
    cases.sort(key=lambda c: (STATUS_ORDER.index(c["status"]), c["deadline"]["dday"] if c["deadline"] else 10 ** 6))
    rd.source("건 폴더", base, True, f"{len(cases)}개")
    return cases


def read_record_table(rd, path, label, must):
    """Generic synced record table (현안목록, 오류노트, 훈련기록): (columns, rows as lists, row dicts)."""
    lines = rd.lines(path)
    found = rd.table(path, lines, must) if lines is not None else None
    if lines is not None and found is None:
        rd.warn(path, f"표 머리({'·'.join(must)} 칸이 있는 줄)를 찾지 못했습니다.")
    header, rows = found if found else ([], [])
    rd.source(label, path, found is not None, f"{len(rows)}줄" if found else "읽지 못함")
    return header, rows


def latest(rows, limit):
    """Rows sorted by 날짜, newest first; later rows first on the same day (tables only grow at the end)."""
    dated = [(parse_date(pick(r, "날짜")), i, r) for i, r in enumerate(rows)]
    dated.sort(key=lambda x: (x[0] or dt.date.min, x[1]), reverse=True)
    return [r for _, _, r in dated[:limit]]


def as_lists(header, rows):
    return [[r.get(h, "") for h in header] for r in rows]


def read_issues(rd):
    path = rd.root / "상황실" / "현안목록.md"
    header, rows = read_record_table(rd, path, "현안목록", ["건 폴더", "상태"])
    states = [pick(r, "상태") for r in rows]
    return {"columns": header, "rows": as_lists(header, rows),
            "open": sum(1 for s in states if s.startswith("진행")),
            "closed": sum(1 for s in states if s.startswith("종료"))}


def read_lore(rd):
    """오류노트 counts and latest rows, 훈련기록 latest rows."""
    path = rd.root / "라운지" / "오류노트.md"
    header, rows = read_record_table(rd, path, "오류노트", ["날짜", "유형", "발견자"])
    this_month = 0
    for r in rows:
        day = parse_date(pick(r, "날짜"))
        if day and (day.year, day.month) == (rd.today.year, rd.today.month):
            this_month += 1

    def counts(name):
        return Counter(pick(r, name) or "(빈칸)" for r in rows).most_common()

    errors = {"columns": header, "latest": as_lists(header, latest(rows, LATEST_ROWS)), "total": len(rows),
              "this_month": this_month, "by_type": counts("유형"), "by_finder": counts("발견자"),
              "by_team": counts("팀")}
    path = rd.root / "라운지" / "훈련기록.md"
    header, rows = read_record_table(rd, path, "훈련기록", ["날짜", "유형"])
    training = {"columns": header, "latest": as_lists(header, latest(rows, LATEST_ROWS)), "total": len(rows)}
    return errors, training


def read_checklists(rd):
    base = rd.root / "자료실" / "교본"
    out = []
    for path in rd.glob(base, "검수체크리스트_*.md"):
        lines = rd.lines(path)
        if lines is None:
            continue
        found = rd.table(path, lines, ["번호", "상태"])
        if found is None:
            rd.warn(path, "표 머리(번호·상태 칸이 있는 줄)를 찾지 못했습니다.")
            continue
        rows = found[1]
        states = Counter(pick(r, "상태") or "(빈칸)" for r in rows)
        out.append({
            "type": path.stem.split("_", 1)[1], "path": rd.rel(path), "total": len(rows),
            "in_use": states.get("사용", 0), "states": states.most_common(),
            "items": [{"no": pick(r, "번호"), "check": pick(r, "확인할 것"), "code": pick(r, "유형 코드"),
                       "severity": pick(r, "중대도")} for r in rows if pick(r, "상태") == "사용"],
        })
    rd.source("검수 체크리스트", base, True, f"{len(out)}개, 사용 항목 {sum(c['in_use'] for c in out)}개")
    return out


# ---------------------------------------------------------------------------
# Build and write

def build(root, today, now=None):
    """Read everything under root and return the dashboard data dict."""
    now = now or dt.datetime.now(KST)
    rd = Reader(root, today)
    teams, due_days = read_skills(rd)
    settings, floors = read_claude(rd, teams)
    schedule = read_schedule(rd)
    cases = read_cases(rd, schedule, teams)
    issues = read_issues(rd)
    errors, training = read_lore(rd)
    checklists = read_checklists(rd)

    status = Counter(c["status"] for c in cases)
    open_cases = [c for c in cases if c["status"] in ("진행 중", "사람 확인 대기")]
    due = [c["deadline"]["dday"] for c in open_cases if c["deadline"]]
    summary = {
        "cases": len(cases), "status": {s: status.get(s, 0) for s in STATUS_ORDER},
        "open": len(open_cases), "due_days": due_days,
        "due_soon": sum(1 for d in due if 0 <= d <= due_days), "overdue": sum(1 for d in due if d < 0),
        "no_open_deadline": sum(1 for c in open_cases if c["no_open_deadline"]),
        "errors_this_month": errors["this_month"], "warnings": len(rd.warnings),
    }
    return {
        "version": VERSION,
        "generated_at": now.isoformat(timespec="seconds"),
        "generated_label": f"{date_label(now.date())} {now:%H:%M}",
        "today": iso(today), "today_label": date_label(today),
        "summary": summary, "cases": cases, "schedule": schedule, "issues": issues,
        "errors": errors, "training": training, "checklists": checklists,
        "settings": settings, "org": {"floors": floors, "teams": teams},
        "sources": rd.sources, "warnings": rd.warnings,
    }


def write_js(data, out):
    """Write window.DASHBOARD_DATA atomically. ASCII-only JSON, so the file reads the same in any charset.
    The temporary file sits next to out as <name>.<random>.tmp, which .gitignore also covers."""
    body = (MARK + " It holds case content: git-ignored, never sync or publish.\n"
            "window.DASHBOARD_DATA = " + json.dumps(data, ensure_ascii=True, indent=1) + ";\n").encode("ascii")
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(out.parent), prefix=out.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:  # binary: no newline translation on Windows
            f.write(body)
        os.replace(tmp, str(out))
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def root_problem(root):
    """Why root is not a project folder, or None."""
    if fs_is_file(root / "CLAUDE.md") and fs_is_dir(root / ".claude"):
        return None
    return (f"저장소 폴더가 아닙니다: {root}\n"
            "CLAUDE.md와 .claude/가 있는 폴더를 --root로 줍니다(빼면 도구/의 위 폴더입니다).")


def out_problem(out, root):
    """Why out must not be written, or None. Keeps case content where .gitignore and the viewer expect it."""
    default = root / "상황실" / OUT_NAME
    if out.name != OUT_NAME:
        return (f"파일 이름은 {OUT_NAME} 그대로 둡니다. 화면은 같은 폴더의 이 이름만 읽고, "
                f".gitignore도 상황실/{OUT_NAME}만 동기화에서 뺍니다.")
    if within(out, root) and not same_path(out, default):
        return (f"저장소 안에서는 상황실/{OUT_NAME}에만 씁니다. "
                "다른 곳에 쓰면 건 내용이 동기화될 수 있습니다.")
    try:
        if out.is_dir():
            return "같은 이름의 폴더가 있습니다."
        with open(str(out), "rb") as f:
            head = f.read(len(MARK.encode("ascii")))
    except FileNotFoundError:
        return None
    except OSError as e:
        return f"이미 있는 파일을 확인하지 못했습니다({e.strerror or e})."
    if head != MARK.encode("ascii"):
        return "이미 있는 파일이 이 도구가 만든 데이터 파일이 아니라서 덮어쓰지 않습니다."
    return None


def due_label(days):
    return "오늘 마감" if days == 0 else f"{days}일 안 마감"


def summary_lines(data, out_label):
    s, c = data["summary"], data["schedule"]["counts"]
    st = s["status"]
    extra = f" · 기록 없음 {st['기록 없음']}" if st["기록 없음"] else ""
    bad = f", 날짜 오류 {c['bad']}" if c["bad"] else ""
    lost = f" · 열린 마감 없음 {s['no_open_deadline']}건" if s.get("no_open_deadline") else ""
    tail = ":" if s["warnings"] else ""
    lines = [
        f"기준일 {data['today_label']} · 데이터 파일 {out_label}",
        f"- 건 {s['cases']}개: 진행 중 {st['진행 중']} · 사람 확인 대기 {st['사람 확인 대기']} · 종결 {st['종결']}{extra}",
        f"- {due_label(s['due_days'])} {s['due_soon']}건 · 지난 마감 {s['overdue']}건{lost} (열린 건 기준)",
        f"- 일정: 지난 미완료 {c['past']} · 오늘부터 {NEXT_DAYS}일 {c['next']} · 그 뒤 {c['later']}"
        f" (완료·취소 {c['closed']}{bad})",
        f"- 이번 달 오류노트 {s['errors_this_month']}줄",
        f"- 경고 {s['warnings']}건{tail}",
    ]
    lines += [f"  [경고] {w['path']}: {w['message']}" for w in data["warnings"]]
    return lines


def parse_today(text):
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"날짜 형식이 아닙니다: {text} (예: 2026-11-05)") from None


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.version_info < MIN_PYTHON:
        print("Python {}.{} 이상이 필요합니다(지금 {}.{}).".format(*MIN_PYTHON, *sys.version_info[:2]))
        return 2
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--today", type=parse_today, help="기준일 YYYY-MM-DD (기본: 오늘, 한국 시각)")
    ap.add_argument("--root", help="저장소 폴더, CLAUDE.md와 .claude/가 있는 곳 (기본: 도구/의 위 폴더)")
    ap.add_argument("--out", help=f"만들 데이터 파일, 이름은 {OUT_NAME} (기본: <root>/상황실/{OUT_NAME})")
    ap.add_argument("--selftest", action="store_true", help="가상의 임시 저장소로 자체 점검")
    a = ap.parse_args(argv[1:])
    if a.selftest:
        return selftest()

    root = Path(a.root).resolve() if a.root else ROOT
    problem = root_problem(root)
    if problem:
        print(problem)
        return 2
    today = a.today or dt.datetime.now(KST).date()
    out = Path(a.out).resolve() if a.out else root / "상황실" / OUT_NAME
    problem = out_problem(out, root)
    if problem:
        print(f"데이터 파일을 쓰지 않았습니다: {out}\n{problem}")
        return 2
    try:
        data = build(root, today)
    except Exception as e:  # inputs are guarded; this keeps the exit-code contract if a bug slips through
        traceback.print_exc()
        print(f"데이터를 만들지 못했습니다(도구 오류: {e!r}). 데이터 파일은 바꾸지 않았습니다.")
        return 2
    try:
        write_js(data, out)
    except OSError as e:
        print(f"데이터 파일을 쓰지 못했습니다: {out} ({e.strerror or e})")
        return 2
    try:
        out_label = out.relative_to(root).as_posix()
    except ValueError:
        out_label = str(out)
    print("대시보드 데이터를 만들었습니다.")
    for line in summary_lines(data, out_label):
        print(line)
    html = out.parent / "대시보드.html"
    if fs_is_file(html):
        try:
            html_label = html.relative_to(root).as_posix()
        except ValueError:
            html_label = str(html)
        print(f"보기: {html_label} 을 브라우저로 엽니다(이미 열려 있으면 새로 고침).")
    else:
        print("보기: 상황실/대시보드.html을 데이터 파일과 같은 폴더에 두고 브라우저로 엽니다.")
    print("이 데이터 파일은 건 내용을 담으므로 동기화하거나 게시하지 않습니다.")
    return 0


# ---------------------------------------------------------------------------
# Selftest: a temporary fictional project (no real names, bills or institutions)

SELFTEST_FILES = {
    "CLAUDE.md": """# 회의실

## 운영 설정
| 항목 | 값 | 상태 |
|---|---|---|
| 기관·부서 | (입력 필요) | 기본값 |
| 최종 검수자 호칭 | 검수관 | 확인 |
| 보완 한도 | 2회 | 기본값 |

## 건물 배치
- 3F 관제·인프라: 서버실(도구), 상황실(`/ops-desk`, 아침 뉴스는 `/ops-desk 뉴스`)
- 2F 실무: 법제팀(`/lawdraft`)
- 1F 사람·외부: 나(최종 검수자), 라운지(`라운지/`)
""",
    ".claude/skills/lawdraft/SKILL.md": """---
name: lawdraft
description: 법제팀 팀장. 의뢰서를 받아 조문 초안을 만든다. "법제 시작" 요청 시 사용.
argument-hint: "[의뢰서 파일 경로]"
---

# 법제팀 팀장

## 팀 설정
| 항목 | 값 |
|---|---|
""",
    ".claude/skills/ops-desk/SKILL.md": """---
name: ops-desk
description: 상황실 팀장. 메일과 일정을 한 장 브리핑으로 만든다. "브리핑" 요청 시 사용.
argument-hint: "[오늘|뉴스]"
---

# 상황실 팀장

## 팀 설정
| 항목 | 값 |
|---|---|
| 다가오는 마감 표시 | 7일 |
""",
    ".claude/agents/lawdraft-writer.md": "---\nname: lawdraft-writer\ndescription: 법제팀 실무. 조문을 쓴다.\n---\n",
    ".claude/agents/lawdraft-checker.md": "---\nname: lawdraft-checker\ndescription: 법제팀 검증. 조문을 대조한다.\n---\n",
    "상황실/통합일정표.md": """# 통합일정표

| 날짜(요일) | 시각 | 일 | 종류 | 건 | 출처 | 역산 기준 | 상태 | 일정 ID | 캘린더 |
|---|---|---|---|---|---|---|---|---|---|
| 2026. 10. 30.(금) | - | 지난 회의 | 회의 | - | - | - | 완료 | S-20261020-E5F6 | - |
| 2026. 11. 2.(월) | 14:00 | 입안 방향 회신 | 마감 | 20261028_△△법(일부)_김** | 가상 | - | 확정 | S-20261101-C3D4 | - |
| 2026. 11. 6.(금) | - | 옛 배부 기한 | 마감 | 20261102_○○법(일부)_홍길동 | 가상 | - | 취소 | S-20261023-3A3B | - |
| 2026. 11. 8.(일) | - | 검토보고서 배부 기한 | 마감 | 20261102_○○법(일부)_홍길동 | 가상 | S-20261023-3A3B 대체 | 제안 | S-20261101-A1B2 | - |
| 2026. 11. 18.(수) | 10:00 | 소위 상정 | 회의 | - | 가상 | - | 제안 | S-20261022-1C1D | - |
| 2026. 11. 19.(목) | - | 자료 제출 | 제출 | - | 가상 | - | 확정 | S-20261022-2E2F | - |
| 2026. 11. 30.(월) | - | 예산 검토 기한 | 마감 | - | 가상 | - | 제안 | S-20261021-0A0B | - |
| 2026. 13. 1. | - | 날짜가 틀린 줄 | 마감 | - | 가상 | - | 제안 | S-20261024-4C4D | - |
| 2026. 11. 10.(화) | - | 첫 회신 기한 | 마감 | 20261103_◇◇법(일부)_홍길동 | 가상 | 2026. 11. 12. D-2 | 취소 | S-20261021-1111 | - |
| 2026. 11. 12.(목) | - | 둘째 회신 기한 | 마감 | 20261103_◇◇법(일부)_홍길동 | 가상 | S-20261021-1111 대체 | 취소 | S-20261025-2222 | - |
| 2026. 11. 16.(월) | - | 회신 기한 | 마감 | 20261103_◇◇법(일부)_홍길동 | 가상 | 2026. 11. 18. D-2, S-20261025-2222 대체 | 확정 | S-20261103-3333 | - |
| 2026. 11. 11.(수) | - | 고리 1 | 마감 | - | 가상 | S-20261026-6666 대체 | 취소 | S-20261026-5555 | - |
| 2026. 11. 11.(수) | - | 고리 2 | 마감 | - | 가상 | S-20261026-5555 대체 | 취소 | S-20261026-6666 | - |
""",
    "상황실/현안목록.md": """# 현안목록

| 건 폴더 | 팀 | 공개 키워드 | 대상 법령 | 공개 의안번호 | 승인일 | 상태 |
|---|---|---|---|---|---|---|
| 20261102_법안검토_○○법 | 법안검토팀 | ○○법 개정 | ○○법 | XXXXXXX | 2026. 11. 2. | 진행 |
""",
    "라운지/오류노트.md": """# 오류노트

| 날짜 | 팀 | 건 | 유형 | 발견자 | 내용 (한 줄) | 다음에 볼 곳 |
|---|---|---|---|---|---|---|
| 2026. 10. 20. | 법제팀 | 건-A1A1A1 | 인용 | 검증 | 지시문의 항 번호가 현행과 다름 | 자료실/규칙/조문대조.md |
| 2026-11-03 | 법제팀 | 건-B2B2B2 | 인용 | 사람 | 부칙 시행일이 빠짐 | 검증 놓침 |
""",
    "라운지/훈련기록.md": """# 훈련기록

| 날짜 | 유형 | 심은 오류 수 | 찾은 수 | 놓친 유형 | 소요 시간 |
|---|---|---|---|---|---|
| 2026. 10. 30. | 법제 | 5 | 4 | 인용 | 15분 |
""",
    "자료실/교본/검수체크리스트_법제.md": """# 검수체크리스트 — 법제

| 번호 | 확인할 것 (검증이 확인할 수 있는 한 문장) | 유형 코드 | 중대도 | 출처 (오류노트·상급자 피드백·사람) | 근거 (익명 ID·날짜) | 넣은 날 | 상태 |
|---|---|---|---|---|---|---|---|
| 1 | 지시문의 조·항·호가 현행 조문에 있는지 확인한다 | 인용 | 중대 | 오류노트 | 건-A1A1A1 · 2026-10-20 | 2026-10-23 | 사용 |
| 2 | 부칙에 시행일이 있는지 확인한다 | 누락 | 중대 | 사람 | 건-B2B2B2 · 2026-11-03 | 2026-11-04 | 사용 |
| 3 | 옛 항목 | 형식 | 경미 | 사람 | 2026-10-01 | 2026-10-02 | 폐지 |
""",
    "산출물/20261102_법안검토_○○법/_진행.md": """# 진행기록
- 건: 20261102_법안검토_○○법
- 익명 ID: 건-C3C3C3
- 팀: 법안검토
- 접수일: 2026. 11. 2.
- 대상: ○○법 일부개정법률안
- 넘겨받은 자료: 없음
- 마감: S-20261023-3A3B(취소), S-20261101-A1B2
- 현재 단계: 4 검증
- 다음 할 일: 검증 2회차 지적 반영

## 사람 결정
| 일시 | 단계 | 물은 것 (선택지) | 답 (원문 그대로) |
|---|---|---|---|
| 2026-11-03 10:00 | 2 쟁점 | 쟁점 A·B 수위 | A안 |

## 검증 회차
| 일시 | 회차 | 판정 | 지적 수 (중대·보통·경미) | 비고 (예: 한도 미산입 — 상급자 F1~F3) |
|---|---|---|---|---|
| 2026-11-03 15:00 | 1 | 보완 | 1·2·0 | - |
| 2026-11-04 11:00 | 2 | 통과 | 0·1·1 | - |

## 승인
| 일시 | 승인자 | 승인한 파일 | 사람이 검수 중 직접 고친 곳 |
|---|---|---|---|
""",
    "산출물/20261028_법제_△△법/_진행.md": """# 진행기록
- 건: 20261028_법제_△△법
- 팀: 법제팀
- 접수일: 2026. 10. 28.
- 마감: S-20261101-C3D4, S-20261101-FFFF
- 현재 단계: 2 입안 방향 확인
- 다음 할 일: [사람 확인] 입안 방향 B안 채택 여부
""",
    "산출물/20261015_조사_□□ 제도/_진행.md": """# 진행기록
- 건: 20261015_조사_□□ 제도
- 팀: research
- 접수일: 2026. 10. 15.
- 마감: S-20261020-E5F6
- 현재 단계: 6 종결
- 다음 할 일: 없음(종결)

## 승인
| 일시 | 승인자 | 승인한 파일 | 사람이 검수 중 직접 고친 곳 |
|---|---|---|---|
| 2026-10-29 17:00 | 검수관 | 04_최종_조사노트.md | 없음 |
""",
    "산출물/20261104_예결산_2027년도 예산안/원자료/.keep": "",
    # 마감 names only the first row of a 대체 chain (1111 취소 → 2222 취소 → 3333 확정)
    "산출물/20261103_심사지원_◇◇법/_진행.md": """# 진행기록
- 건: 20261103_심사지원_◇◇법
- 팀: 심사지원
- 접수일: 2026. 11. 3.
- 마감: S-20261021-1111
- 현재 단계: 2 안건 목록
- 다음 할 일: 쟁점 비교표 작성
""",
    # open case whose 마감 rows are 완료, unreadable and a 대체 cycle: no open deadline
    "산출물/20261101_법제_▽▽법/_진행.md": """# 진행기록
- 건: 20261101_법제_▽▽법
- 팀: 법제
- 접수일: 2026. 11. 1.
- 마감: S-20261020-E5F6, S-20261024-4C4D, S-20261026-5555
- 현재 단계: 3 조문 입안
- 다음 할 일: 조문 초안 보완
""",
}
SELFTEST_UNREADABLE = "산출물/20261030_예결산_☆☆ 결산/_진행.md"  # created as a folder: cannot be read


def selftest():
    failures, checks = [], [0]

    def check(cond, message):
        checks[0] += 1
        if not cond:
            failures.append(message)

    def run(*args):
        """main() with captured output: (exit code, printed text)."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["대시보드갱신.py", "--today", "2026-11-05"] + list(args))
        return code, buf.getvalue()

    today = dt.date(2026, 11, 5)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "project"
        for rel, text in SELFTEST_FILES.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        (root / SELFTEST_UNREADABLE).mkdir(parents=True)
        data = build(root, today)
        cases = {c["folder"]: c for c in data["cases"]}
        a = cases.get("20261102_법안검토_○○법", {})
        b = cases.get("20261028_법제_△△법", {})
        c = cases.get("20261015_조사_□□ 제도", {})
        d = cases.get("20261104_예결산_2027년도 예산안", {})
        e = cases.get("20261103_심사지원_◇◇법", {})
        f = cases.get("20261101_법제_▽▽법", {})
        g = cases.get("20261030_예결산_☆☆ 결산", {})
        check(len(cases) == 7, f"건 7개여야 합니다: {sorted(cases)}")
        check(a.get("status") == "진행 중", f"진행 중 건의 상태: {a.get('status')}")
        check(b.get("status") == "사람 확인 대기", f"사람 확인 건의 상태: {b.get('status')}")
        check(c.get("status") == "종결", f"종결 건의 상태: {c.get('status')}")
        check(d.get("status") == "기록 없음", f"_진행.md 없는 건의 상태: {d.get('status')}")
        check(g.get("status") == "기록 없음" and any("읽지 못했습니다" in w for w in g.get("warnings", [])),
              f"읽지 못하는 _진행.md(같은 이름의 폴더): {g}")
        check((a.get("deadline") or {}).get("id") == "S-20261101-A1B2", f"취소 줄을 건너뛴 마감: {a.get('deadline')}")
        check((a.get("deadline") or {}).get("dday") == 3 and (a.get("deadline") or {}).get("via") == [],
              f"진행 중 건 D-3(마감 칸에 새 ID가 있어 바로 찾음): {a.get('deadline')}")
        check((b.get("deadline") or {}).get("dday") == -3, f"지난 마감 D+3: {b.get('deadline')}")
        check(c.get("deadline") is None and c.get("deadline_note") and not c.get("no_open_deadline"),
              f"완료 일정만 있는 종결 건(경고 없음): {c}")
        check((e.get("deadline") or {}).get("id") == "S-20261103-3333" and (e.get("deadline") or {}).get("dday") == 11
              and (e.get("deadline") or {}).get("via") == ["S-20261021-1111", "S-20261025-2222"],
              f"대체 줄을 두 번 따라간 마감: {e.get('deadline')}")
        check(f.get("deadline") is None and f.get("no_open_deadline")
              and f.get("deadline_issues") == {"closed": ["S-20261020-E5F6", "S-20261026-5555 → S-20261026-6666"],
                                               "bad": ["S-20261024-4C4D"], "missing": []},
              f"열린 마감이 없는 열린 건(완료·날짜 오류·대체 고리): {f.get('deadline_issues')}")
        check(all(x in f.get("deadline_note", "") for x in ISSUE_LABELS.values() if x != "표에 없음"),
              f"마감 메모의 나눔: {f.get('deadline_note')}")
        check(a.get("team") == "법안검토" and b.get("team") == "법제팀" and c.get("team") == "research",
              f"팀 이름: {a.get('team')}, {b.get('team')}, {c.get('team')}")
        check(d.get("team") == "예결산" and d.get("received") == "2026-11-04", f"폴더 이름에서 읽은 팀·접수일: {d}")
        check(a.get("received") == "2026-11-02", f"접수일: {a.get('received')}")
        check(a.get("last_check") == {"round": 2, "verdict": "통과", "when": "2026-11-04 11:00", "findings": "0·1·1"},
              f"최근 검증: {a.get('last_check')}")
        check(a.get("check_count") == 2 and a.get("decision_count") == 1, "검증 회차·사람 결정 수")
        check(c.get("approval_count") == 1 and (c.get("last_approval") or {}).get("who") == "검수관", "승인 기록")
        s = data["summary"]
        check(s["status"] == {"사람 확인 대기": 1, "진행 중": 3, "기록 없음": 2, "종결": 1}, f"상태 수: {s['status']}")
        check(s["open"] == 4 and s["due_soon"] == 1 and s["overdue"] == 1 and s["due_days"] == 7
              and s["no_open_deadline"] == 1, f"마감 요약: {s}")
        check(s["errors_this_month"] == 1, f"이번 달 오류노트: {s['errors_this_month']}")
        order = [x["folder"] for x in data["cases"]]
        check(order == ["20261028_법제_△△법", "20261102_법안검토_○○법", "20261103_심사지원_◇◇법", "20261101_법제_▽▽법",
                        "20261104_예결산_2027년도 예산안", "20261030_예결산_☆☆ 결산", "20261015_조사_□□ 제도"],
              f"건 순서(사람 확인 대기 먼저, 가까운 마감 먼저): {order}")
        counts = data["schedule"]["counts"]
        check(counts == {"past": 1, "next": 3, "later": 2, "closed": 6, "bad": 1}, f"일정 구간: {counts}")
        by_id = {r["id"]: r for r in data["schedule"]["rows"]}
        check(by_id["S-20261022-1C1D"]["bucket"] == "next" and by_id["S-20261022-1C1D"]["dday"] == 13, "14일 구간 끝(D-13)")
        check(by_id["S-20261022-2E2F"]["bucket"] == "later" and by_id["S-20261022-2E2F"]["dday"] == 14, "그 뒤 구간 시작(D-14)")
        check(by_id["S-20261023-3A3B"]["bucket"] == "closed", "취소 줄은 닫힌 구간")
        check(data["schedule"]["next_end"] == "2026-11-18", f"14일 구간 끝 날짜: {data['schedule']['next_end']}")
        check(data["issues"]["open"] == 1 and len(data["issues"]["rows"]) == 1, "현안목록")
        er = data["errors"]
        check(er["total"] == 2 and er["by_type"] == [("인용", 2)] and dict(er["by_finder"]) == {"검증": 1, "사람": 1},
              f"오류노트 집계: {er['by_type']}, {er['by_finder']}")
        check(er["latest"][0][0] == "2026-11-03", "오류노트 최신순")
        check(data["training"]["total"] == 1, "훈련기록")
        cl = data["checklists"]
        check(len(cl) == 1 and cl[0]["type"] == "법제" and cl[0]["in_use"] == 2 and dict(cl[0]["states"]) == {"사용": 2, "폐지": 1}
              and len(cl[0]["items"]) == 2, f"체크리스트 집계: {cl}")
        check([x["state"] for x in data["settings"]] == ["기본값", "확인", "기본값"], "운영 설정")
        floors = data["org"]["floors"]
        teams = data["org"]["teams"]
        check([fl["floor"] for fl in floors] == ["3F", "2F", "1F"], f"층: {[fl['floor'] for fl in floors]}")
        check(floors[0]["rooms"][1]["commands"] == ["/ops-desk", "/ops-desk 뉴스"] and floors[0]["rooms"][1]["teams"] == ["ops-desk"],
              f"상황실 명령: {floors[0]['rooms'][1]}")
        check([x["role"] for x in teams["lawdraft"]["agents"]] == ["실무", "검증"] and teams["lawdraft"]["name"] == "법제팀",
              f"법제팀 역할: {teams.get('lawdraft')}")
        messages = [w["message"] for w in data["warnings"]]
        check(any("_진행.md가 없습니다" in m for m in messages), "경고: _진행.md 없음")
        check(any("_진행.md를 읽지 못했습니다" in m for m in messages), "경고: _진행.md를 읽지 못함")
        check(any("S-20261101-FFFF" in m for m in messages), "경고: 통합일정표에 없는 일정 ID")
        check(any("날짜를 읽지 못했습니다" in m for m in messages), "경고: 날짜 오류 줄")
        check(any(m.startswith("열린 건인데") and "S-20261024-4C4D" in m for m in messages), "경고: 열린 마감이 없는 열린 건")
        check(len(messages) == 5, f"경고는 5건이어야 합니다: {messages}")
        check(s["warnings"] == 5, "요약의 경고 수")
        lines = summary_lines(data, "x")
        check(any("열린 마감 없음 1건" in x for x in lines) and due_label(0) == "오늘 마감", f"요약 줄: {lines}")
        check(pick({"일정 ID": "S-1"}, "일") == "" and pick({"날짜(요일)": "x"}, "날짜") == "x"
              and pick({"내용 (한 줄)": "y"}, "내용") == "y", "칸 이름 일치(앞부분만 같은 칸은 고르지 않음)")

        out = root / "상황실" / OUT_NAME
        write_js(data, out)
        text = out.read_text(encoding="ascii")
        body = text.split("window.DASHBOARD_DATA = ", 1)[-1].rstrip().rstrip(";")
        check(text.startswith(MARK) and text.isascii() and json.loads(body) == json.loads(json.dumps(data)),
              "데이터 파일을 다시 읽으면 같아야 합니다")
        check(not list(out.parent.glob("*.tmp")), "임시 파일이 남지 않아야 합니다")

        # --out and --root guards (exit code 2, nothing written)
        html = root / "상황실" / "대시보드.html"
        html.write_text("<!doctype html>", encoding="utf-8")
        code, _ = run("--root", str(root), "--out", str(html))
        check(code == 2 and html.read_text(encoding="utf-8") == "<!doctype html>", "--out: 다른 이름은 쓰지 않음")
        code, _ = run("--root", str(root), "--out", str(root / "라운지" / OUT_NAME))
        check(code == 2 and not (root / "라운지" / OUT_NAME).exists(), "--out: 저장소 안의 다른 폴더는 쓰지 않음")
        foreign = Path(tmp) / "elsewhere" / OUT_NAME
        foreign.parent.mkdir()
        foreign.write_text("keep me", encoding="utf-8")
        code, _ = run("--root", str(root), "--out", str(foreign))
        check(code == 2 and foreign.read_text(encoding="utf-8") == "keep me", "--out: 도구가 만들지 않은 파일은 덮어쓰지 않음")
        code, printed = run("--root", str(root), "--out", str(Path(tmp) / "copy" / OUT_NAME))
        check(code == 0 and (Path(tmp) / "copy" / OUT_NAME).read_text(encoding="ascii").startswith(MARK),
              f"--out: 저장소 밖 새 파일은 씀 ({printed.strip()[:80]})")
        code, printed = run("--root", str(root))
        check(code == 0 and "경고 5건" in printed, f"기본 경로에 다시 씀: {printed.strip()[:120]}")
        check(not list(out.parent.glob("*.tmp")), "임시 파일이 남지 않아야 합니다(다시 쓴 뒤)")
        nope = Path(tmp) / "nope"
        code, _ = run("--root", str(nope))
        check(code == 2 and not nope.exists(), "--root: 없는 폴더면 멈추고 아무것도 만들지 않음")

        # Unlistable 산출물/ and entries that cannot be checked (pathlib raises PermissionError)
        iterdir, is_dir = Path.iterdir, Path.is_dir

        def denied_iterdir(self):
            if self.name == "산출물":
                raise PermissionError(13, "Permission denied")
            return iterdir(self)

        def denied_is_dir(self):
            if self.parent.name == "산출물":
                raise PermissionError(13, "Permission denied")
            return is_dir(self)

        for patch, attr, expect in ((denied_iterdir, "iterdir", "산출물 폴더를 읽지 못했습니다"),
                                    (denied_is_dir, "is_dir", "건 폴더인지 확인하지 못했습니다")):
            setattr(Path, attr, patch)
            try:
                data = build(root, today)
                check(data["cases"] == [] and any(expect in w["message"] for w in data["warnings"]),
                      f"권한 없음({attr}): {[w['message'] for w in data['warnings']][:3]}")
            except Exception as ex:
                check(False, f"권한 없음({attr})에서 멈춤: {ex!r}")
            finally:
                setattr(Path, attr, iterdir if attr == "iterdir" else is_dir)

        # A 통합일정표 without the 일 and 역산 기준 columns: warn, never show the ID as the name
        bare = Path(tmp) / "bare"
        (bare / "상황실").mkdir(parents=True)
        (bare / "상황실" / "통합일정표.md").write_text(
            "| 날짜(요일) | 상태 | 일정 ID |\n|---|---|---|\n| 2026. 11. 9.(월) | 제안 | S-20261101-0C0C |\n", encoding="utf-8")
        rd = Reader(bare, today)
        sched = read_schedule(rd)
        bare_msgs = [w["message"] for w in rd.warnings]
        check(sched["rows"][0]["what"] == "" and any("'일' 칸이 없습니다" in m for m in bare_msgs)
              and any("'역산 기준' 칸이 없습니다" in m for m in bare_msgs), f"칸이 빠진 통합일정표: {bare_msgs}")

        empty = Path(tmp) / "empty"
        empty.mkdir()
        code, _ = run("--root", str(empty))
        check(code == 2 and not (empty / "상황실").exists(), "--root: 저장소 폴더가 아니면 멈춤")
        try:
            data = build(empty, today)
            check(data["cases"] == [] and data["summary"]["cases"] == 0, "빈 저장소: 건 0개")
            check(data["summary"]["warnings"] >= 5, f"빈 저장소: 읽지 못한 파일마다 경고 ({data['summary']['warnings']}건)")
        except Exception as ex:  # the dashboard must never crash on missing inputs
            check(False, f"빈 저장소에서 멈춤: {ex!r}")

    if failures:
        print(f"자체 점검 실패: {len(failures)}건 / 확인 {checks[0]}개")
        for msg in failures:
            print(f"  [실패] {msg}")
        return 1
    print(f"자체 점검 통과: 확인 {checks[0]}개 (가상 건 7개, 일정 13줄, 경고 5건)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
