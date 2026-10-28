# -*- coding: utf-8 -*-
"""
Print to PNG - Native Windows Virtual Printer Daemon (pdf_to_png_daemon.pyw)
============================================================================
Core Workflow:
1. The "Print to PNG" virtual printer routes print jobs to a dedicated local spool file:
   `%LOCALAPPDATA%\\Temp\\print_to_png_spool.pdf`
   (Avoids sharing `PORTPROMPT:` with `Microsoft Print to PDF`, ensuring both printers
   appear independently in Windows 11 Settings).
2. Captures the original document filename via Win32 Spooler API (`EnumJobsW` /
   `FindFirstPrinterChangeNotification`) and active window title fallback.
3. As soon as the spool file is written, invokes the native Windows File Explorer
   Save As dialog (`comdlg32.GetSaveFileNameW`):
   - File name: Pre-filled with `<OriginalDocumentName>.png`.
   - Save as type: Native dropdown supporting `300 DPI`, `150 DPI`, `600 DPI`, and `1200 DPI`.
4. Renders the document directly to the target path as high-quality PNG(s) using `pypdfium2`
   (single page: `<name>.png`, multi-page: `<name>_p1.png`, `<name>_p2.png`), leaving no PDF behind.
"""

import ctypes
from ctypes import wintypes
import json
import logging
import os
import re
import shutil
import sys
import threading
import time
import uuid
import winreg
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pypdfium2 as pdfium
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

# ==============================================================================
# Configuration & Constants
# ==============================================================================
PRINTER_NAME = "Print to PNG"
SPOOL_FILE_PATH = Path(os.environ.get("LOCALAPPDATA", "")) / "Temp" / "print_to_png_spool.pdf"
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

CONFIG_FILE = BASE_DIR / "config.json"
LOG_FILE = BASE_DIR / "print_to_png.log"

