import os
import time
import pickle
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
SCOPES = ['https://www.googleapis.com/auth/photoslibrary.appendonly']
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'client_secret_719024132506-h7ci22anubitkmr410kl3iotipupj16t.apps.googleusercontent.com.json')
TOKEN_FILE = os.path.join(BASE_DIR, 'token.pickle')

class GooglePhotosUploader:
    def __init__(self):
        self.creds = None
        self.upload_enabled = False
        self.authenticate()

    def authenticate(self):
        try:
            self.creds = self._get_creds()
            self.upload_enabled = self.creds is not None
            logger.info(f"Google Photos 연결 상태: {'활성화' if self.upload_enabled else '비활성화'}")
        except Exception as e:
            logger.error(f"인증 초기화 중 오류: {e}")
            self.upload_enabled = False

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
                    creds = flow.run_local_server(port=0, open_browser=True, timeout_seconds=120)
                    with open(TOKEN_FILE, 'wb') as token:
                        pickle.dump(creds, token)
                except Exception as e:
                    logger.error(f"인증 실패: {e}")
                    return None
        return creds

    def upload_photo(self, file_path):
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
    
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.png'):
            logger.info(f"새로운 스크린샷 감지: {event.src_path}")
            
            # 1. 클립보드 복사
            self.copy_image_to_clipboard(event.src_path)
            
            # 2. 업로드
            if self.uploader:
                self.uploader.upload_photo(event.src_path)
            
            # 3. 개수 제한
            self.enforce_screenshot_limit(os.path.dirname(event.src_path))

    def copy_image_to_clipboard(self, file_path):
        # 기존 로직 유지하되 간소화
        try:
             # pbcopy가 가장 안정적일 수 있음, 여기선 기존 로직을 축약해서 유지
             # 간단히 osascript 사용
             cmd = ["osascript", "-e", 
                    f'tell application "System Events" to set the clipboard to (read (POSIX file "{file_path}") as TIFF picture)']
             subprocess.run(cmd, check=True, capture_output=True)
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