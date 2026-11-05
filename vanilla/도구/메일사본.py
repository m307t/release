#!/usr/bin/env python3
"""Make plain-text copies of exported mail for the ops desk (상황실).

    python3 도구/메일사본.py <메일 폴더> <사본 폴더>
    (Windows: py -3 도구\\메일사본.py ...)

- The copy folder must be new or empty. To redo, use a new folder (new run time).
- One copy per file read from the mail folder, numbered NNN_<원본 이름>.txt, so
  "number of copies = number of original files" always holds:
  - .eml: headers (보낸 사람, 받는 사람, 참조, 날짜, 제목), the text body (plain, or html
    turned into text), attachment names, and any mail forwarded as an attachment.
    Korean in base64/quoted-printable, ks_c_5601-1987/euc-kr (read as cp949) and
    raw 8-bit headers is decoded.
  - .txt: copied as it is (utf-8, cp949 or utf-16). A leading UTF-8 BOM is dropped.
  - other files (.msg etc.): a placeholder copy that says "사본 없음" with the reason.
    Export them again as .eml or .txt.
- Subfolders, hidden files (.DS_Store etc.) and system files (Thumbs.db, desktop.ini, ~$*)
  are not read. Subfolders are listed.
- Copies whose text could not be fully decoded are marked "[확인 필요: 해독 불완전]".
- The originals are never changed. The last line prints the counts.
Exit code 0 = every file copied cleanly, 1 = placeholders, subfolders or incomplete
decoding (see the list), 2 = bad arguments or copy folder not empty.
"""
import email
import email.header
import email.policy
import encodings.aliases
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# Korean mail labelled ks_c_5601-1987 / euc-kr is really cp949 (it has extra syllables such as 똠·햏).
for _alias in ("ks_c_5601_1987", "ks_c_5601", "ksc5601", "ksc_5601", "euc_kr", "euckr", "korean"):
    encodings.aliases.aliases[_alias] = "cp949"

WEAK_CHARSETS = {"us-ascii", "ascii", "iso-8859-1", "latin-1", "latin1", "windows-1252", "cp1252"}
UNSURE = "[확인 필요: 해독 불완전]"
SYSTEM_FILES = {"thumbs.db", "desktop.ini"}  # Windows folder files, not mail (also in .gitignore)


