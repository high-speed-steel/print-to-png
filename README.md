# Print to PNG for Windows

將 Windows 列印工作直接輸出為 PNG 圖片的虛擬印表機工具，支援 Windows 10/11。

## Features

- 使用 Windows 原生列印與檔案儲存對話框
- 自動帶入原始文件名稱
- 支援 150、300、600、1200、2400 與 4800 DPI
- 支援單頁與多頁文件輸出
- 多頁文件自動命名為 `<name>_p1.png`、`<name>_p2.png`
- 不產生或保留中間 PDF 檔案
- 與既有的 Microsoft Print to PDF 並存

## Installation

### Installer

1. 從 [Releases](https://github.com/high-speed-steel/print-to-png/releases) 下載安裝程式。
2. 執行安裝程式並依指示完成安裝。
3. 在任意應用程式的列印選單中選擇 **Print to PNG**。

安裝程式會建立虛擬印表機、背景服務與開機啟動項目。

### From source

需求：Python 3.10 或更新版本。

```powershell
pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File .\install_printer.ps1 -DefaultDPI 300 -RegisterStartup
Start-Process pythonw.exe -ArgumentList ".\pdf_to_png_daemon.pyw" -WindowStyle Hidden
```

## Configuration

編輯 `config.json` 可設定預設 DPI：

```json
{
    "default_dpi": 600,
    "last_save_dir": ""
}
```

列印時也可以在檔案儲存對話框中選擇 DPI。

高 DPI 會產生較大的影像。若輸出失敗，請查看 `%LOCALAPPDATA%\PrintToPNG\print_to_png.log`；
日誌會記錄每頁的渲染進度與錯誤原因。

## Uninstallation

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall_printer.ps1
```

此命令會停止背景服務、移除虛擬印表機及清理開機啟動設定。

## Project Files

| File | Description |
| :--- | :--- |
| `pdf_to_png_daemon.pyw` | Background daemon and PDF-to-PNG renderer |
| `install_printer.ps1` | Virtual printer and startup configuration |
| `uninstall_printer.ps1` | Complete uninstallation script |
| `install.py` | Installer source |
| `build_installer.ps1` | Installer build script |
| `config.json` | Default DPI and save-path configuration |
| `requirements.txt` | Python dependencies |

## License

[MIT License](LICENSE)
