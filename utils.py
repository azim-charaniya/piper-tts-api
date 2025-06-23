# utils.py
import os
import time
import logging

CACHE_DIR = os.path.join(os.getcwd(), 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)

def clear_audio_cache():
    one_day_in_seconds = 86400
    current_time = time.time()
    for filename in os.listdir(CACHE_DIR):
        file_path = os.path.join(CACHE_DIR, filename)
        if os.path.isfile(file_path):
            file_mtime = os.path.getmtime(file_path)
            if (current_time - file_mtime) > one_day_in_seconds:
                try:
                    os.remove(file_path)
                    logging.info(f"Removed old cache file: {filename}")
                except OSError as e:
                    logging.error(f"Error removing cache file: {e}")
