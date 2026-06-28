import os
import time
import pickle
import warnings

warnings.filterwarnings("ignore", category=FutureWarning, module=r"google\.(auth|oauth2).*")

import requests
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import unicodedata
import uuid
import shutil
import tempfile
import datetime
import piexif
from PIL import Image
import subprocess
import AppKit
import io
import webbrowser
import sys
import argparse
import threading
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screenshot_uploader.log'))
    ]
)
logger = logging.getLogger(__name__)

# 절대 경로로 변경
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCOPES = [
    'https://www.googleapis.com/auth/photoslibrary.appendonly',
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
]
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'client_secret_719024132506-h7ci22anubitkmr410kl3iotipupj16t.apps.googleusercontent.com.json')
TOKEN_FILE = os.path.join(BASE_DIR, 'token.pickle')

# OAuth 시 사용할 Chrome 프로필 (기본: Profile 1 = gaeco76@gmail.com)
# 다른 프로필로 바꾸려면 환경변수 SCREENSHOT_CHROME_PROFILE 으로 지정
CHROME_PROFILE = os.environ.get('SCREENSHOT_CHROME_PROFILE', 'Profile 1')


CHROME_BIN = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'


class _ChromeProfileBrowser:
    """webbrowser API 호환 핸들러 — 지정 Chrome 프로필로 URL을 연다.
    Chrome 바이너리를 직접 호출해서 --profile-directory가 안정적으로 적용되게 함."""
    def __init__(self, profile):
        self.profile = profile
    def open(self, url, new=0, autoraise=True):
        try:
            logger.info(f"Chrome 프로필 [{self.profile}] 으로 URL 열기")
            if os.path.exists(CHROME_BIN):
                subprocess.Popen([
                    CHROME_BIN,
                    f'--profile-directory={self.profile}',
                    '--new-window',
                    url,
                ])
            else:
                # Chrome 바이너리가 다른 경로에 있는 경우 fallback
                subprocess.Popen([
                    'open', '-na', 'Google Chrome',
                    '--args', f'--profile-directory={self.profile}', url,
                ])
            return True
        except Exception as e:
            logger.warning(f"Chrome 프로필 호출 실패 ({self.profile}): {e}")
            return False
    def open_new(self, url):
        return self.open(url, new=1)
    def open_new_tab(self, url):
        return self.open(url, new=2)


# 기본 webbrowser 우선순위에 등록 (InstalledAppFlow.run_local_server가 호출하는 webbrowser.open이 이 핸들러를 사용하게 됨)
webbrowser.register('chrome_profile', None, _ChromeProfileBrowser(CHROME_PROFILE), preferred=True)

