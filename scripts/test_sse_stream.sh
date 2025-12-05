#!/bin/bash
# Phase 3: SSE 流式输出测试脚本
#
# 用法:
#   chmod +x scripts/test_sse_stream.sh
#   ./scripts/test_sse_stream.sh
#
# 需要先启动服务器:
#   uvicorn src.interfaces.api.main:app --reload --port 8000

set -e

BASE_URL="http://localhost:8000"
API_URL="$BASE_URL/api/conversation"

echo "============================================"
echo "Phase 3: SSE Stream Test"
echo "============================================"
echo ""

# 测试 1: 健康检查
echo "1. Testing health endpoint..."
curl -s "$API_URL/health" | python -m json.tool
echo ""

# 测试 2: 基本流式请求
echo "2. Testing basic stream..."
echo "   Request: POST /api/conversation/stream"
echo "   Message: 你好，请帮我分析一下"
echo ""
echo "   Response:"
curl -N -X POST "$API_URL/stream" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"message": "你好，请帮我分析一下"}' 2>/dev/null
echo ""
echo ""

# 测试 3: 带工作流 ID 的流式请求
echo "3. Testing stream with workflow_id..."
echo "   Request: POST /api/conversation/stream"
echo "   Message: 分析工作流"
echo "   workflow_id: wf_test_001"
echo ""
echo "   Response (should include tool_call and tool_result):"
curl -N -X POST "$API_URL/stream" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"message": "分析工作流", "workflow_id": "wf_test_001"}' 2>/dev/null
echo ""
echo ""

# 测试 4: 检查响应头
echo "4. Testing response headers..."
echo "   Checking for: Cache-Control, Connection, X-Session-ID"
echo ""
curl -s -I -X POST "$API_URL/stream" \
  -H "Content-Type: application/json" \
  -d '{"message": "test"}' 2>/dev/null | grep -E "Cache-Control|Connection|X-Session-ID|content-type"
echo ""

echo "============================================"
echo "All tests completed!"
echo "============================================"
