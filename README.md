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