DEFAULT_CONFIG = {
    "default_dpi": 300,
    "last_save_dir": "",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("PrintToPNG")


def load_config() -> Dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cfg.update(loaded)
        except Exception as exc:
            logger.warning(f"讀取 config.json 失敗，使用預設值：{exc}")
    else:
        save_config(cfg)
    return cfg


def save_config(cfg: Dict) -> None:
    try:
        CONFIG_FILE.write_text(json.dumps(cfg, indent=4, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        logger.warning(f"寫入 config.json 失敗：{exc}")


# ==============================================================================
# Single Instance Mutex & Per-Monitor DPI Awareness
# ==============================================================================
def init_win32_environment() -> int:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, "Global\\PrintToPNG_Native_Daemon_Mutex")
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        logger.warning("偵測到 Print to PNG 服務已在運行中，本次啟動自動退出。")
        sys.exit(0)
    return mutex


# ==============================================================================
# Default Save Directory Resolution
# ==============================================================================
def get_default_save_dir(cfg: Dict) -> str:
    last_dir = cfg.get("last_save_dir", "")
    if last_dir and Path(last_dir).exists():
        return str(Path(last_dir).resolve())

    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            val, _ = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")
            expanded = Path(os.path.expandvars(val))
            if expanded.exists():
                return str(expanded.resolve())
    except Exception:
        pass

    desktop = Path(os.environ.get("USERPROFILE", "~")).expanduser() / "Desktop"
    return str(desktop.resolve())


# ==============================================================================
# Print Job Original Filename Tracker (Win32 Spooler + Foreground Window)
# ==============================================================================
class SYSTEMTIME(ctypes.Structure):
    _fields_ = [
        ("wYear", wintypes.WORD),
        ("wMonth", wintypes.WORD),
        ("wDayOfWeek", wintypes.WORD),
        ("wDay", wintypes.WORD),
        ("wHour", wintypes.WORD),
        ("wMinute", wintypes.WORD),
        ("wSecond", wintypes.WORD),
        ("wMilliseconds", wintypes.WORD),
    ]


class JOB_INFO_1W(ctypes.Structure):
    _fields_ = [
        ("JobId", wintypes.DWORD),
        ("pPrinterName", wintypes.LPWSTR),
        ("pMachineName", wintypes.LPWSTR),
        ("pUserName", wintypes.LPWSTR),
        ("pDocument", wintypes.LPWSTR),
        ("pDatatype", wintypes.LPWSTR),
        ("pStatus", wintypes.LPWSTR),
        ("Status", wintypes.DWORD),
        ("Priority", wintypes.DWORD),
        ("Position", wintypes.DWORD),
        ("TotalPages", wintypes.DWORD),
        ("PagesPrinted", wintypes.DWORD),
        ("Submitted", SYSTEMTIME),
    ]


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
    for p in prefixes:
        if name.startswith(p):
            name = name[len(p) :].strip()

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
    for pat in suffix_patterns:
        name = re.sub(pat, "", name, flags=re.IGNORECASE).strip()

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

    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", name).strip(" ._")
    return name


class PrintJobTitleTracker:
    PRINTER_CHANGE_JOB = 0x0000FF00

    def __init__(self, printer_name: str) -> None:
        self.printer_name = printer_name
        self._lock = threading.Lock()
        self._last_spooler_doc: str = ""
        self._last_spooler_time: float = 0.0
        self._last_window_doc: str = ""
        self._last_window_time: float = 0.0

    def start(self) -> None:
        threading.Thread(target=self._spooler_loop, daemon=True).start()
        threading.Thread(target=self._active_window_loop, daemon=True).start()

    def get_best_document_name(self) -> str:
        now = time.time()
        with self._lock:
            if self._last_spooler_doc and (now - self._last_spooler_time) <= 15.0:
                return self._last_spooler_doc
            if self._last_window_doc and (now - self._last_window_time) <= 30.0:
                return self._last_window_doc
        return "Printed_Image"

    def _query_jobs(self, winspool, h_printer) -> None:
        needed = wintypes.DWORD(0)
        returned = wintypes.DWORD(0)
        winspool.EnumJobsW(h_printer, 0, 10, 1, None, 0, ctypes.byref(needed), ctypes.byref(returned))
        if needed.value <= 0:
            return
        buf = ctypes.create_string_buffer(needed.value)
        if winspool.EnumJobsW(
            h_printer, 0, 10, 1, buf, needed.value, ctypes.byref(needed), ctypes.byref(returned)
        ) and returned.value > 0:
            jobs = ctypes.cast(buf, ctypes.POINTER(JOB_INFO_1W))
            for i in range(returned.value - 1, -1, -1):
                raw_doc = jobs[i].pDocument
                if raw_doc:
                    clean = sanitize_filename(raw_doc)
                    if clean:
                        with self._lock:
                            self._last_spooler_doc = clean
                            self._last_spooler_time = time.time()
                        logger.info(f"從 Spooler 捕獲列印原始檔名：『{clean}』")
                        break

    def _spooler_loop(self) -> None:
        winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
        kernel32 = ctypes.windll.kernel32

        winspool.OpenPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
        winspool.OpenPrinterW.restype = wintypes.BOOL
        winspool.EnumJobsW.argtypes = [
            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
            ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)
        ]
        winspool.EnumJobsW.restype = wintypes.BOOL
        winspool.FindFirstPrinterChangeNotification.argtypes = [
            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p
        ]
        winspool.FindFirstPrinterChangeNotification.restype = ctypes.c_void_p
        winspool.FindNextPrinterChangeNotification.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p, ctypes.c_void_p
        ]
        winspool.FindNextPrinterChangeNotification.restype = wintypes.BOOL

        while True:
            h_printer = ctypes.c_void_p()
            if not winspool.OpenPrinterW(self.printer_name, ctypes.byref(h_printer), None):
                time.sleep(3.0)
                continue

            h_notify = winspool.FindFirstPrinterChangeNotification(
                h_printer, self.PRINTER_CHANGE_JOB, 0, None
            )
            if not h_notify or h_notify == ctypes.c_void_p(-1).value:
                time.sleep(3.0)
                continue

            while True:
                res = kernel32.WaitForSingleObject(h_notify, 1000)
                if res == 0:
                    change = wintypes.DWORD()
                    winspool.FindNextPrinterChangeNotification(h_notify, ctypes.byref(change), None, None)
                    self._query_jobs(winspool, h_printer)

    def _active_window_loop(self) -> None:
        user32 = ctypes.windll.user32
        while True:
            try:
                hwnd = user32.GetForegroundWindow()
                if hwnd:
                    length = user32.GetWindowTextLengthW(hwnd)
                    if 0 < length < 512:
                        buf = ctypes.create_unicode_buffer(length + 2)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        clean = sanitize_filename(buf.value)
                        if clean:
                            with self._lock:
                                self._last_window_doc = clean
                                self._last_window_time = time.time()
            except Exception:
                pass
            time.sleep(0.3)


