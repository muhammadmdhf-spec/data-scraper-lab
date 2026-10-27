import subprocess
import os
import json
import whisper
import requests
from ultralytics import YOLO
from scenedetect import detect, ContentDetector
import cv2
import numpy as np

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
QUEUE_FILE = "telegram_queue.json"

def download_source(url):
    cmd = ['yt-dlp', '--js-runtimes', 'deno', '--cookies', 'cookies.txt', '-f', 'bestvideo[height<=1440][vcodec!*=av01]+bestaudio/best', '--merge-output-format', 'mp4', url, '-o', 'source.mp4']
    subprocess.run(cmd, check=True)

def extract_audio_and_transcribe():
    subprocess.run(['ffmpeg', '-y', '-i', 'source.mp4', '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', 'audio.wav'], check=True)
    model = whisper.load_model("base")
    result = model.transcribe("audio.wav", task="translate") 
    return result['segments']

def generate_karaoke_ass(segments, start_time, end_time, filename="subs.ass"):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        f.write("Style: Default,Arial,60,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,0,2,10,10,100,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        for seg in segments:
            if seg['start'] >= start_time and seg['end'] <= end_time:
                s_time = f"0:{int(seg['start']//60):02d}:{seg['start']%60:05.2f}"
                e_time = f"0:{int(seg['end']//60):02d}:{seg['end']%60:05.2f}"
                f.write(f"Dialogue: 0,{s_time},{e_time},Default,,0,0,0,,{{\\k50}}{seg['text'].strip().upper()}\n")

def render_vertical_clip(input_path, start, end, output_name, part_num, segments):
    generate_karaoke_ass(segments, start, end)
    filter_complex = f"crop=ih*(9/16):ih,scale=1080:1920,drawtext=text='PART {part_num}':x=w-150:y=50:fontsize=40:fontcolor=yellow:box=1:boxcolor=black@0.5,drawtext=text='🔥 PENTA KILL!':x=(w-text_w)/2:y=h/4:fontsize=80:fontcolor=red:enable='between(t,0,3)',subtitles=subs.ass"
    cmd = ['ffmpeg', '-y', '-ss', str(start), '-to', str(end), '-i', input_path, '-vf', filter_complex, '-c:v', 'libx265', '-preset', 'fast', '-crf', '23', '-c:a', 'aac', '-b:a', '128k', output_name]
    subprocess.run(cmd, check=True)
    if os.path.exists("subs.ass"): os.remove("subs.ass")

def send_to_telegram(video_path):
    print("[INFO] Sending to Telegram Storage...")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
    try:
        with open(video_path, 'rb') as video:
            files = {'video': video}
            data = {'chat_id': CHAT_ID, 'supports_streaming': 'true'}
            res = requests.post(url, data=data, files=files, timeout=120)
            if res.status_code == 200:
                print(f"[SUCCESS] Sent {video_path} to Telegram.")
                return res.json()['result']['video']['file_id']
    except Exception as e:
        print(f"[ERROR] Failed to send to Telegram: {e}")
    return None

def main():
    if not os.path.exists("input.txt"): return
    with open("input.txt", "r") as f: url = f.readline().strip()
    if not url: return
    
    try:
        download_source(url)
        scene_list = detect('source.mp4', ContentDetector())
        clips = [(s[0].get_seconds(), s[1].get_seconds()) for s in scene_list if 10 < (s[1].get_seconds() - s[0].get_seconds()) < 60][:3]
        if not clips: return
        segments = extract_audio_and_transcribe()
        os.makedirs("output", exist_ok=True)
        
        queue = []
        for idx, (start, end) in enumerate(clips, 1):
            out_name = f"output/part{idx:02d}.mp4"
            render_vertical_clip("source.mp4", start, end, out_name, idx, segments)
            file_id = send_to_telegram(out_name)
            if file_id:
                queue.append({"file_id": file_id, "name": f"part{idx:02d}.mp4"})
                
        with open(QUEUE_FILE, "w") as f:
            json.dump(queue, f)
            
        open("input.txt", "w").close()
    except Exception as e: print(f"[ERROR] {e}")
    finally:
        if os.path.exists("source.mp4"): os.remove("source.mp4")
        if os.path.exists("audio.wav"): os.remove("audio.wav")
        if os.path.exists("output"):
            for f in os.listdir("output"): os.remove(os.path.join("output", f))
            os.rmdir("output")

if __name__ == "__main__":
    main()
