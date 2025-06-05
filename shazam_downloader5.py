#!/data/data/com.termux/files/usr/bin/python

import os
import csv
import re
import subprocess
from datetime import datetime
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, USLT, TIT2, TPE1
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
import requests

# === НАСТРОЙКИ ===
CSV_FILE = "/sdcard/Music/SyncedSongs.csv"
BASE_DIR = "/sdcard/Music"
START_CD = 62
MAX_MB = 700
THREADS = 3
ENCODING = "utf-8"

# === ОТКЛЮЧЕНИЕ/ВКЛЮЧЕНИЕ СНА ===
def prevent_sleep():
    subprocess.run(["termux-wake-lock"])

def allow_sleep():
    subprocess.run(["termux-wake-unlock"])

# === ЗАГРУЗКА CSV ===
def parse_csv(file_path):
    with open(file_path, encoding=ENCODING) as f:
        reader = csv.DictReader(f)
        return sorted([
            {
                "artist": row["artist"].strip(),
                "title": row["title"].strip(),
                "date": datetime.fromisoformat(row["date"].replace("Z", ""))
            }
            for row in reader if row["artist"] and row["title"] and row["date"]
        ], key=lambda x: x["date"], reverse=True)

# === ВВОД ПАРАМЕТРОВ ===
def ask_date_range():
    date_format = "%Y-%m-%d"
    start = input("Дата С (ГГГГ-ММ-ДД): ")
    end = input("Дата ПО (ГГГГ-ММ-ДД): ")
    count = int(input("Сколько треков скачать: "))
    return datetime.strptime(start, date_format), datetime.strptime(end, date_format), count

# === ПРОВЕРКА ДУБЛИКАТОВ ===
def is_duplicate(artist, title):
    pattern = f"{artist.lower()} – {title.lower()}.mp3"
    for root, _, files in os.walk(BASE_DIR):
        for name in files:
            if name.lower() == pattern:
                return os.path.join(root, name)
    return None

# === ПОДСЧЁТ РАЗМЕРА ПАПКИ ===
def get_folder_size_mb(path):
    return sum(os.path.getsize(os.path.join(path, f)) for f in os.listdir(path) if f.endswith(".mp3")) / (1024 * 1024)

# === ВЫБОР ПАПКИ ===
def get_next_cd_folder():
    i = START_CD
    while True:
        path = os.path.join(BASE_DIR, f"CD{i}")
        if not os.path.exists(path):
            os.makedirs(path)
        if get_folder_size_mb(path) < MAX_MB:
            return path
        i += 1

# === ПОЛУЧЕНИЕ ТЕКСТА ПЕСНИ ===
def get_lyrics(artist, title):
    try:
        url = f"https://api.lyrics.ovh/v1/{artist}/{title}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and "lyrics" in r.json():
            return r.json()["lyrics"]
    except:
        return None

# === ПОЛУЧЕНИЕ ОБЛОЖКИ С iTUNES ===
def get_album_cover(artist, title):
    try:
        query = f"{artist} {title}"
        url = f"https://itunes.apple.com/search?term={requests.utils.quote(query)}&entity=song&limit=1"
        data = requests.get(url).json()
        if data["resultCount"] > 0:
            art_url = data["results"][0]["artworkUrl100"].replace("100x100", "600x600")
            img = requests.get(art_url)
            return img.content if img.status_code == 200 else None
    except:
        return None

# === СКАЧИВАНИЕ ТРЕКА ===
def download_track(track, results):
    artist, title = track["artist"], track["title"]
    filename = f"{artist} – {title}.mp3"

    dup_path = is_duplicate(artist, title)
    if dup_path:
        results["duplicates"].append(filename)
        return

    folder = get_next_cd_folder()
    filepath = os.path.join(folder, filename)

    search = f"ytsearch3:{artist} {title} audio"
    try:
        subprocess.run([
            "yt-dlp", search,
            "-x", "--audio-format", "mp3", "--audio-quality", "0",
            "--match-filter", "duration < 420",
            "--no-playlist", "-o", filepath
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except:
        results["not_found"].append(f"{artist} – {title}")
        return

    if not os.path.exists(filepath):
        results["not_found"].append(f"{artist} – {title}")
        return

    try:
        audio = MP3(filepath, ID3=ID3)
        if audio.tags is None:
            audio.add_tags()
        audio.tags["TIT2"] = TIT2(encoding=3, text=title)
        audio.tags["TPE1"] = TPE1(encoding=3, text=artist)

        if "APIC:" not in audio:
            cover = get_album_cover(artist, title)
            if cover:
                audio.tags.add(APIC(
                    encoding=3, mime="image/jpeg", type=3, desc="Cover",
                    data=cover
                ))

        lyrics = get_lyrics(artist, title)
        if lyrics:
            audio.tags.add(USLT(encoding=3, lang="eng", desc="Lyrics", text=lyrics))

        audio.save()
        results["downloaded"].append(filename)
    except Exception as e:
        results["errors"].append(f"{filename}: {str(e)}")

# === ОСНОВНАЯ ФУНКЦИЯ ===
def main():
    prevent_sleep()
    try:
        tracks = parse_csv(CSV_FILE)
        start, end, limit = ask_date_range()
        filtered = [t for t in tracks if start <= t["date"] <= end][:limit]

        print(f"\nОбработка {len(filtered)} треков...\n")
        results = {"downloaded": [], "duplicates": [], "not_found": [], "errors": []}

        with ThreadPoolExecutor(max_workers=THREADS) as ex:
            list(tqdm(ex.map(lambda t: download_track(t, results), filtered), total=len(filtered)))

        print("\n✅ Готово:")
        print(f"✔ Скачано: {len(results['downloaded'])}")
        print(f"⏹ Дубликатов: {len(results['duplicates'])}")
        if results["not_found"]:
            print(f"\n❌ Не найдены ({len(results['not_found'])}):")
            for nf in results["not_found"]:
                print(" -", nf)
        if results["errors"]:
            print(f"\n⚠ Ошибки ({len(results['errors'])}):")
            for err in results["errors"]:
                print(" -", err)
    finally:
        allow_sleep()

if __name__ == "__main__":
    main()