class GooglePhotosUploader:
    def __init__(self):
        self.creds = None
        self.upload_enabled = False
        self.authenticate()

    def authenticate(self):
        try:
            self.creds = self._get_creds()
            self.upload_enabled = self.creds is not None
            if self.upload_enabled:
                email = self._resolve_account_email()
                if email:
                    logger.info(f"Google Photos 연결 상태: 활성화 (Authenticated as: {email})")
                else:
                    logger.info("Google Photos 연결 상태: 활성화 (계정 이메일 조회 불가)")
            else:
                logger.info("Google Photos 연결 상태: 비활성화")
        except Exception as e:
            logger.error(f"인증 초기화 중 오류: {e}")
            self.upload_enabled = False

    def _resolve_account_email(self):
        """현재 인증된 계정의 이메일을 반환. 실패 시 None."""
        try:
            id_token = getattr(self.creds, 'id_token', None)
            if id_token:
                import base64, json
                payload = id_token.split('.')[1]
                payload += '=' * (-len(payload) % 4)
                info = json.loads(base64.urlsafe_b64decode(payload))
                email = info.get('email')
                if email:
                    return email
            resp = requests.get(
                'https://www.googleapis.com/oauth2/v3/userinfo',
                headers={'Authorization': f'Bearer {self.creds.token}'},
                timeout=5,
            )
            if resp.status_code == 200:
                return resp.json().get('email')
            logger.warning(f"userinfo 응답 {resp.status_code}: {resp.text[:120]}")
        except Exception as e:
            logger.warning(f"계정 이메일 조회 실패 (무시됨): {e}")
        return None

    def _notify_macos(self, title, message):
        """macOS 알림 배너 표시. 실패해도 조용히 무시."""
        try:
            safe_title = str(title).replace('"', "'").replace('\\', '')
            safe_msg = str(message).replace('"', "'").replace('\\', '')
            subprocess.run(
                ['osascript', '-e',
                 f'display notification "{safe_msg}" with title "{safe_title}"'],
                check=False,
                timeout=5,
            )
        except Exception as e:
            logger.warning(f"macOS 알림 실패 (무시됨): {e}")

    def _get_creds(self):
        creds = None
        if not os.path.exists(CREDENTIALS_FILE):
            logger.warning(f"인증 파일 없음: {CREDENTIALS_FILE}")
            return None
            
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, 'rb') as token:
                    creds = pickle.load(token)
            except Exception as e:
                logger.error(f"토큰 파일 로드 실패: {e}")
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    with open(TOKEN_FILE, 'wb') as token:
                        pickle.dump(creds, token)
                except Exception as e:
                    logger.error(f"토큰 갱신 실패: {e}")
                    creds = None
            
            if not creds:
                try:
                    # 백그라운드에서 실행될 수 있으므로, 브라우저 띄우는 건 주의해야 함
                    # 여기서는 local-only가 아닐 때만 호출된다고 가정 또는 호출 측에서 제어
                    # 하지만 클래스 내버에서는 flow 실행 가능
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                    creds = flow.run_local_server(port=0, open_browser=True, timeout_seconds=300)
                    with open(TOKEN_FILE, 'wb') as token:
                        pickle.dump(creds, token)
                except Exception as e:
                    logger.error(f"인증 실패: {e}")
                    return None
        return creds

    def upload_photo(self, file_path):
        if not self.upload_enabled or not self.creds:
            logger.info("업로드 비활성화 상태 감지, 인증 재확인 시도...")
            self.authenticate()
            if not self.upload_enabled or not self.creds:
                logger.info("업로드 비활성화 상태입니다.")
                return False

        self._refresh_token_if_needed()

        if not self.upload_enabled or not self.creds:
            logger.info("업로드 비활성화 상태입니다.")
            return False

        try:
            safe_name = self._safe_ascii_filename(os.path.basename(file_path), file_path)
            
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = os.path.join(tmpdir, safe_name)
                shutil.copy2(file_path, tmp_path)
                
                # EXIF 설정
                stat = os.stat(file_path)
                dt = datetime.datetime.fromtimestamp(stat.st_mtime).astimezone()
                self._set_exif_datetime(tmp_path, dt)

                upload_token = self._upload_bytes(tmp_path, safe_name)
                if not upload_token:
                    return False

                return self._create_media_item(upload_token)
        except Exception as e:
            logger.error(f"업로드 중 예외 발생: {e}")
            return False

    def _refresh_token_if_needed(self):
        if self.creds and self.creds.expired and self.creds.refresh_token:
            try:
                logger.info("토큰 만료 감지 (upload_photo), 갱신 시도...")
                self.creds.refresh(Request())
                with open(TOKEN_FILE, 'wb') as token:
                    pickle.dump(self.creds, token)
                logger.info("토큰 갱신 성공")
            except Exception as e:
                logger.error(f"토큰 갱신 실패: {e}")
                logger.warning("인증 토큰이 만료되었거나 유효하지 않습니다. 토큰 파일을 삭제합니다.")
                if os.path.exists(TOKEN_FILE):
                    try:
                        os.remove(TOKEN_FILE)
                    except OSError:
                        pass
                self.creds = None
                self.upload_enabled = False
                self._notify_macos(
                    "Screenshot Uploader: 재인증 필요",
                    "OAuth 토큰이 만료/취소되어 업로드가 중단됐습니다. 터미널에서 재인증을 실행하세요.",
                )


    def _safe_ascii_filename(self, filename, file_path):
        ext = os.path.splitext(filename)[1]
        stat = os.stat(file_path)
        dt = datetime.datetime.fromtimestamp(stat.st_mtime).astimezone()
        safe_name = dt.strftime('%Y%m%d_%H%M%S')
        return f"{safe_name}{ext}"

    def _set_exif_datetime(self, file_path, dt):
        try:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
            exif_time = dt.strftime("%Y:%m:%d %H:%M:%S")
            exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = exif_time
            exif_bytes = piexif.dump(exif_dict)
            img = Image.open(file_path)
            img.save(file_path, exif=exif_bytes)
        except Exception as e:
            logger.warning(f"EXIF 설정 실패 (무시됨): {e}")

    def _upload_bytes(self, file_path, safe_name):
        headers = {
            'Authorization': f'Bearer {self.creds.token}',
            'Content-type': 'application/octet-stream',
            'X-Goog-Upload-File-Name': safe_name,
            'X-Goog-Upload-Protocol': 'raw',
        }
        try:
            with open(file_path, 'rb') as f:
                response = requests.post(
                    'https://photoslibrary.googleapis.com/v1/uploads',
                    data=f,
                    headers=headers
                )
            if response.status_code == 200:
                return response.text
            else:
                logger.error(f"바이트 업로드 실패: {response.text}")
                return None
        except Exception as e:
            logger.error(f"바이트 업로드 중 오류: {e}")
            return None

    def _create_media_item(self, upload_token, retry_count=3):
        create_body = {
            "newMediaItems": [{
                "description": "스크린샷 자동 업로드",
                "simpleMediaItem": {"uploadToken": upload_token}
            }]
        }
        
        for i in range(retry_count):
            try:
                response = requests.post(
                    'https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate',
                    headers={
                        'Authorization': f'Bearer {self.creds.token}',
                        'Content-type': 'application/json',
                    },
                    json=create_body
                )
                if response.status_code == 200:
                    data = response.json()
                    if 'newMediaItemResults' in data:
                        item = data['newMediaItemResults'][0]
                        if item.get('status', {}).get('message') == 'Success':
                             media_item = item.get('mediaItem', {})
                             logger.info(f"Google 포토 업로드 성공: {media_item.get('productUrl')}")
                             return True
                        else:
                             logger.error(f"미디어 아이템 생성 실패 상세: {item}")
                    logger.info("Google 포토 업로드 요청 완료")
                    return True
                else:
                    logger.warning(f"미디어 아이템 생성 실패 ({i+1}/{retry_count}): {response.text}")
                    time.sleep(2)
            except Exception as e:
                logger.error(f"미디어 아이템 생성 중 오류: {e}")
        return False


