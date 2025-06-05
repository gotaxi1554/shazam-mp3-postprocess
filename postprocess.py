import os
import re
import requests
import json
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC, USLT, ID3NoHeaderError
from mutagen.mp3 import MP3
from io import BytesIO

GENIUS_API_TOKEN = "FxBxNMpbQojD7XYl5rMjWPZ0eopXgjV0FQ0CUl2c-7pmL8uEavRA4BooqZujIBmf"

# --- Регулярка для очистки имени файла от мусора в конце ---
CLEANUP_PATTERNS = [
    r"\s*_[^)]*$",       # _(*)
    r"\s*[^)]*$",        # (*)
    r"\s*[^]*$",       # [*]
    r"\s*-\s*Official.*$",   # - Official*
    r"\s*-\s*Radio Edit.*$", # - Radio Edit*
    r"\s*-\s*Extended.*$",   # - Extended*
    r"\s*-\s*Remix.*$",      # - Remix*
    r"\s*\d{4}$",            # 2020, 1999 в конце
]

def clean_filename(filename: str) -> str:
    name, ext = os.path.splitext(filename)
    original_name = name
    for pattern in CLEANUP_PATTERNS:
        name = re.sub(pattern, "", name, flags=re.IGNORECASE)
    name = name.strip()
    if name != original_name:
        print(f"Файл: очистка имени '{original_name}' -> '{name}'")
    return name + ext

# --- Функция для получения данных трека с Genius API ---
def genius_search_track(title, artist):
    headers = {'Authorization': f'Bearer {GENIUS_API_TOKEN}'}
    q = f"{title} {artist}"
    url = f"https://api.genius.com/search?q={requests.utils.quote(q)}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        json_resp = resp.json()
        hits = json_resp.get('response', {}).get('hits', [])
        if not hits:
            return None
        song_info = hits[0]['result']
        return song_info
    except Exception as e:
        print(f"Genius API error: {e}")
        return None

# --- Функция для получения текста песни с Genius (новый парсер) ---
def genius_get_lyrics(song_url):
    try:
        page = requests.get(song_url, timeout=10)
        page.raise_for_status()
        html = page.text

        # Новый парсер: ищем div с классом Lyrics__Container
        lyrics_parts = re.findall(r'<div class="Lyrics__Container.*?">(.*?)</div>', html, flags=re.DOTALL)
        if not lyrics_parts:
            # fallback: старый стиль
            lyrics = re.search(r'<div data-lyrics-container="true">(.*?)</div>', html, flags=re.DOTALL)
            if lyrics:
                return re.sub(r'<.*?>', '', lyrics.group(1)).strip()
            else:
                return None

        # Очистка от html-тегов и объединение частей
        lyrics = "\n".join(re.sub(r'<.*?>', '', part).strip() for part in lyrics_parts)
        return lyrics.strip()
    except Exception as e:
        print(f"Ошибка получения текста Genius: {e}")
        return None

# --- Получение обложки с iTunes API ---
def itunes_get_artwork(title, artist):
    try:
        query = f"{artist} {title}"
        url = f"https://itunes.apple.com/search?term={requests.utils.quote(query)}&entity=song&limit=1"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        results = resp.json().get('results', [])
        if not results:
            return None
        artwork_url = results[0].get('artworkUrl100', '')
        if artwork_url:
            # Получаем 600x600 версию
            artwork_url = artwork_url.replace('100x100bb.jpg', '600x600bb.jpg')
            return artwork_url
        return None
    except Exception as e:
        print(f"Ошибка iTunes API: {e}")
        return None

# --- Получение обложки с Deezer API ---
def deezer_get_artwork(title, artist):
    try:
        query = f"{artist} {title}"
        url = f"https://api.deezer.com/search?q={requests.utils.quote(query)}&limit=1"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get('data'):
            cover = data['data'][0].get('album', {}).get('cover_big', None)
            return cover
        return None
    except Exception as e:
        print(f"Ошибка Deezer API: {e}")
        return None

