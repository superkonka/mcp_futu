@echo off
chcp 65001 >nul
echo ==========================================
echo  富途 MCP 服务启动脚本
echo ==========================================
echo.
echo 正在检查富途OpenD连接...
echo.

cd /d C:\Users\Administrator\mcp_futu

:: 检查端口11111 (富途OpenD默认端口)
netstat -an | findstr "11111" >nul
if %errorlevel% neq 0 (
    echo [警告] 富途OpenD 似乎未启动或未登录！
    echo.
    echo 请先执行以下步骤：
    echo 1. 下载并安装富途OpenD: https://www.futunn.com/download/openAPI
    echo 2. 启动OpenD并登录您的富途账号
    echo 3. 确保有相应市场的行情权限
    echo.
    echo 按任意键继续尝试启动服务(可能会报错)...
    pause >nul
)

echo 正在启动富途MCP服务...
echo.
echo 服务地址: http://localhost:8002
echo API文档:  http://localhost:8002/docs
echo.
echo 按 Ctrl+C 停止服务
echo.

.\venv\Scripts\python.exe main_enhanced_simple_alternative.py

pause
