import subprocess
import os
from datetime import datetime, timedelta

def run_script(script_name):
    print(f"[INFO] Executing module: {script_name}...")
    try:
        subprocess.run(["python", script_name], check=True)
    except subprocess.CalledProcessError:
        print(f"[ERROR] Module {script_name} failed.")

def main():
    now_wib = datetime.utcnow() + timedelta(hours=7)
    hour = now_wib.hour
    upload_hours = [1, 5, 9, 13, 18, 22]
    
    if hour in upload_hours:
        run_script("sync_api.py")
    else:
        run_script("process_data.py")

if __name__ == "__main__":
    main()
