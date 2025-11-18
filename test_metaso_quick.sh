#!/bin/bash

# Metaso三接口一键测试
# 快速验证搜索、读取、问答功能

echo "🚀 Metaso三接口一键测试"
echo "========================"

# 1. 搜索测试
echo "🔍 1. 搜索测试"
curl -s -X POST "http://localhost:8001/api/fundamental/search" \
  -H "Content-Type: application/json" \
  -d '{"q": "谁是这个世界上最美丽的女人", "size": 2}' | jq '.ret_msg' || echo "搜索测试完成"

# 2. 网页读取测试  
echo "📄 2. 网页读取测试"
curl -s -X POST "http://localhost:8001/api/fundamental/read_webpage" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.163.com/news/article/K56809DQ000189FH.html"}' | jq '.ret_msg' || echo "网页读取测试完成"

# 3. 问答测试
echo "💬 3. 问答测试"
curl -s -X POST "http://localhost:8001/api/fundamental/chat" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "谁是这个世界上最美丽的女人"}], "stream": false}' | jq '.ret_msg' || echo "问答测试完成"

echo ""
echo "✅ 三接口测试完成！"
echo ""
echo "📝 详细测试请运行: bash test_metaso_all.sh"
echo "🧪 MCP测试请运行: bash test_fundamental_search.sh"