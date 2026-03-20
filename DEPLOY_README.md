# 富途 MCP 服务部署完成

## 📋 部署状态

✅ **部署成功！** 项目已克隆并安装了所有依赖。

## 🚀 启动服务

### 方式1：使用批处理脚本（推荐新手）

双击运行 `run_server.bat`

### 方式2：使用 PowerShell

```powershell
# 前台运行（可以看到日志）
.\start_server.ps1

# 后台运行
.\start_server.ps1 -Background
```

### 方式3：使用智能助手（功能最全）

```powershell
.\venv\Scripts\python.exe futu_assistant.py
```

### 方式4：手动启动

```powershell
cd C:\Users\Administrator\mcp_futu
.\venv\Scripts\python.exe main_enhanced_simple_alternative.py
```

## ⚠️ 重要前提

**必须先启动富途OpenD！**

1. 下载富途OpenD: https://www.futunn.com/download/openAPI
2. 安装并启动OpenD
3. 登录您的富途账号
4. 确保有相应市场的行情权限
5. OpenD默认端口: 11111

## 📡 服务地址

- **Web服务**: http://localhost:8002
- **API文档**: http://localhost:8002/docs
- **健康检查**: http://localhost:8002/health

## 🔧 MCP 客户端配置

在Cursor或其他支持MCP的客户端中添加：

```json
{
  "mcpServers": {
    "futu": {
      "url": "http://127.0.0.1:8002/mcp",
      "name": "富途量化分析平台"
    }
  }
}
```

## 🧪 测试服务

启动服务后，可以测试：

```powershell
# 测试健康检查
curl http://localhost:8002/health

# 测试股票报价
.\venv\Scripts\python.exe -c "
import httpx
import asyncio

async def test():
    async with httpx.AsyncClient() as client:
        r = await client.post('http://localhost:8002/api/quote/stock_quote', 
            json={'code_list': ['HK.00700']})
        print(r.json())

asyncio.run(test())
"
```

## 📁 项目目录

```
mcp_futu/
├── venv/                   # Python虚拟环境
├── main_enhanced.py        # 增强版MCP服务 (端口8001)
├── main_enhanced_simple_alternative.py  # 简化版HTTP服务 (端口8002) ⭐推荐
├── main_simple.py          # 简单版服务 (端口8000)
├── futu_assistant.py       # 智能助手（菜单式操作）
├── run_server.bat          # Windows批处理启动脚本
├── start_server.ps1        # PowerShell启动脚本
├── DEPLOY_README.md        # 本文件
└── ...
```

## 🛠️ 故障排除

### 端口被占用

```powershell
# 查看端口占用
Get-Process -Id (Get-NetTCPConnection -LocalPort 8002).OwningProcess

# 结束进程
Stop-Process -Id <进程ID>
```

### 连接富途失败

- 检查OpenD是否已启动并登录
- 检查防火墙设置
- 检查端口11111是否可用

### 依赖问题

```powershell
# 重新安装依赖
.\venv\Scripts\python.exe -m pip install -r requirements_enhanced.txt
```

## 📚 更多信息

- 详细文档: 查看 `README.md` 和 `README_ENHANCED.md`
- API文档: 服务启动后访问 http://localhost:8002/docs
- 功能报告: 查看 `FUNCTIONALITY_REPORT.md`

## 🎉 开始使用

1. 启动富途OpenD并登录
2. 运行 `run_server.bat` 或 `start_server.ps1`
3. 访问 http://localhost:8002 查看Dashboard
4. 在MCP客户端中配置连接

---

**部署时间**: 2026-03-20
**部署路径**: C:\Users\Administrator\mcp_futu
