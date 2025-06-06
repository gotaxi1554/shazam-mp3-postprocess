import os
from utils import clean_filename, normalize_audio, update_tags, fetch_lyrics, fetch_cover_image
from tqdm import tqdm

def process_directory(directory_path):
    """
    Обрабатывает все MP3-файлы в указанной директории.
    """
    for filename in tqdm(os.listdir(directory_path), desc="Обработка файлов"):
        if filename.lower().endswith(".mp3"):
            filepath = os.path.join(directory_path, filename)
            base_name = clean_filename(filename)
            # Предполагаем, что имя файла в формате 'Artist - Title'
            parts = base_name.split(" - ")
            if len(parts) == 2:
                artist, title = parts
            else:
                artist = "Unknown"
                title = base_name

            # Нормализация аудио
            normalize_audio(filepath)

            # Получение текста песни
            lyrics = fetch_lyrics(title, artist)

            # Получение обложки
            cover_path = os.path.join(directory_path, f"{base_name}_cover.jpg")
            cover = fetch_cover_image(title, artist, cover_path)

            # Обновление тегов
            update_tags(filepath, title=title, artist=artist, lyrics=lyrics, cover_path=cover)

if __name__ == "__main__":
    cd_number = input("Введите номер папки (например, 01): ").zfill(2)
    music_dir = f"/sdcard/Music/CD{cd_number}"
    if os.path.isdir(music_dir):
        process_directory(music_dir)
        print("Обработка завершена.")
    else:
        print(f"Папка {music_dir} не найдена.")
