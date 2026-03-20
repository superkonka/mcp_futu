# 富途 MCP 服务 - Windows 11 安装指南

> 本指南专门针对 Windows 11 系统进行适配和优化

## 📋 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10/11 (64位) |
| Python | 3.10 或更高版本 |
| 内存 | 4GB+ (推荐 8GB) |
| 磁盘空间 | 1GB+ 可用空间 |
| 网络 | 需要连接富途 OpenD |

---

## 🚀 快速安装 (推荐)

### 方法一：使用安装脚本 (推荐)

1. **右键点击开始菜单** → 选择 **Windows PowerShell** 或 **终端**

2. **进入项目目录**:
   ```powershell
   cd C:\Users\Administrator\mcp_futu
   ```

3. **执行安装脚本**:
   ```powershell
   # 设置执行策略（首次运行需要）
   Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
   
   # 运行安装脚本
   .\install_windows.ps1
   ```

4. **按照提示完成安装**

### 方法二：手动安装

#### 1. 安装 Python

- 访问 [python.org](https://python.org/downloads/) 下载 Python 3.10+
- **安装时务必勾选** `Add Python to PATH`

#### 2. 创建虚拟环境

```powershell
cd C:\Users\Administrator\mcp_futu
python -m venv venv
```

#### 3. 激活虚拟环境

```powershell
.\venv\Scripts\activate
```

#### 4. 安装依赖

```powershell
pip install -r requirements_enhanced.txt
```

#### 5. 创建必要目录

```powershell
mkdir data
mkdir cache
mkdir logs
```

---

## ⚙️ 配置

### 1. 复制环境配置

```powershell
copy .env.windows .env
```

### 2. 编辑配置 (可选)

使用记事本或 VS Code 编辑 `.env` 文件:

```powershell
notepad .env
# 或
code .env
```

常用配置项:

```env
# 富途 OpenD 配置 (通常保持默认)
FUTU_HOST=127.0.0.1
FUTU_PORT=11111

# 服务端口
PORT=8001

# 日志级别 (DEBUG/INFO/WARNING/ERROR)
LOG_LEVEL=INFO
```

---

## 🎮 启动服务

### 方法一：交互式启动器 (推荐)

```powershell
python start_windows.py
```

会显示菜单:
```
============================================================
  富途 MCP 服务 - Windows 启动器
============================================================

请选择操作:

  1. 启动所有服务
  2. 停止所有服务
  3. 重启所有服务
  4. 查看服务状态
  5. 启动 Web API (端口8001)
  6. 启动 HTTP 备用 (端口8002)
  7. 启动 MCP 服务 (端口9001)
  8. 健康检查
  9. 查看日志
  0. 退出
```

### 方法二：命令行

```powershell
# 启动所有服务
python start_windows.py start

# 停止所有服务
python start_windows.py stop

# 重启所有服务
python start_windows.py restart

# 查看状态
python start_windows.py status

# 健康检查
python start_windows.py health
```

### 方法三：PowerShell 脚本

```powershell
# 前台运行
.\start_server.ps1

# 后台运行
.\start_server.ps1 -Background
```

### 方法四：批处理脚本

```cmd
.\run_server.bat
```

---

## 🧪 测试

运行兼容性测试:

```powershell
# 完整测试
python test_windows.py

# 快速测试
python test_windows.py --quick

# 生成报告
python test_windows.py --output report.md
```

---

## 🔧 常见问题

### 问题 1: 无法执行 PowerShell 脚本

**错误信息:**
```
无法加载文件，因为在此系统上禁止运行脚本
```

**解决方法:**
```powershell
# 以管理员身份运行 PowerShell，执行:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 或在当前会话中:
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
```

### 问题 2: 端口被占用

**错误信息:**
```
Address already in use
```

**解决方法:**
```powershell
# 使用重启脚本
python restart.py

# 或手动查找并终止
python start_windows.py
# 选择菜单 2 (停止所有服务)
```

### 问题 3: 富途 OpenD 连接失败

**错误信息:**
```
连接富途OpenD失败
```

**解决方法:**
1. 下载并安装 [富途 OpenD](https://www.futunn.com/download/openAPI)
2. 启动 OpenD 并登录富途账号
3. 确保有相应市场的行情权限
4. 检查防火墙设置

### 问题 4: Python 模块导入错误

**错误信息:**
```
ModuleNotFoundError: No module named 'xxx'
```

**解决方法:**
```powershell
# 确保在虚拟环境中
.\venv\Scripts\activate

# 重新安装依赖
pip install -r requirements_enhanced.txt
```

### 问题 5: 路径中包含中文导致问题

**解决方法:**
- 将项目移动到纯英文路径，如 `C:\mcp_futu`
- 或在 `.env` 文件中设置:
  ```env
  PYTHONIOENCODING=utf-8
  ```

---

## 📁 目录结构

```
mcp_futu/
├── 📁 utils/                    # 工具模块
│   ├── __init__.py
│   ├── process_manager.py       # 跨平台进程管理
│   └── path_helper.py           # 路径处理
│
├── 📁 windows/                  # Windows 适配文件
│   ├── start_windows.py         # 统一启动入口 ⭐
│   ├── windows_service.py       # 服务管理器
│   ├── install_windows.ps1      # 安装脚本 ⭐
│   ├── test_windows.py          # 测试脚本
│   └── WINDOWS_SETUP.md         # 本文件
│
├── 📁 app/                      # 核心应用
├── 📁 services/                 # 业务服务
├── 📁 web/                      # 前端看板
│
├── 🐍 main_enhanced.py          # 主服务 (端口8001)
├── 🐍 main_enhanced_simple_alternative.py  # HTTP备用 (端口8002)
├── 📜 start_server.ps1          # PowerShell启动
├── 📜 run_server.bat            # 批处理启动
├── ⚙️ .env.windows              # Windows环境配置模板
└── 📋 requirements.txt          # 依赖列表
```

---

## 🔗 服务地址

服务启动后，可以通过以下地址访问:

| 服务 | 地址 | 说明 |
|------|------|------|
| Web API | http://localhost:8001 | 主服务 (MCP + HTTP) |
| HTTP 备用 | http://localhost:8002 | 纯 HTTP 服务 |
| MCP 服务 | http://localhost:9001/mcp | MCP 独立服务 |
| API 文档 | http://localhost:8001/docs | Swagger UI |
| 健康检查 | http://localhost:8001/health | 服务状态 |

---

## 📝 日志查看

### 实时查看日志

```powershell
# 使用 PowerShell
Get-Content logs\futu_mcp.log -Wait -Tail 50

# 或使用 Python
python start_windows.py
# 选择菜单 9 (查看日志)
```

### 日志文件位置

```
logs/
├── futu_mcp.log        # 主日志
├── error.log           # 错误日志
└── access.log          # 访问日志
```

---

## 🛡️ 防火墙设置

如果服务无法从外部访问，需要配置 Windows 防火墙:

### 方法一：PowerShell (管理员)

```powershell
# 允许特定端口
New-NetFirewallRule -DisplayName "Futu MCP" -Direction Inbound -LocalPort 8001,8002,9001 -Protocol TCP -Action Allow
```

### 方法二：图形界面

1. 打开 **Windows 安全中心**
2. 点击 **防火墙和网络保护**
3. 点击 **高级设置**
4. 点击 **入站规则** → **新建规则**
5. 选择 **端口** → 输入 `8001,8002,9001`
6. 选择 **允许连接**
7. 完成规则创建

---

## 🔄 更新

### 使用 Git 更新

```powershell
# 进入项目目录
cd C:\Users\Administrator\mcp_futu

# 拉取最新代码
git pull origin main

# 更新依赖
.\venv\Scripts\activate
pip install -r requirements_enhanced.txt --upgrade
```

### 手动更新

1. 备份 `.env` 配置文件
2. 下载最新代码并覆盖
3. 恢复 `.env` 配置文件
4. 重新安装依赖

---

## 💡 最佳实践

1. **使用虚拟环境**: 避免与系统 Python 冲突
2. **定期备份配置**: 备份 `.env` 和数据目录
3. **监控日志**: 定期检查日志文件
4. **使用交互式启动器**: `start_windows.py` 提供最佳体验
5. **遇到问题先测试**: 运行 `test_windows.py` 诊断问题

---

## 📞 获取帮助

- **API 文档**: http://localhost:8001/docs
- **健康检查**: http://localhost:8001/health
- **运行测试**: `python test_windows.py`

---

## ✅ 安装检查清单

- [ ] Python 3.10+ 已安装
- [ ] 虚拟环境已创建
- [ ] 依赖安装成功
- [ ] `.env` 文件已配置
- [ ] 富途 OpenD 已启动
- [ ] `test_windows.py` 测试通过
- [ ] 服务可以正常启动
- [ ] API 文档可以访问

完成以上步骤后，您就可以开始使用富途 MCP 服务了！🎉
