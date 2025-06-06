# === 1. Импорты и настройки ===

import os
import re
import requests
import json
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, USLT, TIT2, TPE1, TALB, TDRC, TCON, error
from mutagen import File
from tqdm import tqdm
from pathlib import Path

# Genius API токен
GENIUS_API_TOKEN = "FxBxNMpbQojD7XYl5rMjWPZ0eopXgjV0FQ0CUl2c-7pmL8uEavRA4BooqZujIBmf"

# Заголовки для Genius
GENIUS_HEADERS = {
    "Authorization": f"Bearer {GENIUS_API_TOKEN}"
}

# Каталог с музыкой на телефоне (Termux)
BASE_DIR = "/sdcard/Music"



# === Вспомогательная функция: Поиск песни на Genius ===

def search_genius(artist, title):
    base_url = "https://api.genius.com/search"
    headers = {"Authorization": f"Bearer {GENIUS_API_TOKEN}"}
    query = f"{artist} {title}"
    try:
        response = requests.get(base_url, params={"q": query}, headers=headers, timeout=10)
        data = response.json()
        hits = data.get("response", {}).get("hits", [])
        if hits:
            return hits[0]["result"]
    except Exception:
        pass
    return None
# === 2. Вспомогательные функции ===

def fetch_json(url, headers=None):
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception:
        return None
    return None

def download_image(url):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.content
    except Exception:
        return None
    return None

def safe_add_tag(audio, tag):
    try:
        audio.tags.add(tag)
    except Exception:
        pass

def log_problem(report, filename, message):
    report['problems'].append((filename, message))

# === 3. Очистка имени файла ===

def clean_filename(filepath):
    import re
    import os

    dir_name = os.path.dirname(filepath)
    filename = os.path.basename(filepath)

    # Отделяем имя от расширения
    name, ext = os.path.splitext(filename)

    # Очищаем только имя
    cleaned_name = re.sub(r'[\s_]*[].*?[]', '', name)  # убираем мусор в скобках
    cleaned_name = cleaned_name.strip(" \"'.")  # убираем кавычки, пробелы, точки
    cleaned_name = re.sub(r'\s{2,}', ' ', cleaned_name)  # двойные пробелы
    cleaned_name = re.sub(r'\s*', '', cleaned_name)  # пустые скобки (если остались)

    # Склеиваем обратно с расширением
    final_name = f"{cleaned_name}{ext}"

    cleaned_path = os.path.join(dir_name, final_name)

    # Переименуем файл, если нужно
    if cleaned_path != filepath and os.path.exists(filepath):
        os.rename(filepath, cleaned_path)

    return cleaned_path

# === 4. Загрузка и проверка MP3-файла ===

def load_mp3(path, report):
    try:
        audio = MP3(path, ID3=ID3)

        # Добавим ID3-теги, если их ещё нет
        if audio.tags is None:
            try:
                audio.add_tags()
            except error:
                pass

        return audio
    except Exception as e:
        log_problem(report, os.path.basename(path), "can't sync to MPEG frame")
        return None

# === 5. Получение тегов и обложки из Genius → iTunes → Deezer ===

