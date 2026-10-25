import os
import json
import subprocess
import requests
import random

DRIVES = ["gdrive1:data_store", "gdrive2:data_store", "gdrive3:data_store", "gdrive4:data_store"]
FB_API_URL = "https://graph.facebook.com/v19.0"

def get_gemini_caption():
    api_keys = [os.environ.get("GEMINI_KEY_1"), os.environ.get("GEMINI_KEY_2"), os.environ.get("GEMINI_KEY_3")]
    api_key = random.choice([k for k in api_keys if k])
    if not api_key: return "Epic mobile gaming moment! 🔥 #Gaming"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": "Create a short clickbait English caption for a gaming short video. Add 3 hashtags."}]}]}
    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200: return res.json()['candidates'][0]['content']['parts'][0]['text'].strip().replace('"', '')
    except: pass
    return "How did he survive this?! 😱 #Gaming"

def main():
    all_files = []
    for drv in DRIVES:
        result = subprocess.run(['rclone', 'lsf', drv], capture_output=True, text=True)
        for f in result.stdout.strip().split('\n'):
            if f.endswith('.mp4'): all_files.append({"drive": drv, "file": f})
    if not all_files: return
    all_files.sort(key=lambda x: x["file"])
    target = all_files[0]
    local_file = "temp_target.mp4"
    subprocess.run(['rclone', 'copyto', f"{target['drive']}/{target['file']}", local_file], check=True)
    caption = get_gemini_caption()
    page_id, token = os.environ.get("FB_PAGE_ID"), os.environ.get("FB_PAGE_TOKEN")
    try:
        with open(local_file, 'rb') as video_file:
            res = requests.post(f"{FB_API_URL}/{page_id}/videos", data={"description": caption, "access_token": token}, files={"source": video_file}, timeout=120)
            if res.status_code == 200:
                print("[SUCCESS] Payload synced successfully.")
                subprocess.run(['rclone', 'deletefile', f"{target['drive']}/{target['file']}"], check=True)
    except Exception as e: print(f"[ERROR] Sync failed: {e}")
    if os.path.exists(local_file): os.remove(local_file)

if __name__ == "__main__":
    main()
