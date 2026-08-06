# 富途 MCP 增强版 - 使用指南

## 问题现象

用户遇到了以下问题：
```
futu-enhanced/get_stock_quote_enhanced 失败
响应: null
```

## 问题分析

### 1. 路径错误

用户使用的路径 `/futu-enhanced/get_stock_quote_enhanced` **不正确**。

**正确的做法：**
- **直接 API 调用**: 使用 `/api/quote/stock_quote`
- **MCP 工具调用**: 通过专门的 MCP 客户端调用 `get_stock_quote_enhanced` 工具

### 2. MCP 协议理解

MCP (Model Context Protocol) 不是简单的 HTTP API，而是专门为 AI 助手设计的协议：
- 使用 **SSE (Server-Sent Events)** 协议
- 需要专门的 **MCP 客户端**（如 Claude Desktop、Cursor）
- 不能直接通过 HTTP POST 调用

## 解决方案

### 方案 1: 直接使用 API 端点 ✅ 推荐

**正确的请求方式：**

```bash
curl -X POST http://localhost:8001/api/quote/stock_quote \
  -H "Content-Type: application/json" \
  -d '{
    "code_list": ["HK.09660"],
    "optimization": {
      "enable_optimization": true,
      "only_essential_fields": true,
      "remove_meaningless_values": true
    }
  }'
```

**成功响应示例：**
```json
{
  "ret_code": 0,
  "ret_msg": "获取股票报价成功",
  "data": {
    "quotes": [
      {
        "code": "HK.09660",
        "update_time": "2025-06-17 15:58:43",
        "last_price": 6.45,
        "open_price": 6.88,
        "high_price": 6.93,
        "low_price": 6.38,
        "prev_close_price": 6.87,
        "volume": 270547489,
        "turnover": 1773838817.0
      }
    ],
    "data_count": 1,
    "cache_hit": false,
    "execution_time": 0.081
  }
}
```

### 方案 2: 使用 MCP 客户端

如果需要使用 MCP 工具，需要配置专门的 MCP 客户端：

#### Claude Desktop 配置

编辑 `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "futu-enhanced": {
      "command": "mcp-proxy",
      "args": ["http://localhost:8001/mcp"]
    }
  }
}
```

#### Cursor IDE 配置

在 Cursor 设置中添加：
```json
{
  "mcp.servers": {
    "futu-enhanced": {
      "url": "http://localhost:8001/mcp",
      "description": "富途增强版量化分析服务"
    }
  }
}
```

## 服务状态验证

### 1. 检查服务健康状态

```bash
curl http://localhost:8001/health
```

**正常响应:**
```json
{
  "status": "healthy",
  "futu_connected": true,
  "cache_available": true,
  "timestamp": "2025-06-17T15:58:43.000Z",
  "cache_stats": {
    "memory_cache_size": 0,
    "redis_available": false,
    "sqlite_available": true
  }
}
```

### 2. 检查 MCP 端点

```bash
curl http://localhost:8001/mcp \
  -H "Accept: text/event-stream"
```

**正常响应:** 应该看到 SSE 事件流

## API 端点完整列表

### 增强版股票数据接口

| 端点 | 方法 | 描述 | operation_id |
|------|------|------|--------------|
| `/api/quote/stock_quote` | POST | 股票报价（缓存增强） | `get_stock_quote_enhanced` |
| `/api/quote/history_kline` | POST | 历史K线（缓存增强） | `get_history_kline_enhanced` |
| `/api/quote/stock_basicinfo` | POST | 股票基本信息 | `get_stock_basicinfo` |

### 技术分析接口

| 端点 | 方法 | 描述 | operation_id |
|------|------|------|--------------|
| `/api/analysis/technical_indicators` | POST | 综合技术分析 | `get_technical_indicators` |
| `/api/analysis/macd` | POST | MACD指标 | `get_macd_indicator` |
| `/api/analysis/rsi` | POST | RSI指标 | `get_rsi_indicator` |

### 缓存管理接口

| 端点 | 方法 | 描述 | operation_id |
|------|------|------|--------------|
| `/api/cache/status` | GET | 缓存状态 | `get_cache_status` |
| `/api/cache/preload` | POST | 预加载缓存 | `preload_cache_data` |
| `/api/cache/clear` | DELETE | 清理缓存 | `clear_cache_data` |

## 常见问题排错

### 1. "Method Not Allowed" 错误

**原因:** 使用了错误的 HTTP 方法或路径
**解决:** 确保使用正确的端点路径和 POST 方法

### 2. MCP 连接错误

**现象:** `RuntimeError: Received request before initialization was complete`
**原因:** MCP 初始化未完成
**解决:** 
- 重启服务等待完全初始化
- 确保使用正确的 MCP 客户端

### 3. 响应为 null

**原因:** 使用了不存在的路径
**解决:** 使用正确的 API 端点路径

## 最佳实践

### 1. 开发和测试阶段

**推荐使用直接 API 调用：**
- 简单直接，易于调试
- 支持标准 HTTP 工具（curl, Postman, etc.）
- 响应格式清晰

### 2. AI 助手集成阶段

**使用 MCP 工具：**
- 通过 Claude Desktop 或 Cursor 等 MCP 客户端
- AI 助手可以自动发现和使用工具
- 支持复杂的多步骤操作

### 3. 生产环境部署

**建议同时提供两种方式：**
- HTTP API：供传统应用集成
- MCP 服务：供 AI 助手使用

## 结论

用户遇到的问题是**路径使用错误**导致的。应该：

1. ✅ **立即解决**：使用 `/api/quote/stock_quote` 替代错误的路径
2. 📚 **理解 MCP**：MCP 是 AI 助手专用协议，需要专门客户端
3. 🔧 **选择合适方案**：根据使用场景选择直接 API 或 MCP 工具

**关键提示：** 
- `/futu-enhanced/get_stock_quote_enhanced` ❌ 错误
- `/api/quote/stock_quote` ✅ 正确 