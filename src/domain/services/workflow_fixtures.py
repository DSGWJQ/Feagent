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
- report_pipeline: 覆盖报表/数据流水线
- reconcile_sync: 覆盖对账/同步流水线（api→transform→db upsert→notification）
- code_assistant: 覆盖代码/研发助手流水线（file→llm→python）
- knowledge_assistant: 覆盖运营/客服知识助理流水线（database→transform→llm）

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
        # Deterministic baseline: keep code compatible with our simplified Python-based executor.
        config={
            "code": "result = {'output': (input1.get('value', 0) if isinstance(input1, dict) else 0) * 2}"
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


@WorkflowFixtureFactory.register("report_pipeline")
def _create_report_pipeline() -> Workflow:
    """创建报表/数据流水线 fixture（P0 扩展）

    用途：覆盖“DB → Transform → Python → LLM → File”的核心链路（无外部依赖）
    结构：start -> database -> transform -> python -> textModel -> file -> end
    """
    start = Node.create(
        type=NodeType.START,
        name="Start",
        config={},
        position=Position(x=100, y=100),
    )
    db = Node.create(
        type=NodeType.DATABASE,
        name="DB Query",
        config={
            "database_url": "sqlite:///test_deterministic.db",
            "sql": "SELECT 1 as value",
            "params": {},
        },
        position=Position(x=300, y=100),
    )
    transform = Node.create(
        type=NodeType.TRANSFORM,
        name="Transform",
        config={
            "type": "field_mapping",
            "mapping": {"data": "input1"},
        },
        position=Position(x=500, y=100),
    )
    python_node = Node.create(
        type=NodeType.PYTHON,
        name="Metric Calculation",
        config={
            "code": """
payload = input1
rows = payload.get("data") if payload.__class__ is dict else payload
if rows.__class__ is not list:
    rows = []
count = len(rows)
value = 0
if count > 0 and rows[0].__class__ is dict and "value" in rows[0]:
    value = rows[0]["value"]
result = {"count": count, "value": value}
""".strip("\n"),
        },
        position=Position(x=700, y=100),
    )
    llm = Node.create(
        type=NodeType.TEXT_MODEL,
        name="LLM Analysis",
        config={
            "model": "openai/gpt-5",
            "temperature": 0,
            "maxTokens": 200,
            "prompt": "Summarize the following metrics:\n{input1}",
        },
        position=Position(x=900, y=100),
    )
    file_node = Node.create(
        type=NodeType.FILE,
        name="Export File",
        config={
            "operation": "write",
            "path": "tmp/e2e/report_pipeline.txt",
            "encoding": "utf-8",
            "content": "{input1}",
        },
        position=Position(x=1100, y=100),
    )
    end = Node.create(
        type=NodeType.END,
        name="End",
        config={},
        position=Position(x=1300, y=100),
    )

    return Workflow.create(
        name="[TEST] Report Pipeline",
        description="E2E test fixture: report pipeline workflow",
        nodes=[start, db, transform, python_node, llm, file_node, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=db.id),
            Edge.create(source_node_id=db.id, target_node_id=transform.id),
            Edge.create(source_node_id=transform.id, target_node_id=python_node.id),
            Edge.create(source_node_id=python_node.id, target_node_id=llm.id),
            Edge.create(source_node_id=llm.id, target_node_id=file_node.id),
            Edge.create(source_node_id=file_node.id, target_node_id=end.id),
        ],
        source="e2e_test",
    )


