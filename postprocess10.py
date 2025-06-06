import os
from utils import clean_filename

def process_file(filepath, report):
    try:
        filename = os.path.basename(filepath)
        cleaned_name = clean_filename(filename)
        if cleaned_name != filename:
            os.rename(filepath, os.path.join(os.path.dirname(filepath), cleaned_name))
            filepath = os.path.join(os.path.dirname(filepath), cleaned_name)
        report['processed'] += 1
    except Exception as e:
        report['errors'].append((filepath, str(e)))

def main():
    target_dir = input("Введите название папки (например, CD62): ").strip()
    folder_path = os.path.join("Music", target_dir)
    if not os.path.isdir(folder_path):
        print("Папка не найдена:", folder_path)
        return

    report = {'processed': 0, 'errors': []}

    for filename in os.listdir(folder_path):
        if filename.lower().endswith(".mp3"):
            filepath = os.path.join(folder_path, filename)
            process_file(filepath, report)

    print(f"✔ Обработано треков: {report['processed']}")
    if report['errors']:
        print(f"⚠ Ошибок: {len(report['errors'])}")
        for filepath, error in report['errors']:
            print(" -", os.path.basename(filepath), ":", error)

if __name__ == "__main__":
    main()
