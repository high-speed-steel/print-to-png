$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptDir

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  正在建置獨立一鍵安裝包 install.exe (免預裝 Python)" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

$pythonExe = & python -c "import sys; print(sys.executable)"

Write-Host "`n[1/3] 檢查並安裝 PyInstaller..." -ForegroundColor Yellow
& $pythonExe -m pip install pyinstaller --quiet

Write-Host "`n[2/3] 正在將背景服務編譯為獨立無視窗執行檔 PrintToPNG_Daemon.exe..." -ForegroundColor Yellow
& $pythonExe -m PyInstaller --noconfirm --clean --onefile --noconsole `
    --name "PrintToPNG_Daemon" `
    --collect-all "pypdfium2" `
    --collect-all "pypdfium2_raw" `
    "pdf_to_png_daemon.pyw"

Write-Host "`n[3/3] 正在將 PrintToPNG_Daemon.exe 封裝進單一安裝檔 install.exe..." -ForegroundColor Yellow
& $pythonExe -m PyInstaller --noconfirm --clean --onefile --noconsole `
    --name "install" `
    --add-binary "dist\PrintToPNG_Daemon.exe;." `
    "install.py"

Copy-Item "dist\install.exe" -Destination "$scriptDir\install.exe" -Force

Write-Host "`n======================================================" -ForegroundColor Green
Write-Host "  打包完成！輸出檔案：$scriptDir\install.exe" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
