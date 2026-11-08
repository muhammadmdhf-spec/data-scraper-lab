import sys
import cv2
import numpy as np
from lama_inpaint.runtime import LamaInpaint

def main():
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    start_frame = int(sys.argv[3])
    end_frame = int(sys.argv[4])
    mask_h = int(sys.argv[5])
    mask_w = int(sys.argv[6])
    
    # Perbaikan Masalah 1: Load masker asli yang dibuat oleh process_data.py
    mask = cv2.imread('mask_check.png', cv2.IMREAD_GRAYSCALE)
    
    if mask is None:
        print("[ERROR] File mask_check.png tidak ditemukan!")
        sys.exit(1)
    
    lama = LamaInpaint(device='cpu')
    
    cap = cv2.VideoCapture(input_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    # Codec H264 tetap dipertahankan sesuai perintah Raja
    fourcc = cv2.VideoWriter_fourcc(*'h264')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    current_frame = start_frame
    while current_frame < end_frame:
        ret, frame = cap.read()
        if not ret: break
        
        cleaned = lama(frame, mask)
        out.write(cleaned)
        current_frame += 1
    
    cap.release()
    out.release()

if __name__ == "__main__":
    main()