# --- Скачивание картинки по URL и подготовка для вставки ---
def download_image(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        content_type = resp.headers.get('Content-Type', '').lower()
        if not content_type.startswith('image/'):
            return None, None
        ext = content_type.split('/')[-1]
        if ext not in ['jpeg', 'jpg', 'png']:
            # Не поддерживаемые форматы (например webp)
            return None, None
        return resp.content, ext
    except Exception as e:
        print(f"Ошибка скачивания обложки: {e}")
        return None, None

# --- Вставка обложки в MP3 ---
def embed_cover(mp3, image_data, image_ext):
    if not image_data:
        return False
    try:
        mime = f"image/{image_ext}"
        apic = APIC(
            encoding=3,
            mime=mime,
            type=3,
            desc='Cover',
            data=image_data
        )
        mp3.tags.add(apic)
        return True
    except Exception as e:
        print(f"Ошибка вставки обложки: {e}")
        return False

# --- Вставка текста песни ---
def embed_lyrics(mp3, lyrics):
    if not lyrics:
        return False
    try:
        uslt = USLT(encoding=3, lang='eng', desc='Lyrics', text=lyrics)
        mp3.tags.add(uslt)
        return True
    except Exception as e:
        print(f"Ошибка вставки текста: {e}")
        return False

# --- Основная обработка файла ---
def process_file(filepath, report):
    filename = os.path.basename(filepath)
    dirpath = os.path.dirname(filepath)

    # 1. Очистка имени файла и переименование
    cleaned_name = clean_filename(filename)
    new_path = os.path.join(dirpath, cleaned_name)
    if new_path != filepath:
        if not os.path.exists(new_path):
            os.rename(filepath, new_path)
            filepath = new_path
            report['renamed_files'] += 1
        else:
            # Если файл с чистым именем уже есть — добавим к отчёту как проблемный
            report['problem_files'].append(filename)
            return

    # 2. Проверяем что файл — MP3 и читаем теги
    try:
        audio = MP3(filepath, ID3=ID3)
    except Exception:
        report['problem_files'].append(filename)
        return

    # Если нет тегов — создаём
    try:
        audio.add_tags()
    except ID3NoHeaderError:
        audio.tags = ID3()

    # Для чтения/записи простых тегов
    easy_tags = EasyID3(filepath)

    # 3. Извлекаем предполагаемые теги (исполнитель и название)
    artist = easy_tags.get('artist', [None])[0]
    title = easy_tags.get('title', [None])[0]

    # Если не хватает - пытаемся взять из имени файла (часть до " - ")
    if not artist or not title:
        parts = os.path.splitext(cleaned_name)[0].split(' - ')
        if len(parts) >= 2:
            artist = artist or parts[0].strip()
            title = title or parts[1].strip()

    if not artist or not title:
        report['problem_files'].append(filename)
        return

    # 4. Получаем данные с Genius
    song_info = genius_search_track(title, artist)

    # Попытка обновить теги
    updated = False
    if song_info:
        genius_artist = song_info.get('primary_artist', {}).get('name')
        genius_title = song_info.get('title')
        genius_year = None
        release_date = song_info.get('release_date')
        if release_date and len(release_date) >= 4:
            genius_year = release_date[:4]

        # Обновляем теги если пустые
        if not easy_tags.get('artist'):
            easy_tags['artist'] = genius_artist
            updated = True
        if not easy_tags.get('title'):
            easy_tags['title'] = genius_title
            updated = True
        if genius_year and not easy_tags.get('date'):
            easy_tags['date'] = genius_year
            updated = True
    else:
        # TODO: тут можно расширить поиск через Deezer, Last.fm и др.
        pass

    # 5. Получаем обложку через цепочку источников
    cover_url = None

    # iTunes
    cover_url = itunes_get_artwork(title, artist)
    if not cover_url:
        cover_url = deezer_get_artwork(title, artist)
    if not cover_url and song_info:
        cover_url = song_info.get('song_art_image_url')

    cover_added = False
    if cover_url:
        img_data, img_ext = download_image(cover_url)
        if img_data:
            cover_added = embed_cover(audio, img_data, img_ext)
            if cover_added:
                updated = True

# 6. Получаем и вставляем текст песни
    lyrics_added = False
    lyrics = None
    if song_info and 'url' in song_info:
        lyrics = genius_get_lyrics(song_info['url'])
        if lyrics:
            lyrics_added = embed_lyrics(audio, lyrics)
            if lyrics_added:
                updated = True

    # 7. Сохраняем изменения, если что-то обновилось
    if updated:
        easy_tags.save()
        audio.save()
        report['updated_tags'] += 1
    if cover_added:
        report['covers_added'] += 1
    if lyrics_added:
        report['lyrics_added'] += 1

    report['processed'] += 1


# --- Запуск обработки выбранной папки ---
def main():
    print("Введите номер или имя папки (например: CD62):")
    folder = input(">>> ").strip()
    if not folder:
        print("Не указана папка.")
        return

    if folder.isdigit():
        folder = f"CD{folder}"

    full_path = os.path.join("/sdcard/Music", folder)
    if not os.path.isdir(full_path):
        print(f"Папка не найдена: {full_path}")
        return

    report = {
        'processed': 0,
        'renamed_files': 0,
        'updated_tags': 0,
        'covers_added': 0,
        'lyrics_added': 0,
        'problem_files': []
    }

    files = [f for f in os.listdir(full_path) if f.lower().endswith('.mp3')]
    for file in files:
        process_file(os.path.join(full_path, file), report)

    # --- Финальный отчёт ---
    print("\n🎧 Обработано треков:", report['processed'])
    print("✏️ Переименовано файлов:", report['renamed_files'])
    print("🏷️ Обновлено тегов:", report['updated_tags'])
    print("🖼️ Добавлено обложек:", report['covers_added'])
    print("📝 Добавлено текстов песен:", report['lyrics_added'])

    if report['problem_files']:
        print("⚠ Проблемные файлы:")
        for f in report['problem_files']:
            print("   -", f)


if __name__ == "__main__":
    main()
