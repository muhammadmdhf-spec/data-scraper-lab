import sys
import cv2
import numpy as np
from simple_lama_inpainting import SimpleLama

def main():
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    start_frame = int(sys.argv[3])
    end_frame = int(sys.argv[4])
    mask_h = int(sys.argv[5])
    mask_w = int(sys.argv[6])
    
    mask = cv2.imread('mask_check.png', cv2.IMREAD_GRAYSCALE)
    
    if mask is None:
        print("[ERROR] File mask_check.png tidak ditemukan!")
        sys.exit(1)
    
    lama = SimpleLama()
    
    cap = cv2.VideoCapture(input_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    # Codec diubah ke mp4v agar bisa ditulis di server GitHub
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
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
