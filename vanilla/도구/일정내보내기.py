#!/usr/bin/env python3
"""Check 상황실/통합일정표.md against the calendar state, and export an .ics file.

    python3 도구/일정내보내기.py 점검 [--table 상황실/통합일정표.md]
    python3 도구/일정내보내기.py ics <.ics 파일> [--all] [--table ...]
    (Windows: py -3 도구\\일정내보내기.py ...)

The table header rule (상황실/통합일정표.md) is the only definition of the columns.
This script never edits the table; the ops desk writes the 캘린더 cell after the person
approves and the event is really in the calendar.

점검 (both connector and .ics paths) lists:
  - 보낼 줄: 상태 확정, 캘린더 "-"
  - 바뀐 줄: already sent (gcal:/ics) but 날짜·시각·제목 differ from the fingerprint written
    when it was sent, or 상태 is no longer 확정/완료
  - 지울 줄: already sent and 상태 취소
  - 읽지 못한 줄: bad 일정 ID, duplicate 일정 ID, bad 상태/캘린더 value, or a date, time or
    weekday that cannot be right (checked on every 확정/완료 row, already sent or not)
  For each sendable row it prints the fingerprint to write in the 캘린더 cell
  (for example "gcal:<id> #a1b2c3" or "ics 2026-11-05 #a1b2c3").
ics writes 보낼 줄 (or with --all every 확정 row) as VEVENTs: title "<건> · <일>",
  description "통합일정표에서 옮김 · 일정 ID ...", no attendees, no alarms,
  UID "<일정 ID>@legal-team", times in Asia/Seoul. An .ics import may not update or remove
  events that already exist, so 바뀐 줄 and 지울 줄 must be fixed in the calendar by hand.
Exit code 0 = nothing wrong, 1 = some rows could not be read, 2 = bad arguments or table.
"""
import argparse
import datetime as dt
import hashlib
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COLUMNS = ["날짜(요일)", "시각", "일", "종류", "건", "출처", "역산 기준", "상태", "일정 ID", "캘린더"]
STATES = {"제안", "확정", "완료", "취소"}
DATE = re.compile(r"(\d{4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})")
TIME = re.compile(r"^(\d{1,2}):(\d{2})(?:\s*[~\-–]\s*(\d{1,2}):(\d{2}))?$")
ROW_ID = re.compile(r"^S-\d{8}-[0-9A-F]{4}$")
CASE = re.compile(r"^(-|\d{8}_.+)$")
SENT = re.compile(r"^(gcal:\S+|ics \d{4}-\d{2}-\d{2})\s+#([0-9a-f]{6})$")
EXTERNAL = re.compile(r"^외부:\S+$")
WEEKDAYS = "월화수목금토일"


