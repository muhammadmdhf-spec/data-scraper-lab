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
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
BG_IMAGE = "IMG-20261027-WA6038.jpg"
FB_PAGE_ID = "110050601565770"
STATE_FILE = "state.json"

# ==========================================
# UTILITY & ALERTS
# ==========================================
def send_telegram_alert(message, retries=3):
    print(f"[ALERT] {message}")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for i in range(retries):
        try: 
            res = requests.post(url, data={"chat_id": CHAT_ID, "text": message}, timeout=10)
            if res.status_code == 200: break
        except Exception as e:
            print(f"[ERROR] Gagal kirim notif Telegram (Percobaan {i+1}): {e}")

def check_reminders():
    today = datetime.date.today()
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w") as f: json.dump({"start_date": str(today)}, f)
        return
    with open(STATE_FILE, "r") as f: state = json.load(f)
    if "start_date" not in state:
        with open(STATE_FILE, "w") as f: json.dump({"start_date": str(today)}, f)
        return
    start_date = datetime.datetime.strptime(state["start_date"], "%Y-%m-%d").date()
    days = (today - start_date).days
    if days == 14: send_telegram_alert("🚨 LAKSAMAN! Sudah 2 MINGGU. Waktunya ganti Cookie Facebook (FB_COOKIES_B64)!")
    if days == 21: send_telegram_alert("🚨 LAKSAMAN! Sudah 3 MINGGU. Waktunya ganti Cookie YouTube (YT_COOKIES_B64)!")

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
                    send_telegram_alert("🚨 Cookie FB sudah EXPIRED! Tolong ganti FB_COOKIES_B64!")
                    return False
    return True

# ==========================================
# TELEGRAM PARSER
# ==========================================
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
    except Exception as e: print(f"[ERROR] Telegram: {e}")
    return None, None, None

