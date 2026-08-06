# subscribe_quotes 方法订阅类型修复

## 问题描述

用户在调用 `subscribe_quotes` 方法时遇到 422 状态码错误：

```
Error calling subscribe_quotes. Status code: 422. Response: {"detail":[{"type":"enum","loc":["body","subtype_list",0],"msg":"Input should be 'QUOTE', 'ORDER_BOOK', 'TICKER', 'K_DAY', 'K_1M', 'RT_DATA' or 'BROKER'","input":"K_60M","ctx":{"expected":"'QUOTE', 'ORDER_BOOK', 'TICKER', 'K_DAY', 'K_1M', 'RT_DATA' or 'BROKER'"}}]}
```

### 问题原因
`SubType` 枚举中缺少大量K线订阅类型，用户尝试订阅 `K_60M`（60分钟K线），但系统只支持 `K_DAY` 和 `K_1M`。

### 缺失的订阅类型
原来只有：`QUOTE`, `ORDER_BOOK`, `TICKER`, `K_DAY`, `K_1M`, `RT_DATA`, `BROKER`

缺少：`K_3M`, `K_5M`, `K_15M`, `K_30M`, `K_60M`, `K_WEEK`, `K_MON`

## 修复方案

### 1. 扩展 SubType 枚举
添加了所有富途API支持的K线订阅类型：

```python
class SubType(str, Enum):
    """订阅数据类型"""
    QUOTE = "QUOTE"           # 报价
    ORDER_BOOK = "ORDER_BOOK" # 摆盘
    TICKER = "TICKER"         # 逐笔
    K_1M = "K_1M"            # 1分钟K线
    K_3M = "K_3M"            # 3分钟K线
    K_5M = "K_5M"            # 5分钟K线
    K_15M = "K_15M"          # 15分钟K线
    K_30M = "K_30M"          # 30分钟K线
    K_60M = "K_60M"          # 60分钟K线
    K_DAY = "K_DAY"          # 日K
    K_WEEK = "K_WEEK"        # 周K
    K_MON = "K_MON"          # 月K
    RT_DATA = "RT_DATA"       # 分时数据
    BROKER = "BROKER"         # 经纪队列
```

### 2. 更新转换方法
更新 `_convert_sub_type` 方法支持所有新的订阅类型：

```python
def _convert_sub_type(self, sub_type: SubType) -> ft.SubType:
    sub_map = {
        SubType.QUOTE: ft.SubType.QUOTE,
        SubType.ORDER_BOOK: ft.SubType.ORDER_BOOK,
        SubType.TICKER: ft.SubType.TICKER,
        SubType.K_1M: ft.SubType.K_1M,
        SubType.K_3M: ft.SubType.K_3M,
        SubType.K_5M: ft.SubType.K_5M,
        SubType.K_15M: ft.SubType.K_15M,
        SubType.K_30M: ft.SubType.K_30M,
        SubType.K_60M: ft.SubType.K_60M,
        SubType.K_DAY: ft.SubType.K_DAY,
        SubType.K_WEEK: ft.SubType.K_WEEK,
        SubType.K_MON: ft.SubType.K_MON,
        SubType.RT_DATA: ft.SubType.RT_DATA,
        SubType.BROKER: ft.SubType.BROKER
    }
    return sub_map.get(sub_type, ft.SubType.QUOTE)
```

## 修复效果

### 测试验证结果

```
✅ 测试1: K_60M 订阅成功！（用户原问题已解决）
✅ 测试2: 混合订阅多种K线类型成功
✅ 测试3: 所有K线订阅类型都成功
   - K_1M ✅  K_3M ✅  K_5M ✅
   - K_15M ✅ K_30M ✅ K_60M ✅
   - K_DAY ✅ K_WEEK ✅ K_MON ✅
✅ 测试4: 其他订阅类型都成功
   - QUOTE ✅ ORDER_BOOK ✅ TICKER ✅
   - RT_DATA ✅ BROKER ✅
```

### 修复前 vs 修复后

| 场景 | 修复前 | 修复后 |
|------|--------|--------|
| **K_60M订阅** | ❌ 422错误，枚举值不支持 | ✅ 订阅成功 |
| **支持的K线类型** | 2种（K_1M, K_DAY） | 9种（完整支持） |
| **错误信息** | `Input should be 'QUOTE'...` | 无错误 |

## 使用方法

### 1. 订阅用户遇到问题的K_60M（已修复）
```python
request = SubscribeRequest(
    code_list=["HK.00700"],
    subtype_list=[SubType.K_60M]  # 现在支持了！
)
```

### 2. 混合订阅多种K线类型
```python
request = SubscribeRequest(
    code_list=["HK.00700", "HK.09988"],
    subtype_list=[
        SubType.QUOTE,     # 报价
        SubType.K_5M,      # 5分钟K线
        SubType.K_15M,     # 15分钟K线
        SubType.K_60M,     # 60分钟K线
        SubType.K_DAY      # 日K线
    ]
)
```

### 3. REST API调用
```json
{
    "code_list": ["HK.00700"],
    "subtype_list": ["K_60M"]
}
```

### 4. 所有支持的K线订阅类型
```json
{
    "code_list": ["HK.00700"],
    "subtype_list": [
        "K_1M", "K_3M", "K_5M", "K_15M", "K_30M", "K_60M",
        "K_DAY", "K_WEEK", "K_MON"
    ]
}
```

## 兼容性说明

✅ **向后兼容**：原有的订阅类型（`QUOTE`, `K_DAY`, `K_1M` 等）完全不受影响

✅ **功能增强**：新增了8种K线订阅类型，满足不同时间周期的需求

✅ **API一致性**：与富途OpenAPI的订阅类型保持完全一致

## 新增功能概览

| 订阅类型 | 描述 | 状态 |
|----------|------|------|
| `K_1M` | 1分钟K线 | ✅ 原有 |
| `K_3M` | 3分钟K线 | 🆕 新增 |
| `K_5M` | 5分钟K线 | 🆕 新增 |
| `K_15M` | 15分钟K线 | 🆕 新增 |
| `K_30M` | 30分钟K线 | 🆕 新增 |
| `K_60M` | 60分钟K线 | 🆕 新增 |
| `K_DAY` | 日K线 | ✅ 原有 |
| `K_WEEK` | 周K线 | 🆕 新增 |
| `K_MON` | 月K线 | 🆕 新增 |

## 测试脚本

可以运行以下脚本验证修复效果：
```bash
python test_subscribe_fix.py
```

该脚本会测试所有订阅类型，确保修复完全生效。

## 相关文档更新

- ✅ 更新了 `examples/demo.py` 展示新的订阅功能
- ✅ 创建了完整的测试验证脚本  
- ✅ 枚举定义与富途API保持一致 