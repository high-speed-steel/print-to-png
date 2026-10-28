import os
import re


def sanitize_filename(raw_title: str) -> str:
    """Strip application prefixes/suffixes and extensions to get a clean base filename."""
    name = raw_title.strip()
    if not name:
        return ""

    prefixes = [
        "Microsoft Word - ",
        "Microsoft PowerPoint - ",
        "Microsoft Excel - ",
        "Adobe Acrobat - ",
        "列印 ",
        "Print ",
    ]
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix) :].strip()

    suffix_patterns = [
        r"\s*[-—–]\s*記事本$",
        r"\s*[-—–]\s*Notepad$",
        r"\s*[-—–]\s*Word$",
        r"\s*[-—–]\s*Excel$",
        r"\s*[-—–]\s*PowerPoint$",
        r"\s*[-—–]\s*Google Chrome$",
        r"\s*[-—–]\s*Microsoft\u200b?\s*Edge$",
        r"\s*[-—–]\s*Mozilla Firefox$",
        r"\s*[-—–]\s*Brave$",
        r"\s*[-—–]\s*相片$",
        r"\s*[-—–]\s*Photos$",
        r"\s*[-—–]\s*WPS Office$",
        r"\s*[-—–]\s*Adobe Acrobat.*$",
        r"\s*[-—–]\s*PDF24.*$",
    ]
    for pattern in suffix_patterns:
        name = re.sub(pattern, "", name, flags=re.IGNORECASE).strip()

    ignore_exact = {
        "列印", "print", "相片", "photos", "未命名", "untitled",
        "小畫家", "paint", "設定", "settings", "檔案總管", "file explorer",
        "print pictures", "列印圖片", "本機連接埠",
    }
    if name.lower() in ignore_exact:
        return ""

    stem, ext = os.path.splitext(name)
    if ext.lower() in {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".txt", ".png", ".jpg", ".jpeg", ".bmp", ".webp", ".html", ".htm", ".md", ".csv"
    } and stem.strip():
        name = stem.strip()

    return re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", name).strip(" ._")
