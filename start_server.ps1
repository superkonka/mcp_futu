# 富途 MCP 服务启动脚本
param(
    [switch]$Background = $false
)

$Host.UI.RawUI.WindowTitle = "富途 MCP 服务"

Set-Location -Path "C:\Users\Administrator\mcp_futu"
$env:PYTHONUNBUFFERED = "1"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  富途 MCP 服务启动器" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 检查富途OpenD是否运行
$openDRunning = Get-NetTCPConnection -LocalPort 11111 -ErrorAction SilentlyContinue
if (-not $openDRunning) {
    Write-Host "[警告] 富途OpenD 似乎未启动或未登录！" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "请先执行以下步骤：" -ForegroundColor Yellow
    Write-Host "1. 下载并安装富途OpenD: https://www.futunn.com/download/openAPI"
    Write-Host "2. 启动OpenD并登录您的富途账号"
    Write-Host "3. 确保有相应市场的行情权限"
    Write-Host ""
}

if ($Background) {
    Write-Host "正在后台启动富途MCP服务..." -ForegroundColor Green
    Write-Host "服务地址: http://localhost:8002" -ForegroundColor Green
    Write-Host "API文档:  http://localhost:8002/docs" -ForegroundColor Green
    Write-Host ""
    
    $proc = Start-Process -FilePath ".\venv\Scripts\python.exe" `
        -ArgumentList "main_enhanced_simple_alternative.py" `
        -WindowStyle Hidden -PassThru
    
    Write-Host "服务进程ID: $($proc.Id)" -ForegroundColor Green
    Write-Host "使用 'Get-Process -Id $($proc.Id)' 查看进程状态" -ForegroundColor Gray
} else {
    Write-Host "正在启动富途MCP服务..." -ForegroundColor Green
    Write-Host "服务地址: http://localhost:8002" -ForegroundColor Green
    Write-Host "API文档:  http://localhost:8002/docs" -ForegroundColor Green
    Write-Host ""
    Write-Host "按 Ctrl+C 停止服务" -ForegroundColor Yellow
    Write-Host ""
    
    .\venv\Scripts\python.exe main_enhanced_simple_alternative.py
}
