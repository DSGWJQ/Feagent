#!/usr/bin/env python
"""测试 API 端点"""

import json

import requests

# 测试创建 Agent
url = "http://localhost:8000/api/agents"
data = {
    "start": "我有一个包含销售数据的 CSV 文件",
    "goal": "分析销售数据，找出销售趋势和热门产品，生成可视化报告",
    "name": "销售分析 Agent",
}

print("=" * 80)
print("测试：创建 Agent（自动生成工作流）")
print("=" * 80)
print(f"\n请求 URL: {url}")
print(f"请求数据:\n{json.dumps(data, ensure_ascii=False, indent=2)}")

response = requests.post(url, json=data)

print(f"\n响应状态码: {response.status_code}")
print(f"\n响应数据:\n{json.dumps(response.json(), ensure_ascii=False, indent=2)}")

if response.status_code == 201:
    result = response.json()
    print("\n" + "=" * 80)
    print("✅ 测试成功！")
    print("=" * 80)
    print(f"\nAgent ID: {result['id']}")
    print(f"Agent 名称: {result['name']}")
    print(f"Agent 状态: {result['status']}")
    print("\n生成的工作流（Tasks）：")
    print("-" * 80)
    for i, task in enumerate(result["tasks"], 1):
        print(f"\n{i}. {task['name']}")
        print(f"   ID: {task['id']}")
        print(f"   描述: {task['description']}")
        print(f"   状态: {task['status']}")
else:
    print("\n" + "=" * 80)
    print("❌ 测试失败！")
    print("=" * 80)
