# 富途 MCP 服务 - Windows 安装脚本
# 一键安装和配置环境
# 使用方法: 右键 -> 使用 PowerShell 运行，或在 PowerShell 中执行:
#   Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
#   .\install_windows.ps1

param(
    [switch]$SkipVenv = $false,
    [switch]$SkipFutuCheck = $false,
    [switch]$Development = $false
)

$ErrorActionPreference = "Stop"

# 设置窗口标题
$Host.UI.RawUI.WindowTitle = "富途 MCP 服务 - Windows 安装"

# 颜色输出函数
function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Success($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warning($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Error($msg) { Write-Host "[ERR] $msg" -ForegroundColor Red }

# 检查管理员权限
function Test-Admin {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# 打印标题
function Show-Header {
    Clear-Host
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "  富途 MCP 服务 - Windows 安装向导" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""
}

# 检查系统要求
function Check-SystemRequirements {
    Write-Info "检查系统要求..."
    
    # 检查 Windows 版本
    $osInfo = Get-CimInstance Win32_OperatingSystem
    $windowsVersion = [System.Environment]::OSVersion.Version
    
    Write-Host "  操作系统: $($osInfo.Caption)"
    Write-Host "  版本: $($windowsVersion.Major).$($windowsVersion.Minor).$($windowsVersion.Build)"
    
    if ($windowsVersion.Major -lt 10) {
        Write-Error "需要 Windows 10 或更高版本"
        exit 1
    }
    
    # 检查 PowerShell 版本
    if ($PSVersionTable.PSVersion.Major -lt 5) {
        Write-Error "需要 PowerShell 5.0 或更高版本"
        exit 1
    }
    
    Write-Success "系统要求检查通过"
}

# 检查 Python
function Check-Python {
    Write-Info "检查 Python 环境..."
    
    $pythonCommands = @("python", "python3", "py")
    $pythonPath = $null
    $pythonVersion = $null
    
    foreach ($cmd in $pythonCommands) {
        try {
            $pythonPath = (Get-Command $cmd -ErrorAction SilentlyContinue).Source
            if ($pythonPath) {
                $versionStr = & $pythonPath --version 2>&1
                if ($versionStr -match "Python (\d+)\.(\d+)") {
                    $major = [int]$Matches[1]
                    $minor = [int]$Matches[2]
                    
                    if ($major -eq 3 -and $minor -ge 10) {
                        $pythonVersion = "$major.$minor"
                        break
                    }
                }
            }
        } catch {
            continue
        }
    }
    
    if (-not $pythonPath) {
        Write-Error "未找到 Python 3.10+"
        Write-Host ""
        Write-Host "请安装 Python 3.10 或更高版本:" -ForegroundColor Yellow
        Write-Host "  1. 访问 https://python.org/downloads/"
        Write-Host "  2. 下载并安装 Python 3.10+"
        Write-Host "  3. 安装时勾选 'Add Python to PATH'"
        Write-Host ""
        Write-Host "按任意键退出..."
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        exit 1
    }
    
    Write-Success "找到 Python $pythonVersion ($pythonPath)"
    return $pythonPath
}

# 检查 Git
function Check-Git {
    Write-Info "检查 Git..."
    
    $gitPath = (Get-Command git -ErrorAction SilentlyContinue).Source
    if (-not $gitPath) {
        Write-Warning "未找到 Git"
        Write-Host "建议安装 Git 以便更新: https://git-scm.com/download/win" -ForegroundColor Yellow
        return $null
    }
    
    $gitVersion = git --version
    Write-Success "找到 $gitVersion"
    return $gitPath
}

# 检查富途 OpenD
function Check-FutuOpenD {
    if ($SkipFutuCheck) {
        Write-Info "跳过富途 OpenD 检查"
        return
    }
    
    Write-Info "检查富途 OpenD..."
    
    $portOpen = Test-NetConnection -ComputerName localhost -Port 11111 -WarningAction SilentlyContinue
    
    if (-not $portOpen.TcpTestSucceeded) {
        Write-Warning "富途 OpenD 未检测到 (端口 11111)"
        Write-Host ""
        Write-Host "请先完成以下步骤:" -ForegroundColor Yellow
        Write-Host "  1. 下载富途 OpenD: https://www.futunn.com/download/openAPI"
        Write-Host "  2. 安装并启动 OpenD"
        Write-Host "  3. 使用富途账号登录"
        Write-Host "  4. 确保有相应市场的行情权限"
        Write-Host ""
        
        $continue = Read-Host "是否继续安装? (y/N)"
        if ($continue -ne 'y' -and $continue -ne 'Y') {
            exit 0
        }
    } else {
        Write-Success "富途 OpenD 已连接"
    }
}

# 创建虚拟环境
function Create-VirtualEnvironment($pythonPath) {
    if ($SkipVenv) {
        Write-Info "跳过虚拟环境创建"
        return $pythonPath
    }
    
    Write-Info "创建虚拟环境..."
    
    $venvPath = Join-Path $PSScriptRoot "venv"
    
    if (Test-Path $venvPath) {
        Write-Warning "虚拟环境已存在"
        $recreate = Read-Host "是否重新创建? (y/N)"
        if ($recreate -eq 'y' -or $recreate -eq 'Y') {
            Remove-Item -Path $venvPath -Recurse -Force
        } else {
            return Join-Path $venvPath "Scripts\python.exe"
        }
    }
    
    & $pythonPath -m venv $venvPath
    
    if (-not $?) {
        Write-Error "创建虚拟环境失败"
        exit 1
    }
    
    Write-Success "虚拟环境创建成功"
    
    $venvPython = Join-Path $venvPath "Scripts\python.exe"
    return $venvPython
}

# 安装依赖
function Install-Dependencies($pythonPath) {
    Write-Info "安装依赖..."
    
    $requirementsFile = Join-Path $PSScriptRoot "requirements_enhanced.txt"
    if (-not (Test-Path $requirementsFile)) {
        $requirementsFile = Join-Path $PSScriptRoot "requirements.txt"
    }
    
    if (-not (Test-Path $requirementsFile)) {
        Write-Error "未找到 requirements.txt"
        exit 1
    }
    
    Write-Host "  使用: $requirementsFile"
    
    # 升级 pip
    & $pythonPath -m pip install --upgrade pip
    
    # 安装依赖
    & $pythonPath -m pip install -r $requirementsFile
    
    if (-not $?) {
        Write-Error "安装依赖失败"
        exit 1
    }
    
    Write-Success "依赖安装成功"
}

# 创建目录结构
function Create-DirectoryStructure {
    Write-Info "创建目录结构..."
    
    $directories = @(
        "data",
        "cache",
        "logs",
        "temp"
    )
    
    foreach ($dir in $directories) {
        $path = Join-Path $PSScriptRoot $dir
        if (-not (Test-Path $path)) {
            New-Item -ItemType Directory -Path $path -Force | Out-Null
            Write-Host "  创建: $dir"
        }
    }
    
    Write-Success "目录结构创建完成"
}

# 创建环境配置文件
function Create-EnvironmentConfig {
    Write-Info "创建环境配置文件..."
    
    $envFile = Join-Path $PSScriptRoot ".env"
    $envWindowsFile = Join-Path $PSScriptRoot ".env.windows"
    
    # 如果 .env 不存在，从模板创建
    if (-not (Test-Path $envFile)) {
        $envExample = Join-Path $PSScriptRoot "env.example"
        
        if (Test-Path $envExample) {
            Copy-Item $envExample $envFile
            Write-Host "  从 env.example 创建 .env"
        } else {
            # 创建默认配置
            @"
# 富途 MCP 服务配置

# 富途 OpenD 配置
FUTU_HOST=127.0.0.1
FUTU_PORT=11111

# 服务配置
HOST=127.0.0.1
PORT=8001

# 缓存配置
CACHE_ENABLED=true
CACHE_EXPIRE_SECONDS=60

# 日志级别
LOG_LEVEL=INFO
"@ | Out-File -FilePath $envFile -Encoding UTF8
            Write-Host "  创建默认 .env"
        }
    }
    
    # 创建 Windows 专用配置
    @"
# 富途 MCP 服务 - Windows 专用配置
# 复制此文件为 .env 并使用

# 富途 OpenD 配置
FUTU_HOST=127.0.0.1
FUTU_PORT=11111
FUTU_TELNET_PORT=65234

# 服务配置
HOST=127.0.0.1
PORT=8001
EXTERNAL_MCP_ENDPOINT=http://localhost:9001/mcp

# Dashboard 配置
DASHBOARD_BASE_URL=http://localhost:8001
DASHBOARD_SESSION_TIMEOUT_MINUTES=120

# 缓存配置
CACHE_ENABLED=true
CACHE_EXPIRE_SECONDS=60

# 日志级别
LOG_LEVEL=INFO

# Windows 特定配置
PYTHONUNBUFFERED=1
PYTHONIOENCODING=utf-8
"@ | Out-File -FilePath $envWindowsFile -Encoding UTF8
    
    Write-Success "环境配置创建完成"
}

# 创建快捷方式
function Create-Shortcuts {
    Write-Info "创建快捷方式..."
    
    $WshShell = New-Object -ComObject WScript.Shell
    
    # 创建启动器快捷方式
    $startWindows = Join-Path $PSScriptRoot "start_windows.py"
    if (Test-Path $startWindows) {
        $shortcutPath = Join-Path $PSScriptRoot "启动富途MCP服务.lnk"
        $shortcut = $WshShell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = "python"
        $shortcut.Arguments = "`"$startWindows`""
        $shortcut.WorkingDirectory = $PSScriptRoot
        $shortcut.Description = "启动富途 MCP 服务"
        $shortcut.IconLocation = "powershell.exe,0"
        $shortcut.Save()
        Write-Host "  创建: 启动富途MCP服务.lnk"
    }
    
    # 创建 PowerShell 启动快捷方式
    $psScript = Join-Path $PSScriptRoot "start_server.ps1"
    if (Test-Path $psScript) {
        $shortcutPath = Join-Path $PSScriptRoot "PowerShell启动.lnk"
        $shortcut = $WshShell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = "powershell.exe"
        $shortcut.Arguments = "-ExecutionPolicy Bypass -File `"$psScript`""
        $shortcut.WorkingDirectory = $PSScriptRoot
        $shortcut.Description = "使用 PowerShell 启动富途 MCP 服务"
        $shortcut.IconLocation = "powershell.exe,0"
        $shortcut.Save()
        Write-Host "  创建: PowerShell启动.lnk"
    }
    
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($WshShell) | Out-Null
    
    Write-Success "快捷方式创建完成"
}

# 显示安装完成信息
function Show-Completion($pythonPath) {
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host "  安装完成!" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "使用方法:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  1. 交互式启动器:" -ForegroundColor Yellow
    Write-Host "     python start_windows.py"
    Write-Host ""
    Write-Host "  2. 命令行启动:" -ForegroundColor Yellow
    Write-Host "     python start_windows.py start    # 启动所有服务"
    Write-Host "     python start_windows.py status   # 查看状态"
    Write-Host "     python start_windows.py stop     # 停止服务"
    Write-Host ""
    Write-Host "  3. PowerShell 启动:" -ForegroundColor Yellow
    Write-Host "     .\start_server.ps1"
    Write-Host ""
    Write-Host "服务地址:" -ForegroundColor Cyan
    Write-Host "  - Web API:    http://localhost:8001"
    Write-Host "  - API 文档:   http://localhost:8001/docs"
    Write-Host "  - MCP 服务:   http://localhost:9001/mcp"
    Write-Host ""
    Write-Host "注意事项:" -ForegroundColor Cyan
    Write-Host "  - 确保富途 OpenD 已启动并登录"
    Write-Host "  - 首次使用建议运行测试: python test_windows.py"
    Write-Host ""
    
    $startNow = Read-Host "是否现在启动服务? (y/N)"
    if ($startNow -eq 'y' -or $startNow -eq 'Y') {
        & $pythonPath (Join-Path $PSScriptRoot "start_windows.py")
    }
}

# 主函数
function Main {
    Show-Header
    
    # 检查管理员权限
    if (Test-Admin) {
        Write-Warning "以管理员权限运行"
        Write-Host "建议以普通用户权限运行本脚本" -ForegroundColor Yellow
        Write-Host ""
        $continue = Read-Host "是否继续? (Y/n)"
        if ($continue -eq 'n' -or $continue -eq 'N') {
            exit 0
        }
    }
    
    # 执行安装步骤
    Check-SystemRequirements
    $pythonPath = Check-Python
    Check-Git
    Check-FutuOpenD
    
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""
    
    $pythonPath = Create-VirtualEnvironment $pythonPath
    Install-Dependencies $pythonPath
    Create-DirectoryStructure
    Create-EnvironmentConfig
    Create-Shortcuts
    
    Show-Completion $pythonPath
}

# 运行主函数
try {
    Main
} catch {
    Write-Error "安装过程中出现错误: $_"
    Write-Host $_.ScriptStackTrace
    Write-Host ""
    Write-Host "按任意键退出..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}
