"""测试工作流对话接口"""

import json

import requests

# 测试 1: 删除HTTP节点
print("=" * 60)
print("测试 1: 删除HTTP节点")
print("=" * 60)

response = requests.post(
    "http://localhost:8000/api/workflows/wf_b8c85f1a/chat",
    json={"message": "删除所有HTTP节点"},
)

print(f"状态码: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print(f"AI消息: {data.get('ai_message', '')}")
    print(f"节点数量: {len(data['workflow']['nodes'])}")
    print("节点列表:")
    for node in data["workflow"]["nodes"]:
        print(f"  - {node['name']} ({node['type']})")
    print(f"边数量: {len(data['workflow']['edges'])}")
else:
    print(f"错误: {response.text}")

print()

# 测试 2: 添加数据库节点
print("=" * 60)
print("测试 2: 添加数据库节点")
print("=" * 60)

response = requests.post(
    "http://localhost:8000/api/workflows/wf_b8c85f1a/chat",
    json={"message": "在开始和结束之间添加一个数据库查询节点"},
)

print(f"状态码: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print(f"AI消息: {data.get('ai_message', '')}")
    print(f"节点数量: {len(data['workflow']['nodes'])}")
    print("节点列表:")
    for node in data["workflow"]["nodes"]:
        print(f"  - {node['name']} ({node['type']})")
        if node["type"] == "database":
            print(f"    配置: {json.dumps(node['data'], ensure_ascii=False, indent=6)}")
else:
    print(f"错误: {response.text}")

print()

# 测试 3: 查看最终状态
print("=" * 60)
print("测试 3: 查看最终工作流状态")
print("=" * 60)

response = requests.get("http://localhost:8000/api/workflows/wf_b8c85f1a")

if response.status_code == 200:
    data = response.json()
    print(f"工作流名称: {data['name']}")
    print(f"工作流描述: {data['description']}")
    print(f"节点数量: {len(data['nodes'])}")
    print(f"边数量: {len(data['edges'])}")
    print(f"更新时间: {data['updated_at']}")
    print("\n完整节点列表:")
    for i, node in enumerate(data["nodes"], 1):
        print(
            f"{i}. {node['name']} ({node['type']}) - 位置: ({node['position']['x']}, {node['position']['y']})"
        )
else:
    print(f"错误: {response.text}")
