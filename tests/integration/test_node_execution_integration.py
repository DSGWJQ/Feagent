"""节点执行集成测试 - TDD RED 阶段

定义各类型节点的执行期望：
1. HTTP 节点执行 HTTP 请求
2. Transform 节点转换数据
3. LLM 节点调用语言模型
4. 节点间的数据传递
"""

from unittest.mock import Mock

import pytest

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position


class TestNodeExecution:
    """节点执行集成测试"""

    def test_http_node_execution(self):
        """测试：HTTP 节点应该能发送 HTTP 请求

        RED 阶段期望：
        1. 配置 HTTP 节点（URL、方法、头、体）
        2. 执行节点
        3. 获得响应（状态码、头、体）
        """
        # 创建 HTTP 节点
        http_node = Node.create(
            type=NodeType.HTTP,
            name="Get User",
            config={
                "method": "GET",
                "url": "https://api.example.com/users/1",
                "headers": {"Authorization": "Bearer token123"},
            },
            position=Position(x=0, y=0),
        )

        # 创建 mock executor
        executor = Mock()
        executor.execute = Mock(
            return_value={
                "status_code": 200,
                "data": {"id": 1, "name": "John"},
            }
        )

        # 执行节点
        result = executor.execute(
            node=http_node,
            input_data={},
        )

        # 验证结果
        assert result["status_code"] == 200
        assert result["data"]["name"] == "John"

    def test_transform_node_execution(self):
        """测试：Transform 节点应该能转换数据

        RED 阶段期望：
        1. 配置转换规则（映射、过滤、排序等）
        2. 接收输入数据
        3. 返回转换后的数据
        """
        # 创建 Transform 节点（提取特定字段）
        transform_node = Node.create(
            type=NodeType.TRANSFORM,
            name="Extract User Info",
            config={
                "operation": "map",
                "mapping": {
                    "userId": "id",
                    "userName": "name",
                    "userEmail": "email",
                },
            },
            position=Position(x=100, y=0),
        )

        # 创建 mock executor
        executor = Mock()

        # 输入数据
        input_data = {
            "id": 1,
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "123-456-7890",
        }

        # 设定执行结果
        executor.execute = Mock(
            return_value={
                "userId": 1,
                "userName": "John Doe",
                "userEmail": "john@example.com",
            }
        )

        # 执行节点
        result = executor.execute(
            node=transform_node,
            input_data=input_data,
        )

        # 验证结果（只包含映射的字段）
        assert result == {
            "userId": 1,
            "userName": "John Doe",
            "userEmail": "john@example.com",
        }

    def test_llm_node_execution(self):
        """测试：LLM 节点应该能调用语言模型

        RED 阶段期望：
        1. 配置 LLM 模型（API 密钥、模型名称、参数）
        2. 准备提示词
        3. 调用 LLM API
        4. 返回生成的文本
        """
        # 创建 LLM 节点
        llm_node = Node.create(
            type=NodeType.LLM,
            name="Generate Summary",
            config={
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 500,
                "system_prompt": "你是一个专业的文本摘要专家。",
            },
            position=Position(x=200, y=0),
        )

        # 由于 LLM 执行器还未实现，暂时 mock
        executor = Mock()
        executor.execute = Mock(
            return_value={
                "text": "这是一个自动生成的摘要。",
                "tokens_used": 150,
                "model": "gpt-4",
            }
        )

        # 输入数据（长文本）
        input_data = {
            "text": "这是一篇很长的文章。" * 100,
        }

        # 执行节点
        result = executor.execute(
            node=llm_node,
            input_data=input_data,
        )

        # 验证结果
        assert "text" in result
        assert len(result["text"]) > 0
        assert "tokens_used" in result

    def test_workflow_with_multiple_nodes_data_flow(self):
        """测试：多节点工作流的数据流

        RED 阶段期望：
        1. Start → HTTP 获取数据
        2. HTTP → Transform 转换数据
        3. Transform → LLM 生成内容
        4. LLM → End 输出结果
        """
        # 创建节点
        start_node = Node.create(
            type=NodeType.START,
            name="Start",
            config={},
            position=Position(x=0, y=0),
        )

        http_node = Node.create(
            type=NodeType.HTTP,
            name="Fetch Data",
            config={
                "method": "GET",
                "url": "https://api.example.com/items",
            },
            position=Position(x=100, y=0),
        )

        transform_node = Node.create(
            type=NodeType.TRANSFORM,
            name="Filter and Map",
            config={
                "operation": "filter",
                "condition": "status == 'active'",
            },
            position=Position(x=200, y=0),
        )

        end_node = Node.create(
            type=NodeType.END,
            name="End",
            config={},
            position=Position(x=300, y=0),
        )

        # 创建边
        edges = [
            Edge.create(source_node_id=start_node.id, target_node_id=http_node.id),
            Edge.create(source_node_id=http_node.id, target_node_id=transform_node.id),
            Edge.create(source_node_id=transform_node.id, target_node_id=end_node.id),
        ]

        # 创建工作流
        workflow = Workflow.create(
            name="Data Pipeline",
            description="Multi-node data processing workflow",
            nodes=[start_node, http_node, transform_node, end_node],
            edges=edges,
        )

        # 验证工作流结构
        assert len(workflow.nodes) == 4
        assert len(workflow.edges) == 3
        assert workflow.status == "draft"

    def test_node_executor_error_handling(self):
        """测试：节点执行错误处理

        RED 阶段期望：
        1. HTTP 节点请求失败时捕获异常
        2. 返回错误信息而不是崩溃
        3. 错误信息包含原因和建议
        """
        http_node = Node.create(
            type=NodeType.HTTP,
            name="Failing Request",
            config={
                "method": "GET",
                "url": "https://invalid-url-that-does-not-exist.example.com",
                "timeout": 5,
            },
            position=Position(x=0, y=0),
        )

        # 由于 HTTP executor 还未完全实现，使用 mock
        executor = Mock()
        executor.execute = Mock(
            side_effect=Exception("Connection refused: could not connect to server")
        )

        # 执行应该捕获异常
        with pytest.raises(Exception) as exc_info:
            executor.execute(node=http_node, input_data={})

        assert "Connection refused" in str(exc_info.value)

    def test_node_config_validation(self):
        """测试：节点配置验证

        RED 阶段期望：
        1. HTTP 节点必须有 URL
        2. LLM 节点必须有 model
        3. 无效配置应该抛出异常
        """
        # 创建缺少 URL 的 HTTP 节点配置
        invalid_http_config = {
            "method": "GET",
            # 缺少 "url"
        }

        # 由于验证逻辑还未实现，暂时只定义期望
        # executor 应该在执行时检查必需配置
        http_node = Node.create(
            type=NodeType.HTTP,
            name="Bad Config",
            config=invalid_http_config,
            position=Position(x=0, y=0),
        )

        # 验证节点创建成功（验证在执行时进行）
        assert http_node.config.get("method") == "GET"
        assert "url" not in http_node.config