def cells(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def read_rows(path):
    """Return (rows, problems). Reading stops at the first non-table line after the header."""
    lines = path.read_text(encoding="utf-8").splitlines()
    header_at = next((i for i, l in enumerate(lines) if l.strip().startswith("|") and "일정 ID" in l), None)
    if header_at is None:
        raise ValueError("표 머리(일정 ID 칸이 있는 줄)를 찾지 못했습니다.")
    header = cells(lines[header_at])
    missing = [c for c in COLUMNS if c not in header]
    if missing:
        raise ValueError(f"표 머리에 칸이 없습니다: {', '.join(missing)}")
    rows, problems = [], []
    for n, line in enumerate(lines[header_at + 2:], start=header_at + 3):
        if not line.strip().startswith("|"):
            break
        values = cells(line)
        if len(values) != len(header):
            problems.append(f"{n}줄: 칸 수가 머리와 다릅니다({len(values)}/{len(header)})")
            continue
        row = dict(zip(header, values))
        row["_line"] = n
        rows.append(row)
    return rows, problems


def title_of(row):
    return row["일"] if row["건"] == "-" else f"{row['건']} · {row['일']}"


def clock(hour, minute, text):
    try:
        return dt.time(int(hour), int(minute))
    except ValueError:
        raise ValueError(f"없는 시각입니다: {text}") from None


def when(row):
    """Return (start, end, all_day, note) in Asia/Seoul wall time, or raise ValueError."""
    date_text = row["날짜(요일)"]
    dates = DATE.findall(date_text)
    if not dates:
        raise ValueError("날짜를 읽지 못했습니다")
    if len(dates) > 1 or "~" in date_text:
        raise ValueError("날짜가 둘 이상입니다(여러 날 일정은 첫날·끝날을 두 줄로 쓴다)")
    y, m, d = (int(x) for x in dates[0])
    try:
        day = dt.date(y, m, d)
    except ValueError:
        raise ValueError(f"없는 날짜입니다: {date_text}") from None
    wd = re.search(r"\(([월화수목금토일])\)", date_text)
    if wd and wd.group(1) != WEEKDAYS[day.weekday()]:
        raise ValueError(f"요일이 날짜와 다릅니다: {date_text} (그날은 {WEEKDAYS[day.weekday()]}요일)")
    t = row["시각"]
    if t == "-":
        return day, day + dt.timedelta(days=1), True, ""
    tm = TIME.match(t)
    if not tm:
        raise ValueError(f"시각을 읽지 못했습니다: {t}")
    start = dt.datetime.combine(day, clock(tm.group(1), tm.group(2), t))
    if not tm.group(3):
        return start, start + dt.timedelta(hours=1), False, ""
    end = dt.datetime.combine(day, clock(tm.group(3), tm.group(4), t))
    if end == start:
        raise ValueError(f"시각 범위의 끝이 시작과 같습니다: {t}")
    if end < start:
        return start, end + dt.timedelta(days=1), False, "끝 시각이 시작보다 앞서 다음 날로 봄"
    return start, end, False, ""


def fingerprint(row):
    return hashlib.sha1(f"{row['날짜(요일)']}|{row['시각']}|{title_of(row)}".encode("utf-8")).hexdigest()[:6]


def esc(text):
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line):
    """Fold to 75 octets per RFC 5545 without splitting a UTF-8 character."""
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > (75 if not out else 74):
            out.append(cur)
            cur = b""
        cur += b
    out.append(cur)
    return "\r\n ".join(part.decode("utf-8") for part in out)


def event_lines(row, stamp):
    start, end, all_day, _ = when(row)
    lines = ["BEGIN:VEVENT", f"UID:{row['일정 ID']}@legal-team", f"DTSTAMP:{stamp}"]
    if all_day:
        lines += [f"DTSTART;VALUE=DATE:{start:%Y%m%d}", f"DTEND;VALUE=DATE:{end:%Y%m%d}"]
    else:
        lines += [f"DTSTART;TZID=Asia/Seoul:{start:%Y%m%dT%H%M%S}", f"DTEND;TZID=Asia/Seoul:{end:%Y%m%dT%H%M%S}"]
    lines += [f"SUMMARY:{esc(title_of(row))}",
              f"DESCRIPTION:{esc('통합일정표에서 옮김 · 일정 ID ' + row['일정 ID'])}",
              "TRANSP:TRANSPARENT", "END:VEVENT"]
    return lines


def classify(rows, problems):
    """Split rows into to_send, changed, to_delete, sent_ok. Bad rows go to problems."""
    counts = Counter(r["일정 ID"] for r in rows)
    to_send, changed, to_delete, sent_ok = [], [], [], []
    for row in rows:
        rid, state, cal, n = row["일정 ID"], row["상태"], row["캘린더"], row["_line"]
        if not ROW_ID.match(rid):
            problems.append(f"{n}줄: 일정 ID 형식이 아닙니다({rid or '빈칸'}). 형식은 S-YYYYMMDD-XXXX")
            continue
        if counts[rid] > 1:
            problems.append(f"{n}줄: 일정 ID {rid}가 {counts[rid]}줄에 있습니다(한 줄만 남기고 새 ID를 정하세요)")
            continue
        if state not in STATES:
            problems.append(f"{n}줄 {rid}: 상태 값이 아닙니다({state}). 제안·확정·완료·취소 가운데 하나")
            continue
        if not CASE.match(row["건"]):
            problems.append(f"{n}줄 {rid}: 건 칸 형식이 아닙니다({row['건']}). '-' 또는 '접수일_제명(개정범위)_이름'")
            continue
        if EXTERNAL.match(cal):
            continue  # an event that came from the calendar; never created, changed or deleted by us
        if state in ("확정", "완료"):  # sent rows too: a bad date must not reach the calendar as a 바뀐 줄
            try:
                when(row)
            except ValueError as e:
                problems.append(f"{n}줄 {rid}: {e}")
                continue
        if cal == "-":
            if state == "확정":
                to_send.append(row)
            continue
        m = SENT.match(cal)
        if not m:
            problems.append(f"{n}줄 {rid}: 캘린더 칸 형식이 아닙니다({cal}). '-', 'gcal:<ID> #지문', 'ics YYYY-MM-DD #지문', '외부:<ID>'")
            continue
        if state == "취소":
            to_delete.append(row)
        elif state not in ("확정", "완료"):
            changed.append((row, f"상태가 확정이 아님({state}) — 캘린더에서 지울지 사람에게 묻는다"))
        elif m.group(2) != fingerprint(row):
            changed.append((row, "날짜·시각·제목이 보낸 뒤 바뀜"))
        else:
            sent_ok.append(row)
    return to_send, changed, to_delete, sent_ok