@WorkflowFixtureFactory.register("reconcile_sync")
def _create_reconcile_sync() -> Workflow:
    """创建对账/同步流水线 fixture（P0 扩展）

    用途：覆盖“HTTP API → Transform → DB upsert → Notification”的核心链路（deterministic 下不出网）
    结构：start -> http -> transform -> db_init -> db_upsert -> db_verify -> notification -> end
    """
    start = Node.create(
        type=NodeType.START,
        name="Start",
        config={},
        position=Position(x=100, y=100),
    )
    http_node = Node.create(
        type=NodeType.HTTP_REQUEST,
        name="Fetch External Orders",
        config={
            "url": "https://example.test/orders",
            "method": "GET",
            "headers": {},
            # Deterministic stub support (HttpExecutor reads this in E2E_TEST_MODE=deterministic).
            "mock_response": {
                "status": 200,
                "data": {
                    "items": [
                        {"id": "order_1", "amount": 100},
                        {"id": "order_2", "amount": 200},
                    ]
                },
            },
        },
        position=Position(x=300, y=100),
    )
    transform = Node.create(
        type=NodeType.TRANSFORM,
        name="Map Payload",
        config={
            "type": "field_mapping",
            # Map nested response to a stable shape for downstream templating.
            "mapping": {"items": "input1.data.items"},
        },
        position=Position(x=500, y=100),
    )

    # KISS: isolate per-run DB file in OS temp dir to reduce workspace I/O contention.
    db_url = (
        "sqlite:///{context.initial_input.db_dir}/"
        "reconcile_sync_{context.initial_input.run_id}.db"
    )
    db_init = Node.create(
        type=NodeType.DATABASE,
        name="DB Init",
        config={
            "database_url": db_url,
            "sql": "CREATE TABLE IF NOT EXISTS e2e_orders (id TEXT PRIMARY KEY, amount INTEGER, source TEXT);",
            "params": {},
        },
        position=Position(x=700, y=40),
    )
    db_upsert = Node.create(
        type=NodeType.DATABASE,
        name="DB Upsert",
        config={
            "database_url": db_url,
            "sql": "INSERT OR REPLACE INTO e2e_orders (id, amount, source) VALUES (?, ?, ?);",
            "params": [
                "{input1.items[0].id}",
                "{input1.items[0].amount}",
                "external",
            ],
        },
        position=Position(x=700, y=140),
    )
    db_verify = Node.create(
        type=NodeType.DATABASE,
        name="DB Verify",
        config={
            "database_url": db_url,
            "sql": "SELECT id, amount, source FROM e2e_orders ORDER BY id;",
            "params": {},
        },
        position=Position(x=900, y=100),
    )
    notify = Node.create(
        type=NodeType.NOTIFICATION,
        name="Notify Ops",
        config={
            "type": "webhook",
            "url": "https://example.test/webhook",
            "headers": {},
            "include_input": True,
            "subject": "Reconcile Sync",
            "message": "Sync OK: {input1[0].id} amount={input1[0].amount}",
        },
        position=Position(x=1100, y=100),
    )
    end = Node.create(
        type=NodeType.END,
        name="End",
        config={},
        position=Position(x=1300, y=100),
    )

    return Workflow.create(
        name="[TEST] Reconcile Sync",
        description="E2E test fixture: reconcile/sync workflow",
        nodes=[start, http_node, transform, db_init, db_upsert, db_verify, notify, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=http_node.id),
            Edge.create(source_node_id=http_node.id, target_node_id=transform.id),
            Edge.create(source_node_id=start.id, target_node_id=db_init.id),
            # Ensure transform output is input1 for db_upsert (edge order matters).
            Edge.create(source_node_id=transform.id, target_node_id=db_upsert.id),
            Edge.create(source_node_id=db_init.id, target_node_id=db_upsert.id),
            Edge.create(source_node_id=db_upsert.id, target_node_id=db_verify.id),
            Edge.create(source_node_id=db_verify.id, target_node_id=notify.id),
            Edge.create(source_node_id=notify.id, target_node_id=end.id),
        ],
        source="e2e_test",
    )