def search_metadata(title, artist):
    result = {
        'title': title,
        'artist': artist,
        'album': None,
        'year': None,
        'genre': None,
        'cover_url': None,
        'lyrics_url': None
    }

    query = f"{artist} {title}"

    # 1. Genius API
    genius_api_url = f"https://api.genius.com/search?q={requests.utils.quote(query)}"
    data = fetch_json(genius_api_url, GENIUS_HEADERS)
    if data:
        hits = data.get("response", {}).get("hits", [])
        if hits:
            song = hits[0].get("result", {})
            result['lyrics_url'] = song.get("url")
            if not result['title']:
                result['title'] = song.get("title")
            if not result['artist']:
                result['artist'] = song.get("primary_artist", {}).get("name")

    # 2. iTunes Search API (для обложки и альбома)
    itunes_url = f"https://itunes.apple.com/search?term={requests.utils.quote(query)}&limit=1"
    data = fetch_json(itunes_url)
    if data and data.get("resultCount", 0):
        info = data["results"][0]
        result['album'] = info.get("collectionName")
        result['cover_url'] = info.get("artworkUrl100", "").replace("100x100bb", "600x600bb")
        result['year'] = info.get("releaseDate", "")[:4]
        result['genre'] = info.get("primaryGenreName")

    # 3. Deezer API (резервный источник тегов/обложки)
    if not result['cover_url'] or not result['album']:
        deezer_url = f"https://api.deezer.com/search?q={requests.utils.quote(query)}"
        data = fetch_json(deezer_url)
        if data and data.get("data"):
            track = data["data"][0]
            result['album'] = result['album'] or track["album"]["title"]
            result['cover_url'] = result['cover_url'] or track["album"]["cover_xl"]
            result['artist'] = result['artist'] or track["artist"]["name"]
            result['title'] = result['title'] or track["title"]

    return result

# === 6. Получение и вставка текста песни из Genius → Lyrics.ovh ===

def insert_lyrics(audio, title, artist, lyrics_url=None):
    lyrics_text = None

    # 1. Genius (HTML парсинг по URL)
    if lyrics_url:
        try:
            response = requests.get(lyrics_url, headers=GENIUS_HEADERS, timeout=10)
            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, "html.parser")
                lyrics_div = soup.find("div", class_="lyrics") or soup.find("div", class_="Lyrics__Container-sc")
                if lyrics_div:
                    lyrics_text = lyrics_div.get_text(separator="\n").strip()
        except Exception:
            pass

    # 2. Lyrics.ovh API (резерв)
    if not lyrics_text:
        try:
            url = f"https://api.lyrics.ovh/v1/{requests.utils.quote(artist)}/{requests.utils.quote(title)}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                lyrics_text = data.get("lyrics")
        except Exception:
            pass

    # 3. Добавляем в теги
    if lyrics_text:
        try:
            audio.tags.add(USLT(encoding=3, lang='eng', desc='', text=lyrics_text))
            return True
        except Exception:
            pass

    return False

# === 7. Применение тегов и сохранение обложки (iTunes → Deezer → Genius) ===

def insert_cover_image(audio, title, artist, song_info=None):
    cover_url = None

    # 1. iTunes
    try:
        itunes_response = requests.get(
            "https://itunes.apple.com/search",
            params={"term": f"{artist} {title}", "media": "music", "limit": 1},
            timeout=5
        )
        if itunes_response.status_code == 200:
            results = itunes_response.json().get("results")
            if results:
                cover_url = results[0].get("artworkUrl100", "").replace("100x100", "600x600")
    except Exception:
        pass

    # 2. Deezer (если iTunes не дал)
    if not cover_url:
        try:
            query = f"{artist} {title}"
            deezer_response = requests.get(
                f"https://api.deezer.com/search?q={requests.utils.quote(query)}",
                timeout=5
            )
            if deezer_response.status_code == 200:
                data = deezer_response.json().get("data")
                if data:
                    cover_url = data[0].get("album", {}).get("cover_xl")
        except Exception:
            pass

    # 3. Genius (если передан song_info с обложкой)
    if not cover_url and song_info:
        cover_url = song_info.get("song_art_image_url")

    # 4. Скачиваем и вставляем
    if cover_url:
        try:
            img_data = requests.get(cover_url, timeout=10).content
            audio.tags.add(APIC(
                encoding=3,
                mime='image/jpeg',
                type=3,
                desc='Cover',
                data=img_data
            ))
            return True
        except Exception:
            pass

    return False

# === 8. Обработка одного MP3-файла ===