def describe(row):
    return f"{row['일정 ID']} {row['날짜(요일)']} {row['시각']} {title_of(row)}"


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_check = sub.add_parser("점검", help="보낼·바뀐·지울 줄과 지문을 보여 준다")
    p_ics = sub.add_parser("ics", help="보낼 줄을 .ics로 쓴다")
    p_ics.add_argument("out", help="만들 .ics 파일 (예: 발송실/통합일정표_20261105_0900.ics)")
    p_ics.add_argument("--all", action="store_true", help="확정 줄을 모두 내보낸다(새 캘린더용)")
    for p in (p_check, p_ics):
        p.add_argument("--table", default=str(ROOT / "상황실" / "통합일정표.md"))
    a = ap.parse_args(argv[1:])

    if a.cmd == "ics":
        out = Path(a.out)
        if out.suffix.lower() != ".ics":
            print("내보낼 파일 이름은 .ics로 끝나야 합니다.")
            return 2
        if out.exists():
            print(f"이미 있는 파일입니다: {out} (새 실행 시각으로 이름을 정하세요)")
            return 2
    try:
        rows, problems = read_rows(Path(a.table))
    except (OSError, ValueError) as e:
        print(f"통합일정표를 읽지 못했습니다: {e}")
        return 2
    to_send, changed, to_delete, sent_ok = classify(rows, problems)

    if a.cmd == "ics":
        export = to_send + (sent_ok + [r for r, _ in changed] if a.all else [])
        export = [r for r in export if r["상태"] == "확정"]
        if export:
            stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            body = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//legal-team//통합일정표//KO", "CALSCALE:GREGORIAN",
                    "METHOD:PUBLISH", "BEGIN:VTIMEZONE", "TZID:Asia/Seoul", "BEGIN:STANDARD",
                    "DTSTART:19700101T000000", "TZOFFSETFROM:+0900", "TZOFFSETTO:+0900", "TZNAME:KST",
                    "END:STANDARD", "END:VTIMEZONE"]
            for r in export:
                body += event_lines(r, stamp)
            body.append("END:VCALENDAR")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(("\r\n".join(fold(l) for l in body) + "\r\n").encode("utf-8"))
            today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d")
            print(f"내보냄 {len(export)}개 → {out}")
            print(f"사람이 가져오기를 마치면 캘린더 칸에 적을 값:")
            for r in export:
                print(f"  {describe(r)}  →  ics {today} #{fingerprint(r)}")
        else:
            print("내보낼 확정 일정이 없습니다(파일을 만들지 않음).")
    else:
        print(f"보낼 줄 {len(to_send)}개:")
        for r in to_send:
            note = when(r)[3]
            print(f"  {describe(r)}  →  지문 #{fingerprint(r)}{'  (' + note + ')' if note else ''}")

    for r, why in changed:
        print(f"[바뀐 줄] {describe(r)} — {why}. 지금 지문 #{fingerprint(r)} (캘린더 칸: {r['캘린더']})")
    for r in to_delete:
        print(f"[지울 줄] {describe(r)} — 취소됨 (캘린더 칸: {r['캘린더']}). 지운 뒤 칸을 '-'로 되돌린다")
    for p in problems:
        print(f"[읽지 못함] {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
