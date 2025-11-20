import json

import requests

url = "http://localhost:8000/api/workflows/1"

# 测试数据
data = {
    "nodes": [
        {
            "id": "start-1",
            "type": "start",
            "name": "开始",
            "position": {"x": 100, "y": 100},
            "data": {},
        },
        {
            "id": "http-1",
            "type": "httpRequest",
            "name": "获取数据",
            "position": {"x": 300, "y": 100},
            "data": {"url": "https://jsonplaceholder.typicode.com/posts/1", "method": "GET"},
        },
        {
            "id": "end-1",
            "type": "end",
            "name": "结束",
            "position": {"x": 500, "y": 100},
            "data": {},
        },
    ],
    "edges": [
        {
            "id": "e1",
            "source": "start-1",
            "target": "http-1",
            "sourceHandle": None,
            "label": None,
            "condition": None,
        },
        {
            "id": "e2",
            "source": "http-1",
            "target": "end-1",
            "sourceHandle": None,
            "label": None,
            "condition": None,
        },
    ],
}

print("发送 PATCH 请求...")
print(f"URL: {url}")
print(f"Data: {json.dumps(data, indent=2, ensure_ascii=False)}")

response = requests.patch(url, json=data)

print(f"\n状态码: {response.status_code}")
print(f"响应: {response.text}")

if response.status_code == 200:
    print("\n✅ 成功！")
else:
    print(f"\n❌ 失败: {response.status_code}")
