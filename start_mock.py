#!/usr/bin/env python3
"""
富途 MCP 服务 - Mock 模式启动
用于测试 Windows 适配，无需连接 OpenD
"""

import sys
from pathlib import Path

# 确保可以导入本地模块
project_root = Path(__file__).parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.process_manager import is_port_in_use
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(title="富途 MCP 服务 - Mock 模式")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {
        "status": "healthy (mock mode)",
        "futu_connected": False,
        "mock_mode": True,
        "message": "这是 Mock 模式，用于测试 Windows 适配"
    }

@app.get("/")
def root():
    return {
        "message": "富途 MCP 服务 - Mock 模式",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    print("="*60)
    print("  富途 MCP 服务 - Mock 模式 (Windows 测试)")
    print("="*60)
    print()
    print("服务地址: http://localhost:8001")
    print("API 文档: http://localhost:8001/docs")
    print("健康检查: http://localhost:8001/health")
    print()
    print("注意: 这是 Mock 模式，用于测试 Windows 兼容性")
    print("      真实数据需要启动富途 OpenD 并使用主服务")
    print()
    
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="info")