class ScreenshotHandler(FileSystemEventHandler):
    def __init__(self, uploader=None, limit=10):
        self.uploader = uploader
        self.limit = limit
        self.processed_files = set()
    
    def on_created(self, event):
        if not event.is_directory:
            self.process_screenshot(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self.process_screenshot(event.dest_path)

    def process_screenshot(self, file_path):
        if not file_path.lower().endswith('.png'):
            return

        filename = os.path.basename(file_path)
        if filename.startswith('.'):
            logger.info(f"임시 스크린샷 파일 무시: {file_path}")
            return

        ready_path = self.wait_for_file_ready(file_path)
        if not ready_path:
            logger.warning(f"스크린샷 파일 준비 실패: {file_path}")
            return

        file_key = self.get_file_key(ready_path)
        if file_key in self.processed_files:
            return
        self.processed_files.add(file_key)
        if len(self.processed_files) > 100:
            self.processed_files = set(list(self.processed_files)[-50:])

        logger.info(f"새로운 스크린샷 감지: {ready_path}")

        # 1. 클립보드 복사
        self.copy_image_to_clipboard(ready_path)

        # 2. 업로드
        if self.uploader:
            self.uploader.upload_photo(ready_path)

        # 3. 개수 제한
        self.enforce_screenshot_limit(os.path.dirname(ready_path))

    def wait_for_file_ready(self, file_path, attempts=20, delay=0.25):
        last_size = None
        stable_count = 0
        for _ in range(attempts):
            if not os.path.exists(file_path):
                time.sleep(delay)
                continue

            size = os.path.getsize(file_path)
            if size > 0 and size == last_size:
                stable_count += 1
                if stable_count >= 2:
                    return file_path
            else:
                stable_count = 0
                last_size = size

            time.sleep(delay)
        return file_path if os.path.exists(file_path) else None

    def get_file_key(self, file_path):
        stat = os.stat(file_path)
        return (os.path.realpath(file_path), stat.st_size, stat.st_mtime_ns)

    def copy_image_to_clipboard(self, file_path):
        # NSPasteboard에 직접 이미지 객체를 써넣는다.
        # osascript('read ... as TIFF picture') 방식은 PNG를 TIFF로 강제 해석해
        # macOS 버전/권한에 따라 깨지기 쉬워 PyObjC 경로로 대체함.
        try:
            img = AppKit.NSImage.alloc().initWithContentsOfFile_(file_path)
            if img is None:
                raise RuntimeError("NSImage 로드 실패 (파일 손상 또는 미지원 형식)")
            pasteboard = AppKit.NSPasteboard.generalPasteboard()
            pasteboard.clearContents()
            if not pasteboard.writeObjects_([img]):
                raise RuntimeError("NSPasteboard writeObjects 실패")
            logger.info("클립보드 복사 완료")
        except Exception as e:
            logger.warning(f"클립보드 복사 실패: {e}")

    def enforce_screenshot_limit(self, directory):
        try:
            files = []
            for f in os.listdir(directory):
                path = os.path.join(directory, f)
                if f.lower().endswith('.png') and os.path.isfile(path):
                    files.append((path, os.path.getmtime(path)))
            
            files.sort(key=lambda x: x[1])
            
            if len(files) > self.limit:
                to_remove = len(files) - self.limit
                for i in range(to_remove):
                    try:
                        os.remove(files[i][0])
                        logger.info(f"오래된 스크린샷 삭제: {os.path.basename(files[i][0])}")
                    except Exception as e:
                        logger.error(f"파일 삭제 실패: {e}")
        except Exception as e:
            logger.error(f"개수 제한 로직 오류: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--local-only', action='store_true', help='Google Photos 미사용')
    parser.add_argument('--limit', type=int, default=10, help='파일 유지 개수')
    parser.add_argument('--path', help='스크린샷 감시 디렉토리 경로 (기본값: 시스템 설정 또는 Desktop)')
    args = parser.parse_args()

    screenshot_limit = args.limit
    
    print(f"스크린샷 업로더 시작 (버전: 1.0.7)")
    print(f"작업 디렉토리: {BASE_DIR}")
    print(f"스크린샷 제한 개수: {screenshot_limit}개")
    
    uploader = None
    if not args.local_only:
        # 별도 스레드에서 인증 시도 대신 메인에서 시도하거나, 
        # 여기서는 간단히 초기화 시도.
        # 실제 사용 시엔 UI가 없으므로 터미널에서 흐름 따라야 함.
        print("Google Photos 인증 초기화 중... (브라우저가 열릴 수  있습니다)")
        uploader = GooglePhotosUploader()
    
    # 경로 설정
    screenshot_dir = None
    if args.path:
        screenshot_dir = os.path.expanduser(args.path)
        print(f"사용자 지정 경로를 사용합니다: {screenshot_dir}")
    else:
        try:
            res = subprocess.run(['defaults', 'read', 'com.apple.screencapture', 'location'], capture_output=True, text=True)
            if res.returncode == 0:
                screenshot_dir = res.stdout.strip()
                screenshot_dir = os.path.expanduser(screenshot_dir)
                print(f"시스템 스크린샷 저장 경로를 감지했습니다: {screenshot_dir}")
            else:
                screenshot_dir = os.path.join(os.path.expanduser("~"), "Desktop")
                print(f"기본 스크린샷 경로를 사용합니다: {screenshot_dir}")
        except Exception as e:
            print(f"스크린샷 경로 감지 실패: {e}")
            screenshot_dir = os.path.join(os.path.expanduser("~"), "Desktop")
            print(f"기본 스크린샷 경로를 사용합니다: {screenshot_dir}")

    if not os.path.exists(screenshot_dir):
        logger.warning(f"경로 없음: {screenshot_dir}, 현재 경로 사용")
        screenshot_dir = BASE_DIR

    event_handler = ScreenshotHandler(uploader=uploader, limit=args.limit)
    observer = Observer()
    observer.schedule(event_handler, screenshot_dir, recursive=False)
    observer.start()
    
    logger.info(f"감시 시작: {screenshot_dir}")
    logger.info("Ctrl+C로 종료")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()

if __name__ == "__main__":
    main() 
