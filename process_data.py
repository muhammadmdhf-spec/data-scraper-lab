import subprocess
import os
import requests
import json
import random
import re

# --- KONFIGURASI ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
FB_PAGE_ID = os.environ.get("FB_PAGE_ID")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN")
FB_API_URL = "https://graph.facebook.com/v19.0"
BG_IMAGE = "IMG-20261027-WA6038.jpg" # NAMA FILE BACKGROUND KAMU

def send_telegram_alert(message):
    print(f"[ALERT] Sending message to Telegram: {message}")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        print(f"[ERROR] Failed to send alert: {e}")

def delete_telegram_message(message_id, chat_id):
    print(f"[INFO] Deleting processed link (ID: {message_id}) from Telegram...")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage?chat_id={chat_id}&message_id={message_id}"
    requests.get(url)

def get_oldest_telegram_link():
    print("[INFO] Checking Telegram for oldest link in queue...")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?limit=100"
    try:
        res = requests.get(url).json()
        if not res.get('ok'): return None, None, None
        
        # FIFO: Baca dari pesan paling lama ke paling baru
        for result in res['result']:
            msg = result.get('channel_post') or result.get('message')
            if msg and 'text' in msg:
                text = msg['text']
                chat_id = msg['chat']['id']
                msg_id = msg['message_id']
                chat_type = msg['chat']['type']
                
                is_from_channel = str(chat_id) == str(CHAT_ID) or str(chat_id) == str(CHAT_ID).replace('-100', '')
                is_from_private = chat_type == 'private'
                
                if is_from_channel or is_from_private:
                    if "youtube.com" in text or "youtu.be" in text:
                        match = re.search(r'(https?://\S+)', text)
                        if match:
                            print(f"[SUCCESS] Found oldest link: {match.group(1)}")
                            return match.group(1), msg_id, chat_id
                            
    except Exception as e:
        print(f"[ERROR] Fetch Telegram: {e}")
    return None, None, None

def download_video(url):
    print("[INFO] Downloading FULL 4K gameplay video...")
    cmd = ['yt-dlp', '--js-runtimes', 'deno', '--cookies', 'cookies.txt', 
           '-f', 'bestvideo[height<=2160][vcodec!*=av01]+bestaudio/best', 
           '--merge-output-format', 'mp4', url, '-o', 'raw_video.mp4']
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr
        if "Sign in to confirm you're not a bot" in error_msg or "cookies" in error_msg.lower():
            send_telegram_alert("🚨 LAKSAMAN! COOKIE YOUTUBE EXPIRED! Tolong update YT_COOKIES_B64.")
        else:
            send_telegram_alert(f"❌ Gagal mendownload video: {error_msg[:100]}...")
        raise e

def process_and_upload(caption):
    print(f"[INFO] Rendering FULL Video with Overlay Background...")
    final_video = "final_match.mp4"
    thumb = "thumb.jpg"
    
    if not os.path.exists(BG_IMAGE):
        print(f"[ERROR] File '{BG_IMAGE}' tidak ditemukan!")
        send_telegram_alert(f"❌ Gagal Render: File '{BG_IMAGE}' tidak ada di repo.")
        return False
        
    # FILTER FFMPEG: FULL VIDEO Overlay ke Background
    filter_complex = (
        "[1:v]scale=1080:-1[fg];"
        "[0:v][fg]overlay=(W-w)/2:(H-h)/2:shortest=1"
    )
        
    cmd_ffmpeg = [
        'ffmpeg', '-y', 
        '-loop', '1', '-i', BG_IMAGE, 
        '-i', 'raw_video.mp4', 
        '-filter_complex', filter_complex,
        '-c:v', 'libx265', '-preset', 'ultrafast', '-crf', '23',
        '-c:a', 'aac', '-b:a', '128k', final_video
    ]
    subprocess.run(cmd_ffmpeg, check=True)
    
    # Generate Thumbnail dari video yang sudah jadi
    subprocess.run(['ffmpeg', '-y', '-ss', '03', '-i', final_video, '-vframes', '1', thumb], check=True)
    
    print(f"[INFO] Uploading FULL Video to Facebook...")
    url = f"{FB_API_URL}/{FB_PAGE_ID}/videos"
    is_uploaded = False
    
    try:
        with open(final_video, 'rb') as vid, open(thumb, 'rb') as th:
            files = {'source': vid, 'thumb': th}
            data = {'description': caption, 'access_token': FB_PAGE_TOKEN}
            res = requests.post(url, data=data, files=files, timeout=600)
            
            if res.status_code == 200 and 'id' in res.json():
                print(f"[SUCCESS] Video confirmed uploaded! FB Video ID: {res.json()['id']}")
                is_uploaded = True
            else:
                print(f"[ERROR] FB Upload Failed: {res.text}")
                send_telegram_alert(f"❌ Gagal upload video ke FB. Token FB mungkin expired.")
    except Exception as e:
        print(f"[ERROR] Upload Exception: {e}")
        
    if os.path.exists(final_video): os.remove(final_video)
    if os.path.exists(thumb): os.remove(thumb)
    
    return is_uploaded

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
    link, msg_id, chat_id = get_oldest_telegram_link()
    if not link:
        print("[INFO] Antrean kosong. Robot tidur sampai jadwal berikutnya.")
        return

    try:
        download_video(link)
        caption = get_gemini_caption()
        success = process_and_upload(caption)
        
        # HANYA HAPUS LINK JIKA SUKSES UPLOAD KE FB
        if success and msg_id:
            delete_telegram_message(msg_id, chat_id)
    except Exception as e:
        print(f"[ERROR] Processing failed: {e}")
    finally:
        # Bersihkan file sementara
        if os.path.exists('raw_video.mp4'): os.remove('raw_video.mp4')

if __name__ == "__main__":
    main()
