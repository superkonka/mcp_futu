#!/usr/bin/env python3
"""
富途 MCP 服务 - 严格模式启动
禁用所有模拟数据，确保返回真实数据
"""

import os
import sys

# 设置严格模式环境变量
os.environ['DISABLE_MOCK_DATA'] = 'true'
os.environ['CACHE_ENABLED'] = 'false'
os.environ['FORCE_REAL_ENV'] = 'true'
os.environ['DISABLE_FALLBACK'] = 'true'
os.environ['PYTHONUNBUFFERED'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'

print("="*60)
print("  富途 MCP 服务 - 严格模式")
print("="*60)
print()
print("严格模式已启用：")
print("  ✓ 禁用模拟数据")
print("  ✓ 禁用缓存")
print("  ✓ 强制真实环境")
print("  ✓ 禁用降级处理")
print()
print("所有数据将直接来自富途 OpenD")
print("如果 OpenD 连接失败，API 将返回错误而不是假数据")
print()

# 导入并启动主服务
from main_enhanced import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8001,
        log_level="info"
    )