# ==============================================================================
# Native Windows Save As Dialog (*.png) via comdlg32.GetSaveFileNameW
# ==============================================================================
class OPENFILENAMEW(ctypes.Structure):
    _fields_ = [
        ("lStructSize", wintypes.DWORD),
        ("hwndOwner", wintypes.HWND),
        ("hInstance", wintypes.HINSTANCE),
        ("lpstrFilter", wintypes.LPCWSTR),
        ("lpstrCustomFilter", wintypes.LPWSTR),
        ("nMaxCustFilter", wintypes.DWORD),
        ("nFilterIndex", wintypes.DWORD),
        ("lpstrFile", wintypes.LPWSTR),
        ("nMaxFile", wintypes.DWORD),
        ("lpstrFileTitle", wintypes.LPWSTR),
        ("nMaxFileTitle", wintypes.DWORD),
        ("lpstrInitialDir", wintypes.LPCWSTR),
        ("lpstrTitle", wintypes.LPCWSTR),
        ("Flags", wintypes.DWORD),
        ("nFileOffset", wintypes.WORD),
        ("nFileExtension", wintypes.WORD),
        ("lpstrDefExt", wintypes.LPCWSTR),
        ("lCustData", wintypes.LPARAM),
        ("lpfnHook", ctypes.c_void_p),
        ("lpTemplateName", wintypes.LPCWSTR),
        ("pvReserved", ctypes.c_void_p),
        ("dwReserved", wintypes.DWORD),
        ("FlagsEx", wintypes.DWORD),
    ]


OFN_OVERWRITEPROMPT = 0x00000002
OFN_NOCHANGEDIR = 0x00000008
OFN_PATHMUSTEXIST = 0x00000800
OFN_EXPLORER = 0x00080000


def prompt_native_png_save_dialog(
    default_filename: str, initial_dir: str, default_dpi: int
) -> Tuple[Optional[Path], int]:
    comdlg32 = ctypes.windll.comdlg32
    user32 = ctypes.windll.user32

    hwnd_owner = user32.GetForegroundWindow()

    dpi_options = [default_dpi] + [d for d in (150, 300, 600, 1200) if d != default_dpi]
    filter_parts: List[str] = []
    for dpi in dpi_options:
        filter_parts.append(f"PNG 圖片 - {dpi} DPI (*.png)\0*.png")
    filter_str = "\0".join(filter_parts) + "\0\0"

    file_buf = ctypes.create_unicode_buffer(f"{default_filename}.png", 4096)

    ofn = OPENFILENAMEW()
    ofn.lStructSize = ctypes.sizeof(OPENFILENAMEW)
    ofn.hwndOwner = hwnd_owner
    ofn.lpstrFilter = filter_str
    ofn.nFilterIndex = 1
    ofn.lpstrFile = ctypes.cast(file_buf, wintypes.LPWSTR)
    ofn.nMaxFile = 4096
    ofn.lpstrInitialDir = initial_dir
    ofn.lpstrTitle = "Print to PNG - 另存 PNG 圖片"
    ofn.lpstrDefExt = "png"
    ofn.Flags = OFN_EXPLORER | OFN_OVERWRITEPROMPT | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR

    comdlg32.GetSaveFileNameW.argtypes = [ctypes.POINTER(OPENFILENAMEW)]
    comdlg32.GetSaveFileNameW.restype = wintypes.BOOL

    if comdlg32.GetSaveFileNameW(ctypes.byref(ofn)):
        chosen_path = Path(file_buf.value)
        chosen_idx = max(0, min(ofn.nFilterIndex - 1, len(dpi_options) - 1))
        chosen_dpi = dpi_options[chosen_idx]
        return chosen_path, chosen_dpi

    return None, default_dpi


# ==============================================================================
# Spool File Claiming & Direct PNG Rendering
# ==============================================================================
def claim_spool_pdf(spool_path: Path) -> Optional[Path]:
    backoff = 0.1
    last_size = -1
    stable_count = 0

    for _ in range(60):
        if not spool_path.exists():
            return None
        try:
            size = spool_path.stat().st_size
            if size > 0:
                with open(spool_path, "rb+") as f:
                    header = f.read(5)
                    if header == b"%PDF-":
                        if size == last_size:
                            stable_count += 1
                            if stable_count >= 2:
                                job_pdf = spool_path.parent / f"print_to_png_job_{uuid.uuid4().hex[:8]}.pdf"
                                shutil.copy2(spool_path, job_pdf)
                                f.seek(0)
                                f.truncate(0)
                                break
                        else:
                            last_size = size
                            stable_count = 1
        except (PermissionError, OSError):
            stable_count = 0

        time.sleep(backoff)
        backoff = min(backoff * 1.25, 0.8)
    else:
        return None

    try:
        spool_path.unlink(missing_ok=True)
    except Exception:
        pass

    return job_pdf


