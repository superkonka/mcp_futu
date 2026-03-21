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
print("  Futu MCP Service - Strict Mode")
print("="*60)
print()
print("Strict mode enabled:")
print("  - Disable mock data")
print("  - Disable cache")
print("  - Force real environment")
print("  - Disable fallback")
print()
print("All data will come from Futu OpenD")
print("If OpenD fails, API will return error instead of fake data")
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
