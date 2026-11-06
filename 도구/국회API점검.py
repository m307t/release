#!/usr/bin/env python3
"""Check the National Assembly Open API (open.assembly.go.kr) connection.

Key lookup order: ASSEMBLY_KEY environment variable -> ASSEMBLY_KEY in repo-root .env.
The key value is never printed. Without a key, the API still answers (max 5 rows).

Usage: python3 도구/국회API점검.py [BILL_NO]
       (Windows: py -3 도구\\국회API점검.py [BILL_NO])
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://open.assembly.go.kr/portal/openapi/ALLBILL"


def load_key():
    key = os.environ.get("ASSEMBLY_KEY", "").strip()
    if key:
        return key, "환경변수"
    env = ROOT / ".env"
    if env.exists():
        # utf-8-sig: Windows Notepad's "UTF-8 (BOM)" would otherwise hide the first line's key.
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line.startswith("ASSEMBLY_KEY="):
                val = line.split("=", 1)[1].split("#", 1)[0].strip().strip("'\"")
                if val:
                    return val, ".env"
    return "", "없음"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    # ALLBILL requires BILL_NO. The default is an arbitrary public bill used only as a connectivity probe.
    bill_no = sys.argv[1] if len(sys.argv) > 1 else "2117808"
    try:
        key, source = load_key()
    except UnicodeDecodeError:
        # The error text is not printed: it quotes bytes of the file.
        print("[실패] .env를 UTF-8로 읽지 못했다.")
        print("- 메모장 등에서 인코딩을 UTF-8로 골라 .env를 다시 저장한다.")
        return 2
    params = {"Type": "json", "pIndex": 1, "pSize": 1, "BILL_NO": bill_no}
    if key:
        params["KEY"] = key
    url = BASE + "?" + urllib.parse.urlencode(params)
    # The API returns "Bad Request." without a browser user agent.
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    print(f"인증키: {source}" + ("" if key else " (키 없이 조회: 한 번에 5건까지)"))
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
    except (urllib.error.URLError, OSError) as e:
        print(f"[실패] 접속 불가: {e}")
        print("- 클라우드 세션이면 환경 설정의 네트워크 허용 도메인에 open.assembly.go.kr 추가가 필요하다.")
        return 2
    try:
        data = json.loads(body)
    except ValueError:
        print(f"[실패] JSON이 아닌 응답: {body[:200]}")
        return 3
    if "ALLBILL" not in data:
        result = data.get("RESULT", {})
        print(f"[실패] {result.get('CODE')} {result.get('MESSAGE')}")
        if key and str(result.get("CODE", "")).startswith("ERROR-290"):
            print("- 인증키가 유효하지 않다. open.assembly.go.kr 마이페이지에서 키를 확인한다.")
        return 4
    head = data["ALLBILL"][0]["head"]
    code = head[1]["RESULT"]["CODE"]
    rows = data["ALLBILL"][1].get("row", []) if len(data["ALLBILL"]) > 1 else []
    print(f"[성공] 응답 코드 {code}, 전체 {head[0]['list_total_count']}건")
    for r in rows:
        print(f"- {r.get('BILL_NO')} {r.get('BILL_NM')} (제안일 {r.get('PPSL_DT')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
