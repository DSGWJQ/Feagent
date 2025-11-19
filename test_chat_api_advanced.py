"""测试工作流对话接口 - 高级场景"""

import requests
import json

WORKFLOW_ID = "wf_b8c85f1a"
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
            config_str = ""
            if node["data"]:
                config_str = f" - 配置: {json.dumps(node['data'], ensure_ascii=False)}"
            print(f"  - {node['name']} ({node['type']}){config_str}")
        return True
    else:
        print(f"❌ 错误: {response.text}")
        return False


# 测试场景 1: 添加多个节点
test_chat(
    "添加一个HTTP节点用于获取用户数据，然后添加一个LLM节点用于分析数据",
    "测试 1: 添加多个节点"
)

# 测试场景 2: 修改节点配置
test_chat(
    "把HTTP节点的URL改成 https://api.github.com/users/octocat",
    "测试 2: 修改节点配置"
)

# 测试场景 3: 添加条件分支
test_chat(
    "在LLM节点后面添加两个分支：一个数据库节点用于保存成功结果，一个HTTP节点用于发送失败通知",
    "测试 3: 添加条件分支"
)

# 测试场景 4: 重新组织工作流
test_chat(
    "删除所有节点，重新创建一个简单的工作流：开始 -> HTTP请求 -> 结束",
    "测试 4: 重新组织工作流"
)

# 测试场景 5: 添加Python节点
test_chat(
    "在HTTP请求后添加一个Python节点，用于处理返回的JSON数据",
    "测试 5: 添加Python节点"
)

# 最终状态
print_separator("最终工作流状态")
response = requests.get(f"{BASE_URL}/{WORKFLOW_ID}")
if response.status_code == 200:
    data = response.json()
    print(f"工作流名称: {data['name']}")
    print(f"节点总数: {len(data['nodes'])}")
    print(f"边总数: {len(data['edges'])}")
    print(f"更新时间: {data['updated_at']}")
    print("\n节点详情:")
    for i, node in enumerate(data["nodes"], 1):
        pos = node["position"]
        print(f"{i}. [{node['type']}] {node['name']} @ ({pos['x']}, {pos['y']})")
    print("\n边详情:")
    for i, edge in enumerate(data["edges"], 1):
        print(f"{i}. {edge['source']} -> {edge['target']}")
else:
    print(f"❌ 错误: {response.text}")

print("\n" + "=" * 60)
print("✅ 所有测试完成！")
print("=" * 60)

