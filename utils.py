import os
import re
import requests
import subprocess
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, APIC, USLT, ID3NoHeaderError
from mutagen.mp3 import MP3
from lyricsgenius import Genius

# Инициализация Genius API
GENIUS_ACCESS_TOKEN = "ВАШ_ТОКЕН_ЗДЕСЬ"  # Замените на ваш токен
genius = Genius(GENIUS_ACCESS_TOKEN, skip_non_songs=True, excluded_terms=["(Remix)", "(Live)"])

def clean_filename(filename):
    """
    Очищает имя файла от лишних символов и расширения.
    """
    name = os.path.splitext(filename)[0]
    name = re.sub(r'\s*.*?', '', name)  # удаление текста в скобках
    name = re.sub(r'[_\-]+', ' ', name)     # замена подчеркиваний и дефисов на пробелы
    return name.strip()

def normalize_audio(filepath):
    """
    Нормализует громкость аудиофайла с помощью ffmpeg.
    """
    temp_output = filepath + ".normalized.mp3"
    command = [
        "ffmpeg", "-i", filepath,
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-y", temp_output
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.replace(temp_output, filepath)

def fetch_lyrics(title, artist):
    """
    Получает текст песни с Genius.
    """
    try:
        song = genius.search_song(title, artist)
        if song:
            return song.lyrics
    except Exception as e:
        print(f"Ошибка при получении текста песни: {e}")
    return None

def fetch_cover_image(title, artist, save_path):
    """
    Загружает обложку песни с Genius.
    """
    try:
        song = genius.search_song(title, artist)
        if song and song.song_art_image_url:
            response = requests.get(song.song_art_image_url)
            if response.status_code == 200:
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                return save_path
    except Exception as e:
        print(f"Ошибка при получении обложки: {e}")
    return None

def update_tags(filepath, title, artist, album=None, year=None, lyrics=None, cover_path=None):
    """
    Обновляет ID3-теги MP3-файла.
    """
    try:
        audio = ID3(filepath)
    except ID3NoHeaderError:
        audio = ID3()

    audio["TIT2"] = TIT2(encoding=3, text=title)
    audio["TPE1"] = TPE1(encoding=3, text=artist)
    if album:
        audio["TALB"] = TALB(encoding=3, text=album)
    if year:
        audio["TDRC"] = TDRC(encoding=3, text=str(year))
    if lyrics:
        audio["USLT"] = USLT(encoding=3, desc="Lyrics", text=lyrics)
    if cover_path and os.path.isfile(cover_path):
        with open(cover_path, 'rb') as img:
            audio["APIC"] = APIC(
                encoding=3,
                mime='image/jpeg',
                type=3,
                desc='Cover',
                data=img.read()
            )
    audio.save(filepath)
