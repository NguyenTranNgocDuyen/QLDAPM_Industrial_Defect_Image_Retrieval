# Khởi động Keyboard Annotation Studio
Write-Host "Đang khởi động Keyboard Annotation Studio tại http://localhost:5050..." -ForegroundColor Cyan

$pythonExe = "D:\trainModel\.venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

& $pythonExe "$PSScriptRoot\server.py"
