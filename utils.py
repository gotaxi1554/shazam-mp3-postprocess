import os
import re
import sys
from glob import glob
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, USLT, TIT2, TPE1, TALB, TDRC
from tqdm import tqdm

def process_file(filepath, report):
    try:
        # Очистка имени файла
        filename = os.path.basename(filepath)
        cleaned_name = clean_filename(filename)
        if cleaned_name != filename:
            os.rename(filepath, os.path.join(os.path.dirname(filepath), cleaned_name))
            filepath = os.path.join(os.path.dirname(filepath), cleaned_name)

        # Извлекаем исполнителя и название
        artist, title = extract_artist_title(cleaned_name)

        # Загружаем MP3
        audio = MP3(filepath, ID3=ID3)
        if audio.tags is None:
            audio.add_tags()

        # Нормализация звука (псевдо, замени при необходимости)
        normalize_audio(filepath)
        report['normalized'] += 1

        # Обложка
        cover_added = fetch_cover_image(audio, artist, title)
        if cover_added:
            report['covers'] += 1

        # Текст песни
        lyrics_added = fetch_lyrics(audio, artist, title)
        if lyrics_added:
            report['lyrics'] += 1

        # Обновляем и сохраняем теги
        updated = update_tags_and_save(audio, filepath, artist, title)
        if updated:
            report['tags'] += 1

        report['processed'] += 1

    except Exception as e:
        report['errors'] += 1
        report['error_files'].append((filepath, str(e)))


def main():
    folder_input = input("Введите номер или имя папки (например: CD62): ").strip()
    music_dir = os.path.join("/sdcard/Music", folder_input)

    if not os.path.isdir(music_dir):
        print(f"❌ Папка не найдена: {music_dir}")
        sys.exit(1)

    mp3_files = sorted(glob(os.path.join(music_dir, '*.mp3')))
    report = {
        'processed': 0,
        'normalized': 0,
        'tags': 0,
        'covers': 0,
        'lyrics': 0,
        'errors': 0,
        'error_files': []
    }

    print(f"🔍 Обработка треков в папке: {music_dir}")
    for filepath in tqdm(mp3_files, desc="Обработка треков"):
        process_file(filepath, report)

    print("\n=== Отчёт ===")
    print(f"✔ Обработано треков: {report['processed']}")
    print(f"🎧 Нормализовано: {report['normalized']}")
    print(f"🏷️ Обновлено тегов: {report['tags']}")
    print(f"🖼️ Добавлено обложек: {report['covers']}")
    print(f"📝 Добавлено текстов песен: {report['lyrics']}")
    print(f"⚠ Проблемных файлов: {report['errors']}")
    if report['errors']:
        for f, err in report['error_files']:
            print(f" - {os.path.basename(f)}: {err}")

if __name__ == "__main__":
    main()
