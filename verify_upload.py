import os
import time
import argparse
import shutil
from PIL import Image, ImageDraw
import datetime
from screenshot_uploader import GooglePhotosUploader, ScreenshotHandler

def create_dummy_image(filename):
    img = Image.new('RGB', (100, 100), color = 'red')
    d = ImageDraw.Draw(img)
    d.text((10,10), "Test", fill=(255,255,0))
    img.save(filename)
    return filename

def main():
    parser = argparse.ArgumentParser(description='Test Google Photos Upload')
    parser.add_argument('--image', help='Path to an existing image file to test with')
    args = parser.parse_args()

    print("Google Photos Upload Verification Script")
    print("--------------------------------")

    # 1. 인증 초기화
    print("1. Initializing Authentication...")
    uploader = GooglePhotosUploader()
    if not uploader.upload_enabled:
        print("Authentication failed or not enabled. Please check credentials.")
        return

    # 2. 테스트 이미지 준비
    if args.image and os.path.exists(args.image):
        test_image = args.image
        print(f"2. Using existing image: {test_image}")
    else:
        test_image = "verify_screenshot_dummy.png"
        create_dummy_image(test_image)
        print(f"2. Created dummy image: {test_image}")

    # 3. 업로드 테스트
    print(f"3. Attempting to upload {test_image}...")
    
    # We can use the uploader directly
    success = uploader.upload_photo(test_image)
    
    if success:
        print("\nSUCCESS: Upload completed successfully!")
    else:
        print("\nFAILURE: Upload failed.")

    # Clean up dummy
    if not args.image and os.path.exists(test_image):
        os.remove(test_image)
        print("Cleaned up dummy image.")

if __name__ == "__main__":
    main()
