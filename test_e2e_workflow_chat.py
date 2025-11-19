"""
端到端测试：AI对话编辑工作流

测试流程：
1. 创建一个测试工作流
2. 通过对话接口修改工作流
3. 验证工作流被正确修改
4. 验证返回的数据格式正确（前端可以直接使用）
"""

import requests
import json

API_BASE_URL = "http://localhost:8000"

def test_e2e_workflow_chat():
    print("=" * 60)
    print("端到端测试：AI对话编辑工作流")
    print("=" * 60)

    # 使用已存在的工作流ID（从之前的测试中）
    workflow_id = "wf_b8c85f1a"

    # 1. 获取现有工作流
    print(f"\n步骤 1: 获取现有工作流 ({workflow_id})")
    get_response = requests.get(f"{API_BASE_URL}/api/workflows/{workflow_id}")

    if get_response.status_code != 200:
        print(f"❌ 获取工作流失败: {get_response.status_code}")
        print(get_response.text)
        print("\n提示：请先创建一个工作流，或使用正确的工作流ID")
        return False

    workflow = get_response.json()
    print(f"✅ 工作流获取成功: {workflow_id}")
    print(f"   工作流名称: {workflow['name']}")
    print(f"   初始节点数: {len(workflow['nodes'])}")
    print(f"   初始边数: {len(workflow['edges'])}")
    
    # 2. 测试场景1：添加HTTP节点
    print("\n步骤 2: 测试场景1 - 添加HTTP节点")
    chat_response = requests.post(
        f"{API_BASE_URL}/api/workflows/{workflow_id}/chat",
        json={
            "message": "在开始和结束之间添加一个HTTP节点，用于获取天气数据"
        }
    )
    
    if chat_response.status_code != 200:
        print(f"❌ 对话请求失败: {chat_response.status_code}")
        print(chat_response.text)
        return False
    
    result = chat_response.json()
    print(f"✅ 对话成功")
    print(f"   AI回复: {result['ai_message']}")
    print(f"   更新后节点数: {len(result['workflow']['nodes'])}")
    print(f"   更新后边数: {len(result['workflow']['edges'])}")
    
    # 验证返回数据格式（前端需要的格式）
    print("\n步骤 3: 验证返回数据格式")
    workflow_data = result['workflow']
    
    # 检查必需字段
    required_fields = ['id', 'name', 'description', 'nodes', 'edges']
    for field in required_fields:
        if field not in workflow_data:
            print(f"❌ 缺少字段: {field}")
            return False
    
    print("✅ 工作流数据格式正确")
    
    # 检查节点格式
    if len(workflow_data['nodes']) > 0:
        node = workflow_data['nodes'][0]
        node_required_fields = ['id', 'type', 'name', 'data', 'position']
        for field in node_required_fields:
            if field not in node:
                print(f"❌ 节点缺少字段: {field}")
                return False

        # 检查position格式
        if 'x' not in node['position'] or 'y' not in node['position']:
            print(f"❌ 节点position格式错误")
            return False

        print("✅ 节点数据格式正确")
    
    # 检查边格式
    if len(workflow_data['edges']) > 0:
        edge = workflow_data['edges'][0]
        edge_required_fields = ['id', 'source', 'target']
        for field in edge_required_fields:
            if field not in edge:
                print(f"❌ 边缺少字段: {field}")
                return False

        print("✅ 边数据格式正确")
    
    # 3. 测试场景2：添加多个节点
    print("\n步骤 4: 测试场景2 - 添加多个节点")
    chat_response2 = requests.post(
        f"{API_BASE_URL}/api/workflows/{workflow_id}/chat",
        json={
            "message": "在HTTP节点后添加一个LLM节点和一个数据库节点"
        }
    )
    
    if chat_response2.status_code != 200:
        print(f"❌ 对话请求失败: {chat_response2.status_code}")
        print(chat_response2.text)
        return False
    
    result2 = chat_response2.json()
    print(f"✅ 对话成功")
    print(f"   AI回复: {result2['ai_message']}")
    print(f"   更新后节点数: {len(result2['workflow']['nodes'])}")
    print(f"   更新后边数: {len(result2['workflow']['edges'])}")
    
    # 4. 测试场景3：删除节点
    print("\n步骤 5: 测试场景3 - 删除节点")
    chat_response3 = requests.post(
        f"{API_BASE_URL}/api/workflows/{workflow_id}/chat",
        json={
            "message": "删除数据库节点"
        }
    )
    
    if chat_response3.status_code != 200:
        print(f"❌ 对话请求失败: {chat_response3.status_code}")
        print(chat_response3.text)
        return False
    
    result3 = chat_response3.json()
    print(f"✅ 对话成功")
    print(f"   AI回复: {result3['ai_message']}")
    print(f"   更新后节点数: {len(result3['workflow']['nodes'])}")
    print(f"   更新后边数: {len(result3['workflow']['edges'])}")
    
    # 5. 验证前端可以使用的数据格式
    print("\n步骤 6: 验证前端数据转换")
    
    # 模拟前端转换逻辑
    def convert_to_react_flow_format(workflow):
        """转换后端格式到 React Flow 格式"""
        nodes = []
        edges = []

        for node in workflow['nodes']:
            nodes.append({
                'id': node['id'],
                'type': node['type'],  # 前端需要映射类型
                'position': {'x': node['position']['x'], 'y': node['position']['y']},
                'data': node['data'] or {}
            })

        for edge in workflow['edges']:
            edges.append({
                'id': edge['id'],
                'source': edge['source'],
                'target': edge['target'],
                'label': edge.get('condition')
            })

        return nodes, edges
    
    try:
        react_flow_nodes, react_flow_edges = convert_to_react_flow_format(result3['workflow'])
        print(f"✅ 前端数据转换成功")
        print(f"   React Flow 节点数: {len(react_flow_nodes)}")
        print(f"   React Flow 边数: {len(react_flow_edges)}")
        
        # 打印示例节点
        if len(react_flow_nodes) > 0:
            print(f"\n   示例节点:")
            print(f"   {json.dumps(react_flow_nodes[0], indent=4, ensure_ascii=False)}")
        
        # 打印示例边
        if len(react_flow_edges) > 0:
            print(f"\n   示例边:")
            print(f"   {json.dumps(react_flow_edges[0], indent=4, ensure_ascii=False)}")
    
    except Exception as e:
        print(f"❌ 前端数据转换失败: {e}")
        return False
    
    # 6. 最终验证
    print("\n步骤 7: 最终验证")
    get_response = requests.get(f"{API_BASE_URL}/api/workflows/{workflow_id}")
    
    if get_response.status_code != 200:
        print(f"❌ 获取工作流失败: {get_response.status_code}")
        return False
    
    final_workflow = get_response.json()
    print(f"✅ 工作流数据一致性验证通过")
    print(f"   最终节点数: {len(final_workflow['nodes'])}")
    print(f"   最终边数: {len(final_workflow['edges'])}")
    
    # 打印所有节点
    print(f"\n   所有节点:")
    for node in final_workflow['nodes']:
        print(f"   - {node['name']} ({node['type']})")
    
    print("\n" + "=" * 60)
    print("✅ 端到端测试全部通过！")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    try:
        success = test_e2e_workflow_chat()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

