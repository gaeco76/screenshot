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

# 절대 경로로 변경
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCOPES = ['https://www.googleapis.com/auth/photoslibrary.appendonly']
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'client_secret_719024132506-h7ci22anubitkmr410kl3iotipupj16t.apps.googleusercontent.com.json')
TOKEN_FILE = os.path.join(BASE_DIR, 'token.pickle')

class ScreenshotHandler(FileSystemEventHandler):
    def __init__(self, creds=None):
        self.creds = creds
        # 인증 정보 업데이트 메서드 추가
        self.upload_enabled = creds is not None
        print(f"초기 업로드 상태: {'활성화' if self.upload_enabled else '비활성화 (준비 중)'}")
    
    def update_creds(self, new_creds):
        self.creds = new_creds
        self.upload_enabled = new_creds is not None
        print(f"Google Photos 연결 상태가 업데이트되었습니다: {'활성화' if self.upload_enabled else '비활성화'}")

    def safe_ascii_filename(self, filename, file_path):
        ext = os.path.splitext(filename)[1]
        stat = os.stat(file_path)
        # 시스템 로컬 타임존 기준으로 변환
        dt = datetime.datetime.fromtimestamp(stat.st_mtime).astimezone()
        safe_name = dt.strftime('%Y%m%d_%H%M%S')
        return f"{safe_name}{ext}"

    def set_exif_datetime(self, file_path, dt):
        # dt: datetime 객체 (로컬 타임존)
        try:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
            exif_time = dt.strftime("%Y:%m:%d %H:%M:%S")
            exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = exif_time
            exif_bytes = piexif.dump(exif_dict)
            img = Image.open(file_path)
            img.save(file_path, exif=exif_bytes)
        except Exception as e:
            print(f"EXIF 설정 중 오류: {e}")

    def copy_image_to_clipboard(self, file_path):
        try:
            # 여러 다른 방식으로 클립보드 복사 시도
            # 1. NSImage 방식 시도
            try:
                # PNG 형식으로 클립보드에 복사
                img = Image.open(file_path)
                output = io.BytesIO()
                img.save(output, format='PNG')
                data = output.getvalue()
                output.close()
                
                # NSData 생성 및 pasteboard에 쓰기
                ns_data = AppKit.NSData.alloc().initWithBytes_length_(data, len(data))
                nsimage = AppKit.NSImage.alloc().initWithData_(ns_data)
                
                pb = AppKit.NSPasteboard.generalPasteboard()
                pb.clearContents()
                success = pb.writeObjects_([nsimage])
                
                if success:
                    print("클립보드에 이미지 복사 완료 (NSImage 방식)")
                    return
                else:
                    print("NSImage 클립보드 복사 실패, 다른 방식 시도")
            except Exception as e:
                print(f"NSImage 클립보드 복사 오류: {e}, 다른 방식 시도")
            
            # 2. Shell 명령어 방식 시도 (osascript)
            try:
                cmd = ["osascript", "-e", 
                       f'tell application "System Events" to set the clipboard to (read (POSIX file "{file_path}") as TIFF picture)']
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    print("클립보드에 이미지 복사 완료 (osascript 방식)")
                    return
                else:
                    print(f"osascript 클립보드 복사 실패: {result.stderr}")
            except Exception as e:
                print(f"osascript 클립보드 복사 오류: {e}")
                
            # 3. 마지막 방식 시도 (screencapture 명령어)
            try:
                # 임시 파일 생성
                temp_file = os.path.join(tempfile.gettempdir(), f"clipboard_temp_{uuid.uuid4()}.png")
                shutil.copy2(file_path, temp_file)
                
                # pbcopy 명령어로 클립보드에 복사
                cmd = ["pbcopy", "<", temp_file]
                result = subprocess.run(" ".join(cmd), shell=True)
                if result.returncode == 0:
                    print("클립보드에 이미지 복사 완료 (pbcopy 방식)")
                else:
                    print("pbcopy 클립보드 복사 실패")
                
                # 임시 파일 삭제
                try:
                    os.remove(temp_file)
                except:
                    pass
            except Exception as e:
                print(f"pbcopy 클립보드 복사 오류: {e}")
                
        except Exception as e:
            print(f"클립보드 복사 실패 (모든 방식 실패): {e}")

    def enforce_screenshot_limit(self, directory, limit=10):
        # directory 내 스크린샷 파일이 limit 초과 시, 오래된 파일부터 삭제
        try:
            # 스크린샷 파일 패턴 인식 개선
            all_files = os.listdir(directory)
            screenshot_files = []
            
            for f in all_files:
                # PNG 파일만 처리하고 디렉토리 제외
                file_path = os.path.join(directory, f)
                if f.lower().endswith('.png') and os.path.isfile(file_path):
                    # 파일이 저장된 시간 기준으로 정렬할 수 있도록 튜플로 저장
                    screenshot_files.append((file_path, os.path.getmtime(file_path)))
            
            # 수정 시간 기준으로 정렬 (오래된 파일이 앞에 위치)
            screenshot_files.sort(key=lambda x: x[1])
            
            print(f"스크린샷 파일 총 {len(screenshot_files)}개 발견 (제한: {limit}개)")
            
            # 개수 확인 후 삭제
            if len(screenshot_files) > limit:
                excess_count = len(screenshot_files) - limit
                print(f"제한 초과: {excess_count}개 파일 삭제 필요")
                
                # 가장 오래된 파일부터 삭제
                for i in range(excess_count):
                    if i >= len(screenshot_files):
                        break
                    
                    oldest_file = screenshot_files[i][0]
                    try:
                        filename = os.path.basename(oldest_file)
                        os.remove(oldest_file)
                        print(f"삭제됨: {filename}")
                    except Exception as e:
                        print(f"파일 삭제 실패: {oldest_file}, {e}")
                
                print(f"정리 완료: {excess_count}개 파일 삭제됨")
            else:
                print(f"현재 스크린샷 개수: {len(screenshot_files)}개 (제한: {limit}개)")
        except Exception as e:
            print(f"스크린샷 개수 제한 기능 오류: {e}")
            import traceback
            traceback.print_exc()

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.png'):
            print(f"새로운 스크린샷 감지: {event.src_path}")
            
            # 1. 클립보드 복사 - 먼저 실행 (실패해도 계속 진행)
            try:
                self.copy_image_to_clipboard(event.src_path)
            except Exception as e:
                print(f"클립보드 복사 오류 (무시하고 계속 진행): {e}")
            
            # 2. Google Photos 업로드 시도 - 분리하여 실행
            if self.creds:
                try:
                    self.upload_to_google_photos(event.src_path)
                except Exception as e:
                    print(f"Google Photos 업로드 오류 (무시하고 계속 진행): {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("Google Photos 인증 정보가 없습니다. 로컬 기능만 사용합니다.")
            
            # 3. 스크린샷 파일 개수 제한 - 마지막에 실행
            try:
                self.enforce_screenshot_limit(os.path.dirname(event.src_path), limit=10)
            except Exception as e:
                print(f"스크린샷 개수 제한 오류 (무시하고 계속 진행): {e}")
                
    def upload_to_google_photos(self, file_path):
        if not self.creds:
            print("인증 정보가 없어 업로드를 건너뜁니다.")
            return
            
        try:
            safe_name = self.safe_ascii_filename(os.path.basename(file_path), file_path)
            # 임시 디렉토리에 ASCII 파일명으로 복사
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = os.path.join(tmpdir, safe_name)
                shutil.copy2(file_path, tmp_path)
                # EXIF DateTimeOriginal 삽입
                stat = os.stat(file_path)
                dt = datetime.datetime.fromtimestamp(stat.st_mtime).astimezone()
                self.set_exif_datetime(tmp_path, dt)
                headers = {
                    'Authorization': f'Bearer {self.creds.token}',
                    'Content-type': 'application/octet-stream',
                    'X-Goog-Upload-File-Name': safe_name,
                    'X-Goog-Upload-Protocol': 'raw',
                }
                with open(tmp_path, 'rb') as f:
                    response = requests.post(
                        'https://photoslibrary.googleapis.com/v1/uploads',
                        data=f,
                        headers=headers
                    )
            if response.status_code == 200:
                upload_token = response.text
                print("업로드 토큰 획득:", upload_token)
            else:
                print("업로드 토큰 획득 실패:", response.text)
                # 인증 세션 오류 감지 시 자동 인증 플로우 실행
                if "Authentication session is not defined" in response.text:
                    print("인증 세션 만료. 브라우저 인증을 다시 진행합니다.")
                    if os.path.exists(TOKEN_FILE):
                        os.remove(TOKEN_FILE)
                    try:
                        self.creds = get_google_photos_creds()
                        print("인증 완료. 업로드를 재시도합니다.")
                        self.upload_to_google_photos(file_path)
                    except Exception as e:
                        print(f"재인증 실패: {e}")
                return

            create_body = {
                "newMediaItems": [
                    {
                        "description": "스크린샷 자동 업로드",
                        "simpleMediaItem": {
                            "uploadToken": upload_token
                        }
                    }
                ]
            }
            # 업로드 실패 시 최대 3회, 2초 간격으로 재시도
            for i in range(3):
                create_response = requests.post(
                    'https://photoslibrary.googleapis.com/v1/mediaItems:batchCreate',
                    headers={
                        'Authorization': f'Bearer {self.creds.token}',
                        'Content-type': 'application/json',
                    },
                    json=create_body
                )
                if create_response.status_code == 200:
                    print("Google 포토 업로드 성공")
                    # 업로드 확인을 위해 Google Photos 페이지 열기
                    try:
                        response_data = create_response.json()
                        if response_data and 'newMediaItemResults' in response_data:
                            item_id = response_data['newMediaItemResults'][0]['mediaItem']['id']
                            photo_url = f"https://photos.google.com/photo/{item_id}"
                            print(f"업로드된 사진: {photo_url}")
                            # 브라우저 자동 실행 제거
                            # webbrowser.open(photo_url)
                    except Exception as e:
                        print(f"업로드 정보 확인 실패: {e}")
                    break
                else:
                    print(f"Google 포토 업로드 실패({i+1}회):", create_response.text)
                    time.sleep(2)
        except Exception as e:
            print(f"Google 포토 업로드 중 예외 발생: {e}")
            import traceback
            traceback.print_exc()

def get_google_photos_creds():
    try:
        creds = None
        
        # 인증 파일 존재 확인
        if not os.path.exists(CREDENTIALS_FILE):
            print(f"Google Photos 인증 파일을 찾을 수 없습니다: {CREDENTIALS_FILE}")
            print("로컬 기능만 활성화됩니다.")
            return None
            
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, 'rb') as token:
                    creds = pickle.load(token)
                print("저장된 인증 정보를 로드했습니다.")
            except Exception as e:
                print(f"토큰 파일 읽기 실패: {e}")
                if os.path.exists(TOKEN_FILE):
                    os.remove(TOKEN_FILE)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    print("인증 토큰을 갱신했습니다.")
                    with open(TOKEN_FILE, 'wb') as token:
                        pickle.dump(creds, token)
                    return creds
                except Exception as e:
                    print(f"토큰 갱신 실패: {e}")
                    # 토큰 갱신 실패 시 새로운 인증 진행
                    if os.path.exists(TOKEN_FILE):
                        os.remove(TOKEN_FILE)
                    creds = None
            
            if not creds:
                try:
                    print("Google Photos 인증을 시도합니다...")
                    print("주의: 인증 과정 중에도 로컬 기능은 계속 작동합니다.")
                    
                    # 브라우저를 통한 인증 시도
                    flow = InstalledAppFlow.from_client_secrets_file(
                        CREDENTIALS_FILE, SCOPES)
                    # 명시적으로 브라우저 자동 실행 활성화, 타임아웃 설정
                    try:
                        creds = flow.run_local_server(port=0, open_browser=True, timeout_seconds=120)
                        with open(TOKEN_FILE, 'wb') as token:
                            pickle.dump(creds, token)
                        print("Google Photos 인증이 완료되었습니다.")
                        return creds
                    except Exception as auth_error:
                        print(f"브라우저 인증 실패: {auth_error}")
                        # 인증 실패 시 None 반환 (로컬 기능만 사용)
                        return None
                except Exception as e:
                    print(f"인증 과정 시작 실패: {e}")
                    print("인증 없이 계속 진행합니다. 로컬 기능만 사용 가능합니다.")
                    return None
        
        return creds
    except KeyboardInterrupt:
        print("사용자가 인증을 취소했습니다. 로컬 기능만 사용합니다.")
        return None
    except Exception as e:
        print(f"인증 과정 중 오류 발생: {e}")
        print("인증 없이 계속 진행합니다. 로컬 기능만 사용 가능합니다.")
        return None

