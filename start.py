#!/usr/bin/env python3
"""
富途 MCP API 服务启动器
优化版本，包含状态监控和错误处理
"""

import asyncio
import sys
import time
import signal
import subprocess
from pathlib import Path
from typing import Optional

import uvicorn
from loguru import logger

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from client_helper import MCPClientHelper

class EnhancedMCPServer:
    """增强的MCP服务器启动器"""
    
    def __init__(self):
        self.server_process: Optional[subprocess.Popen] = None
        self.is_running = False
        
    def check_dependencies(self) -> bool:
        """检查依赖包"""
        logger.info("📦 检查依赖包...")
        
        required_packages = [
            ('fastapi', 'fastapi'),
            ('uvicorn', 'uvicorn'), 
            ('futu-api', 'futu'),  # 包名是futu-api，但导入名是futu
            ('fastapi-mcp', 'fastapi_mcp'),  # 包名是fastapi-mcp，但导入名是fastapi_mcp
            ('pydantic', 'pydantic'),
            ('loguru', 'loguru'),
            ('aiohttp', 'aiohttp')
        ]
        
        missing_packages = []
        for package_name, import_name in required_packages:
            try:
                __import__(import_name)
            except ImportError:
                missing_packages.append(package_name)
        
        if missing_packages:
            logger.error(f"❌ 缺少依赖包: {', '.join(missing_packages)}")
            logger.info("请运行: pip install -r requirements.txt")
            return False
        
        logger.info("✅ 依赖包检查通过")
        return True
    
    async def check_futu_connection(self) -> bool:
        """检查富途OpenD连接"""
        logger.info("🔌 检查富途OpenD连接 (127.0.0.1:11111)...")
        
        try:
            import futu as ft
            quote_ctx = ft.OpenQuoteContext(host='127.0.0.1', port=11111)
            ret, data = quote_ctx.get_global_state()
            quote_ctx.close()
            
            if ret == ft.RET_OK:
                logger.info("✅ 富途OpenD连接正常")
                return True
            else:
                logger.error(f"❌ 富途OpenD连接失败: {data}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 富途OpenD连接检查失败: {e}")
            logger.info("请确保富途OpenD已启动并运行在端口11111")
            return False
    
    def signal_handler(self, signum, frame):
        """处理终止信号"""
        logger.info("🛑 收到终止信号，正在关闭服务...")
        self.is_running = False
        if self.server_process:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("强制终止服务器进程")
                self.server_process.kill()
        sys.exit(0)
    
    async def start_server_async(self):
        """异步启动服务器"""
        logger.info("🌐 启动MCP API服务...")
        logger.info("服务地址: http://127.0.0.1:8000")
        logger.info("API文档: http://127.0.0.1:8000/docs")
        logger.info("MCP端点: http://127.0.0.1:8000/mcp")
        logger.info("健康检查: http://127.0.0.1:8000/health")
        logger.info("就绪检查: http://127.0.0.1:8000/ready")
        logger.info("")
        logger.info("按 Ctrl+C 停止服务")
        logger.info("")
        
        try:
            # 设置信号处理器
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
            
            self.is_running = True
            
            # 启动uvicorn服务器
            config = uvicorn.Config(
                "main:app",
                host="127.0.0.1",
                port=8000,
                reload=False,  # 生产环境关闭reload
                log_level="info",
                access_log=True
            )
            
            server = uvicorn.Server(config)
            
            # 启动服务器
            await server.serve()
            
        except Exception as e:
            logger.error(f"❌ 服务启动失败: {e}")
            self.is_running = False
            raise
    
    async def monitor_server_startup(self):
        """监控服务器启动状态"""
        helper = MCPClientHelper(max_retries=20, retry_delay=0.5)
        
        # 给服务器一些启动时间
        await asyncio.sleep(1)
        
        # 等待服务器就绪
        success = await helper.wait_and_connect()
        
        if success:
            status = await helper.get_server_status()
            logger.info("🎉 服务器启动完成！")
            logger.info(f"📊 服务器状态: {status}")
            
            # 显示可用的工具列表
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get("http://127.0.0.1:8000/docs") as response:
                        if response.status == 200:
                            logger.info("📚 API文档已可用")
            except:
                pass
                
            logger.info("")
            logger.info("🚀 MCP服务器已准备好接受连接！")
            logger.info("可以开始使用AI助手调用富途API工具了。")
            
        else:
            logger.error("❌ 服务器启动超时或失败")
    
    async def run(self):
        """运行服务器"""
        try:
            # 预检查
            if not self.check_dependencies():
                return False
            
            if not await self.check_futu_connection():
                return False
            
            # 并发启动服务器和监控
            await asyncio.gather(
                self.start_server_async(),
                self.monitor_server_startup(),
                return_exceptions=True
            )
            
        except KeyboardInterrupt:
            logger.info("🛑 用户中断服务")
        except Exception as e:
            logger.error(f"❌ 服务运行失败: {e}")
            return False
        finally:
            self.is_running = False
        
        return True

def main():
    """主函数"""
    print("🚀 富途 MCP API 服务启动器 (增强版)")
    print("=" * 50)
    
    try:
        server = EnhancedMCPServer()
        result = asyncio.run(server.run())
        
        if not result:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except Exception as e:
        logger.error(f"❌ 启动器失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 