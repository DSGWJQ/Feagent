"""测试工作流集成

测试工作流编辑器和执行功能的端到端集成
"""

import json
import time

import requests

# 测试配置
API_BASE_URL = "http://127.0.0.1:8000/api"
WORKFLOW_ID = "wf_b8c85f1a"


def test_get_workflow():
    """测试获取工作流"""
    print("\n📝 测试 1: 获取工作流详情")
    print(f"   GET {API_BASE_URL}/workflows/{WORKFLOW_ID}")

    response = requests.get(f"{API_BASE_URL}/workflows/{WORKFLOW_ID}")

    print(f"   状态码: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print("   ✅ 成功获取工作流")
        print(f"      名称: {data['name']}")
        print(f"      节点数: {len(data['nodes'])}")
        print(f"      边数: {len(data['edges'])}")
        print("      节点列表:")
        for node in data["nodes"]:
            print(f"         - {node['id']}: {node['type']} ({node['name']})")
        return data
    else:
        print(f"   ❌ 失败: {response.text}")
        return None


def test_update_workflow():
    """测试更新工作流（拖拽调整）"""
    print("\n📝 测试 2: 更新工作流（拖拽调整）")
    print(f"   PATCH {API_BASE_URL}/workflows/{WORKFLOW_ID}")

    # 修改节点位置
    request_data = {
        "nodes": [
            {
                "id": "node_38712f54",
                "type": "start",
                "name": "开始",
                "data": {},
                "position": {"x": 100, "y": 300},  # 修改位置
            },
            {
                "id": "node_f2f3fe66",
                "type": "http",
                "name": "HTTP 请求",
                "data": {"url": "https://api.example.com", "method": "GET"},
                "position": {"x": 400, "y": 300},  # 修改位置
            },
            {
                "id": "node_884237f0",
                "type": "end",
                "name": "结束",
                "data": {},
                "position": {"x": 700, "y": 300},  # 修改位置
            },
        ],
        "edges": [
            {"id": "edge_d4cc9fd0", "source": "node_38712f54", "target": "node_f2f3fe66"},
            {"id": "edge_61293715", "source": "node_f2f3fe66", "target": "node_884237f0"},
        ],
    }

    response = requests.patch(
        f"{API_BASE_URL}/workflows/{WORKFLOW_ID}",
        json=request_data,
        headers={"Content-Type": "application/json"},
    )

    print(f"   状态码: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print("   ✅ 成功更新工作流")
        print("      更新后节点位置:")
        for node in data["nodes"]:
            print(f"         - {node['id']}: ({node['position']['x']}, {node['position']['y']})")
        return data
    else:
        print(f"   ❌ 失败: {response.text}")
        return None


def test_execute_workflow():
    """测试执行工作流（非流式）"""
    print("\n📝 测试 3: 执行工作流（非流式）")
    print(f"   POST {API_BASE_URL}/workflows/{WORKFLOW_ID}/execute")

    request_data = {"initial_input": {"message": "test"}}

    response = requests.post(
        f"{API_BASE_URL}/workflows/{WORKFLOW_ID}/execute",
        json=request_data,
        headers={"Content-Type": "application/json"},
    )

    print(f"   状态码: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print("   ✅ 成功执行工作流")
        print(f"      执行日志条目数: {len(data['execution_log'])}")
        print("      执行日志:")
        for entry in data["execution_log"]:
            print(f"         - {entry['node_type']} ({entry['node_id']}): {entry['output']}")
        print(f"      最终结果: {data['final_result']}")
        return data
    else:
        print(f"   ❌ 失败: {response.text}")
        return None


def test_execute_workflow_streaming():
    """测试执行工作流（SSE 流式）"""
    print("\n📝 测试 4: 执行工作流（SSE 流式）")
    print(f"   POST {API_BASE_URL}/workflows/{WORKFLOW_ID}/execute/stream")

    request_data = {"initial_input": {"message": "test"}}

    response = requests.post(
        f"{API_BASE_URL}/workflows/{WORKFLOW_ID}/execute/stream",
        json=request_data,
        headers={"Content-Type": "application/json"},
        stream=True,
    )

    print(f"   状态码: {response.status_code}")

    if response.status_code == 200:
        print("   ✅ 开始接收 SSE 事件流:")
        event_count = 0
        for line in response.iter_lines():
            if line:
                line_str = line.decode("utf-8")
                if line_str.startswith("data: "):
                    event_count += 1
                    event_data = json.loads(line_str[6:])  # 去掉 "data: " 前缀
                    event_type = event_data.get("type")
                    print(f"      [{event_count}] {event_type}: {event_data}")

                    # 如果收到完成或错误事件，停止
                    if event_type in ["workflow_complete", "workflow_error"]:
                        break

        print(f"   ✅ 接收到 {event_count} 个事件")
        return True
    else:
        print(f"   ❌ 失败: {response.text}")
        return False


def main():
    """运行所有测试"""
    print("=" * 80)
    print("🚀 开始工作流集成测试")
    print("=" * 80)

    try:
        # 测试 1: 获取工作流
        workflow = test_get_workflow()
        if not workflow:
            print("\n❌ 测试失败：无法获取工作流")
            return

        time.sleep(1)

        # 测试 2: 更新工作流
        updated_workflow = test_update_workflow()
        if not updated_workflow:
            print("\n❌ 测试失败：无法更新工作流")
            return

        time.sleep(1)

        # 测试 3: 执行工作流（非流式）
        execution_result = test_execute_workflow()
        if not execution_result:
            print("\n❌ 测试失败：无法执行工作流")
            return

        time.sleep(1)

        # 测试 4: 执行工作流（SSE 流式）
        streaming_result = test_execute_workflow_streaming()
        if not streaming_result:
            print("\n❌ 测试失败：无法执行流式工作流")
            return

        print("\n" + "=" * 80)
        print("🎉 所有测试通过！")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
