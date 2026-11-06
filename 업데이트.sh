#!/usr/bin/env bash
# Bring the newest release of the distribution into this office (macOS / Linux / Git Bash on Windows).
#   ./업데이트.sh          show what comes in and ask before merging
#   ./업데이트.sh --check  only show; changes nothing
#   ./업데이트.sh --yes    merge without asking (after you have seen --check)
# Claude runs 도구/업데이트.py itself: --check first, your approval, then --yes.
# The work is done by 도구/업데이트.py; this file only finds Python 3.8 or later.
# It never pushes: upload the result with ./동기화.sh afterwards.
set -euo pipefail
cd "$(dirname "$0")"
CHECK='import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)'
for py in python3 python; do
  if command -v "$py" >/dev/null 2>&1 && "$py" -c "$CHECK" >/dev/null 2>&1; then
    exec "$py" 도구/업데이트.py "$@"
  fi
done
# Windows Git Bash with only the py launcher (python.org installer default).
if command -v py >/dev/null 2>&1 && py -3 -c "$CHECK" >/dev/null 2>&1; then
  exec py -3 도구/업데이트.py "$@"
fi
echo ""
echo "업데이트 중단: Python 3.8 이상을 찾지 못했습니다. 아무것도 바꾸지 않았습니다."
exit 1
