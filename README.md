# Print to PNG for Windows

**Print to PNG** 是一套專為 Windows 10 / 11 打造的超輕量、100% 原生體驗「列印直存 PNG 圖片」虛擬印表機系統。

不依賴任何未簽章的第三方虛擬驅動、不跳出任何第三方軟體控制台或廣告視窗——當您在任何軟體按下 `Ctrl + P` 並選擇 **`Print to PNG`** 時，只會彈出 **Windows 檔案總管原生的「另存新檔 (*.png)」對話框**，自動帶入原文件檔名，並支援即時切換 **150 / 300 / 600 / 1200 DPI** 高解析度直存 PNG！

---

## 核心特色

- **100% Windows 原生體驗**：
  沿用微軟官方內建簽章驅動 (`Microsoft Print To PDF`) 結合專屬背景暫存埠與 Win32 `comdlg32.dll` (`GetSaveFileNameW`) 原生對話框，全程無黑窗、無第三方 GUI。
- **與原系統印表機完美共存**：
  採用獨立背景連接埠 (`%LOCALAPPDATA%\Temp\print_to_png_spool.pdf`)，不佔用 `PORTPROMPT:`，確保在開有「Windows 保護列印模式」的 Windows 11 設定頁面中，原有的 `Microsoft Print to PDF` 與 `Print to PNG` 各自獨立顯示。
- **自動帶入原始文件檔名**：
  透過 Win32 Spooler API (`EnumJobsW` / `FindFirstPrinterChangeNotification`) 與前景視窗標題雙重追蹤，彈出「另存新檔」時自動填好 `<原始檔名>.png`。
- **原生下拉選單即時切換 DPI**：
  在原生「另存新檔」視窗的 **「存檔類型(T)」** 下拉選單中，直接內建 4 種解析度檔位：
  - `PNG 圖片 - 300 DPI (*.png)`（預設，可在 `config.json` 修改）
  - `PNG 圖片 - 150 DPI (*.png)`
  - `PNG 圖片 - 600 DPI (*.png)`
  - `PNG 圖片 - 1200 DPI (*.png)`
- **直接輸出 PNG，零 PDF 殘留**：
  採用高效能 `pypdfium2` (PDFium) 渲染引擎，按下「儲存」的瞬間直接將高品質 PNG 寫入目標資料夾：
  - **單頁文件**：直接輸出 `<檔名>.png`
  - **多頁文件**：自動輸出 `<檔名>_p1.png`, `<檔名>_p2.png`, ...

---

## 系統架構與運作流程

```
[任何應用程式 Ctrl+P]
        │
        ▼ 選擇「Print to PNG」
[Microsoft Print To PDF 驅動] ──(Win32 Spooler 捕獲原始檔名)──┐
        │                                                     │
        ▼ 寫入專屬背景暫存埠 (%LOCALAPPDATA%\Temp)            ▼
[Background Daemon (pdf_to_png_daemon.pyw)] <─────────────────┘
        │
        ▼ 呼叫 Win32 comdlg32.GetSaveFileNameW
[彈出 Windows 原生「另存新檔 (*.png)」視窗 (預填原檔名 + 可選 150~1200 DPI)]
        │
        ▼ 使用者點擊「儲存」
[pypdfium2 高速渲染直存目標資料夾 (.png / _p1.png, _p2.png)]
```

---

## 快速安裝方式

### 方式 A：使用單一執行檔 `install.exe`（推薦一般使用者，免安裝 Python）
1. 下載 Release 中的 `install.exe`（或自行透過 `build_installer.ps1` 建置）。
2. 雙擊執行 `install.exe`。
3. 系統將在 2 秒內自動完成：
   - 釋出背景服務至 `%LOCALAPPDATA%\PrintToPNG\PrintToPNG_Daemon.exe`
   - 建立 **`Print to PNG`** 虛擬印表機與專屬連接埠
   - 於 `shell:startup` 註冊開機自動背景啟動
   - 立即啟動無黑窗背景常駐服務

### 方式 B：從原始碼安裝（適合開發者）
1. 確認系統已安裝 Python 3.10+。
2. 安裝依賴套件：
   ```powershell
   pip install -r requirements.txt
   ```
3. 執行 PowerShell 自動部署腳本（建立虛擬印表機並註冊開機自動啟動）：
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install_printer.ps1 -DefaultDPI 300 -RegisterStartup
   ```
4. 立即在背景啟動無黑窗常駐服務：
   ```powershell
   Start-Process pythonw.exe -ArgumentList ".\pdf_to_png_daemon.pyw" -WindowStyle Hidden
   ```

---

## 如何調整預設 DPI？

1. **單次列印時調整**：
   在彈出的 Windows「另存新檔」對話框下方，點開 **「存檔類型(T)」** 下拉選單，直接選擇 `150 DPI`、`300 DPI`、`600 DPI` 或 `1200 DPI`。
2. **永久修改預設 DPI**：
   編輯 `config.json`（若使用 `install.exe` 安裝則位於 `%LOCALAPPDATA%\PrintToPNG\config.json`）中的 `"default_dpi"` 數值：
   ```json
   {
       "default_dpi": 600,
       "last_save_dir": ""
   }
   ```
   修改後無須重啟服務，下一次列印即自動生效。

---

## 解除安裝

執行以下 PowerShell 指令即可完整停止背景服務、移除 `Print to PNG` 虛擬印表機與開機啟動捷徑：

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall_printer.ps1
```

---

## 專案目錄結構

| 檔案名稱 | 說明 |
| :--- | :--- |
| `pdf_to_png_daemon.pyw` | 核心背景服務（監聽暫存埠、捕獲原檔名、彈出原生 `*.png` 另存新檔、PDFium 渲染） |
| `install_printer.ps1` | PowerShell 虛擬印表機、專屬連接埠與開機啟動配置腳本 |
| `uninstall_printer.ps1` | PowerShell 完整解除安裝與清理腳本 |
| `install.py` | 供 PyInstaller 封裝 `install.exe` 使用的自解壓安裝器源碼 |
| `build_installer.ps1` | 一鍵將整套系統打包為單一 `install.exe` 的自動化建置腳本 |
| `config.json` | 預設 DPI 解析度與上次儲存路徑設定檔 |
| `requirements.txt` | Python 套件依賴清單 (`pypdfium2`, `Pillow`, `watchdog`) |
| `LICENSE` | MIT 開源授權條款 |

---

## 授權條款 (License)

本專案採用 [MIT License](LICENSE) 開源授權。
