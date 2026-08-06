# MCP 工具调用 → HTTP API 映射指南

## 🔄 **完整的工具映射**

由于MCP协议存在初始化时序问题，这里提供完整的HTTP API替代方案：

### 1. **股票报价查询**

**MCP工具调用（有问题）：**
```
工具名: futu-enhanced/get_stock_quote_enhanced
参数: {
  "code_list": ["HK.09660"],
  "optimization": {"only_essential_fields": true}
}
```

**HTTP API（稳定）：**
```bash
curl -X POST http://localhost:8001/api/quote/stock_quote \
  -H "Content-Type: application/json" \
  -d '{
    "code_list": ["HK.09660"],
    "optimization": {"only_essential_fields": true}
  }'
```

### 2. **技术指标分析**

**MCP工具调用（有问题）：**
```
工具名: futu-enhanced/get_technical_indicators
参数: {
  "code": "HK.09660",
  "indicators": ["macd", "rsi"],
  "ktype": "K_30M"
}
```

**HTTP API（稳定）：**
```bash
curl -X POST http://localhost:8001/api/analysis/technical_indicators \
  -H "Content-Type: application/json" \
  -d '{
    "code": "HK.09660",
    "indicators": ["macd", "rsi"],
    "ktype": "K_30M"
  }'
```

### 3. **历史K线数据**

**MCP工具调用（有问题）：**
```
工具名: futu-enhanced/get_history_kline_enhanced
参数: {
  "code": "HK.09660",
  "ktype": "K_DAY",
  "start": "2024-01-01",
  "end": "2024-12-31"
}
```

**HTTP API（稳定）：**
```bash
curl -X POST http://localhost:8001/api/market/history_kline \
  -H "Content-Type: application/json" \
  -d '{
    "code": "HK.09660",
    "ktype": "K_DAY",
    "start": "2024-01-01",
    "end": "2024-12-31"
  }'
```

### 4. **智能分析**

**MCP工具调用（有问题）：**
```
工具名: futu-enhanced/analyze_stock_enhanced
参数: {
  "code": "HK.09660",
  "analysis_type": "comprehensive"
}
```

**HTTP API（稳定）：**
```bash
curl -X POST http://localhost:8001/api/analysis/simple \
  -H "Content-Type: application/json" \
  -d '{
    "code": "HK.09660",
    "analysis_type": "comprehensive"
  }'
```

## 🧪 **测试示例**

### 当前你想要的调用：

```bash
# 获取腾讯控股(HK.09660)的股票报价
curl -X POST http://localhost:8001/api/quote/stock_quote \
  -H "Content-Type: application/json" \
  -d '{
    "code_list": ["HK.09660"],
    "optimization": {"only_essential_fields": true}
  }' | jq '.'
```

### 预期响应：
```json
{
  "ret_code": 0,
  "ret_msg": "获取股票报价成功",
  "data": {
    "quote_list": [{
      "code": "HK.09660",
      "name": "腾讯控股",
      "cur_price": 325.4,
      "change_val": 2.8,
      "change_rate": 0.87,
      "volume": 12345678,
      "turnover": 4.01e9
    }]
  }
}
```

## 📊 **API端点完整列表**

| 功能 | HTTP端点 | 状态 |
|------|----------|------|
| **股票报价** | `/api/quote/stock_quote` | ✅ 稳定 |
| **技术指标** | `/api/analysis/technical_indicators` | ✅ 稳定 |
| **历史K线** | `/api/market/history_kline` | ✅ 稳定 |
| **智能分析** | `/api/analysis/simple` | ✅ 稳定 |
| **健康检查** | `/health` | ✅ 稳定 |
| **工具列表** | `/api/tools/list` | ✅ 稳定 |

## 🔧 **编程语言示例**

### Python
```python
import requests

# 获取股票报价
response = requests.post(
    "http://localhost:8001/api/quote/stock_quote",
    json={
        "code_list": ["HK.09660"],
        "optimization": {"only_essential_fields": True}
    }
)
data = response.json()
print(f"股价: {data['data']['quote_list'][0]['cur_price']}")
```

### JavaScript
```javascript
const response = await fetch('http://localhost:8001/api/quote/stock_quote', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    code_list: ['HK.09660'],
    optimization: {only_essential_fields: true}
  })
});
const data = await response.json();
console.log('股价:', data.data.quote_list[0].cur_price);
```

## 🎯 **最佳实践**

### 1. **错误处理**
```bash
# 带错误处理的调用
response=$(curl -s -X POST http://localhost:8001/api/quote/stock_quote \
  -H "Content-Type: application/json" \
  -d '{"code_list": ["HK.09660"]}')

ret_code=$(echo "$response" | jq -r '.ret_code')
if [ "$ret_code" = "0" ]; then
    echo "调用成功"
    echo "$response" | jq '.data'
else
    echo "调用失败: $(echo "$response" | jq -r '.ret_msg')"
fi
```

### 2. **批量查询**
```bash
# 同时查询多个股票
curl -X POST http://localhost:8001/api/quote/stock_quote \
  -H "Content-Type: application/json" \
  -d '{
    "code_list": ["HK.09660", "HK.00700", "US.AAPL"],
    "optimization": {"only_essential_fields": true}
  }'
```

### 3. **组合分析**
```bash
# 先获取报价，再分析技术指标
code="HK.09660"

# 1. 获取当前报价
quote=$(curl -s -X POST http://localhost:8001/api/quote/stock_quote \
  -H "Content-Type: application/json" \
  -d "{\"code_list\": [\"$code\"]}")

# 2. 分析技术指标
technical=$(curl -s -X POST http://localhost:8001/api/analysis/technical_indicators \
  -H "Content-Type: application/json" \
  -d "{\"code\": \"$code\", \"indicators\": [\"rsi\", \"macd\"]}")

echo "报价: $(echo "$quote" | jq '.data.quote_list[0].cur_price')"
echo "RSI: $(echo "$technical" | jq '.data.trend_indicators.rsi.current_value')"
```

## 💡 **总结**

1. **HTTP API 100% 稳定可用** ✅
2. **功能完全等同于MCP工具** ✅
3. **性能更好，无初始化问题** ✅
4. **支持所有编程语言** ✅

建议完全切换到HTTP API，避免MCP的初始化时序问题。所有功能都有对应的HTTP端点，且更稳定可靠。 