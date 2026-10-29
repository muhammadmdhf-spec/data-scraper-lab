import subprocess
import os
import requests
import json
import random
import re
import datetime
import base64
from playwright.sync_api import sync_playwright

# --- KONFIGURASI ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
BG_IMAGE = "IMG-20261027-WA6038.jpg"
FB_PAGE_ID = "110050601565770"
STATE_FILE = "state.json"
MEMORY_FILE = "ui_memory.json"

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
        except: pass

def check_reminders():
    today = datetime.date.today()
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w") as f: json.dump({"start_date": str(today)}, f)
        return
    with open(STATE_FILE, "r") as f: state = json.load(f)
    start_date = datetime.datetime.strptime(state.get("start_date", str(today)), "%Y-%m-%d").date()
    days = (today - start_date).days
    if days == 14: send_telegram_alert("🚨 LAKSAMAN! Sudah 2 MINGGU. Waktunya ganti Cookie Facebook (FB_COOKIES_B64)!")
    if days == 21: send_telegram_alert("🚨 LAKSAMAN! Sudah 3 MINGGU. Waktunya ganti Cookie YouTube (YT_COOKIES_B64)!")

def check_fb_cookie_expiry():
    if not os.path.exists("fb_cookies.txt"): return False
    with open("fb_cookies.txt", "r") as f:
        for line in f:
            if line.startswith("#") or not line.strip(): continue
            parts = line.strip().split("\t")
            if len(parts) == 7 and parts[5] == "c_user": 
                if datetime.datetime.fromtimestamp(int(parts[4])) < datetime.datetime.now():
                    send_telegram_alert("🚨 Cookie FB sudah EXPIRED! Tolong ganti FB_COOKIES_B64!")
                    return False
    return True

# ==========================================
# UI MEMORY (OTAK PEMBELAJARAN BOT)
# ==========================================
def load_ui_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return {}

def save_ui_memory(data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f)
    print("[INFO] Memori UI berhasil disimpan ke file lokal.")

def push_ui_memory_to_github():
    # Fungsi untuk mengunggah memori ke GitHub agar diingat besok
    print("[INFO] Mengunggah memori ke GitHub...")
    try:
        subprocess.run(['git', 'config', '--global', 'user.name', 'AutoBot'], check=True)
        subprocess.run(['git', 'config', '--global', 'user.email', 'bot@autobot.com'], check=True)
        subprocess.run(['git', 'add', MEMORY_FILE], check=True)
        subprocess.run(['git', 'commit', '-m', 'Update UI Memory (Learned from Gemini)'], check=True)
        # Gunakan token bawaan GitHub Actions untuk push
        subprocess.run(['git', 'push'], check=True)
        print("[SUCCESS] Memori berhasil diunggah ke GitHub!")
    except Exception as e:
        print(f"[WARNING] Gagal push memori: {e}")

# ==========================================
# TELEGRAM & DOWNLOADER
# ==========================================
def get_oldest_telegram_link():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?limit=100"
    try:
        res = requests.get(url).json()
        for result in res.get('result', []):
            msg = result.get('channel_post') or result.get('message')
            if msg and 'text' in msg:
                text = msg['text']
                if str(msg['chat']['id']) == str(CHAT_ID) or str(msg['chat']['id']) == str(CHAT_ID).replace('-100', '') or msg['chat']['type'] == 'private':
                    match = re.search(r'(https?://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+)', text)
                    if match: return match.group(1), msg['message_id'], msg['chat']['id']
    except: pass
    return None, None, None

def delete_telegram_message(msg_id, chat_id):
    requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage?chat_id={chat_id}&message_id={msg_id}")

def download_video(url):
    print("[INFO] Downloading 1080p Video...")
    cmd = ['yt-dlp', '--js-runtimes', 'deno', '--cookies', 'cookies.txt', '-f', 'bestvideo[height<=1080]+bestaudio/best', '--merge-output-format', 'mp4', '--retries', '10', url, '-o', 'raw_video.mp4']
    subprocess.run(cmd, check=True, capture_output=True, text=True)

def process_video():
    print("[INFO] Editing Video (1080p Ultra High Bitrate, H.264)...")
    filter_complex = "[1:v]scale=1080:-1[fg];[0:v][fg]overlay=(W-w)/2:(H-h)/2:shortest=1"
    cmd = ['ffmpeg', '-y', '-loop', '1', '-i', BG_IMAGE, '-i', 'raw_video.mp4', '-filter_complex', filter_complex, '-c:v', 'libx264', '-preset', 'superfast', '-b:v', '25M', '-maxrate', '30M', '-bufsize', '60M', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '320k', 'final_video.mp4']
    subprocess.run(cmd, check=True)
    return "final_video.mp4"

