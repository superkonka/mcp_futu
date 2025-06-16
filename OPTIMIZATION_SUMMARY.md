# get_stock_basicinfo 方法优化总结

## 问题描述
之前使用 `get_stock_basicinfo` 方法时会导致token超出限制，主要原因是：
1. **数据量巨大**：一次返回3000+只股票的完整信息
2. **字段冗余**：包含大量无意义的字段（如"N/A"值）
3. **缺乏数据量控制**：无法限制返回的股票数量

## 优化方案

### 1. 添加核心字段配置
在 `ESSENTIAL_FIELDS` 中为 `basic_info` 添加了核心字段定义：
```python
'basic_info': [
    'code', 'name', 'lot_size', 'stock_type', 'listing_date', 
    'delisting', 'exchange_type'
]
```

### 2. 扩展无意义值过滤
添加了更多无意义值的过滤规则：
```python
'option_type': ['N/A', '', None],
'strike_price': ['N/A', '', None, 0.0],
'suspension': ['N/A', '', None],
'stock_child_type': ['N/A', '', None],
'index_option_type': ['N/A', '', None]
```

### 3. 添加数据量限制
在 `StockBasicInfoRequest` 中添加 `max_count` 参数：
- 默认值：100只股票
- 作用：限制返回的股票数量，避免token超出

### 4. 响应信息增强
返回数据中包含：
- `data_count`：实际返回的股票数量
- `total_available`：可用的股票总数
- 在返回消息中提示是否应用了数量限制

## 优化效果对比

| 场景 | 优化前 | 优化后 | 优化比例 |
|------|--------|--------|----------|
| **默认获取** | 3251只股票，14字段，1092.69 KB | 50只股票，7字段，8.41 KB | **减少99.2%** |
| **自定义字段** | - | 20只股票，3字段，1.33 KB | **减少99.9%** |
| **极简模式** | - | 10只股票，2字段，0.52 KB | **减少99.95%** |

## 使用方法

### 1. 推荐配置（数量限制+字段优化）
```python
request = StockBasicInfoRequest(
    market=Market.HK,
    stock_type=SecurityType.STOCK,
    max_count=50,  # 限制返回50只股票
    optimization=DataOptimization(
        enable_optimization=True,
        only_essential_fields=True,
        remove_meaningless_values=True
    )
)
```

### 2. 自定义字段模式
```python
request = StockBasicInfoRequest(
    market=Market.HK,
    stock_type=SecurityType.STOCK,
    max_count=20,
    optimization=DataOptimization(
        enable_optimization=True,
        custom_fields=['code', 'name', 'lot_size'],  # 只返回指定字段
        remove_meaningless_values=True
    )
)
```

### 3. 极简模式（仅代码和名称）
```python
request = StockBasicInfoRequest(
    market=Market.HK,
    stock_type=SecurityType.STOCK,
    max_count=10,
    optimization=DataOptimization(
        enable_optimization=True,
        custom_fields=['code', 'name']
    )
)
```

### 4. REST API调用示例
```json
{
    "market": "HK",
    "stock_type": "STOCK",
    "max_count": 20,
    "optimization": {
        "enable_optimization": true,
        "only_essential_fields": true,
        "remove_meaningless_values": true
    }
}
```

## 返回结果示例

### 优化后的返回结果
```json
{
    "ret_code": 0,
    "ret_msg": "获取股票基本信息成功（已限制返回50/3251只股票）",
    "data": {
        "basic_info": [
            {
                "code": "HK.00001",
                "name": "长和",
                "lot_size": 500,
                "stock_type": "STOCK",
                "listing_date": "2015-03-18",
                "delisting": false,
                "exchange_type": "HK_MAINBOARD"
            }
        ],
        "data_count": 50,
        "total_available": 3251
    }
}
```

## 建议

1. **默认使用优化配置**：建议所有调用都启用优化，避免token超出
2. **合理设置max_count**：根据实际需求设置返回数量，通常10-100只股票足够
3. **使用自定义字段**：如果只需要特定信息，使用`custom_fields`进一步减少数据量
4. **监控数据大小**：在生产环境中监控返回数据的大小，确保不超过LLM的token限制

## 测试验证

运行以下脚本可以验证优化效果：
```bash
python test_optimized_basicinfo.py
```

该脚本会对比不同优化配置下的数据大小和字段数量，帮助选择最适合的配置。 