#!/bin/bash
# screenshot uploader launchd 설치 스크립트
# 템플릿(.plist.template)의 __HOME__ 플레이스홀더를 현재 $HOME 으로 치환해
# ~/Library/LaunchAgents 에 설치하고 데몬을 (재)시작한다.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="com.screenshot.uploader"
TEMPLATE="${SCRIPT_DIR}/${LABEL}.plist.template"
DEST_DIR="${HOME}/Library/LaunchAgents"
DEST="${DEST_DIR}/${LABEL}.plist"

if [ ! -f "$TEMPLATE" ]; then
  echo "오류: 템플릿 없음 - $TEMPLATE" >&2
  exit 1
fi

mkdir -p "$DEST_DIR"

# __HOME__ → $HOME 치환 후 설치
sed "s|__HOME__|${HOME}|g" "$TEMPLATE" > "$DEST"
echo "설치 완료: $DEST"

# 기존 데몬 내리고 다시 올리기
launchctl unload "$DEST" 2>/dev/null || true
launchctl load "$DEST"
echo "데몬 시작: $LABEL"

# 상태 확인
sleep 1
if launchctl list | grep -q "$LABEL"; then
  echo "등록 확인: $(launchctl list | grep "$LABEL")"
else
  echo "경고: launchctl 목록에서 $LABEL 미확인" >&2
fi
