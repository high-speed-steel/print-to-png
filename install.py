# -*- coding: utf-8 -*-
"""
Print to PNG - Standalone One-Click Installer (install.py -> compiled to install.exe)
=====================================================================================
Extracts the bundled `PrintToPNG_Daemon.exe` to `%LOCALAPPDATA%\\PrintToPNG`,
creates the "Print to PNG" virtual printer and dedicated spool port, generates
`config.json`, registers the Windows startup shortcut (`shell:startup`), and
launches the background daemon immediately.
"""

import ctypes
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PRINTER_NAME = "Print to PNG"
DRIVER_NAME = "Microsoft Print To PDF"
INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "PrintToPNG"
SPOOL_FILE_PATH = Path(os.environ.get("LOCALAPPDATA", "")) / "Temp" / "print_to_png_spool.pdf"
DAEMON_EXE_NAME = "PrintToPNG_Daemon.exe"


def get_bundled_daemon_path() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        p = Path(sys._MEIPASS) / DAEMON_EXE_NAME
        if p.exists():
            return p
    return Path(__file__).resolve().parent / "dist" / DAEMON_EXE_NAME


def run_powershell(ps_script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        capture_output=True,
        text=True,
        creationflags=0x08000000,  # CREATE_NO_WINDOW
    )


def main() -> None:
    try:
        # 1. Stop any running instance before updating
        run_powershell(
            "Stop-Process -Name 'PrintToPNG_Daemon' -Force -ErrorAction SilentlyContinue; "
            "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*pdf_to_png_daemon*' } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        )

        # 2. Create target folder and copy daemon & default config
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        src_daemon = get_bundled_daemon_path()
        target_daemon = INSTALL_DIR / DAEMON_EXE_NAME

        if not src_daemon.exists():
            raise FileNotFoundError(f"找不到內嵌的服務執行檔：{src_daemon}")

        shutil.copy2(src_daemon, target_daemon)

        config_path = INSTALL_DIR / "config.json"
        if not config_path.exists():
            config_path.write_text(
                json.dumps({"default_dpi": 300, "last_save_dir": ""}, indent=4, ensure_ascii=False),
                encoding="utf-8",
            )

        # 3. Configure dedicated port, virtual printer, and Startup shortcut
        port_str = str(SPOOL_FILE_PATH)
        ps_setup = f"""
        $ErrorActionPreference = 'Stop'
        $port = Get-PrinterPort -Name '{port_str}' -ErrorAction SilentlyContinue
        if (-not $port) {{
            Add-PrinterPort -Name '{port_str}'
        }}
        $printer = Get-Printer -Name '{PRINTER_NAME}' -ErrorAction SilentlyContinue
        if ($printer) {{
            Set-Printer -Name '{PRINTER_NAME}' -DriverName '{DRIVER_NAME}' -PortName '{port_str}'
        }} else {{
            Add-Printer -Name '{PRINTER_NAME}' -DriverName '{DRIVER_NAME}' -PortName '{port_str}'
        }}

        $startupFolder = [Environment]::GetFolderPath('Startup')
        $shortcutPath = Join-Path $startupFolder 'PrintToPNG_Daemon.lnk'
        $wsh = New-Object -ComObject WScript.Shell
        $sc = $wsh.CreateShortcut($shortcutPath)
        $sc.TargetPath = '{str(target_daemon)}'
        $sc.WorkingDirectory = '{str(INSTALL_DIR)}'
        $sc.WindowStyle = 7
        $sc.Description = 'Print to PNG 原生直存背景服務'
        $sc.Save()
        """
        res = run_powershell(ps_setup)
        if res.returncode != 0:
            raise RuntimeError(f"印表機或啟動捷徑配置失敗：\n{res.stderr}")

        # 4. Launch background daemon
        subprocess.Popen(
            [str(target_daemon)],
            cwd=str(INSTALL_DIR),
            close_fds=True,
            creationflags=0x00000008 | 0x08000000,  # DETACHED_PROCESS | CREATE_NO_WINDOW
        )

        ctypes.windll.user32.MessageBoxW(
            0,
            f"「{PRINTER_NAME}」已成功安裝並啟動！\n\n"
            f"• 安裝路徑：{INSTALL_DIR}\n"
            f"• 預設解析度：300 DPI（可於另存新檔下拉選單選擇 150–4800 DPI，或調整 config.json）\n"
            f"• 開機自動啟動：已啟用\n\n"
            f"現在您可以在任何軟體按 Ctrl+P 選擇「{PRINTER_NAME}」直接另存 PNG 圖片！",
            "Print to PNG 安裝完成",
            0x00000040,
        )

    except Exception as exc:
        ctypes.windll.user32.MessageBoxW(
            0,
            f"安裝過程中發生錯誤：\n{exc}",
            "Print to PNG 安裝失敗",
            0x00000010,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
