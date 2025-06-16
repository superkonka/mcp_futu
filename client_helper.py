#!/usr/bin/env python3
"""
MCP客户端连接助手
提供带重试机制的MCP服务器连接功能
"""

import asyncio
import aiohttp
import time
from typing import Optional, Dict, Any
from loguru import logger

class MCPClientHelper:
    """MCP客户端连接助手"""
    
    def __init__(self, 
                 base_url: str = "http://127.0.0.1:8000",
                 max_retries: int = 10,
                 retry_delay: float = 0.5,
                 backoff_factor: float = 1.5,
                 timeout: float = 30.0):
        self.base_url = base_url.rstrip('/')
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.backoff_factor = backoff_factor
        self.timeout = timeout
        
    async def wait_for_server_ready(self) -> bool:
        """等待服务器就绪"""
        logger.info("等待MCP服务器就绪...")
        
        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                    # 首先检查健康状态
                    async with session.get(f"{self.base_url}/health") as response:
                        if response.status == 200:
                            health_data = await response.json()
                            if health_data.get("ready", False):
                                logger.info(f"MCP服务器已就绪 (尝试 {attempt + 1}/{self.max_retries})")
                                return True
                            else:
                                logger.debug(f"服务器健康但未就绪: {health_data}")
                        else:
                            logger.debug(f"健康检查失败: HTTP {response.status}")
                            
            except Exception as e:
                logger.debug(f"连接尝试 {attempt + 1} 失败: {e}")
            
            if attempt < self.max_retries - 1:
                delay = self.retry_delay * (self.backoff_factor ** attempt)
                logger.debug(f"等待 {delay:.1f}s 后重试...")
                await asyncio.sleep(delay)
        
        logger.error(f"经过 {self.max_retries} 次尝试，服务器仍未就绪")
        return False
    
    async def test_mcp_connection(self) -> bool:
        """测试MCP连接"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                # 测试MCP端点
                async with session.get(f"{self.base_url}/mcp") as response:
                    if response.status == 200:
                        logger.info("MCP端点连接成功")
                        return True
                    else:
                        logger.warning(f"MCP端点返回错误: HTTP {response.status}")
                        return False
        except Exception as e:
            logger.error(f"MCP连接测试失败: {e}")
            return False
    
    async def get_server_status(self) -> Optional[Dict[str, Any]]:
        """获取服务器详细状态"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{self.base_url}/health") as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return {"error": f"HTTP {response.status}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def wait_and_connect(self) -> bool:
        """等待并连接到MCP服务器"""
        logger.info("开始连接MCP服务器...")
        
        # 第一步：等待服务器基本启动
        start_time = time.time()
        server_ready = await self.wait_for_server_ready()
        
        if not server_ready:
            return False
        
        # 第二步：测试MCP连接
        mcp_ready = await self.test_mcp_connection()
        
        if mcp_ready:
            elapsed = time.time() - start_time
            logger.info(f"✅ MCP服务器连接成功 (耗时: {elapsed:.2f}s)")
            return True
        else:
            logger.error("❌ MCP连接测试失败")
            return False

    async def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """调用MCP工具"""
        try:
            payload = {
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": params
                }
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.post(
                    f"{self.base_url}/mcp",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    result = await response.json()
                    logger.info(f"工具调用结果: HTTP {response.status}, 响应: {result}")
                    return result
                    
        except Exception as e:
            logger.error(f"工具调用失败: {e}")
            raise

    async def close(self):
        """关闭连接"""
        # 这里可以添加清理逻辑，目前使用aiohttp.ClientSession不需要特别清理
        pass

async def main():
    """示例用法"""
    helper = MCPClientHelper(
        base_url="http://127.0.0.1:8000",
        max_retries=15,
        retry_delay=0.5
    )
    
    # 等待服务器就绪
    success = await helper.wait_and_connect()
    
    if success:
        # 获取服务器状态
        status = await helper.get_server_status()
        print(f"服务器状态: {status}")
        
        print("✅ 可以安全地连接MCP客户端了！")
        print(f"MCP端点: {helper.base_url}/mcp")
    else:
        print("❌ 无法连接到MCP服务器")

if __name__ == "__main__":
    asyncio.run(main()) 