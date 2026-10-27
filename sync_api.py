import os
import json
import requests
import random

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
QUEUE_FILE = "telegram_queue.json"
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

def download_from_telegram(file_id, filename):
    print(f"[INFO] Downloading {filename} from Telegram...")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
    res = requests.get(url).json()
    if not res.get('ok'): return False
    file_path = res['result']['file_path']
    download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    with requests.get(download_url, stream=True) as r:
        r.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): 
                f.write(chunk)
    return True

def main():
    if not os.path.exists(QUEUE_FILE): return
    with open(QUEUE_FILE, "r") as f: queue = json.load(f)
    if not queue: return

    target = queue[0]
    local_file = "temp_target.mp4"
    
    if download_from_telegram(target['file_id'], local_file):
        caption = get_gemini_caption()
        page_id, token = os.environ.get("FB_PAGE_ID"), os.environ.get("FB_PAGE_TOKEN")
        try:
            print("[INFO] Uploading to Facebook...")
            with open(local_file, 'rb') as video_file:
                res = requests.post(f"{FB_API_URL}/{page_id}/videos", data={"description": caption, "access_token": token}, files={"source": video_file}, timeout=120)
                if res.status_code == 200:
                    print("[SUCCESS] Uploaded to Facebook!")
                    queue.pop(0)
                    with open(QUEUE_FILE, "w") as f: json.dump(queue, f)
        except Exception as e: print(f"[ERROR] FB Upload failed: {e}")
    
    if os.path.exists(local_file): os.remove(local_file)

if __name__ == "__main__":
    main()
