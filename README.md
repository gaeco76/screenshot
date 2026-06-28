# 스크린샷 자동 업로더

맥미니에서 스크린샷을 자동으로 Google Drive에 업로드하는 스크립트입니다.

## 설치 방법

1. Python 3.7 이상이 설치되어 있어야 합니다.

2. 필요한 패키지 설치:
```bash
pip install -r requirements.txt
```

3. Google Cloud Console에서 프로젝트를 생성하고 Google Drive API를 활성화합니다.

4. OAuth 2.0 클라이언트 ID를 생성하고 `credentials.json` 파일을 다운로드하여 스크립트와 같은 디렉토리에 저장합니다.

## 사용 방법

1. 스크립트 실행:
```bash
python screenshot_uploader.py
```

2. 처음 실행 시 Google 계정 인증이 필요합니다. 브라우저가 열리면 Google 계정으로 로그인하고 권한을 승인해주세요.

3. 스크립트가 실행되면 데스크톱에 저장되는 모든 스크린샷이 자동으로 Google Drive의 'Screenshots' 폴더에 업로드됩니다.

## 주의사항

- 스크립트는 데스크톱에 저장되는 스크린샷만 감지합니다.
- 스크린샷은 PNG 형식만 지원합니다.
- Google Drive API 할당량에 주의하세요.

# Screenshot 프로젝트

## 로그 관리

이 프로젝트는 `error.log` 파일의 크기를 자동으로 관리합니다. 파일 크기가 20MB를 초과하면 이전 로그를 삭제하고 최신 로그만 유지합니다.

### 로그 관리 스크립트 사용법

1. 수동으로 실행:
   ```bash
   ./log_rotator.sh
   ```

2. 자동 실행 설정 (cron 작업):
   ```bash
   # 매시간 로그 크기 확인
   crontab -e
   ```
   
   다음 라인 추가:
   ```
   0 * * * * cd /Users/m5/screenshot && ./log_rotator.sh >> cron.log 2>&1
   ```

### Cron 작업 설정 방법

1. 터미널을 열고 `crontab -e` 입력
2. 위의 cron 라인을 추가 (경로를 실제 프로젝트 경로로 수정)
3. 저장하고 나가기 (vi: ESC 누른 후 `:wq` 입력)

이렇게 설정하면 매시간 로그 파일 크기를 확인하고 필요시 조정합니다. 