def delete_telegram_message(msg_id, chat_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage?chat_id={chat_id}&message_id={msg_id}"
    requests.get(url)

# ==========================================
# YOUTUBE DOWNLOADER (FORCE 1080P)
# ==========================================
def download_video(url):
    print("[INFO] Downloading Video (Dipaksa 1080p)...")
    # Memaksa download format 1080p tepat (jika tidak ada, ambil yang terbaik di bawah 1080p)
    cmd_1080 = ['yt-dlp', '--js-runtimes', 'deno', '--cookies', 'cookies.txt', 
           '-f', 'bestvideo[height<=1080]+bestaudio/best', 
           '--merge-output-format', 'mp4', '--retries', '10', url, '-o', 'raw_video.mp4']
    try: 
        subprocess.run(cmd_1080, check=True, capture_output=True, text=True)
        return True
    except Exception as e:
        print(f"[WARNING] Gagal download 1080p: {e}. Mencoba kualitas terendah...")
        cmd_fallback = ['yt-dlp', '--js-runtimes', 'deno', '--cookies', 'cookies.txt', 
               '-f', 'worst', '--retries', '5', url, '-o', 'raw_video.mp4']
        try:
            subprocess.run(cmd_fallback, check=True, capture_output=True, text=True)
            return True
        except Exception as e2:
            send_telegram_alert("❌ Gagal Download Total. Cek Cookie YouTube.")
            raise e2

# ==========================================
# FFMPEG EDITOR (ULTRA HIGH BITRATE 1080P)
# ==========================================
def process_video():
    print("[INFO] Editing Video (1080p Ultra High Bitrate, H.264)...")
    final_video = "final_video.mp4"
    
    # Pastikan resolusi output tepat 1080x1920
    filter_complex = "[1:v]scale=1080:-1[fg];[0:v][fg]overlay=(W-w)/2:(H-h)/2:shortest=1"
    
    # PARAMETER BITRATE SUPER TINGGI:
    # -b:v 25M (Bitrate video 25 Mbps)
    # -maxrate 30M (Batas maksimal 30 Mbps)
    # -bufsize 60M (Buffer size besar)
    # -c:a aac -b:a 320k (Audio kualitas studio)
    # -preset superfast (Agar proses render tidak kelamaan di GitHub)
    
    if not os.path.exists(BG_IMAGE): 
        print("[WARNING] Background image tidak ditemukan! Menggunakan layar hitam.")
        cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=1080x1920', '-i', 'raw_video.mp4', 
               '-filter_complex', filter_complex, 
               '-c:v', 'libx264', '-preset', 'superfast', '-b:v', '25M', '-maxrate', '30M', '-bufsize', '60M',
               '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '320k', final_video]
    else:
        cmd = ['ffmpeg', '-y', '-loop', '1', '-i', BG_IMAGE, '-i', 'raw_video.mp4', 
               '-filter_complex', filter_complex, 
               '-c:v', 'libx264', '-preset', 'superfast', '-b:v', '25M', '-maxrate', '30M', '-bufsize', '60M',
               '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '320k', final_video]
               
    try:
        subprocess.run(cmd, check=True)
        return final_video
    except Exception as e:
        send_telegram_alert(f"❌ Gagal Render Video: {e}")
        return None

# ==========================================
# GEMINI CAPTION GENERATOR
# ==========================================
def get_yt_metadata(url):
    try:
        cmd = ['yt-dlp', '--dump-json', '--js-runtimes', 'deno', '--cookies', 'cookies.txt', url]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return data.get('title', 'HOK Gameplay'), data.get('description', '')[:200]
    except: return "HOK Gameplay", ""

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
        if res.status_code == 200: return res.json()['candidates'][0]['content']['parts'][0]['text'].strip().replace('"', '')
    except: pass
    return "Bro, this clutch play is actually insane! 😱🔥 #HOK"

# ==========================================
# PLAYWRIGHT UPLOADER (THE ULTIMATE FALLBACK)
# ==========================================
def upload_via_playwright(video_path, caption):
    print("[INFO] Memulai Browser Automation (Sistem Pertahanan Berlapis)...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            
            cookies = []
            with open("fb_cookies.txt", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("#") or not line.strip(): continue
                    parts = line.strip().split("\t")
                    if len(parts) == 7:
                        cookies.append({
                            "name": parts[5], "value": parts[6], "domain": parts[0],
                            "path": parts[2], "secure": parts[3] == "TRUE",
                            "expires": float(parts[4]) if parts[4] else -1
                        })
            
            if not cookies:
                send_telegram_alert("❌ Gagal membaca Cookie FB.")
                return False

            context.add_cookies(cookies)
            page = context.new_page()
            
            page.on("dialog", lambda dialog: dialog.accept())
            
            print("[INFO] Health Check: Membuka Facebook...")
            page.goto("https://www.facebook.com/", timeout=60000)
            if "login" in page.url or "checkpoint" in page.url:
                send_telegram_alert("🚨 Cookie FB tidak valid. Tolong ganti FB_COOKIES_B64!")
                return False
                
            print(f"[INFO] Membuka Halaman Page ID: {FB_PAGE_ID}")
            page.goto(f"https://www.facebook.com/profile.php?id={FB_PAGE_ID}/videos", timeout=60000)
            
            try: page.wait_for_load_state("networkidle", timeout=15000)
            except: pass
            page.wait_for_timeout(5000) 
            
            print("[INFO] Mencari Tombol Upload...")
            upload_selectors = [
                '*[aria-label="Foto/video"][role="button"]', '*[aria-label="Photo/video"][role="button"]',
                'div[aria-label="Foto/video"]', 'div[aria-label="Photo/video"]',
                'text="Foto/video"', 'text="Photo/video"'
            ]
            upload_btn = None
            for selector in upload_selectors:
                try:
                    locator = page.locator(selector).first
                    if locator.is_visible(timeout=3000):
                        upload_btn = locator
                        break
                except: continue

            if upload_btn:
                try:
                    with page.expect_file_chooser(timeout=10000) as fc_info:
                        upload_btn.click(force=True)
                    fc_info.value.set_files(video_path)
                except: 
                    upload_btn = None
            
            if not upload_btn:
                print("[WARNING] Tombol gagal diklik. Menggunakan Direct Injection...")
                try:
                    page.locator('input[type="file"]').first.set_input_files(video_path)
                except:
                    send_telegram_alert("❌ Gagal memasukkan file ke FB.")
                    return False

            print("[INFO] Mengetik Caption...")
            try:
                page.locator('[contenteditable="true"]').first.fill(caption)
            except:
                page.locator('div[role="textbox"]').first.fill(caption)
            
            # ========================================================
            # WAKTU TUNGGU DIPERPANJANG KARENA FILENYA BESAR (BITRATE TINGGI)
            # ========================================================
            print("[INFO] Menunggu Facebook memproses video bitrate tinggi (90s)...")
            page.wait_for_timeout(90000) 
            
            print("[INFO] Mencari dan Menekan Tombol Post...")
            post_clicked = False
            post_selectors = [
                'div[role="button"]:has-text("Post")', 'div[role="button"]:has-text("Posting")',
                '*[aria-label="Post"][role="button"]', '*[aria-label="Posting"][role="button"]'
            ]
            for selector in post_selectors:
                try:
                    post_btn = page.locator(selector).last
                    post_btn.wait_for(state="visible", timeout=15000)
                    post_btn.click(force=True, timeout=5000)
                    post_clicked = True
                    break
                except: continue
            
            if not post_clicked:
                print("[WARNING] Klik normal gagal. Menggunakan JavaScript Injection...")
                try:
                    js_script = """
                    var buttons = document.querySelectorAll('div[role="button"]');
                    for (var i = 0; i < buttons.length; i++) {
                        var text = buttons[i].innerText.trim();
                        if (text === 'Post' || text === 'Posting' || text === 'Bagikan') {
                            buttons[i].click();
                            return true;
                        }
                    }
                    return false;
                    """
                    if page.evaluate(js_script): post_clicked = True
                except: pass

            if not post_clicked:
                send_telegram_alert("❌ Gagal Total Menekan Tombol Post.")
                return False

            print("[INFO] Memverifikasi Upload...")
            page.wait_for_timeout(15000) 
            
            try:
                page.wait_for_selector("text=Your video is now live", timeout=30000)
                browser.close(); return True
            except: pass
            
            if page.locator('[contenteditable="true"]').count() == 0:
                browser.close(); return True
                
            if f"/videos" in page.url:
                browser.close(); return True

            send_telegram_alert("⚠️ Upload diproses, tapi verifikasi visual gagal. Cek FB manual.")
            browser.close(); return False
            
    except Exception as e:
        print(f"[ERROR] Playwright Fatal Error: {e}")
        send_telegram_alert(f"❌ Gagal upload via Browser: {str(e)[:50]}")
        return False

# ==========================================
# MAIN EXECUTION
# ==========================================
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
        print(f"[ERROR] Main Error: {e}")
    finally:
        for f in ['raw_video.mp4', 'final_video.mp4', 'audio.wav']:
            if os.path.exists(f): 
                try: os.remove(f)
                except: pass

if __name__ == "__main__":
    main()
