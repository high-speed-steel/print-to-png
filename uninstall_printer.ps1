<#
.SYNOPSIS
    完整移除「Print to PNG」虛擬印表機、開機啟動捷徑與背景常駐服務。
#>

[CmdletBinding()]
param (
    [string]$PrinterName = "Print to PNG",
    [string]$PortName    = "$env:LOCALAPPDATA\Temp\print_to_png_spool.pdf"
)

Write-Host "正在停止 Print to PNG 背景常駐服務..." -ForegroundColor Yellow
Stop-Process -Name "PrintToPNG_Daemon" -Force -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*pdf_to_png_daemon*" } | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

Write-Host "正在移除虛擬印表機 ($PrinterName)..." -ForegroundColor Yellow
Remove-Printer -Name $PrinterName -ErrorAction SilentlyContinue
Remove-PrinterPort -Name $PortName -ErrorAction SilentlyContinue

Write-Host "正在移除開機啟動捷徑..." -ForegroundColor Yellow
$startupFolder = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startupFolder "PrintToPNG_Daemon.lnk"
if (Test-Path $shortcutPath) {
    Remove-Item $shortcutPath -Force
}

$installDir = "$env:LOCALAPPDATA\PrintToPNG"
if (Test-Path $installDir) {
    Remove-Item $installDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "已完整移除 Print to PNG 系統！" -ForegroundColor Green
