"""WorkflowFixtureFactory - E2E 测试专用 Workflow 工厂

设计目的：
- 为 Playwright E2E 测试提供确定性数据准备能力
- 支持快速创建预定义 workflow fixtures
- 使用装饰器模式注册 fixture 类型

Fixture 类型：
- main_subgraph_only: 正常的主连通子图执行流程
- with_isolated_nodes: 测试主子图约束防御
- side_effect_workflow: 测试副作用确认流程
- invalid_config: 测试保存校验失败场景

注意：
- 此模块仅用于测试环境
- 生产环境应禁用相关 API
"""

from collections.abc import Callable
from typing import Any

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position


class WorkflowFixtureFactory:
    """Workflow Fixture 工厂（测试专用）

    使用装饰器模式注册 fixture 生成函数：
    ```python
    @WorkflowFixtureFactory.register("my_fixture")
    def _create_my_fixture() -> Workflow:
        ...
    ```
    """

    FIXTURES: dict[str, Callable[[], Workflow]] = {}

    @classmethod
    def register(
        cls, fixture_type: str
    ) -> Callable[[Callable[[], Workflow]], Callable[[], Workflow]]:
        """装饰器：注册 fixture 生成函数"""

        def decorator(func: Callable[[], Workflow]) -> Callable[[], Workflow]:
            cls.FIXTURES[fixture_type] = func
            return func

        return decorator

    @classmethod
    def list_fixture_types(cls) -> list[str]:
        """列出所有可用的 fixture 类型"""
        return list(cls.FIXTURES.keys())

    def create_fixture(
        self,
        fixture_type: str,
        project_id: str | None = None,
        custom_nodes: list[dict[str, Any]] | None = None,
    ) -> Workflow:
        """创建指定类型的 fixture workflow

        Args:
            fixture_type: fixture 类型名称
            project_id: 关联的项目 ID（可选）
            custom_nodes: 自定义节点覆盖（可选）

        Returns:
            Workflow 实体

        Raises:
            DomainError: 当 fixture_type 不存在时
        """
        if fixture_type not in self.FIXTURES:
            raise DomainError(
                f"Unknown fixture_type: {fixture_type}. "
                f"Valid types: {', '.join(self.FIXTURES.keys())}"
            )

        workflow = self.FIXTURES[fixture_type]()

        if project_id:
            workflow.project_id = project_id

        if custom_nodes:
            self._apply_custom_nodes(workflow, custom_nodes)

        return workflow

    def _apply_custom_nodes(self, workflow: Workflow, custom_nodes: list[dict[str, Any]]) -> None:
        """应用自定义节点覆盖"""
        for custom in custom_nodes:
            node_id = custom.get("id")
            if not node_id:
                continue

            for i, node in enumerate(workflow.nodes):
                if node.id == node_id:
                    if "config" in custom:
                        node.config = custom["config"]
                    if "name" in custom:
                        node.name = custom["name"]
                    workflow.nodes[i] = node
                    break


@WorkflowFixtureFactory.register("main_subgraph_only")
def _create_main_subgraph() -> Workflow:
    """创建主子图 workflow (P0 必需)

    用途：测试正常的主连通子图执行流程
    结构：start -> process_data -> end
    """
    start = Node.create(
        type=NodeType.START,
        name="Start",
        config={},
        position=Position(x=100, y=100),
    )
    process = Node.create(
        type=NodeType.JAVASCRIPT,
        name="Process Data",
        config={"code": "return { output: (input_data?.value || 0) * 2 };"},
        position=Position(x=300, y=100),
    )
    end = Node.create(
        type=NodeType.END,
        name="End",
        config={},
        position=Position(x=500, y=100),
    )

    return Workflow.create(
        name="[TEST] Main Subgraph Only",
        description="E2E test fixture: main subgraph workflow",
        nodes=[start, process, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=process.id),
            Edge.create(source_node_id=process.id, target_node_id=end.id),
        ],
        source="e2e_test",
    )


@WorkflowFixtureFactory.register("with_isolated_nodes")
def _create_with_isolated() -> Workflow:
    """创建带孤立节点的 workflow (P1 必需)

    用途：测试主子图约束防御 (UX-WF-101)
    结构：
    - Main: start -> node_A -> end
    - Isolated: isolated_no_in, isolated_no_out
    """
    start = Node.create(
        type=NodeType.START,
        name="Start",
        config={},
        position=Position(x=100, y=100),
    )
    node_a = Node.create(
        type=NodeType.JAVASCRIPT,
        name="Node A",
        config={"code": "return input_data;"},
        position=Position(x=300, y=100),
    )
    end = Node.create(
        type=NodeType.END,
        name="End",
        config={},
        position=Position(x=500, y=100),
    )
    isolated_1 = Node.create(
        type=NodeType.JAVASCRIPT,
        name="Isolated (No Incoming)",
        config={"code": "return {};"},
        position=Position(x=300, y=300),
    )
    isolated_2 = Node.create(
        type=NodeType.JAVASCRIPT,
        name="Isolated (No Outgoing)",
        config={"code": "return {};"},
        position=Position(x=500, y=300),
    )

    workflow = Workflow(
        id="wf_test_isolated",
        name="[TEST] With Isolated Nodes",
        description="E2E test fixture: workflow with isolated nodes",
        nodes=[start, node_a, end, isolated_1, isolated_2],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=node_a.id),
            Edge.create(source_node_id=node_a.id, target_node_id=end.id),
        ],
        source="e2e_test",
    )

    from uuid import uuid4

    workflow.id = f"wf_{uuid4().hex[:8]}"

    return workflow


@WorkflowFixtureFactory.register("side_effect_workflow")
def _create_side_effect() -> Workflow:
    """创建副作用 workflow (P0 必需)

    用途：测试副作用确认流程 (UX-WF-004)
    结构：start -> http_call -> end
    """
    start = Node.create(
        type=NodeType.START,
        name="Start",
        config={},
        position=Position(x=100, y=100),
    )
    http_node = Node.create(
        type=NodeType.HTTP_REQUEST,
        name="HTTP Call",
        config={
            "url": "https://httpbin.org/post",
            "method": "POST",
            "body": {"test": True},
        },
        position=Position(x=300, y=100),
    )
    end = Node.create(
        type=NodeType.END,
        name="End",
        config={},
        position=Position(x=500, y=100),
    )

    return Workflow.create(
        name="[TEST] Side Effect Workflow",
        description="E2E test fixture: workflow with side effect nodes",
        nodes=[start, http_node, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=http_node.id),
            Edge.create(source_node_id=http_node.id, target_node_id=end.id),
        ],
        source="e2e_test",
    )


@WorkflowFixtureFactory.register("invalid_config")
def _create_invalid() -> Workflow:
    """创建无效配置 workflow (P1 必需)

    用途：测试保存校验失败场景 (UX-WF-102)
    结构：start -> broken_node -> end
    """
    start = Node.create(
        type=NodeType.START,
        name="Start",
        config={},
        position=Position(x=100, y=100),
    )
    broken = Node.create(
        type=NodeType.JAVASCRIPT,
        name="Broken Node",
        config={"code": None},  # code 为空，触发校验失败
        position=Position(x=300, y=100),
    )
    end = Node.create(
        type=NodeType.END,
        name="End",
        config={},
        position=Position(x=500, y=100),
    )

    return Workflow.create(
        name="[TEST] Invalid Config",
        description="E2E test fixture: workflow with invalid config",
        nodes=[start, broken, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=broken.id),
            Edge.create(source_node_id=broken.id, target_node_id=end.id),
        ],
        source="e2e_test",
    )
