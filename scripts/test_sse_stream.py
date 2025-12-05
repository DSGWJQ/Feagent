#!/usr/bin/env python3
"""Phase 3: SSE 流式输出测试脚本 (Python 版本)

用法:
    python scripts/test_sse_stream.py

需要先启动服务器:
    uvicorn src.interfaces.api.main:app --reload --port 8000
"""

import argparse
import json
import sys
from typing import Any

try:
    import requests
except ImportError:
    print("请安装 requests: pip install requests")
    sys.exit(1)


def print_header(title: str):
    print("=" * 50)
    print(f" {title}")
    print("=" * 50)


def print_event(event: dict[str, Any], index: int):
    """格式化打印事件"""
    event_type = event.get("type", "unknown")
    content = event.get("content", "")
    sequence = event.get("sequence", 0)

    # 类型对应的颜色/符号
    type_symbols = {
        "thinking": "💭",
        "tool_call": "🔧",
        "tool_result": "📋",
        "final": "✅",
        "error": "❌",
    }

    symbol = type_symbols.get(event_type, "📌")
    print(f"  [{index}] {symbol} {event_type} (seq={sequence})")

    if content:
        # 截断长内容
        display_content = content[:100] + "..." if len(content) > 100 else content
        print(f"      Content: {display_content}")

    if event_type == "tool_call":
        metadata = event.get("metadata", {})
        tool_name = metadata.get("tool_name", "unknown")
        tool_id = metadata.get("tool_id", "")
        print(f"      Tool: {tool_name} (id={tool_id})")

    if event_type == "tool_result":
        metadata = event.get("metadata", {})
        success = metadata.get("success", False)
        result = metadata.get("result", {})
        print(f"      Success: {success}")
        print(f"      Result: {json.dumps(result, ensure_ascii=False)[:100]}")


def test_health(base_url: str) -> bool:
    """测试健康检查端点"""
    print("\n1. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   Status: {data.get('status')}")
            print(f"   Active Sessions: {data.get('active_sessions', 0)}")
            return True
        else:
            print(f"   Error: Status code {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"   Error: {e}")
        return False


def test_stream(base_url: str, message: str, workflow_id: str | None = None) -> bool:
    """测试流式端点"""
    print(f"\n{'2' if not workflow_id else '3'}. Testing stream...")
    print(f"   Message: {message}")
    if workflow_id:
        print(f"   Workflow ID: {workflow_id}")

    payload = {"message": message}
    if workflow_id:
        payload["workflow_id"] = workflow_id

    try:
        response = requests.post(
            f"{base_url}/stream",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            stream=True,
            timeout=30,
        )

        if response.status_code != 200:
            print(f"   Error: Status code {response.status_code}")
            return False

        # 显示响应头
        print("\n   Headers:")
        print(f"   - Content-Type: {response.headers.get('content-type')}")
        print(f"   - Cache-Control: {response.headers.get('Cache-Control')}")
        print(f"   - X-Session-ID: {response.headers.get('X-Session-ID')}")

        print("\n   Events:")

        events = []
        event_index = 1

        for line in response.iter_lines():
            if line:
                line_str = line.decode("utf-8")
                if line_str.startswith("data: "):
                    data_str = line_str[6:]
                    if data_str == "[DONE]":
                        print(f"  [{event_index}] 🏁 [DONE]")
                        break
                    try:
                        event = json.loads(data_str)
                        events.append(event)
                        print_event(event, event_index)
                        event_index += 1
                    except json.JSONDecodeError:
                        print(f"  [{event_index}] ⚠️ Invalid JSON: {data_str[:50]}")
                        event_index += 1

        # 验证事件
        print("\n   Summary:")
        print(f"   - Total events: {len(events)}")

        event_types = [e.get("type") for e in events]
        print(f"   - Event types: {', '.join(set(event_types))}")

        has_thinking = "thinking" in event_types
        has_final = "final" in event_types
        print(f"   - Has thinking: {has_thinking}")
        print(f"   - Has final: {has_final}")

        if workflow_id:
            has_tool_call = "tool_call" in event_types
            has_tool_result = "tool_result" in event_types
            print(f"   - Has tool_call: {has_tool_call}")
            print(f"   - Has tool_result: {has_tool_result}")

        return True

    except requests.RequestException as e:
        print(f"   Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test SSE streaming endpoint")
    parser.add_argument("--host", default="localhost", help="Server host")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}/api/conversation"

    print_header("Phase 3: SSE Stream Test")

    # 测试 1: 健康检查
    if not test_health(base_url):
        print("\n❌ Health check failed. Is the server running?")
        print(f"   Start with: uvicorn src.interfaces.api.main:app --port {args.port}")
        sys.exit(1)

    # 测试 2: 基本流式请求
    test_stream(base_url, "你好，请帮我分析一下")

    # 测试 3: 带工作流 ID 的流式请求
    test_stream(base_url, "分析工作流", workflow_id="wf_test_001")

    print_header("All tests completed!")


if __name__ == "__main__":
    main()
