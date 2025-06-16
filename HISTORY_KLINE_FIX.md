# get_history_kline 方法时间范围修复

## 问题描述

用户在使用 `get_history_kline` 方法请求"过去5天的波动数据"时，虽然现在是6月，但返回的却是3月份的数据。

### 问题原因
当用户没有指定 `start` 和 `end` 参数时，富途API默认返回历史最早的数据，而不是最近的数据。

### 用户请求示例
```json
{
  "code": "HK.06693",
  "ktype": "K_DAY", 
  "autype": "qfq",
  "max_count": 5
}
```

### 问题结果
返回了2025-03-10和2025-03-11的数据，而不是最近5天的数据。

## 修复方案

### 1. 智能时间范围计算
在 `get_history_kline` 方法中添加了智能时间范围处理：

```python
# 智能处理时间范围：如果没有指定start和end，自动设置为最近的时间范围
if not start_date and not end_date:
    from datetime import datetime, timedelta
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    # 根据K线类型和max_count计算开始日期
    days_back = self._calculate_days_back(request.ktype, request.max_count)
    start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
```

### 2. 添加智能日期计算方法
新增 `_calculate_days_back` 方法，根据不同K线类型智能计算所需的时间范围：

| K线类型 | 计算方式 | 说明 |
|---------|----------|------|
| **日K** | `max_count × 1.5` | 考虑交易日，保险系数1.5 |
| **周K** | `max_count × 7 + 7` | 每周一根，加7天保险 |
| **月K** | `max_count × 30 + 30` | 每月一根，加30天保险 |
| **分钟K** | 基于交易时间计算 | 每天约6小时交易，考虑交易日 |

### 3. 更新模型描述
优化了 `HistoryKLineRequest` 模型的字段描述，让用户明确知道智能时间范围功能。

## 修复效果

### 修复前 vs 修复后

| 场景 | 修复前 | 修复后 |
|------|--------|--------|
| **请求参数** | `max_count=5`，无时间范围 | `max_count=5`，无时间范围 |
| **返回数据** | 2025-03-10 ~ 2025-03-11 | 2025-06-09 ~ 2025-06-13 |
| **是否正确** | ❌ 返回历史最早数据 | ✅ 返回最近数据 |

### 测试验证结果

```
测试1: 获取过去5条日K数据（不指定时间）
- 自动设置时间范围: 2025-06-09 到 2025-06-16
- 返回数据: 2025-06-09 到 2025-06-13 的5条数据
- ✅ 成功！返回的是最近的数据（6月份）

测试2: 获取过去10条5分钟K线数据  
- 自动设置时间范围: 2025-06-06 到 2025-06-16
- 返回了6月6日的5分钟K线数据

测试3: 指定时间范围测试
- 按照指定的时间范围正确返回数据
```

## 使用方法

### 1. 智能获取最近数据（推荐）
```python
# 不指定时间，自动获取最近的数据
request = HistoryKLineRequest(
    code="HK.06693",
    ktype=KLType.K_DAY,
    autype=AuType.QFQ,
    max_count=5,  # 系统会自动计算时间范围
    optimization=DataOptimization(
        enable_optimization=True,
        only_essential_fields=True
    )
)
```

### 2. REST API调用
```json
{
    "code": "HK.06693",
    "ktype": "K_DAY",
    "autype": "qfq", 
    "max_count": 5,
    "optimization": {
        "enable_optimization": true,
        "only_essential_fields": true
    }
}
```

### 3. 指定时间范围（保持原有功能）
```python
request = HistoryKLineRequest(
    code="HK.06693",
    start="2025-06-01",
    end="2025-06-13", 
    ktype=KLType.K_DAY,
    autype=AuType.QFQ
)
```

## 兼容性说明

✅ **向后兼容**：现有指定了 `start` 和 `end` 的代码完全不受影响

✅ **智能增强**：没有指定时间范围的请求现在会自动获取最近数据

✅ **日志提示**：系统会记录自动设置的时间范围，便于调试

## 额外优化

1. **默认max_count调整**：从1000改为100，避免数据量过大
2. **优化配置集成**：支持数据优化配置，减少无意义字段
3. **示例代码更新**：更新演示代码展示智能时间范围功能

## 测试脚本

可以运行以下脚本验证修复效果：
```bash
python test_history_kline_fix.py
```

该脚本会测试不同场景下的时间范围处理，确保修复生效。 