@WorkflowFixtureFactory.register("knowledge_assistant")
def _create_knowledge_assistant() -> Workflow:
    """创建运营/客服知识助理 fixture（P0 扩展）

    用途：覆盖"Database → Transform → LLM"链路（deterministic 下不依赖真实 LLM）
    结构：start -> database(query KB) -> transform -> textModel -> end
    """
    start = Node.create(
        type=NodeType.START,
        name="Start",
        config={},
        position=Position(x=100, y=100),
    )

    db_url = "sqlite:///tmp/e2e/knowledge_assistant.db"
    db_query = Node.create(
        type=NodeType.DATABASE,
        name="Query Knowledge Base",
        config={
            "database_url": db_url,
            "sql": """
                SELECT id, question, answer, category
                FROM knowledge_base
                WHERE category = 'product_info'
                ORDER BY id LIMIT 5
            """.strip(),
            "params": {},
        },
        position=Position(x=300, y=100),
    )

    transform = Node.create(
        type=NodeType.TRANSFORM,
        name="Map KB Data",
        config={
            "type": "field_mapping",
            "mapping": {"kb_records": "input1"},
        },
        position=Position(x=500, y=100),
    )

    llm = Node.create(
        type=NodeType.TEXT_MODEL,
        name="Generate Reply",
        config={
            "model": "openai/gpt-5",
            "temperature": 0,
            "maxTokens": 300,
            "prompt": """Based on the following knowledge base records, generate a professional customer service reply.

Knowledge Base Records:
{input1.kb_records}

Please provide a concise and helpful response.""",
        },
        position=Position(x=700, y=100),
    )

    end = Node.create(
        type=NodeType.END,
        name="End",
        config={},
        position=Position(x=900, y=100),
    )

    return Workflow.create(
        name="[TEST] Knowledge Assistant",
        description="E2E test fixture: operations/customer service knowledge assistant workflow",
        nodes=[start, db_query, transform, llm, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=db_query.id),
            Edge.create(source_node_id=db_query.id, target_node_id=transform.id),
            Edge.create(source_node_id=transform.id, target_node_id=llm.id),
            Edge.create(source_node_id=llm.id, target_node_id=end.id),
        ],
        source="e2e_test",
    )


@WorkflowFixtureFactory.register("code_assistant")
def _create_code_assistant() -> Workflow:
    """创建代码/研发助手 fixture（P0 扩展）

    用途：覆盖“File → LLM → Python”链路（deterministic 下不依赖真实 LLM）
    结构：start -> file(read) -> textModel -> python -> end
    """
    start = Node.create(
        type=NodeType.START,
        name="Start",
        config={},
        position=Position(x=100, y=100),
    )
    file_node = Node.create(
        type=NodeType.FILE,
        name="Read Source",
        config={
            "operation": "read",
            "path": "README.md",
            "encoding": "utf-8",
        },
        position=Position(x=300, y=100),
    )
    llm = Node.create(
        type=NodeType.TEXT_MODEL,
        name="LLM Review",
        config={
            "model": "openai/gpt-5",
            "temperature": 0,
            "maxTokens": 200,
            "prompt": "Review the following file content and summarize key points:\n{input1.content}",
        },
        position=Position(x=500, y=100),
    )
    python_node = Node.create(
        type=NodeType.PYTHON,
        name="Static Check",
        config={
            "code": """
acc = 0
for i in range(30000000):
    acc += i % 7
text = input1 if input1.__class__ is str else str(input1)
result = {"summary_len": len(text), "ok": len(text) > 0, "acc": acc}
""".strip("\n"),
        },
        position=Position(x=700, y=100),
    )
    end = Node.create(
        type=NodeType.END,
        name="End",
        config={},
        position=Position(x=900, y=100),
    )

    return Workflow.create(
        name="[TEST] Code Assistant",
        description="E2E test fixture: code assistant workflow",
        nodes=[start, file_node, llm, python_node, end],
        edges=[
            Edge.create(source_node_id=start.id, target_node_id=file_node.id),
            Edge.create(source_node_id=file_node.id, target_node_id=llm.id),
            Edge.create(source_node_id=llm.id, target_node_id=python_node.id),
            Edge.create(source_node_id=python_node.id, target_node_id=end.id),
        ],
        source="e2e_test",
    )
