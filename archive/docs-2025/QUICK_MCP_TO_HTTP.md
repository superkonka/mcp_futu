# 🚀 MCP → HTTP API 快速参考

## ⚡ **你的调用解决方案**

### **原MCP调用（有问题）：**
```
工具: futu-enhanced/get_stock_quote_enhanced
参数: {
  "code_list": ["HK.09660"],
  "optimization": {"only_essential_fields": true}
}
```

### **HTTP API替代（稳定）：**
```bash
curl -X POST http://localhost:8001/api/quote/stock_quote \
  -H "Content-Type: application/json" \
  -d '{
    "code_list": ["HK.09660"],
    "optimization": {"only_essential_fields": true}
  }'
```

### **实际响应数据：**
```json
{
  "ret_code": 0,
  "ret_msg": "获取股票报价成功",
  "data": {
    "quotes": [{
      "code": "HK.09660",
      "update_time": "2025-06-17 16:05:51",
      "last_price": 6.45,
      "open_price": 6.88,
      "high_price": 6.93,
      "low_price": 6.38,
      "prev_close_price": 6.87,
      "volume": 275452289,
      "turnover": 1805462497.0
    }]
  }
}
```

## 📊 **常用API端点**

| MCP工具 | HTTP端点 | 说明 |
|---------|----------|------|
| `get_stock_quote_enhanced` | `/api/quote/stock_quote` | 股票报价 ✅ |
| `get_technical_indicators` | `/api/analysis/technical_indicators` | 技术指标 ✅ |
| `get_history_kline_enhanced` | `/api/market/history_kline` | K线数据 ✅ |
| `analyze_stock_enhanced` | `/api/analysis/simple` | 智能分析 ✅ |

## 🎯 **状态总结**

- ✅ **HTTP API**: 100%可用，无问题
- ⚠️ **MCP协议**: 初始化时序bug（上游库问题）
- 🔧 **解决方案**: 使用HTTP API替代

## 💡 **建议**

直接使用HTTP API，功能完全相同但更稳定可靠！ 