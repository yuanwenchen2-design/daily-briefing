# ═══════════════════════════════════════════════
# 每日简报 · 开机自启动设置脚本
# 用法: 右键 → "使用 PowerShell 运行"
# 或:   powershell -ExecutionPolicy Bypass -File setup_startup.ps1
# ═══════════════════════════════════════════════

$ErrorActionPreference = "Stop"

# 项目路径
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source

if (-not $PythonExe) {
    Write-Host "❌ 未找到 Python，请先安装 Python 3.10+" -ForegroundColor Red
    Write-Host "   下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "按 Enter 退出"
    exit 1
}

Write-Host "════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  每日简报 · 开机自启动设置" -ForegroundColor Cyan
Write-Host "════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "Python: $PythonExe" -ForegroundColor Green
Write-Host "项目路径: $ProjectDir" -ForegroundColor Green
Write-Host ""

# 1. 安装依赖
Write-Host "[1/4] 安装 Python 依赖..." -ForegroundColor Yellow
pip install -r "$ProjectDir\requirements.txt" -q
Write-Host "  ✓ 依赖安装完成" -ForegroundColor Green

# 2. 复制 .env 配置（如果不存在）
$EnvFile = "$ProjectDir\.env"
$EnvExample = "$ProjectDir\.env.example"
if (-not (Test-Path $EnvFile)) {
    Copy-Item $EnvExample $EnvFile
    Write-Host "[2/4] 已创建 .env 配置文件，请编辑填入你的 API Key:" -ForegroundColor Yellow
    Write-Host "  $EnvFile" -ForegroundColor White
    Write-Host "  特别是 ANTHROPIC_API_KEY（在 https://console.anthropic.com/ 获取）" -ForegroundColor DarkYellow
} else {
    Write-Host "[2/4] .env 配置文件已存在" -ForegroundColor Green
}

# 3. 创建启动快捷方式
Write-Host "[3/4] 创建启动快捷方式..." -ForegroundColor Yellow
$StartupDir = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupDir "每日简报.lnk"

$WScriptShell = New-Object -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonExe
$Shortcut.Arguments = "`"$ProjectDir\main.py`""
$Shortcut.WorkingDirectory = $ProjectDir
$Shortcut.WindowStyle = 7  # 最小化
$Shortcut.Description = "每日简报 · Daily Briefing"
$Shortcut.Save()

Write-Host "  ✓ 启动快捷方式已创建: $ShortcutPath" -ForegroundColor Green

# 4. 测试运行
Write-Host "[4/4] 测试运行..." -ForegroundColor Yellow
Write-Host "  即将运行一次简报采集（按 Ctrl+C 可跳过）..." -ForegroundColor DarkYellow
Write-Host ""

Start-Sleep -Seconds 2

try {
    & $PythonExe "$ProjectDir\main.py"
} catch {
    Write-Host "  测试运行结束或中断" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  设置完成！" -ForegroundColor Green
Write-Host "════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "下次开机时，每日简报将自动运行。" -ForegroundColor White
Write-Host "浏览器会自动打开 http://127.0.0.1:5200" -ForegroundColor White
Write-Host ""
Write-Host "手动运行: python $ProjectDir\main.py" -ForegroundColor DarkGray
Write-Host "仅看历史: python $ProjectDir\main.py --server" -ForegroundColor DarkGray
Write-Host ""

Read-Host "按 Enter 退出"
