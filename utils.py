import os
import re
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC, USLT
from mutagen.mp3 import MP3

def clean_filename(filename):
    name, ext = os.path.splitext(filename)
    cleaned = re.sub(r'[\[\]{}()_–•“”"*?<>|=]+', "", name)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    cleaned = re.sub(r"(\s[-~\s]*\d{4,})$", "", cleaned)
    return f"{cleaned}{ext}"

# Допиши сюда любые другие утилиты по желанию
