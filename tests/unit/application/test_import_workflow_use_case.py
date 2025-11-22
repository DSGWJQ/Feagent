"""ImportWorkflowUseCase 单元测试

测试目标：
1. 验证 ImportWorkflowUseCase 能够正确导入 Coze 工作流
2. 验证输入验证逻辑
3. 验证 Repository 调用
4. 验证异常处理

V2新功能：
- 支持从 Coze 平台导入工作流
- 自动进行节点类型映射
- 追踪工作流来源（source/source_id）

测试策略：
- 使用 Mock Repository 进行单元测试
- 不依赖真实数据库
- 测试各种边界条件和异常情况
"""

from unittest.mock import Mock

import pytest

from src.application.use_cases.import_workflow import (
    ImportWorkflowInput,
    ImportWorkflowUseCase,
)
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError


class TestImportWorkflowUseCase:
    """ImportWorkflowUseCase 测试类"""

    def test_import_workflow_from_coze_success(self):
        """测试成功导入 Coze 工作流

        验收标准：
        - 输入有效的 Coze JSON 时，能够成功创建 Workflow
        - 调用 Workflow.from_coze_json() 创建实体
        - 调用 Repository.save() 保存 Workflow
        - 返回包含 workflow_id, name, source, source_id 的输出
        """
        # Arrange: 准备测试数据和 Mock
        mock_repo = Mock()
        use_case = ImportWorkflowUseCase(workflow_repository=mock_repo)

        coze_json = {
            "workflow_id": "coze_wf_12345",
            "name": "Coze测试工作流",
            "description": "从Coze导入的工作流",
            "nodes": [
                {
                    "id": "node_1",
                    "type": "llm",
                    "name": "LLM处理",
                    "config": {"model": "gpt-4"},
                    "position": {"x": 100, "y": 100},
                }
            ],
            "edges": [],
        }

        input_data = ImportWorkflowInput(coze_json=coze_json)

        # Act: 执行用例
        result = use_case.execute(input_data)

        # Assert: 验证结果
        assert result is not None, "应该返回导入结果"
        assert result.workflow_id is not None, "应该返回 workflow_id"
        assert result.workflow_id.startswith("wf_"), "workflow_id 应该以 wf_ 开头"
        assert result.name == "Coze测试工作流", "name 应该匹配 Coze JSON"
        assert result.source == "coze", "source 应该是 coze"
        assert result.source_id == "coze_wf_12345", "source_id 应该是原始 workflow_id"

        # 验证 Repository 调用
        mock_repo.save.assert_called_once(), "应该调用 Repository.save() 一次"
        saved_workflow = mock_repo.save.call_args[0][0]
        assert isinstance(saved_workflow, Workflow), "保存的应该是 Workflow 实例"
        assert saved_workflow.name == "Coze测试工作流"
        assert saved_workflow.source == "coze"

    def test_import_workflow_with_empty_json(self):
        """测试导入空 JSON 时抛出异常

        验收标准：
        - coze_json 为空时，抛出 DomainError
        - 不调用 Repository.save()
        """
        # Arrange
        mock_repo = Mock()
        use_case = ImportWorkflowUseCase(workflow_repository=mock_repo)

        input_data = ImportWorkflowInput(coze_json={})

        # Act & Assert
        with pytest.raises(DomainError, match="Coze JSON不能为空"):
            use_case.execute(input_data)

        # 验证不调用 save
        mock_repo.save.assert_not_called()

    def test_import_workflow_without_nodes(self):
        """测试导入没有节点的工作流时抛出异常

        验收标准：
        - nodes 为空时，抛出 DomainError
        - 不调用 Repository.save()
        """
        # Arrange
        mock_repo = Mock()
        use_case = ImportWorkflowUseCase(workflow_repository=mock_repo)

        coze_json = {
            "workflow_id": "coze_wf_12345",
            "name": "空工作流",
            "description": "测试",
            "nodes": [],
            "edges": [],
        }

        input_data = ImportWorkflowInput(coze_json=coze_json)

        # Act & Assert
        with pytest.raises(DomainError, match="至少需要一个节点"):
            use_case.execute(input_data)

        # 验证不调用 save
        mock_repo.save.assert_not_called()

    def test_import_workflow_with_unsupported_node_type(self):
        """测试导入包含不支持节点类型的工作流时抛出异常

        验收标准：
        - 节点类型不支持时，抛出 DomainError 并说明支持的类型
        - 不调用 Repository.save()
        """
        # Arrange
        mock_repo = Mock()
        use_case = ImportWorkflowUseCase(workflow_repository=mock_repo)

        coze_json = {
            "workflow_id": "coze_wf_12345",
            "name": "测试工作流",
            "description": "包含不支持的节点类型",
            "nodes": [
                {
                    "id": "node_1",
                    "type": "unsupported_type",
                    "name": "未知节点",
                    "config": {},
                    "position": {"x": 100, "y": 100},
                }
            ],
            "edges": [],
        }

        input_data = ImportWorkflowInput(coze_json=coze_json)

        # Act & Assert
        with pytest.raises(DomainError, match="不支持的Coze节点类型"):
            use_case.execute(input_data)

        # 验证不调用 save
        mock_repo.save.assert_not_called()

    def test_import_workflow_with_invalid_edge_reference(self):
        """测试导入包含无效边引用的工作流时抛出异常

        验收标准：
        - 边引用的节点不存在时，抛出 DomainError
        - 不调用 Repository.save()
        """
        # Arrange
        mock_repo = Mock()
        use_case = ImportWorkflowUseCase(workflow_repository=mock_repo)

        coze_json = {
            "workflow_id": "coze_wf_12345",
            "name": "测试工作流",
            "description": "包含无效边引用",
            "nodes": [
                {
                    "id": "node_1",
                    "type": "llm",
                    "name": "LLM节点",
                    "config": {},
                    "position": {"x": 100, "y": 100},
                }
            ],
            "edges": [
                {
                    "id": "edge_1",
                    "source": "node_1",
                    "target": "node_999",  # 不存在的节点
                }
            ],
        }

        input_data = ImportWorkflowInput(coze_json=coze_json)

        # Act & Assert
        with pytest.raises(DomainError, match="节点不存在"):
            use_case.execute(input_data)

        # 验证不调用 save
        mock_repo.save.assert_not_called()

    def test_import_workflow_with_multiple_nodes_and_edges(self):
        """测试导入包含多个节点和边的复杂工作流

        验收标准：
        - 能够正确导入多个节点
        - 能够正确导入多个边
        - 所有节点类型映射正确
        """
        # Arrange
        mock_repo = Mock()
        use_case = ImportWorkflowUseCase(workflow_repository=mock_repo)

        coze_json = {
            "workflow_id": "coze_wf_complex",
            "name": "复杂工作流",
            "description": "包含多个节点和边",
            "nodes": [
                {
                    "id": "node_1",
                    "type": "llm",
                    "name": "LLM节点",
                    "config": {"model": "gpt-4"},
                    "position": {"x": 100, "y": 100},
                },
                {
                    "id": "node_2",
                    "type": "http",
                    "name": "HTTP节点",
                    "config": {"url": "https://api.example.com"},
                    "position": {"x": 300, "y": 100},
                },
                {
                    "id": "node_3",
                    "type": "condition",
                    "name": "条件节点",
                    "config": {"condition": "status == 200"},
                    "position": {"x": 500, "y": 100},
                },
            ],
            "edges": [
                {"id": "edge_1", "source": "node_1", "target": "node_2"},
                {"id": "edge_2", "source": "node_2", "target": "node_3"},
            ],
        }

        input_data = ImportWorkflowInput(coze_json=coze_json)

        # Act
        result = use_case.execute(input_data)

        # Assert
        assert result.name == "复杂工作流"
        assert result.source == "coze"
        assert result.source_id == "coze_wf_complex"

        # 验证保存的 Workflow
        saved_workflow = mock_repo.save.call_args[0][0]
        assert len(saved_workflow.nodes) == 3, "应该有3个节点"
        assert len(saved_workflow.edges) == 2, "应该有2条边"
