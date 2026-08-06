# 🚀 富途MCP增强服务 - 快速启动指南

## 📋 **一行命令启动**

```bash
# 克隆项目并启动（首次使用）
git clone <your-repo-url> && cd mcp_futu && python -m venv venv && source venv/bin/activate && pip install -r requirements_enhanced.txt && python restart.py
```

## ⚡ **日常使用**

```bash
# 进入项目目录
cd mcp_futu
source venv/bin/activate  # 激活虚拟环境

# 🚀 一键重启（推荐）
python restart.py

# 🔍 验证启动
curl http://localhost:8001/health
```

## 🎯 **核心命令**

### **启动选项**
```bash
python restart.py              # 智能重启（推荐）
python main_enhanced.py         # 手动启动增强版
python start_enhanced.py        # 完整监控版本
```

### **功能测试**
```bash
# 股票报价
curl -X POST http://localhost:8001/api/quote/stock_quote \
  -H "Content-Type: application/json" \
  -d '{"code_list": ["HK.00700"]}'

# 技术分析
curl -X POST http://localhost:8001/api/analysis/technical_indicators \
  -H "Content-Type: application/json" \
  -d '{"code": "HK.00700", "indicators": ["all"]}'

# 完整测试套件
python test_complete_functionality.py
```

### **系统监控**
```bash
curl http://localhost:8001/health           # 健康检查
curl http://localhost:8001/api/cache/status # 缓存状态
open http://localhost:8001/docs             # API文档
```

## 🚨 **故障处理**

### **端口占用错误**
```
ERROR: [Errno 48] Address already in use
```
**解决方案**: `python restart.py`

### **富途连接失败**
```
ERROR: 连接富途OpenD失败
```
**解决方案**: 
1. 启动富途OpenD客户端
2. 登录账号并确保有行情权限
3. `python restart.py`

### **依赖缺失**
```
ModuleNotFoundError: No module named 'xxx'
```
**解决方案**: `pip install -r requirements_enhanced.txt`

## 📊 **预期结果**

**成功启动输出:**
```
🎉 重启成功!
🌐 服务地址: http://localhost:8001
📚 API文档: http://localhost:8001/docs
🔍 健康检查: curl http://localhost:8001/health
```

**健康检查响应:**
```json
{
  "status": "healthy",
  "futu_connected": true,
  "cache_available": true,
  "timestamp": "2025-06-18T17:47:28.035188"
}
```

## 🔧 **高级配置**

### **环境变量**
```bash
export FUTU_HOST=127.0.0.1    # OpenD地址
export FUTU_PORT=11111        # OpenD端口
export CACHE_SIZE=2000        # 缓存大小
```

### **Redis缓存（可选）**
```bash
brew install redis            # macOS
brew services start redis     # 启动Redis
python restart.py             # 重启服务
```

### **多版本选择**
```bash
python main_enhanced.py                    # 端口8001 - MCP+HTTP
python main_enhanced_simple_alternative.py # 端口8002 - 纯HTTP
python main_simple.py                      # 端口8000 - 基础版
```

## 🎯 **使用建议**

**生产环境**: 使用 `python restart.py` 启动端口8001增强版  
**开发调试**: 使用 `python main_enhanced.py` 查看详细日志  
**高并发**: 启用Redis缓存 + 负载均衡配置  

---

**�� 5分钟即可启动专业量化分析平台！** 