def get_yt_metadata(url):
    try:
        cmd = ['yt-dlp', '--dump-json', '--js-runtimes', 'deno', '--cookies', 'cookies.txt', url]
        data = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
        return data.get('title', 'HOK Gameplay'), data.get('description', '')[:200]
    except: return "HOK Gameplay", ""

def generate_caption(yt_title, yt_desc):
    api_keys = [os.environ.get("GEMINI_KEY_1"), os.environ.get("GEMINI_KEY_2"), os.environ.get("GEMINI_KEY_3")]
    valid_keys = [k for k in api_keys if k]
    if not valid_keys: return "Bro this gameplay is insane! 💀 #HOK #HonorOfKings"
    prompt = f"YT Title: '{yt_title}' Desc: '{yt_desc}'. Write a 1-sentence clickbait American slang caption for FB Reels. Max 125 chars. 3 viral hashtags. Sound like a hyped gamer, NOT an AI."
    try:
        res = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={random.choice(valid_keys)}", json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        if res.status_code == 200: return res.json()['candidates'][0]['content']['parts'][0]['text'].strip().replace('"', '')
    except: pass
    return "Bro, this clutch play is actually insane! 😱🔥 #HOK"

# ==========================================
# 🧠 AI VISION & LEARNING
# ==========================================
def ask_gemini_vision(page):
    print("[INFO] Memanggil Guru (Gemini Vision) untuk mencari tombol Post...")
    screenshot_path = "fb_screen.png"
    try:
        page.screenshot(path=screenshot_path)
        with open(screenshot_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        
        api_keys = [os.environ.get("GEMINI_KEY_1"), os.environ.get("GEMINI_KEY_2"), os.environ.get("GEMINI_KEY_3")]
        valid_keys = [k for k in api_keys if k]
        
        prompt = """
        Ini adalah screenshot halaman upload video Facebook. 
        Tolong cari tombol 'Post' atau 'Posting' atau 'Bagikan'.
        Jika tombol tersebut berwarna BIRU (aktif), berikan koordinat X dan Y-nya dalam format JSON: {"x": 123, "y": 456}.
        Jika tombol masih ABU-ABU (disabled), balas dengan: {"status": "disabled"}.
        Jangan berikan teks lain selain JSON.
        """
        
        payload = {"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/png", "data": encoded_string}}]}]}
        
        for key in valid_keys:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
            res = requests.post(url, json=payload, timeout=30)
            if res.status_code == 200:
                text_response = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                json_match = re.search(r'\{.*\}', text_response)
                if json_match:
                    data = json.loads(json_match.group())
                    if "x" in data and "y" in data: return data["x"], data["y"]
                    elif data.get("status") == "disabled": return "disabled"
        return None
    except Exception as e:
        print(f"[ERROR] AI Vision Exception: {e}")
        return None
    finally:
        if os.path.exists(screenshot_path): os.remove(screenshot_path)

