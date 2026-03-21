# 严格模式指南 - 禁用模拟数据

> 确保所有返回数据都是真实数据，避免误判

## 🎯 快速启动严格模式

```powershell
python start_strict.py
```

这将自动：
- ✅ 禁用模拟数据
- ✅ 禁用缓存
- ✅ 强制真实环境
- ✅ 禁用降级处理

---

## 🔧 手动配置

### 方法 1: 使用环境变量

```powershell
# 设置环境变量
$env:DISABLE_MOCK_DATA = "true"
$env:CACHE_ENABLED = "false"

# 启动服务
python main_enhanced.py
```

### 方法 2: 修改 .env 文件

```env
# 禁用模拟数据
DISABLE_MOCK_DATA=true

# 禁用缓存（强制实时获取）
CACHE_ENABLED=false

# 强制真实环境
FORCE_REAL_ENV=true
```

---

## 📋 配置说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DISABLE_MOCK_DATA` | `false` | `true` = API 失败时返回错误，不返回模拟数据 |
| `CACHE_ENABLED` | `true` | `false` = 禁用缓存，强制从 OpenD 获取最新数据 |
| `FORCE_REAL_ENV` | `false` | `true` = 强制使用真实环境，忽略模拟环境请求 |
| `DISABLE_FALLBACK` | `false` | `true` = 禁用降级处理，失败时直接报错 |

---

## ⚠️ 重要提示

### 严格模式的影响

1. **API 可能更慢**
   - 禁用缓存后，每次请求都从 OpenD 获取
   - 响应时间可能从 <10ms 增加到 200-500ms

2. **API 可能失败**
   - 如果 OpenD 连接有问题，API 会直接报错
   - 不会返回缓存数据或模拟数据作为回退

3. **OpenD 负载增加**
   - 每次请求都直接查询 OpenD
   - 频繁调用可能触发 OpenD 限流

### 适用场景

✅ **推荐使用严格模式**
- 实盘交易前的数据验证
- 需要确保数据 100% 真实
- 调试数据准确性问题

❌ **不推荐使用严格模式**
- 高频查询场景
- 开发测试阶段
- 对响应速度要求高

---

## 🔍 验证严格模式

### 检查服务状态

```bash
curl http://localhost:8001/health
```

应该看到：
```json
{
  "status": "healthy",
  "futu_connected": true,
  "cache_enabled": false,
  "strict_mode": true
}
```

### 测试模拟数据禁用

```bash
# 查询一个不存在的股票代码
curl -X POST http://localhost:8001/api/quote/stock_quote \
  -H "Content-Type: application/json" \
  -d '{"code_list": ["INVALID.CODE"]}'
```

严格模式下应该返回错误，而不是模拟数据。

---

## 🚀 切换回普通模式

### 临时切换（当前会话）

```powershell
# 取消环境变量
Remove-Item Env:\DISABLE_MOCK_DATA
Remove-Item Env:\CACHE_ENABLED

# 重启服务
python main_enhanced.py
```

### 永久切换（修改 .env）

```env
DISABLE_MOCK_DATA=false
CACHE_ENABLED=true
```

---

## 📞 问题排查

### 问题 1: API 频繁报错

**原因**: OpenD 连接不稳定或限流

**解决**: 适当启用缓存，或降低请求频率

```env
CACHE_ENABLED=true
CACHE_EXPIRE_SECONDS=30  # 短缓存时间
```

### 问题 2: 响应太慢

**原因**: 禁用缓存后每次都查询 OpenD

**解决**: 仅在必要时使用严格模式，平时使用普通模式

### 问题 3: 某些接口无法使用

**原因**: 严格模式下禁用降级处理

**解决**: 检查 OpenD 权限和连接状态

---

## 💡 最佳实践

### 混合使用策略

```python
# 平时使用普通模式（允许缓存）
python main_enhanced.py

# 重要操作前切换到严格模式
python start_strict.py

# 验证数据后切回普通模式
```

### 程序化切换

```python
import os

# 启用严格模式
os.environ['DISABLE_MOCK_DATA'] = 'true'
os.environ['CACHE_ENABLED'] = 'false'

# 执行关键操作
# ...

# 恢复普通模式
os.environ['DISABLE_MOCK_DATA'] = 'false'
os.environ['CACHE_ENABLED'] = 'true'
```

---

## ✅ 检查清单

使用严格模式前确认：

- [ ] OpenD 已启动并连接正常
- [ ] 网络连接稳定
- [ ] 能接受较慢的响应速度
- [ ] 能接受偶尔的 API 失败
- [ ] 了解严格模式的影响

---

## 📊 性能对比

| 模式 | 平均响应时间 | 数据新鲜度 | 可用性 |
|------|-------------|-----------|--------|
| 普通模式 | 10-50ms | 可能滞后（缓存）| 高（有降级）|
| 严格模式 | 200-500ms | 实时 | 中（无降级）|

选择适合你需求的模式！
