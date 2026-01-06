"""SeedTestWorkflow Use Cases - E2E 测试数据管理用例

业务场景：
- 为 Playwright E2E 测试提供确定性数据准备能力
- 支持快速创建预定义 workflow fixtures
- 支持批量清理测试数据

安全控制：
- 仅在测试/开发环境启用（通过 enable_test_seed_api 配置）
- 必须携带 X-Test-Mode: true 请求头（API 层验证）
- 所有测试 workflow 的 source 字段都设置为 "e2e_test"
"""

from dataclasses import dataclass, field
from typing import Any

from src.domain.entities.workflow import Workflow
from src.domain.ports.workflow_repository import WorkflowRepository
from src.domain.services.workflow_fixtures import WorkflowFixtureFactory


@dataclass
class SeedTestWorkflowInput:
    """创建测试 Workflow 的输入参数"""

    fixture_type: str
    project_id: str = "e2e_test_project"
    custom_metadata: dict[str, Any] | None = None
    custom_nodes: list[dict[str, Any]] | None = None


@dataclass
class SeedTestWorkflowOutput:
    """创建测试 Workflow 的输出"""

    workflow_id: str
    project_id: str
    fixture_type: str
    metadata: dict[str, Any]
    cleanup_token: str


class SeedTestWorkflowUseCase:
    """创建测试 Workflow 用例（仅测试环境）

    职责：
    1. 根据 fixture_type 生成 workflow
    2. 设置 source="e2e_test" 标记测试数据
    3. 持久化 workflow
    4. 生成清理 token
    """

    # NOTE: NodeType 有多种历史命名（例如前端 V0 的 `httpRequest`）。
    # 这里统一做小写匹配，避免 fixture 使用 `httpRequest` 时被漏判为“无副作用”。
    SIDE_EFFECT_NODE_TYPES = {"http", "httprequest", "database", "tool", "notification", "file"}
    TEST_SOURCE_MARKER = "e2e_test"

    def __init__(
        self,
        workflow_repository: WorkflowRepository,
        fixture_factory: WorkflowFixtureFactory | None = None,
    ):
        self.workflow_repository = workflow_repository
        self.fixture_factory = fixture_factory or WorkflowFixtureFactory()

    def execute(self, input_data: SeedTestWorkflowInput) -> SeedTestWorkflowOutput:
        """执行用例：创建测试 Workflow"""
        workflow = self.fixture_factory.create_fixture(
            fixture_type=input_data.fixture_type,
            project_id=input_data.project_id,
            custom_nodes=input_data.custom_nodes,
        )

        workflow.source = self.TEST_SOURCE_MARKER
        workflow.source_id = f"{input_data.fixture_type}:{workflow.id}"

        self.workflow_repository.save(workflow)

        return SeedTestWorkflowOutput(
            workflow_id=workflow.id,
            project_id=workflow.project_id or input_data.project_id,
            fixture_type=input_data.fixture_type,
            metadata={
                "node_count": len(workflow.nodes),
                "edge_count": len(workflow.edges),
                "has_isolated_nodes": self._has_isolated_nodes(workflow),
                "side_effect_nodes": self._find_side_effect_nodes(workflow),
                "custom_metadata": input_data.custom_metadata,
            },
            cleanup_token=f"cleanup_{workflow.id}",
        )

    def _has_isolated_nodes(self, workflow: Workflow) -> bool:
        """检查是否存在孤立节点"""
        connected_nodes = set()
        for edge in workflow.edges:
            connected_nodes.add(edge.source_node_id)
            connected_nodes.add(edge.target_node_id)

        all_node_ids = {node.id for node in workflow.nodes}
        isolated = all_node_ids - connected_nodes

        return len(isolated) > 0

    def _find_side_effect_nodes(self, workflow: Workflow) -> list[str]:
        """找出所有副作用节点"""
        side_effect_nodes = []
        for node in workflow.nodes:
            node_type = node.type.value if hasattr(node.type, "value") else str(node.type)
            if node_type.lower() in self.SIDE_EFFECT_NODE_TYPES:
                side_effect_nodes.append(node.id)
        return side_effect_nodes


@dataclass
class CleanupTestWorkflowsInput:
    """清理测试 Workflow 的输入参数"""

    cleanup_tokens: list[str] = field(default_factory=list)
    delete_by_source: bool = False


@dataclass
class CleanupTestWorkflowsOutput:
    """清理测试 Workflow 的输出"""

    deleted_count: int
    failed: list[str]


class CleanupTestWorkflowsUseCase:
    """清理测试 Workflow 用例

    职责：
    1. 根据 cleanup_tokens 批量删除
    2. 支持按 source="e2e_test" 删除所有测试数据
    3. 返回删除统计
    """

    TEST_SOURCE_MARKER = "e2e_test"

    def __init__(self, workflow_repository: WorkflowRepository):
        self.workflow_repository = workflow_repository

    def execute(self, input_data: CleanupTestWorkflowsInput) -> CleanupTestWorkflowsOutput:
        """执行用例：清理测试 Workflow"""
        deleted_count = 0
        failed: list[str] = []

        for token in input_data.cleanup_tokens:
            workflow_id = token.replace("cleanup_", "")
            try:
                if self.workflow_repository.exists(workflow_id):
                    self.workflow_repository.delete(workflow_id)
                    deleted_count += 1
            except Exception as e:
                failed.append(f"{workflow_id}: {e}")

        if input_data.delete_by_source:
            deleted_by_source = self._delete_by_source()
            deleted_count += deleted_by_source

        return CleanupTestWorkflowsOutput(
            deleted_count=deleted_count,
            failed=failed,
        )

    def _delete_by_source(self) -> int:
        """删除所有 source="e2e_test" 的 workflow"""
        deleted = 0
        try:
            all_workflows = self.workflow_repository.find_all()
            for workflow in all_workflows:
                if workflow.source == self.TEST_SOURCE_MARKER:
                    try:
                        self.workflow_repository.delete(workflow.id)
                        deleted += 1
                    except Exception:
                        pass
        except Exception:
            pass
        return deleted
