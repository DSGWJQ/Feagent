"""测试边验证修复"""

import requests

WORKFLOW_ID = "wf_917c7d75"  # 使用另一个工作流测试
BASE_URL = "http://localhost:8000/api/workflows"


def print_separator(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def test_chat(message, description):
    """测试对话接口"""
    print_separator(description)
    print(f"用户消息: {message}")

    response = requests.post(
        f"{BASE_URL}/{WORKFLOW_ID}/chat",
        json={"message": message},
    )

    print(f"状态码: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"✅ AI回复: {data.get('ai_message', '')}")
        print(f"节点数量: {len(data['workflow']['nodes'])}")
        print(f"边数量: {len(data['workflow']['edges'])}")
        print("节点列表:")
        for node in data["workflow"]["nodes"]:
            print(f"  - {node['name']} ({node['type']})")
        print("边列表:")
        for edge in data["workflow"]["edges"]:
            print(f"  - {edge['source']} -> {edge['target']}")
        return True
    else:
        print(f"❌ 错误: {response.text}")
        return False


# 测试场景 1: 重置工作流
test_chat("删除所有节点，创建一个新的工作流：开始 -> 结束", "测试 1: 重置工作流")

# 测试场景 2: 添加中间节点
test_chat("在开始和结束之间添加一个HTTP节点", "测试 2: 添加中间节点")

# 测试场景 3: 添加Python节点（之前失败的场景）
test_chat("在HTTP节点后添加一个Python节点，用于处理数据", "测试 3: 添加Python节点（修复后）")

# 测试场景 4: 添加多个节点
test_chat("在Python节点后添加一个LLM节点和一个数据库节点", "测试 4: 添加多个节点")

# 测试场景 5: 复杂的工作流重组
test_chat(
    "在开始节点后添加两个并行分支：一个HTTP节点和一个数据库节点，然后都连接到结束节点",
    "测试 5: 添加并行分支",
)

# 最终状态
print_separator("最终工作流状态")
response = requests.get(f"{BASE_URL}/{WORKFLOW_ID}")
if response.status_code == 200:
    data = response.json()
    print(f"工作流名称: {data['name']}")
    print(f"节点总数: {len(data['nodes'])}")
    print(f"边总数: {len(data['edges'])}")
    print("\n节点详情:")
    for i, node in enumerate(data["nodes"], 1):
        pos = node["position"]
        print(f"{i}. [{node['type']}] {node['name']} @ ({pos['x']}, {pos['y']})")
    print("\n边详情:")
    for i, edge in enumerate(data["edges"], 1):
        print(f"{i}. {edge['source']} -> {edge['target']}")

    # 验证工作流的完整性
    print("\n工作流完整性检查:")
    node_ids = {node["id"] for node in data["nodes"]}
    valid_edges = 0
    invalid_edges = 0
    for edge in data["edges"]:
        if edge["source"] in node_ids and edge["target"] in node_ids:
            valid_edges += 1
        else:
            invalid_edges += 1
            print(f"  ⚠️ 无效边: {edge['source']} -> {edge['target']}")

    print(f"  ✅ 有效边: {valid_edges}")
    print(f"  ❌ 无效边: {invalid_edges}")

    # 检查自连接
    self_loops = [edge for edge in data["edges"] if edge["source"] == edge["target"]]
    if self_loops:
        print(f"  ⚠️ 发现 {len(self_loops)} 个自连接边")
    else:
        print("  ✅ 没有自连接边")
else:
    print(f"❌ 错误: {response.text}")

print("\n" + "=" * 60)
print("✅ 边验证修复测试完成！")
print("=" * 60)
