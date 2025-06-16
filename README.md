# 富途 MCP API 服务

基于 FastAPI 和 Model Context Protocol (MCP) 的富途证券行情 API 服务，将富途 OpenAPI 封装为 MCP 工具，支持 AI 助手直接调用富途行情数据。
有个前提是必须自己安装好OpenD登陆好账号先

## 🚀 功能特性

- **完整的行情接口封装**: 支持富途 OpenAPI 的所有主要行情接口
- **MCP 协议支持**: 使用 `fastapi-mcp` 库自动将 FastAPI 接口转换为 MCP 工具
- **多市场支持**: 港股、美股、A股、新加坡、日本等市场
- **实时数据**: 股票报价、K线、分时、摆盘、逐笔等实时行情数据
- **AI 友好**: 可直接被 Claude、Cursor 等 AI 助手调用
- **高性能**: 基于 FastAPI 的异步架构
- **易于部署**: 支持单独部署或集成部署

## 📋 支持的行情接口

| 接口名称 | MCP 工具名 | 功能描述 |
|---------|-----------|----------|
| 股票报价 | `get_stock_quote` | 获取实时股票报价信息 |
| 历史K线 | `get_history_kline` | 获取历史K线数据，支持各种周期 |
| 当前K线 | `get_current_kline` | 获取当前K线数据 |
| 市场快照 | `get_market_snapshot` | 获取市场快照信息 |
| 股票基本信息 | `get_stock_basicinfo` | 获取股票基本信息列表 |
| 订阅行情 | `subscribe_quotes` | 订阅实时行情推送 |
| 摆盘数据 | `get_order_book` | 获取买卖档位信息 |
| 逐笔数据 | `get_rt_ticker` | 获取实时逐笔成交数据 |
| 分时数据 | `get_rt_data` | 获取分时走势数据 |
| 交易日查询 | `get_trading_days` | 获取指定时间段的交易日 |

## 🛠️ 技术架构

```
AI 助手 (Claude/Cursor) 
    ↓ MCP 协议
FastAPI MCP 服务
    ↓ 富途 Python SDK
富途 OpenD 网关
    ↓ TCP 协议
富途服务器
```

### 核心技术栈

- **FastAPI**: 现代化的 Web 框架
- **fastapi-mcp**: FastAPI 到 MCP 的转换库
- **futu-api**: 富途官方 Python SDK
- **Pydantic**: 数据验证和序列化
- **Uvicorn**: ASGI 服务器

## 📦 安装部署

### 1. 环境要求

- Python 3.10+
- 富途 OpenD 客户端 (需要先启动)

### 2. 克隆项目

```bash
git clone <your-repo-url>
cd mcp_futu
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

复制 `env.example` 为 `.env` 并修改配置:

```bash
cp env.example .env
```

配置示例:
```env
# 富途 OpenD 配置
FUTU_HOST=127.0.0.1
FUTU_PORT=11111

# 服务配置  
HOST=127.0.0.1
PORT=8000
LOG_LEVEL=INFO
```

### 5. 启动服务

```bash
python main.py
```

服务启动后:
- **API 文档**: http://localhost:8000/docs
- **MCP 端点**: http://localhost:8000/mcp
- **健康检查**: http://localhost:8000/health

## 🔧 使用方法

### 1. 直接 API 调用

```bash
# 获取股票报价
curl -X POST "http://localhost:8000/quote/stock_quote" \
  -H "Content-Type: application/json" \
  -d '{"code_list": ["HK.00700", "US.AAPL"]}'
```

### 2. 与 AI 助手集成

#### Cursor 集成

在 Cursor 设置中添加 MCP 服务器:
```
MCP Server URL: http://localhost:8000/mcp
```

#### Claude Desktop 集成

编辑 `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "futu-mcp": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

## 📊 使用示例

### 获取腾讯和苹果股票报价

```python
# AI 助手可以这样调用
request = {
    "code_list": ["HK.00700", "US.AAPL"]
}
response = await get_stock_quote(request)
```

### 获取港股历史日K线

```python
request = {
    "code": "HK.00700",
    "start": "2024-01-01", 
    "end": "2024-12-31",
    "ktype": "K_DAY",
    "autype": "qfq"
}
response = await get_history_kline(request)
```

## 🔒 安全考虑

1. **网络安全**: 确保富途 OpenD 和本服务在安全网络环境中运行
2. **访问控制**: 建议配置防火墙限制访问来源
3. **数据权限**: 确保拥有相应市场的行情权限
4. **密码保护**: 如需要交易功能，妥善保管交易密码

## 📈 性能优化

- **连接池**: 复用富途 API 连接
- **异步处理**: 全异步架构提升并发性能
- **数据缓存**: 可选的响应数据缓存
- **错误重试**: 自动重试机制保证稳定性

## 🚨 注意事项

1. **富途 OpenD**: 必须先启动富途 OpenD 客户端
2. **行情权限**: 确保账户有相应市场的行情权限
3. **网络稳定**: 保持与富途服务器的稳定连接
4. **API 限制**: 遵守富途 API 的调用频率限制

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📜 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 🔗 相关链接

- [富途 OpenAPI 文档](https://openapi.futunn.com/futu-api-doc/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [fastapi-mcp 库](https://github.com/tadata-org/fastapi_mcp)
- [Model Context Protocol](https://modelcontextprotocol.io/)

## 📞 支持

如有问题或建议，请提交 Issue 或联系开发团队。 