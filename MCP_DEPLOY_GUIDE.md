# 富途 MCP 服务 - 共享部署指南

> 让其他人通过网络使用你电脑上的 MCP 服务

## 📋 前提条件

- ✅ 你的电脑需要开机并保持服务运行
- ✅ 其他人需要能访问你的电脑 IP
- ✅ 建议在同一局域网内（办公室/家庭 WiFi）

---

## 🚀 快速配置（同一局域网）

### 步骤 1: 获取你的 IP 地址

```powershell
# 在 PowerShell 中执行
ipconfig | findstr "IPv4"
```

记下你的内网 IP，例如：`192.168.1.100`

### 步骤 2: 修改服务绑定地址

编辑 `.env` 文件：

```env
# 从
HOST=127.0.0.1

# 改为你的内网 IP
HOST=0.0.0.0  # 监听所有网卡，或指定你的 IP
```

### 步骤 3: 配置 Windows 防火墙

```powershell
# 以管理员身份运行 PowerShell
New-NetFirewallRule -DisplayName "Futu MCP" -Direction Inbound -LocalPort 8001,8002,9001 -Protocol TCP -Action Allow
```

### 步骤 4: 重启服务

```powershell
python start_windows.py restart
```

---

## 🔌 他人使用方式

### 方式 1: HTTP API 直接调用

其他人可以使用你的 IP 访问：

```bash
# 替换 192.168.1.100 为你的实际 IP
curl http://192.168.1.100:8001/health
```

### 方式 2: MCP 客户端配置 (Cursor/Claude)

在 Cursor 或 Claude 桌面应用中配置：

```json
{
  "mcpServers": {
    "futu-shared": {
      "url": "http://192.168.1.100:8001/mcp",
      "name": "富途 MCP (共享)"
    }
  }
}
```

### 方式 3: Python 客户端

```python
import httpx

BASE_URL = "http://192.168.1.100:8001"

async def get_stock_quote(codes):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/quote/stock_quote",
            json={"code_list": codes}
        )
        return response.json()
```

---

## 🔐 安全建议

### 1. 仅开放必要端口

不要暴露以下端口到公网：
- ❌ 11111 (OpenD 端口，仅限本地)
- ✅ 8001 (Web API 可以开放)
- ✅ 9001 (MCP 服务可以开放)

### 2. 使用防火墙限制 IP

```powershell
# 只允许特定 IP 访问
New-NetFirewallRule `
  -DisplayName "Futu MCP Limited" `
  -Direction Inbound `
  -LocalPort 8001 `
  -Protocol TCP `
  -RemoteAddress 192.168.1.0/24 `
  -Action Allow
```

### 3. 添加简单认证 (可选)

在 `.env` 中添加：
```env
API_KEY=your_secret_key_here
```

---

## 🌐 公网访问方案 (高级)

如果你需要让互联网上任意用户访问：

### 方案 A: 云服务器部署

1. 购买云服务器 (阿里云/腾讯云/AWS)
2. 在服务器上安装 OpenD 并登录
3. 部署本服务
4. 配置安全组开放 8001 端口

### 方案 B: 内网穿透 (临时)

使用 ngrok 临时暴露服务：

```powershell
# 安装 ngrok
choco install ngrok

# 启动隧道
ngrok http 8001
```

会得到类似 `https://xxxx.ngrok.io` 的地址，其他人可以直接访问。

### 方案 C: FRP 内网穿透

如果你有公网服务器，可以使用 FRP：

```ini
# frpc.ini
[common]
server_addr = your_server_ip
server_port = 7000
token = your_token

[futu-mcp]
type = tcp
local_ip = 127.0.0.1
local_port = 8001
remote_port = 8001
```

---

## 📱 MCP 客户端配置示例

### Cursor 配置

1. 打开 Cursor → Settings → MCP
2. 添加服务器：

```json
{
  "mcpServers": {
    "futu": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-proxy@latest", "http://192.168.1.100:8001/mcp"]
    }
  }
}
```

### Claude Desktop 配置

编辑 `claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "futu": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-proxy@latest", "http://192.168.1.100:8001/mcp"]
    }
  }
}
```

### 直接使用 SSE (推荐)

如果你的客户端支持 SSE：

```json
{
  "mcpServers": {
    "futu": {
      "url": "http://192.168.1.100:8001/mcp",
      "transport": "sse"
    }
  }
}
```

---

## 🔧 共享管理脚本

我为你创建了共享管理脚本：

### 启动共享服务

```powershell
python share_service.py --start
```

### 查看当前连接

```powershell
python share_service.py --status
```

### 停止共享

```powershell
python share_service.py --stop
```

---

## ❓ 常见问题

### Q: 其他人无法连接？

检查清单：
1. 你的电脑防火墙是否放行端口？
2. 是否使用 `0.0.0.0` 绑定？
3. 对方是否能 ping 通你的 IP？
4. 是否在同一网段？

### Q: 连接超时？

- 检查 Windows Defender 防火墙
- 检查路由器防火墙
- 尝试关闭防火墙测试：
  ```powershell
  netsh advfirewall set allprofiles state off
  ```

### Q: MCP 客户端报错？

- 确保 MCP 服务已启动 (端口 9001)
- 检查 `EXTERNAL_MCP_ENDPOINT` 配置
- 尝试使用 HTTP 代理模式

---

## 📊 性能建议

共享给多人使用时：

1. **限制并发数**：在 `.env` 中设置
   ```env
   MAX_CONCURRENT_REQUESTS=10
   ```

2. **启用缓存**：减少 OpenD 请求
   ```env
   CACHE_ENABLED=true
   CACHE_EXPIRE_SECONDS=60
   ```

3. **监控资源**：
   ```powershell
   python monitor.py
   ```

---

## 🔗 总结

| 场景 | 方案 | 难度 | 安全性 |
|------|------|------|--------|
| 同一 WiFi | 直接共享 IP | ⭐ 简单 | ⭐⭐⭐ 安全 |
| 不同网络 | 内网穿透 | ⭐⭐ 中等 | ⭐⭐ 一般 |
| 长期使用 | 云服务器 | ⭐⭐⭐ 复杂 | ⭐⭐⭐⭐ 很安全 |

选择适合你场景的方案即可！
