import asyncio
import aiohttp
import json
import uuid
from loguru import logger

class MCPSSEClient:
    """基于SSE的MCP客户端"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = None
        self.message_url = None
        
    async def connect(self):
        """连接到MCP服务器"""
        try:
            self.session = aiohttp.ClientSession()
            
            # 首先获取SSE端点URL
            async with self.session.get(f"{self.base_url}/mcp") as response:
                if response.status == 200:
                    # 读取第一个事件来获取endpoint URL
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if line.startswith('event: endpoint'):
                            continue
                        elif line.startswith('data: '):
                            self.message_url = f"{self.base_url}{line[6:]}"
                            logger.info(f"获取到消息端点: {self.message_url}")
                            break
                    
                    if self.message_url:
                        return True
                    else:
                        logger.error("未能获取到消息端点URL")
                        return False
                else:
                    logger.error(f"连接MCP端点失败: HTTP {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"连接失败: {e}")
            return False
    
    async def send_message(self, method: str, params: dict = None):
        """发送MCP消息"""
        if not self.message_url:
            raise Exception("未连接到MCP服务器")
            
        message = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params or {}
        }
        
        try:
            async with self.session.post(
                self.message_url,
                json=message,
                headers={"Content-Type": "application/json"}
            ) as response:
                result = await response.json()
                logger.info(f"发送消息: {method}, 响应: {result}")
                return result
                
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            raise
    
    async def call_tool(self, tool_name: str, arguments: dict):
        """调用MCP工具"""
        return await self.send_message("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
    
    async def list_tools(self):
        """列出可用工具"""
        return await self.send_message("tools/list")
    
    async def close(self):
        """关闭连接"""
        if self.session:
            await self.session.close()

async def test_mcp_kline():
    """测试K线数据获取"""
    client = MCPSSEClient("http://127.0.0.1:8001")
    
    try:
        # 连接到MCP服务器
        logger.info("连接到MCP服务器...")
        connected = await client.connect()
        if not connected:
            logger.error("连接失败")
            return
            
        # 列出可用工具
        logger.info("获取可用工具列表...")
        tools = await client.list_tools()
        logger.info(f"可用工具: {tools}")
        
        # 调用历史K线工具
        logger.info("调用get_history_kline工具...")
        result = await client.call_tool("get_history_kline", {
            "code": "HK.01810",
            "ktype": "K_DAY",
            "autype": "qfq", 
            "max_count": 5
        })
        
        logger.info(f"K线数据结果: {result}")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_mcp_kline()) 