def decode_bytes(data, charset=None):
    """Decode mail bytes. Returns (text, complete)."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace"), True
    tries = []
    if charset and charset.lower() not in WEAK_CHARSETS:
        tries.append(charset)
    tries += ["utf-8", "cp949"]  # strict utf-8 first: cp949 can mis-read utf-8 bytes
    if charset and charset.lower() in WEAK_CHARSETS:
        tries.append(charset)  # a weak label is trusted only if utf-8 and cp949 both fail
    for cs in tries:
        try:
            return data.decode(cs), True
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("cp949", errors="replace"), False


class _Text(HTMLParser):
    BREAKS = {"br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in self.BREAKS:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        elif tag in self.BREAKS:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_to_text(markup):
    parser = _Text()
    parser.feed(markup)
    parser.close()
    return "".join(parser.out)


def tidy(text):
    text = text.lstrip("\ufeff").replace("\r\n", "\n")  # a UTF-8 BOM survives a utf-8 decode
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def part_text(part):
    """Returns (text, complete) for one text/* part."""
    text, ok = decode_bytes(part.get_payload(decode=True) or b"", part.get_content_charset())
    if part.get_content_type() == "text/html":
        text = html_to_text(text)
    return tidy(text), ok


def header_text(msg, key):
    """Decode a header from its raw bytes, so 8-bit cp949 headers also come out right."""
    raw = next((v for k, v in msg.raw_items() if k.lower() == key.lower()), None)
    if raw is None:
        return None, True
    raw = re.sub(r"\r?\n[ \t]+", " ", str(raw))
    raw = raw.encode("ascii", "surrogateescape").decode("latin-1")
    pieces, ok = [], True
    for chunk, cs in email.header.decode_header(raw):
        data = chunk if isinstance(chunk, bytes) else chunk.encode("latin-1")
        text, done = decode_bytes(data, cs)
        pieces.append(text)
        ok = ok and done
    return "".join(pieces).strip(), ok


def body_of(msg):
    """Plain body, or html body when the plain one is missing or empty."""
    had_bytes = False
    for pref in (("plain",), ("html",)):
        part = msg.get_body(preferencelist=pref)
        if part is not None:
            text, ok = part_text(part)
            if text:
                return text, ok
            had_bytes = had_bytes or bool((part.get_payload(decode=True) or b"").strip())
    if had_bytes:  # the body has bytes but no readable text came out (broken html etc.)
        return "(본문 없음: 본문에서 글자를 뽑지 못함 — 원본 확인)", False
    return "(본문 없음)", True


def message_text(msg, depth=0):
    """Returns (lines, complete) for a message and the mails forwarded inside it."""
    lines, ok = [], True
    for label, key in (("보낸 사람", "From"), ("받는 사람", "To"), ("참조", "Cc"), ("날짜", "Date"), ("제목", "Subject")):
        value, done = header_text(msg, key)
        ok = ok and done
        if value:
            lines.append(f"{label}: {value}")
    forwarded, names = [], []
    for part in msg.iter_attachments():
        if part.get_content_type() == "message/rfc822":
            inner = part.get_payload(0) if part.is_multipart() else part.get_content()
            subject, _ = header_text(inner, "Subject")
            names.append(f"(전달된 메일: {subject or '제목 없음'})")
            forwarded.append(inner)
        else:
            name = part.get_filename()
            names.append(name or "(이름 없음)")
    lines.append(f"첨부: {', '.join(names) if names else '없음'}")
    lines.append("---")
    body, done = body_of(msg)
    ok = ok and done
    lines.append(body)
    for inner in forwarded:
        if depth >= 3:
            lines.append("\n--- 전달된 메일 (너무 깊어 생략) ---")
            break
        lines.append("\n--- 전달된 메일 ---")
        inner_lines, done = message_text(inner, depth + 1)
        ok = ok and done
        lines.extend(inner_lines)
    return lines, ok


def eml_to_text(path):
    msg = email.message_from_bytes(path.read_bytes(), policy=email.policy.default)
    lines, ok = message_text(msg)
    return "\n".join([f"원본: {path.name}"] + lines) + "\n", ok


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(argv) != 3:
        print(__doc__)
        return 2
    src, dst = Path(argv[1]), Path(argv[2])
    if not src.is_dir():
        print(f"메일 폴더가 없습니다: {src}")
        return 2
    if dst.resolve() == src.resolve() or src.resolve() in dst.resolve().parents:
        print("사본 폴더는 메일 폴더 밖에 둡니다.")
        return 2
    if dst.exists() and (not dst.is_dir() or any(dst.iterdir())):
        print(f"사본 폴더가 비어 있지 않습니다: {dst} (다시 만들 때는 새 폴더를 지정하세요)")
        return 2
    dst.mkdir(parents=True, exist_ok=True)
    entries = sorted(p for p in src.iterdir()
                     if not p.name.startswith((".", "~$")) and p.name.lower() not in SYSTEM_FILES)
    folders = [p for p in entries if p.is_dir()]
    files = [p for p in entries if p.is_file()]
    notes = []
    for n, path in enumerate(files, start=1):
        ext = path.suffix.lower()
        ok = True
        try:
            if ext == ".eml":
                text, ok = eml_to_text(path)
            elif ext == ".txt":
                body, ok = decode_bytes(path.read_bytes())
                text = f"원본: {path.name}\n---\n{tidy(body)}\n"
            else:
                text = f"원본: {path.name}\n사본 없음: 지원하지 않는 형식입니다. .eml 또는 .txt로 다시 내보내 주세요.\n"
                notes.append(f"[사본 없음] {path.name} (지원하지 않는 형식)")
        except Exception as e:  # keep going; leave a placeholder so the counts still match
            text = f"원본: {path.name}\n사본 없음: 읽기 오류 ({e})\n"
            notes.append(f"[사본 없음] {path.name} (읽기 오류: {e})")
        if not ok:
            text = f"{UNSURE}\n{text}"
            notes.append(f"{UNSURE} {path.name}")
        (dst / f"{n:03d}_{path.stem}.txt").write_text(text, encoding="utf-8")
    for p in folders:
        notes.append(f"[읽지 않음] {p.name}/ (하위 폴더: 안의 메일을 메일 폴더 바로 아래로 옮겨 주세요)")
    for note in notes:
        print(note)
    print(f"원본 파일 {len(files)}개 → 사본 {len(files)}개 (사본 없음·해독 불완전 {len(notes) - len(folders)}개), 읽지 않은 하위 폴더 {len(folders)}개")
    return 1 if notes else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
