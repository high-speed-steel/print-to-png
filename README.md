# Print to PNG for Windows

A lightweight virtual printer that converts Windows print jobs directly into PNG images. Supports Windows 10 and Windows 11.

## Features

- Uses the native Windows print and save dialogs
- Automatically suggests the original document name
- Supports 150, 300, 600, 1200, 2400, and 4800 DPI
- Supports single-page and multi-page documents
- Names multi-page output as `<name>-p1.png`, `<name>-p2.png`, and so on
- Does not retain intermediate PDF files
- Works alongside Microsoft Print to PDF

## Installation

### Installer

1. Download the installer from [Releases](https://github.com/high-speed-steel/print-to-png/releases).
2. Run the installer and follow the setup instructions.
3. Select **Print to PNG** from any application's print menu.

The installer creates the virtual printer, background service, and startup entry.

### From Source

Requirements: Python 3.10 or later.

```powershell
pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File .\install_printer.ps1 -DefaultDPI 300 -RegisterStartup
Start-Process pythonw.exe -ArgumentList ".\pdf_to_png_daemon.pyw" -WindowStyle Hidden
```

## Configuration

Edit `config.json` to configure the default DPI:

```json
{
    "default_dpi": 600,
    "last_save_dir": ""
}
```

The DPI can also be selected in the native save dialog.

High DPI settings produce larger images and may require more processing time and memory. If rendering fails, check:

```text
%LOCALAPPDATA%\PrintToPNG\print_to_png.log
```

The log records per-page rendering progress and error details.

## Uninstallation

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall_printer.ps1
```

This stops the background service, removes the virtual printer, and cleans up the startup entry.

## Project Files

| File | Description |
| :--- | :--- |
| `pdf_to_png_daemon.pyw` | Background daemon and PDF-to-PNG renderer |
| `print_to_png_config.py` | Configuration and save-directory management |
| `print_to_png_filename.py` | Document-title and filename normalization |
| `print_to_png_dialog.py` | Native Windows PNG save dialog |
| `print_to_png_renderer.py` | Spool-file claiming and PDF rendering |
| `install_printer.ps1` | Virtual printer and startup configuration |
| `uninstall_printer.ps1` | Complete uninstallation script |
| `install.py` | Installer source |
| `build_installer.ps1` | Installer build script |
| `config.json` | Default DPI and save-path configuration |
| `requirements.txt` | Python dependencies |

## License

[MIT License](LICENSE)
