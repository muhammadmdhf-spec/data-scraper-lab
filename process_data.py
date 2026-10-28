import subprocess
import os
import requests
import json
import random
import re
import datetime
from playwright.sync_api import sync_playwright

# --- KONFIGURASI ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip() # Hanya untuk Channel/Grup
BG_IMAGE = "IMG-20261027-WA6038.jpg"
FB_PAGE_ID = "110050601565770" # ID Page Ethan Wayne
STATE_FILE = "state.json"

def send_telegram_alert(message):
    print(f"[ALERT] {message}")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try: 
        requests.post(url, data={"chat_id": CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        print(f"[ERROR] Gagal kirim notif Telegram: {e}")

# 🛡️ FITUR 1: AUTO-REMINDER COOKIE (14 HARI FB & 21 HARI YT)
def check_reminders():
    today = datetime.date.today()
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w") as f: 
            json.dump({"start_date": str(today)}, f)
        return
    
    with open(STATE_FILE, "r") as f: 
        state = json.load(f)
    
    if "start_date" not in state:
        with open(STATE_FILE, "w") as f: 
            json.dump({"start_date": str(today)}, f)
        return

    start_date = datetime.datetime.strptime(state["start_date"], "%Y-%m-%d").date()
    days = (today - start_date).days

    if days == 14:
        send_telegram_alert("🚨 LAKSAMAN! Sudah 2 MINGGU. Waktunya ganti Cookie Facebook (FB_COOKIES_B64) agar akun aman!")
    if days == 21:
        send_telegram_alert("🚨 LAKSAMAN! Sudah 3 MINGGU. Waktunya ganti Cookie YouTube (YT_COOKIES_B64) agar download lancar!")

# 🍪 FITUR 2: DETEKSI COOKIE FB EXPIRED DINI
def check_fb_cookie_expiry():
    print("[INFO] Checking FB Cookie Expiry...")
    if not os.path.exists("fb_cookies.txt"): return False
    with open("fb_cookies.txt", "r") as f:
        for line in f:
            if line.startswith("#") or not line.strip(): continue
            parts = line.strip().split("\t")
            if len(parts) == 7 and parts[5] == "c_user": 
                exp_timestamp = int(parts[4])
                exp_date = datetime.datetime.fromtimestamp(exp_timestamp)
                if exp_date < datetime.datetime.now():
                    send_telegram_alert("🚨 Cookie FB sudah EXPIRED (Berdasarkan Tanggal). Tolong ganti FB_COOKIES_B64!")
                    return False
    return True

def get_oldest_telegram_link():
    print("[INFO] Checking Telegram...")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?limit=100"
    try:
        res = requests.get(url).json()
        for result in res.get('result', []):
            msg = result.get('channel_post') or result.get('message')
            if msg and 'text' in msg:
                text = msg['text']
                chat_id = msg['chat']['id']
                msg_id = msg['message_id']
                chat_type = msg['chat']['type']
                
                if str(chat_id) == str(CHAT_ID) or str(chat_id) == str(CHAT_ID).replace('-100', '') or chat_type == 'private':
                    match = re.search(r'(https?://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+)', text)
                    if match: return match.group(1), msg_id, chat_id
    except Exception as e: 
        print(f"[ERROR] Telegram: {e}")
    return None, None, None

def delete_telegram_message(msg_id, chat_id):
    print(f"[INFO] Menghapus link dari Telegram...")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage?chat_id={chat_id}&message_id={msg_id}"
    requests.get(url)

def get_yt_metadata(url):
    print("[INFO] Mengambil Metadata YouTube...")
    try:
        cmd = ['yt-dlp', '--dump-json', '--js-runtimes', 'deno', '--cookies', 'cookies.txt', url]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return data.get('title', 'HOK Gameplay'), data.get('description', '')[:200]
    except: 
        return "HOK Gameplay", ""

def download_video(url):
    print("[INFO] Downloading 4K Video...")
    cmd = ['yt-dlp', '--js-runtimes', 'deno', '--cookies', 'cookies.txt', 
           '-f', 'bestvideo[height<=2160][vcodec!*=av01]+bestaudio/best', 
           '--merge-output-format', 'mp4', url, '-o', 'raw_video.mp4']
    try: 
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except Exception as e:
        send_telegram_alert("❌ Gagal Download. Cek Cookie YouTube (YT_COOKIES_B64).")
        raise e

def process_video():
    print("[INFO] Editing Video with Overlay...")
    if not os.path.exists(BG_IMAGE): 
        send_telegram_alert("❌ File background tidak ada di repo!")
        return None
    filter_complex = "[1:v]scale=1080:-1[fg];[0:v][fg]overlay=(W-w)/2:(H-h)/2:shortest=1"
    cmd = ['ffmpeg', '-y', '-loop', '1', '-i', BG_IMAGE, '-i', 'raw_video.mp4', 
           '-filter_complex', filter_complex, '-c:v', 'libx265', '-preset', 'ultrafast', 
           '-crf', '23', '-c:a', 'aac', '-b:a', '192k', 'final_video.mp4']
    subprocess.run(cmd, check=True)
    return "final_video.mp4"

def generate_caption(yt_title, yt_desc):
    print("[INFO] Membuat Caption Slang Amerika...")
    api_keys = [os.environ.get("GEMINI_KEY_1"), os.environ.get("GEMINI_KEY_2"), os.environ.get("GEMINI_KEY_3")]
    valid_keys = [k for k in api_keys if k]
    if not valid_keys: return "Bro this gameplay is insane! 💀 #HOK #HonorOfKings"
    
    prompt = f"YT Title: '{yt_title}' Desc: '{yt_desc}'. Write a 1-sentence clickbait American slang caption for FB Reels. Max 125 chars. 3 viral hashtags. Sound like a hyped gamer, NOT an AI."
    
    api_key = random.choice(valid_keys)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        if res.status_code == 200: 
            return res.json()['candidates'][0]['content']['parts'][0]['text'].strip().replace('"', '')
    except: pass
    return "Bro, this clutch play is actually insane! 😱🔥 #HOK #HonorOfKings"

# 🎭 FITUR 3: SMART LOCATORS & HEALTH CHECK (DENGAN USER-AGENT DESKTOP)
def upload_via_playwright(video_path, caption):
    print("[INFO] Memulai Browser Automation (Playwright)...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            
            # MEMAKSA BROWSER MENGGUNAKAN TAMPILAN DESKTOP (BUKAN M.FACEBOOK)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            
            with open("fb_cookies.txt", "r") as f:
                cookies = [{"domain": l.split("\t")[0], "flag": l.split("\t")[1], "path": l.split("\t")[2],
                            "secure": l.split("\t")[3]=="TRUE", "expirationDate": int(l.split("\t")[4]), 
                            "name": l.split("\t")[5], "value": l.split("\t")[6]} 
                           for l in f if not l.startswith("#") and len(l.split("\t"))==7]
            context.add_cookies(cookies)
            
            page = context.new_page()
            
            # HEALTH CHECK
            print("[INFO] Health Check: Membuka Facebook...")
            page.goto("https://www.facebook.com/", timeout=60000)
            if "login" in page.url or "checkpoint" in page.url:
                send_telegram_alert("🚨 Cookie FB tidak valid (diminta login). Tolong ganti FB_COOKIES_B64!")
                return False
                
            print(f"[INFO] Membuka Halaman Page ID: {FB_PAGE_ID}")
            page.goto(f"https://www.facebook.com/profile.php?id={FB_PAGE_ID}/videos", timeout=60000)
            page.wait_for_timeout(5000)
            
            # SMART LOCATORS
            print("[INFO] Mencari Tombol Upload...")
            try:
                page.locator("div[aria-label='Photo/Video']").first.click(timeout=5000)
            except:
                try: 
                    page.get_by_role("button", name=re.compile(r"Video|Foto/Video", re.IGNORECASE)).first.click(timeout=5000)
                except: 
                    page.locator("text='Photo/Video'").first.click(timeout=5000)
            
            page.wait_for_timeout(3000)
            print("[INFO] Memasukkan File Video 4K...")
            page.locator('input[type="file"]').first.set_input_files(video_path)
            
            # TUNGGU PROSES 4K (60 DETIK)
            print("[INFO] Menunggu Facebook memproses video 4K (60s)...")
            page.wait_for_timeout(60000) 
            
            print("[INFO] Mengetik Caption...")
            page.locator('[contenteditable="true"]').first.fill(caption)
            page.wait_for_timeout(2000)
            
            print("[INFO] Menekan Tombol Posting...")
            try: 
                page.get_by_role("button", name=re.compile(r"Post|Posting|Bagikan", re.IGNORECASE)).last.click(timeout=10000)
            except: 
                page.locator("div[aria-label='Post']").last.click(timeout=10000)
            
            # VERIFIKASI SUKSES
            print("[INFO] Memverifikasi Upload...")
            try:
                page.wait_for_selector("text=Your video is now live", timeout=60000)
                print("[SUCCESS] Verified Live on FB!")
                browser.close(); return True
            except:
                if page.locator('[contenteditable="true"]').count() == 0:
                    print("[SUCCESS] Modal tertutup. Menganggap sukses.")
                    browser.close(); return True
                else:
                    send_telegram_alert("⚠️ Upload diproses, tapi verifikasi gagal. Cek FB manual.")
                    browser.close(); return False
    except Exception as e:
        print(f"[ERROR] Playwright: {e}")
        send_telegram_alert(f"❌ Gagal upload via Browser: {str(e)[:50]}")
        return False

def main():
    check_reminders()
    if not check_fb_cookie_expiry(): return 
    
    link, msg_id, chat_id = get_oldest_telegram_link()
    if not link:
        print("[INFO] Antrean kosong. Robot tidur.")
        return

    try:
        yt_title, yt_desc = get_yt_metadata(link)
        download_video(link)
        final_video = process_video()
        
        if final_video:
            caption = generate_caption(yt_title, yt_desc)
            print(f"[INFO] Caption Final: {caption}")
            
            success = upload_via_playwright(final_video, caption)
            
            if success and msg_id:
                delete_telegram_message(msg_id, chat_id)
                
    except Exception as e: 
        print(f"[ERROR] Main: {e}")
    finally:
        for f in ['raw_video.mp4', 'final_video.mp4']:
            if os.path.exists(f): os.remove(f)

if __name__ == "__main__":
    main()