# ==========================================
# PLAYWRIGHT UPLOADER (THE ULTIMATE FALLBACK)
# ==========================================
def upload_via_playwright(video_path, caption):
    print("[INFO] Memulai Browser Automation (Sistem Pembelajaran)...")
    ui_memory = load_ui_memory()
    
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
                        cookies.append({"name": parts[5], "value": parts[6], "domain": parts[0], "path": parts[2], "secure": parts[3] == "TRUE", "expires": float(parts[4]) if parts[4] else -1})
            
            context.add_cookies(cookies)
            page = context.new_page()
            page.on("dialog", lambda dialog: dialog.accept())
            
            print(f"[INFO] Membuka Halaman Page ID: {FB_PAGE_ID}")
            page.goto(f"https://www.facebook.com/profile.php?id={FB_PAGE_ID}/videos", timeout=60000)
            try: page.wait_for_load_state("networkidle", timeout=15000)
            except: pass
            page.wait_for_timeout(5000) 
            
            print("[INFO] Mencari Tombol Upload...")
            upload_btn = page.locator('*[aria-label="Foto/video"][role="button"], *[aria-label="Photo/video"][role="button"]').first
            if upload_btn.is_visible():
                with page.expect_file_chooser(timeout=10000) as fc_info:
                    upload_btn.click(force=True)
                fc_info.value.set_files(video_path)
            else:
                page.locator('input[type="file"]').first.set_input_files(video_path)

            print("[INFO] Mengetik Caption...")
            page.locator('[contenteditable="true"]').first.fill(caption)
            
            print("[INFO] Menunggu Facebook memproses video (60s)...")
            page.wait_for_timeout(60000) 
            
            # ========================================================
            # 🧠 PROSES BELAJAR & MENGAJAR
            # ========================================================
            post_success = False
            
            # LANGKAH 1: Cek Memori (Apakah bot sudah pintar?)
            if "post_coords" in ui_memory:
                coords = ui_memory["post_coords"]
                print(f"[INFO] Memori ditemukan! Mencoba klik koordinat X:{coords['x']}, Y:{coords['y']}...")
                page.mouse.click(coords['x'], coords['y'])
                page.wait_for_timeout(10000)
                
                # Cek apakah berhasil (Modal tertutup)
                if page.locator('[contenteditable="true"]').count() == 0:
                    print("[SUCCESS] Memori bekerja sempurna! Tombol Post berhasil diklik tanpa Gemini.")
                    post_success = True
                else:
                    print("[WARNING] Memori gagal (Facebook merubah UI). Menghapus memori lama...")
                    del ui_memory["post_coords"]
            
            # LANGKAH 2: Jika Memori Gagal atau Belum Ada, Panggil Guru (Gemini)
            if not post_success:
                max_ai_retries = 5
                for attempt in range(max_ai_retries):
                    print(f"[INFO] Memanggil Guru (AI Vision), Percobaan ke-{attempt+1}...")
                    ai_result = ask_gemini_vision(page)
                    
                    if ai_result == "disabled":
                        print("[INFO] AI melihat tombol Post masih disabled. Menunggu 30 detik lagi...")
                        page.wait_for_timeout(30000)
                        continue
                        
                    elif isinstance(ai_result, tuple):
                        x, y = ai_result
                        print(f"[INFO] Guru menemukan koordinat X:{x}, Y:{y}. Mengklik...")
                        page.mouse.click(x, y)
                        page.wait_for_timeout(10000)
                        
                        # Cek apakah berhasil
                        if page.locator('[contenteditable="true"]').count() == 0:
                            print("[SUCCESS] Guru berhasil! Video terupload.")
                            # SIMPAN KE MEMORI
                            ui_memory["post_coords"] = {"x": x, "y": y}
                            save_ui_memory(ui_memory)
                            post_success = True
                            break
                    else:
                        print("[WARNING] Guru buta atau error. Mencoba JS Injection...")
                        try:
                            js_script = "var b = document.querySelectorAll('div[role=\"button\"]'); for(var i=0; i<b.length; i++){ if(['Post','Posting','Bagikan'].includes(b[i].innerText.trim())){ b[i].click(); return true; } } return false;"
                            if page.evaluate(js_script): 
                                print("[SUCCESS] JS Injection berhasil!")
                                post_success = True
                                break
                        except: pass
                        page.wait_for_timeout(30000)

            if not post_success:
                send_telegram_alert("❌ AI Vision dan Fallback JS gagal menemukan tombol Post.")
                browser.close(); return False

            print("[INFO] Memverifikasi Upload...")
            page.wait_for_timeout(15000) 
            
            if page.locator('[contenteditable="true"]').count() == 0:
                browser.close(); return True
                
            send_telegram_alert("⚠️ Tombol diklik, tapi verifikasi visual gagal. Cek FB manual.")
            browser.close(); return False
            
    except Exception as e:
        send_telegram_alert(f"❌ Fatal Error: {str(e)[:50]}")
        return False

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    check_reminders()
    if not check_fb_cookie_expiry(): return 
    
    link, msg_id, chat_id = get_oldest_telegram_link()
    if not link: return

    try:
        yt_title, yt_desc = get_yt_metadata(link)
        download_video(link)
        final_video = process_video()
        
        if final_video:
            caption = generate_caption(yt_title, yt_desc)
            success = upload_via_playwright(final_video, caption)
            
            if success and msg_id:
                delete_telegram_message(msg_id, chat_id)
                
            # Jika ada memori baru, push ke GitHub
            if os.path.exists(MEMORY_FILE):
                push_ui_memory_to_github()
                
    except Exception as e: 
        print(f"[ERROR] Main Error: {e}")
    finally:
        for f in ['raw_video.mp4', 'final_video.mp4', 'audio.wav', 'fb_screen.png']:
            if os.path.exists(f): 
                try: os.remove(f)
                except: pass

if __name__ == "__main__":
    main()
