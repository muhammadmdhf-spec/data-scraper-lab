import subprocess
import os
import requests
import json
import random
import re
import whisper

# --- KONFIGURASI ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
FB_PAGE_ID = os.environ.get("FB_PAGE_ID")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN")
FB_API_URL = "https://graph.facebook.com/v19.0"

def send_telegram_alert(message):
    print(f"[ALERT] Sending message to Telegram: {message}")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        print(f"[ERROR] Failed to send alert: {e}")

def get_telegram_link():
    print("[INFO] Checking Telegram for new links...")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?limit=10"
    try:
        res = requests.get(url).json()
        if not res.get('ok'): return None, None
        
        for result in reversed(res['result']):
            if 'message' in result and 'text' in result['message']:
                text = result['message']['text']
                chat_id = result['message']['chat']['id']
                message_id = result['message']['message_id']
                
                if str(chat_id) == str(CHAT_ID) or str(chat_id) == str(CHAT_ID).replace('-100', ''):
                    if "youtube.com" in text or "youtu.be" in text:
                        match = re.search(r'(https?://\S+)', text)
                        if match:
                            return match.group(1), message_id
    except Exception as e:
        print(f"[ERROR] Fetch Telegram: {e}")
    return None, None

def delete_telegram_message(message_id):
    print(f"[INFO] Deleting message {message_id} from Telegram...")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage?chat_id={CHAT_ID}&message_id={message_id}"
    requests.get(url)

def download_video(url):
    print("[INFO] Downloading full gameplay video...")
    cmd = ['yt-dlp', '--js-runtimes', 'deno', '--cookies', 'cookies.txt', 
           '-f', 'bestvideo[height<=1080][vcodec!*=av01]+bestaudio/best', 
           '--merge-output-format', 'mp4', url, '-o', 'raw_video.mp4']
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr
        if "Sign in to confirm you're not a bot" in error_msg or "cookies" in error_msg.lower():
            send_telegram_alert("🚨 LAKSAMAN! COOKIE YOUTUBE EXPIRED! Tolong update YT_COOKIES_B64 di GitHub Secrets.")
        else:
            send_telegram_alert(f"❌ Gagal mendownload video: {error_msg[:100]}...")
        raise e

def find_matches():
    print("[INFO] Extracting audio to find matches...")
    subprocess.run(['ffmpeg', '-y', '-i', 'raw_video.mp4', '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', 'audio.wav'], check=True)
    
    print("[INFO] Whisper is listening...")
    model = whisper.load_model("base")
    result = model.transcribe("audio.wav", task="transcribe") 
    
    matches = []
    current_start = None
    start_words = ["welcome", "welcome to honor of kings", "welcome to hok"]
    end_words = ["victory", "defeat", "win", "lost", "game over"]

    for seg in result['segments']:
        text = seg['text'].lower()
        if current_start is None:
            if any(word in text for word in start_words):
                current_start = seg['start']
        else:
            if any(word in text for word in end_words):
                end_time = seg['end']
                matches.append((current_start, end_time))
                current_start = None
                
    if not matches:
        matches.append((10, min(60, len(result['segments'])))
    return matches

def process_and_upload(matches, caption):
    success_count = 0
    for i, (start, end) in enumerate(matches, 1):
        print(f"[INFO] Rendering Match {i} (Top Focus - Full Screen)...")
        final_video = f"match_{i}.mp4"
        thumb = f"thumb_{i}.jpg"
        
        # FILTER FFMPEG: FULL SCREEN, FOKUS KE ATAS (Agar Map & Skor kelihatan)
        # Kita potong rasio 9:16 secara presisi, dan posisinya di ATAS (y=0)
        filter_complex = "crop=ih*(9/16):ih:(iw-ih*(9/16))/2:0,scale=1080:1920"
            
        cmd_ffmpeg = [
            'ffmpeg', '-y', '-ss', str(start), '-to', str(end), '-i', 'raw_video.mp4',
            '-vf', filter_complex,
            '-c:v', 'libx265', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k', final_video
        ]
        subprocess.run(cmd_ffmpeg, check=True)
        
        subprocess.run(['ffmpeg', '-y', '-ss', '03', '-i', final_video, '-vframes', '1', thumb], check=True)
        
        print(f"[INFO] Uploading Match {i} to Facebook...")
        url = f"{FB_API_URL}/{FB_PAGE_ID}/videos"
        is_uploaded = False
        
        try:
            with open(final_video, 'rb') as vid, open(thumb, 'rb') as th:
                files = {'source': vid, 'thumb': th}
                data = {'description': caption, 'access_token': FB_PAGE_TOKEN}
                res = requests.post(url, data=data, files=files, timeout=300)
                
                if res.status_code == 200 and 'id' in res.json():
                    print(f"[SUCCESS] Match {i} confirmed uploaded! FB Video ID: {res.json()['id']}")
                    is_uploaded = True
                else:
                    print(f"[ERROR] FB Upload Failed: {res.text}")
                    send_telegram_alert(f"❌ Gagal upload Match {i} ke FB. Token FB mungkin expired.")
        except Exception as e:
            print(f"[ERROR] Upload Exception: {e}")
            
        if os.path.exists(final_video): os.remove(final_video)
        if os.path.exists(thumb): os.remove(thumb)
        if is_uploaded: success_count += 1
    return success_count > 0

def get_gemini_caption():
    api_keys = [os.environ.get("GEMINI_KEY_1"), os.environ.get("GEMINI_KEY_2"), os.environ.get("GEMINI_KEY_3")]
    valid_keys = [k for k in api_keys if k]
    if not valid_keys: return "Bro, this clutch play is actually insane! 😱🔥 #HonorOfKings #HOK"
    
    api_key = random.choice(valid_keys)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    prompt_text = "You are an American TikTok gaming influencer. Write a short, viral, slang-filled clickbait caption for an Honor of Kings pure gameplay video. Use words like 'Bro', 'Insane', 'Clutch', 'W', 'Cracked'. Ask a question to bait comments. Include 3-5 viral gaming hashtags. Max 150 chars."
    payload = {"contents": [{"parts": [{"text": prompt_text}]}]}
    
    try:
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code == 200: 
            res_json = res.json()
            if 'candidates' in res_json and len(res_json['candidates']) > 0:
                return res_json['candidates'][0]['content']['parts'][0]['text'].strip().replace('"', '')
    except Exception as e:
        print(f"[WARNING] Gemini Exception: {e}")
    return "Bro, this clutch play is actually insane! 😱🔥 Drop a W in the comments! #HonorOfKings #HOK"

def main():
    link, msg_id = get_telegram_link()
    if not link:
        print("[INFO] No new YouTube links in Telegram. Sleeping.")
        return

    try:
        download_video(link)
        matches = find_matches()
        if matches:
            caption = get_gemini_caption()
            success = process_and_upload(matches, caption)
            if success and msg_id:
                delete_telegram_message(msg_id)
    except Exception as e:
        print(f"[ERROR] Processing failed: {e}")
    finally:
        for f in ['raw_video.mp4', 'audio.wav']:
            if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    main()