def process_file(file_path, report):
    try:
        # Пропускаем если не mp3
        if not file_path.lower().endswith(".mp3"):
            return

        # Попытка открыть файл
        audio = MP3(file_path, ID3)

        # Проверка ID3 тега
        if audio.tags is None:
            try:
                audio.add_tags()
            except Exception:
                pass  # Уже есть или ошибка добавления

        # === Очистка имени файла от мусора через clean_filename ===
        new_path = clean_filename(file_path)
        if new_path != file_path:
            file_path = new_path
            audio = MP3(file_path, ID3)  # Переоткрываем с новым путём

        base_name = os.path.basename(file_path)
        dir_name = os.path.dirname(file_path)

        # === Извлечение тегов ===
        title = audio.tags.get("TIT2", TIT2(encoding=3, text=os.path.splitext(base_name)[0])).text[0]
        artist = audio.tags.get("TPE1", TPE1(encoding=3, text="Unknown Artist")).text[0]
        year = audio.tags.get("TDRC", TDRC(encoding=3, text="2000")).text[0]

        updated_tags = False
        if not title or title.lower() == "unknown":
            title = os.path.splitext(base_name)[0]
            audio.tags["TIT2"] = TIT2(encoding=3, text=title)
            updated_tags = True
        if not artist or artist.lower() == "unknown":
            artist = "Unknown Artist"
            audio.tags["TPE1"] = TPE1(encoding=3, text=artist)
            updated_tags = True
        if not year or not str(year).isdigit():
            audio.tags["TDRC"] = TDRC(encoding=3, text="2000")
            updated_tags = True

        # === Получение данных с Genius API ===
        genius_result = search_genius(title, artist)
        if genius_result and "url" in genius_result:
            lyrics_added = insert_lyrics(audio, title, artist, lyrics_url=genius_result["url"])
        else:
            lyrics_added = insert_lyrics(audio, title, artist)

        # === Добавление обложки ===
        cover_added = insert_cover_image(audio, title, artist, song_info=genius_result)

        # === Сохранение изменений ===
        audio.save()

        # === Обновление отчёта ===
        report["processed"] += 1
        report["normalized"] += 1
        if updated_tags:
            report["tags"] += 1
        if cover_added:
            report["covers"] += 1
        if lyrics_added:
            report["lyrics"] += 1

    except Exception as e:
        if "can't sync to MPEG frame" in str(e):
            report["problem_files"].append(os.path.basename(file_path))
        else:
            tqdm.write(f"⚠ Ошибка при обработке {file_path}: {e}")

# === 9. Основная функция ===

def main():
    print("Введите номер или имя папки (например: CD62):")
    folder_input = input(">>> ").strip()
    base_path = "/sdcard/Music/"
    full_path = os.path.join(base_path, folder_input if folder_input.startswith("CD") else f"CD{folder_input}")

    if not os.path.isdir(full_path):
        print(f"❌ Папка не найдена: {full_path}")
        return

    # Формируем список файлов
    mp3_files = [f for f in os.listdir(full_path) if f.lower().endswith(".mp3")]
    total = len(mp3_files)
    if total == 0:
        tqdm.write("❗ В выбранной папке нет MP3-файлов.")
        return

    # Инициализация отчёта
    report = {
        "processed": 0,
        "normalized": 0,
        "tags": 0,
        "covers": 0,
        "lyrics": 0,
        "problem_files": []
    }

    tqdm.write(f"🔍 Обработка треков в папке: {full_path}")
    for file in tqdm(mp3_files, desc="Обработка треков", ncols=70):
        process_file(os.path.join(full_path, file), report)

    # === Отчёт ===
    print("\n=== Отчёт ===")
    print(f"✔ Обработано треков: {report['processed']}")
    print(f"🎧 Нормализовано: {report['normalized']}")
    print(f"🏷️ Обновлено тегов: {report['tags']}")
    print(f"🖼️ Добавлено обложек: {report['covers']}")
    print(f"📝 Добавлено текстов песен: {report['lyrics']}")
    print(f"⚠ Проблемных файлов: {len(report['problem_files'])}")
    if report["problem_files"]:
        for bad_file in report["problem_files"]:
            print(f"   - {bad_file}")

if __name__ == "__main__":
    main()

