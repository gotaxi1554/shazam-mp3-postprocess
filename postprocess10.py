import os
import re
from glob import glob
from tqdm import tqdm
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, USLT, TIT2, TPE1, TALB, TDRC

from utils import (
    clean_filename,
    extract_artist_title,
    normalize_audio,
    fetch_cover_image,
    fetch_lyrics,
    update_tags_and_save
)

def process_file(filepath, report):
    try:
        # Очистка имени файла
        filename = os.path.basename(filepath)
        cleaned_name = clean_filename(filename)
        if cleaned_name != filename:
            os.rename(filepath, os.path.join(os.path.dirname(filepath), cleaned_name))
            filepath = os.path.join(os.path.dirname(filepath), cleaned_name)

        # Извлечение информации
        artist, title = extract_artist_title(cleaned_name)
        if not artist or not title:
            report['errors'].append(filepath)
            return

        # Нормализация звука
        if normalize_audio(filepath):
            report['normalized'] += 1

        # Загрузка обложки
        audio = MP3(filepath, ID3=ID3)
        cover_added = False
        if not any(isinstance(frame, APIC) for frame in audio.tags.values()):
            cover_data = fetch_cover_image(artist, title)
            if cover_data:
                audio.tags.add(APIC(
                    encoding=3,
                    mime='image/jpeg',
                    type=3,
                    desc='Cover',
                    data=cover_data
                ))
                cover_added = True

        # Загрузка текста песни
        lyrics_added = False
        if not any(isinstance(frame, USLT) for frame in audio.tags.values()):
            lyrics = fetch_lyrics(artist, title)
            if lyrics:
                audio.tags.add(USLT(encoding=3, lang='eng', desc='Lyrics', text=lyrics))
                lyrics_added = True

        # Обновление тегов
        updated = update_tags_and_save(audio, artist, title)

        if updated:
            report['tags'] += 1
        if cover_added:
            report['covers'] += 1
        if lyrics_added:
            report['lyrics'] += 1
        report['processed'] += 1

    except Exception as e:
        report['errors'].append(filepath)


def main():
    folder = input("Введите номер или имя папки (например: CD62): ").strip()
    folder_path = os.path.join("/sdcard/Music", folder)
    if not os.path.exists(folder_path):
        print(f"❌ Папка {folder_path} не найдена!")
        return

    files = sorted(glob(os.path.join(folder_path, "*.mp3")))
    if not files:
        print("❗ В папке нет MP3-файлов.")
        return

    report = {
        'processed': 0,
        'normalized': 0,
        'tags': 0,
        'covers': 0,
        'lyrics': 0,
        'errors': []
    }

    print(f"🔍 Обработка треков в папке: {folder_path}\n")

    for filepath in tqdm(files, desc="Обработка треков", unit="трек"):
        process_file(filepath, report)

    print("\n=== Отчёт ===")
    print(f"✔ Обработано: {report['processed']}")
    print(f"🎧 Нормализовано: {report['normalized']}")
    print(f"🏷️ Обновлено тегов: {report['tags']}")
    print(f"🖼️ Добавлено обложек: {report['covers']}")
    print(f"📝 Добавлено текстов песен: {report['lyrics']}")
    print(f"⚠ Проблемных файлов: {len(report['errors'])}")
    if report['errors']:
        print("\nПроблемные файлы:")
        for f in report['errors']:
            print("-", f)

if __name__ == "__main__":
    main()
