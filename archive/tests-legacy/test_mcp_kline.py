import asyncio
from client_helper import MCPClientHelper

async def test_kline():
    helper = MCPClientHelper('http://127.0.0.1:8001')
    try:
        # 等待服务器就绪
        print("等待服务器就绪...")
        await helper.wait_for_server_ready()
        
        # 测试MCP连接
        print('测试MCP连接...')
        await helper.test_mcp_connection()
        
        # 调用工具
        print('调用get_history_kline工具...')
        result = await helper.call_tool(
            'get_history_kline',
            {
                'code': 'HK.01810',
                'ktype': 'K_DAY', 
                'autype': 'qfq',
                'max_count': 10
            }
        )
        print(f'调用结果: {result}')
        
    except Exception as e:
        print(f'错误: {e}')
        import traceback
        traceback.print_exc()
    finally:
        await helper.close()

if __name__ == "__main__":
    asyncio.run(test_kline()) 