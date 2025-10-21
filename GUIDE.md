# 스크린샷 자동 업로더 사용 가이드

## 🚀 실행 방법

### 백그라운드 실행 (권장)
```bash
cd /Users/a2023/00code/screenshot
nohup python3 -u screenshot_uploader.py > screenshot_uploader.log 2>&1 &
```

### 프로세스 확인
```bash
ps aux | grep screenshot_uploader | grep -v grep
```

### 로그 확인
```bash
# 실시간 로그
tail -f /Users/a2023/00code/screenshot/screenshot_uploader.log

# 최근 30줄
tail -30 /Users/a2023/00code/screenshot/screenshot_uploader.log
```

### 프로그램 종료
```bash
pkill -f screenshot_uploader.py
```

## 📸 스크린샷 찍는 방법

macOS 기본 단축키:
- **전체 화면**: `Cmd + Shift + 3`
- **영역 선택**: `Cmd + Shift + 4`
- **창 선택**: `Cmd + Shift + 4` 후 `Space`

스크린샷을 찍으면 자동으로:
1. ✅ 클립보드에 복사됨
2. ✅ Google Photos에 업로드됨
3. ✅ 로그에 업로드 URL 표시됨
4. ✅ 10개 초과 시 오래된 파일 자동 삭제

## 🔍 테스트 방법

### 1. 직접 스크린샷 찍기
```bash
# 스크린샷을 찍어보세요 (Cmd + Shift + 3 또는 Cmd + Shift + 4)
# 그리고 로그 확인:
tail -20 /Users/a2023/00code/screenshot/screenshot_uploader.log
```

예상 출력:
```
새로운 스크린샷 감지: /Users/a2023/00code/screenshot/스크린샷 2025-XX-XX ...
클립보드에 이미지 복사 완료
업로드 토큰 획득: ...
Google 포토 업로드 성공
업로드된 사진: https://photos.google.com/photo/...
```

### 2. 프로그램 상태 확인
```bash
# 프로세스 실행 중인지 확인
ps aux | grep screenshot_uploader | grep -v grep

# 모니터링 경로 확인
tail -30 /Users/a2023/00code/screenshot/screenshot_uploader.log | grep "감지"
```

## ⚙️ 설정

### 스크린샷 최대 개수 변경
```bash
python3 screenshot_uploader.py --limit 20  # 20개로 변경
```

### Google Photos 인증 없이 로컬 기능만 사용
```bash
python3 screenshot_uploader.py --local-only
```

## 🐛 문제 해결

### 업로드가 안 될 때

1. **프로세스 확인**
```bash
ps aux | grep screenshot_uploader | grep -v grep
```

2. **로그 확인**
```bash
tail -50 /Users/a2023/00code/screenshot/screenshot_uploader.log
```

3. **인증 재시도**
```bash
# 프로그램 종료
pkill -f screenshot_uploader.py

# 토큰 삭제
rm /Users/a2023/00code/screenshot/token.pickle

# 재시작 (브라우저에서 재인증)
python3 -u screenshot_uploader.py
```

4. **스크린샷 경로 확인**
```bash
defaults read com.apple.screencapture location
```

### 스크린샷 경로가 다를 때

macOS 스크린샷 저장 경로를 변경:
```bash
# 원하는 경로로 변경
defaults write com.apple.screencapture location ~/00code/screenshot

# 설정 적용
killall SystemUIServer
```

## 📊 모니터링

### 현재 스크린샷 개수 확인
```bash
ls -la /Users/a2023/00code/screenshot/*.png | wc -l
```

### 최근 업로드 확인
```bash
grep "업로드 성공" /Users/a2023/00code/screenshot/screenshot_uploader.log | tail -10
```

### 업로드된 사진 URL 확인
```bash
grep "photos.google.com" /Users/a2023/00code/screenshot/screenshot_uploader.log | tail -10
```

## 🔄 자동 시작 설정 (선택)

시스템 시작 시 자동 실행하려면:
```bash
# LaunchAgent 설정 파일 편집
vi ~/Library/LaunchAgents/com.screenshot.uploader.plist
```

내용:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.screenshot.uploader</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/Users/a2023/00code/screenshot/screenshot_uploader.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/a2023/00code/screenshot/screenshot_uploader.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/a2023/00code/screenshot/screenshot_uploader.err</string>
</dict>
</plist>
```

로드:
```bash
launchctl load ~/Library/LaunchAgents/com.screenshot.uploader.plist
```

## ✅ 주요 기능

- ✅ **자동 업로드**: 스크린샷 찍으면 즉시 Google Photos 업로드
- ✅ **클립보드 복사**: 스크린샷이 자동으로 클립보드에 복사됨
- ✅ **파일 개수 제한**: 최대 10개 유지 (오래된 파일 자동 삭제)
- ✅ **백그라운드 인증**: 프로그램 시작 후 백그라운드에서 인증
- ✅ **경로 자동 감지**: macOS 시스템 설정의 스크린샷 경로 자동 감지
- ✅ **EXIF 정보**: 원본 타임스탬프 보존

## 📝 버전 정보

- **버전**: 1.0.7
- **마지막 수정**: 2025-10-21
- **주요 변경사항**:
  - macOS 시스템 스크린샷 경로 자동 감지 추가
  - 경로 불일치 문제 해결

