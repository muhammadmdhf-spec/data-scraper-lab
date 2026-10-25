import yt_dlp
import os

def fetch_best_resource():
    print("[INFO] Fetching resource...")
    search_queries = ["Honor of Kings global skin review", "HOK global gameplay top", "Honor of Kings funny moments"]
    ydl_opts = {'quiet': True, 'extract_flat': True, 'force_generic_extractor': True}
    valid_candidates = []

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for query in search_queries:
            try:
                result = ydl.extract_info(f"ytsearch10:{query}", download=False)
                for entry in result.get('entries', []):
                    if not entry: continue
                    title = entry.get('title', '').lower()
                    views = entry.get('view_count', 0) or 0
                    if "indonesia" in title or "indo" in title: continue
                    if views < 1000: continue
                    valid_candidates.append({'id': entry.get('id'), 'views': views, 'url': f"https://www.youtube.com/watch?v={entry.get('id')}"})
            except Exception as e: pass

    if valid_candidates:
        valid_candidates.sort(key=lambda x: x['views'], reverse=True)
        with open("input.txt", "w") as f: f.write(valid_candidates[0]['url'] + "\n")
        print(f"[SUCCESS] Found target with {valid_candidates[0]['views']} views.")

if __name__ == "__main__":
    fetch_best_resource()
