#!/bin/bash

# error.log 파일 경로 설정
LOG_FILE="./error.log"

# 최대 허용 크기 (bytes) - 20MB = 20 * 1024 * 1024
MAX_SIZE=$((20 * 1024 * 1024))

# 파일 크기 확인 함수
check_and_rotate() {
  # 파일이 존재하는지 확인
  if [ -f "$LOG_FILE" ]; then
    # 현재 파일 크기 확인
    CURRENT_SIZE=$(stat -f%z "$LOG_FILE")
    
    # 파일 크기가 MAX_SIZE를 초과하는지 확인
    if [ "$CURRENT_SIZE" -gt "$MAX_SIZE" ]; then
      echo "로그 파일이 20MB를 초과했습니다. 최신 로그를 유지하고 이전 로그를 삭제합니다."
      
      # 파일의 마지막 부분만 임시 파일에 저장 (약 20MB 유지)
      tail -c "$MAX_SIZE" "$LOG_FILE" > "${LOG_FILE}.tmp"
      
      # 임시 파일을 원래 파일로 이동
      mv "${LOG_FILE}.tmp" "$LOG_FILE"
      
      echo "로그 파일 크기가 조정되었습니다: $(stat -f%z "$LOG_FILE" | awk '{print $1/1024/1024 " MB"}')"
    else
      echo "로그 파일 크기는 정상입니다: $(echo "$CURRENT_SIZE / 1024 / 1024" | bc -l | xargs printf "%.2f")MB"
    fi
  else
    echo "로그 파일을 찾을 수 없습니다: $LOG_FILE"
  fi
}

# 실행
check_and_rotate 