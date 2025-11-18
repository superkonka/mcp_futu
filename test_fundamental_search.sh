#!/bin/bash

# 富途MCP增强服务 - 基本面搜索接口测试脚本
# 测试新增加的基本面搜索功能

echo "🚀 开始测试基本面搜索接口..."
echo "=================================="

# 测试1: 基础基本面搜索
echo "📊 测试1: 基础基本面搜索"
echo "关键词: 影响小米股价的相关信息"
curl -X POST "http://localhost:8001/api/fundamental/search" \
  -H "Content-Type: application/json" \
  -d '{
    "q": "影响小米股价的相关信息",
    "scope": "webpage",
    "includeSummary": true,
    "size": 5,
    "includeRawContent": false,
    "conciseSnippet": true
  }' | python3 -m json.tool

echo ""
echo "=================================="

# 测试2: 股票基本面搜索（简化接口）
echo "📈 测试2: 股票基本面搜索（简化接口）"
echo "股票代码: HK.01810 (小米集团)"
curl -X POST "http://localhost:8001/api/fundamental/stock_search" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_code": "HK.01810",
    "stock_name": "小米集团"
  }' | python3 -m json.tool

echo ""
echo "=================================="

# 测试3: 美股搜索
echo "💹 测试3: 美股基本面搜索"
echo "股票代码: US.AAPL (苹果公司)"
curl -X POST "http://localhost:8001/api/fundamental/stock_search" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_code": "US.AAPL",
    "stock_name": "苹果公司"
  }' | python3 -m json.tool

echo ""
echo "=================================="

# 测试4: 港股搜索
echo "🇭🇰 测试4: 港股基本面搜索"
echo "股票代码: HK.00700 (腾讯控股)"
curl -X POST "http://localhost:8001/api/fundamental/stock_search" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_code": "HK.00700",
    "stock_name": "腾讯控股"
  }' | python3 -m json.tool

echo ""
echo "=================================="

# 测试5: 自定义搜索（新闻范围）
echo "📰 测试5: 新闻搜索"
echo "关键词: 新能源汽车行业分析"
curl -X POST "http://localhost:8001/api/fundamental/search" \
  -H "Content-Type: application/json" \
  -d '{
    "q": "新能源汽车行业分析 2024",
    "scope": "news",
    "includeSummary": true,
    "size": 8
  }' | python3 -m json.tool

echo echo ""
echo "=================================="

# 测试6: 网页读取
echo "📄 测试6: 网页内容读取"
echo "读取网易新闻网页: https://www.163.com/news/article/K56809DQ000189FH.html"
curl -X POST "http://localhost:8001/api/fundamental/read_webpage" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.163.com/news/article/K56809DQ000189FH.html"
  }' | python3 -m json.tool

echo ""
echo "=================================="

# 测试7: 智能问答
echo "💬 测试7: 智能问答"
echo "问题: 谁是这个世界上最美丽的女人"
curl -X POST "http://localhost:8001/api/fundamental/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "谁是这个世界上最美丽的女人"
      }
    ],
    "model": "fast",
    "stream": true
  }' | python3 -m json.tool

echo ""
echo "=================================="

# 测试8: 股票相关问答
echo "💹 测试8: 股票相关问答"
echo "问题: 请分析小米集团的股票投资价值"
curl -X POST "http://localhost:8001/api/fundamental/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user", 
        "content": "请分析小米集团的股票投资价值，从基本面和技术面角度"
      }
    ],
    "model": "fast",
    "stream": false
  }' | python3 -m json.tool

echo ""
echo "=================================="
echo "✅ 所有测试完成！"
echo ""
echo "📋 使用说明："
echo "1. 确保服务已启动: python3 main_enhanced_mcp_fixed.py"
echo "2. 基础搜索接口: POST /api/fundamental/search"
echo "3. 股票搜索接口: POST /api/fundamental/stock_search"
echo "4. 网页读取接口: POST /api/fundamental/read_webpage"
echo "5. 智能问答接口: POST /api/fundamental/chat"
echo ""
echo "🔧 MCP客户端调用示例："
echo "搜索: {\"name\": \"get_fundamental_search\", \"arguments\": {\"q\": \"影响小米股价的相关信息\", \"size\": 10}}"
echo "读取网页: {\"name\": \"read_webpage\", \"arguments\": {\"url\": \"https://www.163.com/news/article/K56809DQ000189FH.html\"}}"
echo "问答: {\"name\": \"chat_completion\", \"arguments\": {\"messages\": [{\"role\": \"user\", \"content\": \"谁是这个世界上最美丽的女人\"}], \"model\": \"fast\"}}"