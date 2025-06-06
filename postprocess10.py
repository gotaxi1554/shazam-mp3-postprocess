import os
import sys
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, ID3NoHeaderError
from utils import clean_filename, analyze_filename, get_cover, get_lyrics, update_tags
from tqdm import tqdm

# === Основной процессинг ===
def process_folder(folder_path):
    files = [f for f in os.listdir(folder_path) if f.lower().endswith('.mp3')]
    total = len(files)
    stats = {
        'processed': 0,
        'normalized': 0,
        'tags_updated': 0,
        'covers_added': 0,
        'lyrics_added': 0,
        'problems': []
    }

    print(f"\n🔍 Обработка треков в папке: {folder_path}\n")

    for file in tqdm(files, desc="Обработка треков", unit="трек"):
        try:
            full_path = os.path.join(folder_path, file)
            new_name = clean_filename(file)
            if new_name != file:
                new_path = os.path.join(folder_path, new_name)
                os.rename(full_path, new_path)
                full_path = new_path

            artist, title = analyze_filename(new_name)
            if not artist or not title:
                stats['problems'].append(new_name)
                continue

            audio = MP3(full_path)
            try:
                tags = ID3(full_path)
            except ID3NoHeaderError:
                tags = ID3()

            cover_data = get_cover(artist, title)
            lyrics = get_lyrics(artist, title)
            updated = update_tags(full_path, artist, title, cover_data, lyrics)

            stats['processed'] += 1
            stats['normalized'] += 1  # здесь можно вставить проверку нормализации громкости
            if updated['tags']:
                stats['tags_updated'] += 1
            if updated['cover']:
                stats['covers_added'] += 1
            if updated['lyrics']:
                stats['lyrics_added'] += 1
        except Exception as e:
            stats['problems'].append(file)

    print("\n=== Отчёт ===")
    print(f"✔ Обработано: {stats['processed']}")
    print(f"🎧 Нормализовано: {stats['normalized']}")
    print(f"🏷️ Обновлено тегов: {stats['tags_updated']}")
    print(f"🖼️ Добавлено обложек: {stats['covers_added']}")
    print(f"📝 Добавлено текстов песен: {stats['lyrics_added']}")
    print(f"⚠ Проблемных файлов: {len(stats['problems'])}")
    if stats['problems']:
        print("\n❗ Не удалось обработать:")
        for f in stats['problems']:
            print(f"- {f}")


# === Точка входа ===
if __name__ == "__main__":
    try:
        folder_id = input("Введите номер или имя папки (например: CD62): ").strip()
        if not folder_id:
            raise ValueError("Папка не указана")
        base_path = "/sdcard/Music"
        folder_path = os.path.join(base_path, folder_id)
        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"Папка не найдена: {folder_path}")

        process_folder(folder_path)
    except Exception as err:
        print(f"Ошибка: {err}")
        sys.exit(1)

