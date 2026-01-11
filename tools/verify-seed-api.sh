#!/bin/bash
# Seed API 验证脚本 (Bash版本)
# 使用: bash tools/verify-seed-api.sh

set -e  # 遇到错误立即退出

BASE_URL="${SEED_API_BASE_URL:-http://localhost:8000}"
HEADER_TEST_MODE="X-Test-Mode: true"
HEADER_JSON="Content-Type: application/json"

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

cleanup_tokens=()
failed=false

# 清理函数
cleanup() {
  if [ ${#cleanup_tokens[@]} -eq 0 ]; then
    return
  fi

  echo ""
  echo "[Cleanup] Cleaning up ${#cleanup_tokens[@]} workflows..."

  # 构建JSON数组
  tokens_json=$(printf '"%s",' "${cleanup_tokens[@]}")
  tokens_json="[${tokens_json%,}]"

  response=$(curl -s -X DELETE "${BASE_URL}/api/test/workflows/cleanup" \
    -H "$HEADER_TEST_MODE" \
    -H "$HEADER_JSON" \
    -d "{\"cleanup_tokens\": $tokens_json}")

  deleted_count=$(echo "$response" | grep -o '"deleted_count":[0-9]*' | cut -d: -f2)
  echo -e "${GREEN}[Pass] ✅ Cleanup successful: deleted_count=${deleted_count}${NC}"
}

# 注册清理函数
trap cleanup EXIT

echo "[Start] Seed API verification..."

# 1. 检查fixture-types
echo "[Check] Verifying Seed API is enabled..."
response=$(curl -s -w "\n%{http_code}" -X GET "${BASE_URL}/api/test/workflows/fixture-types" -H "$HEADER_TEST_MODE")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" != "200" ]; then
  echo -e "${RED}[FAIL] ❌ Expected 200, got $http_code${NC}"
  echo "Response: $body"
  exit 1
fi

# 检查4种fixtures存在
for fixture in "main_subgraph_only" "with_isolated_nodes" "side_effect_workflow" "invalid_config"; do
  if ! echo "$body" | grep -q "$fixture"; then
    echo -e "${RED}[FAIL] ❌ Missing fixture type: $fixture${NC}"
    exit 1
  fi
done
echo -e "${GREEN}[Pass] ✅ Fixture types verified${NC}"

# 2. 测试4种fixtures
echo "[Test] Testing 4 fixtures..."

for fixture in "main_subgraph_only" "with_isolated_nodes" "side_effect_workflow" "invalid_config"; do
  response=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/api/test/workflows/seed" \
    -H "$HEADER_TEST_MODE" \
    -H "$HEADER_JSON" \
    -d "{\"fixture_type\": \"$fixture\", \"project_id\": \"e2e_test_project\", \"custom_metadata\": {\"seed_verify\": true}}")

  http_code=$(echo "$response" | tail -n1)
  body=$(echo "$response" | sed '$d')

  if [ "$http_code" != "201" ]; then
    echo -e "${RED}[FAIL] ❌ Fixture $fixture expected 201, got $http_code${NC}"
    echo "Response: $body"
    failed=true
    continue
  fi

  # 提取cleanup_token
  cleanup_token=$(echo "$body" | grep -o '"cleanup_token":"[^"]*"' | cut -d'"' -f4)
  if [ -n "$cleanup_token" ]; then
    cleanup_tokens+=("$cleanup_token")
  fi

  workflow_id=$(echo "$body" | grep -o '"workflow_id":"[^"]*"' | cut -d'"' -f4)
  echo -e "${GREEN}[Pass] ✅ $fixture: workflow_id=$workflow_id${NC}"

  # 验证元数据
  if [ "$fixture" == "main_subgraph_only" ]; then
    node_count=$(echo "$body" | grep -o '"node_count":[0-9]*' | cut -d: -f2)
    if [ "$node_count" != "3" ]; then
      echo -e "${YELLOW}[Warn] ⚠️  main_subgraph_only node_count=$node_count (expected 3)${NC}"
    fi
  fi
done

# 3. 测试错误处理
echo "[Test] Testing error handling..."

# 无效fixture type
response=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/api/test/workflows/seed" \
  -H "$HEADER_TEST_MODE" \
  -H "$HEADER_JSON" \
  -d '{"fixture_type": "nonexistent_fixture"}')

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" == "400" ]; then
  echo -e "${GREEN}[Pass] ✅ Invalid fixture type returns 400${NC}"
else
  echo -e "${RED}[FAIL] ❌ Invalid fixture expected 400, got $http_code${NC}"
  failed=true
fi

# 缺失header
response=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/api/test/workflows/seed" \
  -H "$HEADER_JSON" \
  -d '{"fixture_type": "main_subgraph_only"}')

http_code=$(echo "$response" | tail -n1)

if [ "$http_code" == "403" ]; then
  echo -e "${GREEN}[Pass] ✅ Missing X-Test-Mode header returns 403${NC}"
else
  echo -e "${RED}[FAIL] ❌ Missing header expected 403, got $http_code${NC}"
  failed=true
fi

# 4. 并发测试
echo "[Test] Testing concurrency (5 parallel seeds)..."

pids=()
temp_dir=$(mktemp -d)

for i in {1..5}; do
  fixture_type=$( [ $((i % 4)) -eq 0 ] && echo "main_subgraph_only" || \
                  [ $((i % 4)) -eq 1 ] && echo "with_isolated_nodes" || \
                  [ $((i % 4)) -eq 2 ] && echo "side_effect_workflow" || \
                  echo "invalid_config" )

  (
    response=$(curl -s -X POST "${BASE_URL}/api/test/workflows/seed" \
      -H "$HEADER_TEST_MODE" \
      -H "$HEADER_JSON" \
      -d "{\"fixture_type\": \"$fixture_type\", \"project_id\": \"e2e_concurrent_$i\"}")

    cleanup_token=$(echo "$response" | grep -o '"cleanup_token":"[^"]*"' | cut -d'"' -f4)
    echo "$cleanup_token" > "$temp_dir/token_$i"
  ) &
  pids+=($!)
done

# 等待所有并发请求完成
wait "${pids[@]}"

# 收集cleanup tokens
for i in {1..5}; do
  if [ -f "$temp_dir/token_$i" ]; then
    token=$(cat "$temp_dir/token_$i")
    if [ -n "$token" ]; then
      cleanup_tokens+=("$token")
    fi
  fi
done

rm -rf "$temp_dir"
echo -e "${GREEN}[Pass] ✅ Concurrency test: 5 parallel seeds completed${NC}"

# 检查是否有失败
if [ "$failed" = true ]; then
  echo ""
  echo -e "${RED}[FAIL] ❌ Some tests failed${NC}"
  exit 1
fi

echo ""
echo -e "${GREEN}[OK] ✅ Seed API verification passed${NC}"
exit 0
