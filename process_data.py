import subprocess
import os
import requests
import json
import re
import time
import cv2
import numpy as np
import torch
from simple_lama_inpainting import SimpleLama
import datetime
import fcntl
import contextlib

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

PROCESSED_FILE = "processed_links.txt"
if os.path.exists(PROCESSED_FILE):
    with open(PROCESSED_FILE, "r") as f:
        processed_links = set(line.strip() for line in f)
else:
    processed_links = set()

@contextlib.contextmanager
def lama_lock(lock_file_path):
    lock_file = open(lock_file_path, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": CHAT_ID, "text": message}, timeout=10)
    except: pass

def get_new_telegram_links():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?limit=100"
    try:
        res = requests.get(url).json()
        for result in res.get('result', []):
            msg = result.get('channel_post') or result.get('message')
            if msg and 'text' in msg:
                text = msg['text']
                if str(msg['chat']['id']) == str(CHAT_ID) or str(msg['chat']['id']) == str(CHAT_ID).replace('-100', '') or msg['chat']['type'] == 'private':
                    match = re.search(r'(https?://(?:www\.)?(?:bilibili\.com|b23\.tv|facebook\.com|fb\.watch)/\S+)', text)
                    if match:
                        link = match.group(1)
                        if link not in processed_links:
                            return link, msg['message_id'], msg['chat']['id']
    except: pass
    return None, None, None

def mark_as_processed(link):
    processed_links.add(link)
    with open(PROCESSED_FILE, "w") as f:
        for l in processed_links:
            f.write(l + "\n")

def delete_telegram_message(msg_id, chat_id):
    requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage?chat_id={chat_id}&message_id={msg_id}")

def get_cookie_file(link):
    if 'bilibili' in link or 'b23.tv' in link:
        return 'cookies_bili.txt'
    elif 'facebook' in link or 'fb.watch' in link:
        return 'cookies_fb.txt'
    return 'cookies_fb.txt'

def get_metadata(link):
    cookie_file = get_cookie_file(link)
    try:
        cmd = ['yt-dlp', '--dump-json', '--js-runtimes', 'deno', '--cookies', cookie_file, link]
        data = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
        title = data.get('title', 'Video')
        description = data.get('description', '')
        tags = data.get('tags', [])
        caption = f"{title}\n\n{description[:200]}...\n\n"
        if tags: caption += " ".join([f"#{t.replace(' ', '')}" for t in tags[:10]])
        return caption
    except: return "Video tanpa caption"

def download_video(link):
    cookie_file = get_cookie_file(link)
    for res in ['1440', '1080', '720']:
        cmd = ['yt-dlp', '--js-runtimes', 'deno', '--cookies', cookie_file, '-f', f'bestvideo[height<={res}]+bestaudio/best', '--merge-output-format', 'mp4', '--retries', '10', link, '-o', 'raw_video.mp4']
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True
        except: continue
    return False

def crop_watermark(input_path, output_path, x, y, w, h):
    print("[INFO] Langkah 2: Memotong area watermark...")
    cmd = ['ffmpeg', '-y', '-i', input_path, '-vf', f'crop={w}:{h}:{x}:{y}', '-c:v', 'libx264', '-crf', '18', output_path]
    subprocess.run(cmd, check=True, capture_output=True, text=True)

def create_mask(cropped_video):
    print("[INFO] Langkah 3: Membuat masker otomatis...")
    cap = cv2.VideoCapture(cropped_video)
    frames = []
    count = 0
    while cap.isOpened() and count < 7:
        ret, frame = cap.read()
        if not ret: break
        frames.append(frame)
        count += 1
    cap.release()
    
    if len(frames) < 2: return None
    
    std = np.std(frames, axis=0).mean(axis=2)
    static_pixels = (std < 15).astype(np.uint8) * 255
    
    hsv = cv2.cvtColor(frames[0], cv2.COLOR_BGR2HSV)
    bright = ((hsv[:,:,2] > 150) & (hsv[:,:,1] < 90)).astype(np.uint8) * 255
    
    mask = cv2.bitwise_and(static_pixels, bright)
    
    kernel = np.ones((3,3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.dilate(mask, kernel, iterations=3)
    
    cv2.imwrite("mask_check.png", mask)
    
    return mask

def lama_inpaint_with_tmux(input_path, output_path, mask, max_frames_per_segment=1000):
    print("[INFO] Langkah 4: LaMA Inpainting dengan tmux & resume...")
    lama = SimpleLama()
    
    cap = cv2.VideoCapture(input_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    
    segments = []
    for start in range(0, total_frames, max_frames_per_segment):
        end = min(start + max_frames_per_segment, total_frames)
        segments.append((start, end))
    
    cleaned_segments = []
    for idx, (start, end) in enumerate(segments):
        segment_file = f"clean_segment_{idx:03d}.mp4"
        if os.path.exists(segment_file):
            print(f"[INFO] Segmen {idx} sudah ada, lanjut...")
            cleaned_segments.append(segment_file)
            continue
        
        print(f"[INFO] Memproses segmen {idx}: frame {start} sampai {end}")
        
        session_name = f"lama_seg_{idx}"
        cmd = f"tmux new-session -d -s {session_name} 'python process_lama.py {input_path} {segment_file} {start} {end} {mask.shape[0]} {mask.shape[1]}'"
        subprocess.run(cmd, shell=True, check=True)
        
        while True:
            result = subprocess.run(['tmux', 'has-session', '-t', session_name], capture_output=True)
            if result.returncode != 0:
                break
            time.sleep(10)
        
        cleaned_segments.append(segment_file)
    
    with open('concat_list.txt', 'w') as f:
        for seg in cleaned_segments:
            f.write(f"file '{seg}'\n")
    
    subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'concat_list.txt', '-c', 'copy', output_path], check=True)
    os.remove('concat_list.txt')
    for seg in cleaned_segments:
        try: os.remove(seg)
        except: pass
    
    return True

def overlay_back(original_path, cleaned_path, output_path, x, y):
    print("[INFO] Langkah 5: Menempelkan kembali (presisi piksel)...")
    cmd = ['ffmpeg', '-y', '-i', original_path, '-i', cleaned_path, '-filter_complex', f'[0:v][1:v]overlay={x}:{y}', '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'copy', output_path]
    subprocess.run(cmd, check=True, capture_output=True, text=True)

def split_video():
    cmd = ['ffmpeg', '-y', '-i', 'clean_video.mp4', '-c', 'copy', '-map', '0', '-segment_time', '30', '-f', 'segment', 'part_%03d.mp4']
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return sorted([f for f in os.listdir('.') if f.startswith('part_') and f.endswith('.mp4')])

def send_to_telegram(files, caption):
    send_telegram_alert(f"📝 CAPTION & HASHTAG:\n\n{caption}")
    time.sleep(2)
    for i, file in enumerate(files, 1):
        send_telegram_alert(f"PART {i}")
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
        try:
            with open(file, 'rb') as video:
                files_data = {'video': video}
                data = {'chat_id': CHAT_ID, 'supports_streaming': 'true'}
                requests.post(url, data=data, files=files_data, timeout=120)
        except: pass
        time.sleep(1)

def process_link(link, msg_id, chat_id):
    try:
        caption = get_metadata(link)
        if not download_video(link):
            send_telegram_alert("❌ Gagal download video.")
            mark_as_processed(link)
            return False
        
        x, y, w, h = 20, 20, 340, 100
        crop_watermark('raw_video.mp4', 'cropped_wm.mp4', x, y, w, h)
        mask = create_mask('cropped_wm.mp4')
        if mask is None:
            send_telegram_alert("❌ Gagal membuat masker.")
            mark_as_processed(link)
            return False
        
        with lama_lock("lama.lock"):
            lama_inpaint_with_tmux('cropped_wm.mp4', 'cleaned_wm.mp4', mask)
        
        overlay_back('raw_video.mp4', 'cleaned_wm.mp4', 'clean_video.mp4', x, y)
        
        files = split_video()
        if files:
            send_to_telegram(files, caption)
            if msg_id: delete_telegram_message(msg_id, chat_id)
            send_telegram_alert("✅ Semua potongan terkirim. Muse AI, silakan rakit dan upload!")
            mark_as_processed(link)
            return True
        else:
            send_telegram_alert("❌ Tidak ada file yang dihasilkan.")
            mark_as_processed(link)
            return False
                
    except Exception as e: 
        send_telegram_alert(f"❌ Gagal memproses: {e}")
        mark_as_processed(link)
        return False
    finally:
        for f in os.listdir('.'):
            if f.startswith('part_') or f.startswith('clean_segment_') or f in ['raw_video.mp4', 'clean_video.mp4', 'cropped_wm.mp4', 'cleaned_wm.mp4', 'mask_check.png']:
                try: os.remove(f)
                except: pass

def main():
    while True:
        link, msg_id, chat_id = get_new_telegram_links()
        if not link:
            print("[INFO] Tidak ada link baru. Tidur.")
            break
        
        print(f"[INFO] Memproses link: {link}")
        process_link(link, msg_id, chat_id)
        
        time.sleep(5)

if __name__ == "__main__":
    main()