def render_pdf_to_target_png(job_pdf: Path, target_png: Path, dpi: int) -> List[Path]:
    scale = dpi / 72.0
    stem = target_png.stem
    if stem.lower().endswith(".png"):
        stem = stem[:-4]
    parent_dir = target_png.parent
    parent_dir.mkdir(parents=True, exist_ok=True)

    output_files: List[Path] = []
    pdf_doc = pdfium.PdfDocument(str(job_pdf))
    num_pages = len(pdf_doc)
    logger.info(f"開始直接輸出 PNG ({num_pages} 頁, {dpi} DPI) -> {target_png}")

    for page_index in range(num_pages):
        page = pdf_doc[page_index]
        bitmap = page.render(scale=scale, rotation=0)
        pil_image = bitmap.to_pil()

        if num_pages == 1:
            out_path = parent_dir / f"{stem}.png"
        else:
            out_path = parent_dir / f"{stem}_p{page_index + 1}.png"

        pil_image.save(str(out_path), format="PNG", dpi=(dpi, dpi))
        output_files.append(out_path)
        page.close()

    pdf_doc.close()
    return output_files


# ==============================================================================
# Watchdog Spool Port Handler
# ==============================================================================
class SpoolPortHandler(FileSystemEventHandler):
    def __init__(self, title_tracker: PrintJobTitleTracker) -> None:
        super().__init__()
        self.title_tracker = title_tracker
        self._lock = threading.Lock()
        self._busy = False

    def _check_spool_file(self, event_path: str) -> None:
        p = Path(event_path)
        if p.name.lower() != SPOOL_FILE_PATH.name.lower():
            return

        with self._lock:
            if self._busy:
                return
            self._busy = True

        threading.Thread(target=self._process_print_job, daemon=True).start()

    def _process_print_job(self) -> None:
        try:
            job_pdf = claim_spool_pdf(SPOOL_FILE_PATH)
            if not job_pdf or not job_pdf.exists():
                return

            doc_name = self.title_tracker.get_best_document_name()
            cfg = load_config()
            default_dpi = int(cfg.get("default_dpi", 300))
            initial_dir = get_default_save_dir(cfg)

            logger.info(
                f"已攔截列印工作！正在彈出原生 PNG 另存新檔對話框 (預設檔名='{doc_name}.png', 預設 DPI={default_dpi})"
            )

            chosen_path, chosen_dpi = prompt_native_png_save_dialog(
                default_filename=doc_name,
                initial_dir=initial_dir,
                default_dpi=default_dpi,
            )

            if chosen_path is None:
                logger.info("使用者取消了另存新檔對話框，已丟棄本次列印暫存。")
                return

            cfg["last_save_dir"] = str(chosen_path.parent.resolve())
            save_config(cfg)

            outputs = render_pdf_to_target_png(job_pdf, chosen_path, chosen_dpi)
            logger.info(f"直存 PNG 成功 ({chosen_dpi} DPI)：{[str(o) for o in outputs]}")

        except Exception as exc:
            logger.error(f"處理列印轉 PNG 作業時發生錯誤：{exc}", exc_info=True)
        finally:
            try:
                if "job_pdf" in locals() and job_pdf and job_pdf.exists():
                    job_pdf.unlink(missing_ok=True)
            except Exception:
                pass
            with self._lock:
                self._busy = False

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._check_spool_file(event.src_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._check_spool_file(event.src_path)


# ==============================================================================
# Entry Point
# ==============================================================================
def main() -> None:
    _mutex = init_win32_environment()
    cfg = load_config()
    logger.info("======================================================")
    logger.info(
        f"Print to PNG 原生直存服務已啟動 | 預設解析度：{cfg.get('default_dpi', 300)} DPI"
    )
    logger.info(f"專屬暫存連接埠：{SPOOL_FILE_PATH}")
    logger.info(f"設定檔路徑：{CONFIG_FILE}")
    logger.info("======================================================")

    SPOOL_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    title_tracker = PrintJobTitleTracker(PRINTER_NAME)
    title_tracker.start()

    handler = SpoolPortHandler(title_tracker)
    observer = Observer()
    observer.schedule(handler, str(SPOOL_FILE_PATH.parent), recursive=False)
    observer.start()

    if SPOOL_FILE_PATH.exists() and SPOOL_FILE_PATH.stat().st_size > 0:
        handler._check_spool_file(str(SPOOL_FILE_PATH))

    try:
        while True:
            time.sleep(1.0)
    except (KeyboardInterrupt, SystemExit):
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