def auth_worker(handler, disable_auth=False):
    """백그라운드에서 인증을 처리하는 작업자 함수"""
    if disable_auth:
        print("Google Photos 인증이 비활성화되었습니다. 로컬 기능만 사용합니다.")
        return
    
    try:
        print("백그라운드에서 Google Photos 인증을 시도합니다...")
        creds = get_google_photos_creds()
        if creds:
            print("Google Photos 인증이 완료되었습니다.")
            handler.update_creds(creds)
        else:
            print("Google Photos 인증에 실패했습니다. 로컬 기능만 사용합니다.")
    except Exception as e:
        print(f"인증 스레드 오류: {e}")
        print("로컬 기능만 사용합니다.")

def main():
    try:
        # 명령줄 인자 파싱
        parser = argparse.ArgumentParser(description='스크린샷 자동 업로더')
        parser.add_argument('--local-only', action='store_true', 
                          help='Google Photos 인증을 건너뛰고 로컬 기능만 사용합니다')
        parser.add_argument('--limit', type=int, default=10,
                          help='스크린샷 최대 개수 (기본값: 10)')
        args = parser.parse_args()
        
        screenshot_limit = args.limit
        
        print(f"스크린샷 업로더 시작 (버전: 1.0.6)")
        print(f"작업 디렉토리: {BASE_DIR}")
        print(f"스크린샷 제한 개수: {screenshot_limit}개")
        
        # 로컬 기능 먼저 활성화
        print("로컬 기능을 초기화하는 중...")
        event_handler = ScreenshotHandler(creds=None)  # 초기에는 인증 정보 없이 시작
        observer = Observer()
        
        # macOS 시스템 설정에서 스크린샷 저장 경로 가져오기
        try:
            result = subprocess.run(
                ['defaults', 'read', 'com.apple.screencapture', 'location'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                screenshot_dir = result.stdout.strip()
                screenshot_dir = os.path.expanduser(screenshot_dir)  # ~ 확장
                print(f"시스템 스크린샷 저장 경로를 감지했습니다: {screenshot_dir}")
            else:
                # 기본값: 데스크탑
                screenshot_dir = os.path.join(os.path.expanduser("~"), "Desktop")
                print(f"기본 스크린샷 경로를 사용합니다: {screenshot_dir}")
        except Exception as e:
            print(f"스크린샷 경로 감지 실패: {e}")
            screenshot_dir = os.path.join(os.path.expanduser("~"), "Desktop")
            print(f"기본 스크린샷 경로를 사용합니다: {screenshot_dir}")
        
        # 디렉토리 존재 확인
        if not os.path.exists(screenshot_dir):
            print(f"스크린샷 디렉토리가 존재하지 않습니다: {screenshot_dir}")
            screenshot_dir = BASE_DIR
            print(f"대신 현재 디렉토리를 사용합니다: {screenshot_dir}")
        
        # 프로그램 시작 시 스크린샷 개수 제한 적용
        print("스크린샷 개수 초기화 중...")
        try:
            event_handler.enforce_screenshot_limit(screenshot_dir, limit=screenshot_limit)
        except Exception as e:
            print(f"스크린샷 개수 초기화 오류 (무시하고 계속 진행): {e}")
        
        # 감시 설정 및 시작
        observer.schedule(
            event_handler,
            path=screenshot_dir,
            recursive=False
        )
        observer.start()
        print(f"스크린샷 모니터링이 시작되었습니다... (감시 경로: {screenshot_dir})")
        print("클립보드 복사 및 스크린샷 관리 기능이 활성화되었습니다.")
        
        # 백그라운드에서 Google Photos 인증 시도
        if not args.local_only:
            print("백그라운드에서 Google Photos 인증을 시작합니다...")
            auth_thread = threading.Thread(
                target=auth_worker, 
                args=(event_handler, args.local_only)
            )
            auth_thread.daemon = True  # 메인 스레드가 종료되면 함께 종료
            auth_thread.start()
        else:
            print("--local-only 옵션이 지정되어 Google Photos 인증을 건너뜁니다.")
        
        last_check_time = time.time()
        check_interval = 60  # 60초마다 스크린샷 개수 확인
        
        try:
            while True:
                current_time = time.time()
                # 주기적으로 스크린샷 개수 확인
                if current_time - last_check_time > check_interval:
                    try:
                        event_handler.enforce_screenshot_limit(screenshot_dir, limit=screenshot_limit)
                    except Exception as e:
                        print(f"정기 스크린샷 개수 확인 오류 (무시하고 계속 진행): {e}")
                    last_check_time = current_time
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            print("\n모니터링이 중지되었습니다.")
        observer.join()
    except Exception as e:
        print(f"프로그램 실행 중 예상치 못한 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 