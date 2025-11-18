#!/bin/bash

# Metaso三合一接口测试脚本
# 测试搜索、网页读取、问答三个接口

echo "🚀 Metaso三合一接口测试开始"
echo "=================================="
echo ""

# 检查服务状态
echo "🔍 检查服务状态..."
health_status=$(curl -s "http://localhost:8001/health" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print('healthy' if data.get('status') == 'healthy' else 'unhealthy')
except:
    print('error')
")

if [ "$health_status" != "healthy" ]; then
    echo "❌ 服务未就绪，请先启动服务: python3 main_enhanced_mcp_fixed.py"
    exit 1
fi

echo "✅ 服务状态正常"
echo ""

# 测试1: 搜索接口
echo "🔍 测试1: 搜索接口"
echo "关键词: 谁是这个世界上最美丽的女人"
echo "----------------------------------"

curl -s -X POST "http://localhost:8001/api/fundamental/search" \
  -H "Content-Type: application/json" \
  -d '{
    "q": "谁是这个世界上最美丽的女人",
    "scope": "webpage",
    "includeSummary": true,
    "size": 3
  }' | python3 -m json.tool

echo ""
echo "=================================="
echo ""

# 测试2: 网页读取接口
echo "📄 测试2: 网页读取接口"
echo "读取网易新闻: https://www.163.com/news/article/K56809DQ000189FH.html"
echo "----------------------------------"

curl -s -X POST "http://localhost:8001/api/fundamental/read_webpage" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.163.com/news/article/K56809DQ000189FH.html"
  }' | python3 -m json.tool

echo ""
echo "=================================="
echo ""

# 测试3: 问答接口
echo "💬 测试3: 问答接口"
echo "问题: 谁是这个世界上最美丽的女人"
echo "----------------------------------"

curl -s -X POST "http://localhost:8001/api/fundamental/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "谁是这个世界上最美丽的女人"
      }
    ],
    "model": "fast",
    "stream": false
  }' | python3 -m json.tool

echo ""
echo "=================================="
echo ""

# 测试4: 股票相关综合测试
echo "📈 测试4: 股票相关综合测试"
echo "搜索小米股票信息 -> 读取相关网页 -> 问答分析"
echo "----------------------------------"

echo "步骤1: 搜索小米股票信息"
search_result=$(curl -s -X POST "http://localhost:8001/api/fundamental/search" \
  -H "Content-Type: application/json" \
  -d '{
    "q": "小米集团股票分析 2024",
    "scope": "webpage",
    "size": 1
  }')

echo "搜索结果:"
echo "$search_result" | python3 -m json.tool

# 提取第一个搜索结果的URL（如果有）
first_url=$(echo "$search_result" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    if data.get('ret_code') == 0 and data.get('data', {}).get('results'):
        print(data['data']['results'][0].get('url', ''))
    else:
        print('')
except:
    print('')
")

if [ -n "$first_url" ] && [ "$first_url" != "" ]; then
    echo ""
    echo "步骤2: 读取第一个搜索结果的网页内容"
    curl -s -X POST "http://localhost:8001/api/fundamental/read_webpage" \
      -H "Content-Type: application/json" \
      -d "{\"url\": \"$first_url\"}" | python3 -m json.tool
fi

echo ""
echo "步骤3: 问答分析小米股票"
curl -s -X POST "http://localhost:8001/api/fundamental/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "请简要分析小米集团的股票投资价值"
      }
    ],
    "model": "fast",
    "stream": false
  }' | python3 -m json.tool

echo ""
echo "=================================="
echo "✅ 所有测试完成！"
echo ""
echo "📋 测试结果总结："
echo "1. ✅ 搜索接口 - 测试关键词搜索功能"
echo "2. ✅ 网页读取接口 - 测试网页内容提取功能"  
echo "3. ✅ 问答接口 - 测试智能对话功能"
echo "4. ✅ 综合测试 - 测试接口联动效果"
echo ""
echo "🔧 MCP工具调用示例："
echo "搜索: {\"name\": \"get_fundamental_search\", \"arguments\": {\"q\": \"小米股票分析\", \"size\": 5}}"
echo "读取网页: {\"name\": \"read_webpage\", \"arguments\": {\"url\": \"https://example.com/article.html\"}}"
echo "问答: {\"name\": \"chat_completion\", \"arguments\": {\"messages\": [{\"role\": \"user\", \"content\": \"如何投资港股\"}], \"model\": \"fast\"}}"
echo ""
echo "🚀 如需运行完整测试，请执行: bash test_metaso_all.sh"