<#
.SYNOPSIS
    建立 Windows 本地的「Print to PNG」獨立虛擬印表機與開機自動啟動任務。
.DESCRIPTION
    1. 為「Print to PNG」建立專屬的背景暫存連接埠 (%LOCALAPPDATA%\Temp\print_to_png_spool.pdf)，
       不與原本的 Microsoft Print to PDF 共用 PORTPROMPT:，讓兩台印表機在 Windows 11 設定中各自獨立顯示。
    2. 支援 -DefaultDPI <int> 直接設定預設輸出 DPI（例如 150, 300, 600, 1200）。
    3. 支援 -RegisterStartup 自動將 pdf_to_png_daemon.pyw 註冊至 Windows「啟動 (shell:startup)」。
#>

[CmdletBinding()]
param (
    [string]$PrinterName = "Print to PNG",
    [string]$DriverName  = "Microsoft Print To PDF",
    [string]$PortName    = "$env:LOCALAPPDATA\Temp\print_to_png_spool.pdf",
    [int]$DefaultDPI     = 300,
    [switch]$RegisterStartup
)

$ErrorActionPreference = "Stop"

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  部署「$PrinterName」獨立虛擬印表機系統 (直存 PNG 架構)" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

# 1. 驗證驅動程式是否就緒
Write-Host "`n[1/4] 驗證列印驅動程式 ($DriverName)..." -ForegroundColor Yellow
$driver = Get-PrinterDriver -Name $DriverName -ErrorAction SilentlyContinue
if (-not $driver) {
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        throw "系統尚未啟用『$DriverName』，請以系統管理員身分執行此腳本以啟用 Printing-PrintToPDFServices-Features。"
    }
    Enable-WindowsOptionalFeature -Online -FeatureName "Printing-PrintToPDFServices-Features" -NoRestart | Out-Null
    Add-PrinterDriver -Name $DriverName
}
Write-Host "驅動程式『$DriverName』驗證通過。" -ForegroundColor Green

# 2. 建立專屬背景暫存連接埠 (讓 Microsoft Print to PDF 與 Print to PNG 分開獨立顯示)
Write-Host "`n[2/4] 配置專屬背景連接埠 ($PortName)..." -ForegroundColor Yellow
$port = Get-PrinterPort -Name $PortName -ErrorAction SilentlyContinue
if (-not $port) {
    Add-PrinterPort -Name $PortName
}
Write-Host "專屬連接埠已就緒。" -ForegroundColor Green

# 3. 建立或更新「Print to PNG」虛擬印表機，並確保原本的 Microsoft Print to PDF 存在
Write-Host "`n[3/4] 配置虛擬印表機 ($PrinterName)..." -ForegroundColor Yellow
$origPdfPrinter = Get-Printer -Name "Microsoft Print to PDF" -ErrorAction SilentlyContinue
if (-not $origPdfPrinter) {
    Add-Printer -Name "Microsoft Print to PDF" -DriverName $DriverName -PortName "PORTPROMPT:"
}

$existingPrinter = Get-Printer -Name $PrinterName -ErrorAction SilentlyContinue
if ($existingPrinter) {
    Set-Printer -Name $PrinterName -DriverName $DriverName -PortName $PortName
    Write-Host "已成功更新『$PrinterName』虛擬印表機配置！" -ForegroundColor Green
} else {
    Add-Printer -Name $PrinterName -DriverName $DriverName -PortName $PortName
    Write-Host "已成功建立『$PrinterName』虛擬印表機！" -ForegroundColor Green
}

# 4. 寫入預設 DPI 至 config.json
Write-Host "`n[4/4] 設定預設輸出解析度 ($DefaultDPI DPI)..." -ForegroundColor Yellow
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$configPath = Join-Path $scriptDir "config.json"
$configObj = @{
    default_dpi   = $DefaultDPI
    last_save_dir = ""
}
if (Test-Path $configPath) {
    try {
        $existingCfg = Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($existingCfg.last_save_dir) {
            $configObj.last_save_dir = $existingCfg.last_save_dir
        }
    } catch {}
}
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($configPath, ($configObj | ConvertTo-Json), $utf8NoBom)
Write-Host "已寫入設定檔 $configPath (預設 DPI = $DefaultDPI)。" -ForegroundColor Green

# 5. (選用) 自動註冊開機背景常駐服務
if ($RegisterStartup) {
    Write-Host "`n[+] 正在配置開機自動啟動捷徑 (shell:startup)..." -ForegroundColor Yellow
    $daemonPath = Join-Path $scriptDir "pdf_to_png_daemon.pyw"
    $realPythonw = & python -c "import sys, pathlib; p = pathlib.Path(sys.executable).with_name('pythonw.exe'); print(p if p.exists() else '')" 2>$null
    if (-not $realPythonw) {
        $pythonwCmd = Get-Command "pythonw.exe" -ErrorAction SilentlyContinue
        if ($pythonwCmd) { $realPythonw = $pythonwCmd.Source }
    }

    if ((Test-Path $daemonPath) -and $realPythonw) {
        $startupFolder = [Environment]::GetFolderPath('Startup')
        $shortcutPath = Join-Path $startupFolder "PrintToPNG_Daemon.lnk"
        $wshShell = New-Object -ComObject WScript.Shell
        $shortcut = $wshShell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $realPythonw
        $shortcut.Arguments = "`"$daemonPath`""
        $shortcut.WorkingDirectory = $scriptDir
        $shortcut.WindowStyle = 7
        $shortcut.Description = "Print to PNG 背景無感直存服務"
        $shortcut.Save()
        Write-Host "已成功在啟動資料夾建立捷徑：$shortcutPath" -ForegroundColor Green
    }
}

Write-Host "`n======================================================" -ForegroundColor Cyan
Write-Host "  部署完成！兩台印表機已獨立分離，且列印將直接彈出 *.png 另存新檔！" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
