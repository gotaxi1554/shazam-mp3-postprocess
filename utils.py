import os
import re
import requests


def analyze_filename(filepath):
    """Извлекает исполнителя и название из файла 'ARTIST - TITLE.mp3'."""
    name = os.path.basename(filepath)
    name, _ = os.path.splitext(name)
    if " - " in name:
        artist, title = name.split(" - ", 1)
        return artist.strip(), title.strip()
    else:
        return None, None

def clean_filename(filepath):
    """
    Переименовывает файл, удаляя любые скобки с содержимым ((), [], {}, __)
    и оставляя только 'Исполнитель - Название'.
    """
    dir_name = os.path.dirname(filepath)
    base = os.path.basename(filepath)
    name, ext = os.path.splitext(base)
    # Удаляем всё в скобках любого типа вместе со скобками и пробелами перед ними
    name = re.sub(r'[\(\[\{_][^)\]\}_]*[\)\]\}_]', '', name)
    # Ещё раз, на случай если несколько скобок подряд
    name = re.sub(r'[\(\[\{_][^)\]\}_]*[\)\]\}_]', '', name)
    # Удаляем двойные и тройные пробелы, а также пробелы у краёв
    name = re.sub(r'\s+', ' ', name).strip()
    # Оставляем только допустимые символы (буквы, цифры, пробел, дефис, подчёркивание, точка)
    clean = re.sub(r'[^\w\s\-.]', '', name).strip()
    # Ещё раз чистим лишние пробелы
    clean = re.sub(r'\s+', ' ', clean).strip()
    new_path = os.path.join(dir_name, clean + ext)
    if new_path != filepath:
        os.rename(filepath, new_path)

def search_itunes_cover(artist, title):
    """Поиск обложки на iTunes."""
    try:
        query = f"{artist} {title}".replace(' ', '+')
        url = f"https://itunes.apple.com/search?term={query}&entity=song&limit=1"
        r = requests.get(url, timeout=5)
        if r.ok:
            data = r.json()
            if data['resultCount'] > 0:
                cover_url = data['results'][0]['artworkUrl100'].replace('100x100bb', '600x600bb')
                img = requests.get(cover_url, timeout=5)
                if img.ok:
                    return img.content
    except Exception:
        pass
    return None

def search_lastfm_cover(artist, title, api_key=None):
    """Поиск обложки на Last.fm (нужен API-ключ)."""
    if not api_key:
        return None
    try:
        url = f"http://ws.audioscrobbler.com/2.0/?method=track.getInfo&api_key={api_key}&artist={artist}&track={title}&format=json"
        r = requests.get(url, timeout=5)
        if r.ok:
            data = r.json()
            images = data.get('track', {}).get('album', {}).get('image', [])
            if images:
                cover_url = images[-1]['#text']
                if cover_url:
                    img = requests.get(cover_url, timeout=5)
                    if img.ok:
                        return img.content
    except Exception:
        pass
    return None

def get_cover(artist, title, lastfm_api_key=None):
    """
    Универсальный поиск обложки: сначала iTunes, затем Last.fm (если есть API-ключ).
    """
    cover = search_itunes_cover(artist, title)
    if cover:
        return cover
    cover = search_lastfm_cover(artist, title, api_key=lastfm_api_key)
    if cover:
        return cover
    # Можно добавить ещё источники!
    return None

def get_lyrics(artist, title):
    """Поиск текста песни на lyrics.ovh"""
    try:
        url = f"https://api.lyrics.ovh/v1/{artist}/{title}"
        r = requests.get(url, timeout=5)
        if r.ok:
            data = r.json()
            lyrics = data.get('lyrics')
            if lyrics:
                return lyrics
    except Exception:
        pass
    # Сюда можно добавить другие источники (например, Genius)
    return None
