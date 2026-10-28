import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import List, Optional, Tuple

from print_to_png_config import SUPPORTED_DPI_OPTIONS


class OPENFILENAMEW(ctypes.Structure):
    _fields_ = [
        ("lStructSize", wintypes.DWORD), ("hwndOwner", wintypes.HWND),
        ("hInstance", wintypes.HINSTANCE), ("lpstrFilter", wintypes.LPCWSTR),
        ("lpstrCustomFilter", wintypes.LPWSTR), ("nMaxCustFilter", wintypes.DWORD),
        ("nFilterIndex", wintypes.DWORD), ("lpstrFile", wintypes.LPWSTR),
        ("nMaxFile", wintypes.DWORD), ("lpstrFileTitle", wintypes.LPWSTR),
        ("nMaxFileTitle", wintypes.DWORD), ("lpstrInitialDir", wintypes.LPCWSTR),
        ("lpstrTitle", wintypes.LPCWSTR), ("Flags", wintypes.DWORD),
        ("nFileOffset", wintypes.WORD), ("nFileExtension", wintypes.WORD),
        ("lpstrDefExt", wintypes.LPCWSTR), ("lCustData", wintypes.LPARAM),
        ("lpfnHook", ctypes.c_void_p), ("lpTemplateName", wintypes.LPCWSTR),
        ("pvReserved", ctypes.c_void_p), ("dwReserved", wintypes.DWORD),
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
    dpi_options = [default_dpi] + [dpi for dpi in SUPPORTED_DPI_OPTIONS if dpi != default_dpi]
    filter_parts: List[str] = [
        f"PNG 圖片 - {dpi} DPI (*.png)\0*.png" for dpi in dpi_options
    ]
    file_buf = ctypes.create_unicode_buffer(f"{default_filename}.png", 4096)
    ofn = OPENFILENAMEW()
    ofn.lStructSize = ctypes.sizeof(OPENFILENAMEW)
    ofn.hwndOwner = user32.GetForegroundWindow()
    ofn.lpstrFilter = "\0".join(filter_parts) + "\0\0"
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
        index = max(0, min(ofn.nFilterIndex - 1, len(dpi_options) - 1))
        return Path(file_buf.value), dpi_options[index]
    return None, default_dpi
