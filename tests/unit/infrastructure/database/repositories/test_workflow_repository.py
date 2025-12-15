"""WorkflowRepository集成测试

测试SQLAlchemyWorkflowRepository的持久化功能，遵循TDD原则。

测试范围：
1. 保存工作流（save）- 包含聚合持久化（Workflow + Nodes + Edges）
2. 根据ID查找工作流（get_by_id, find_by_id）
3. 列出所有工作流（find_all）- 验证排序规则
4. 检查工作流是否存在（exists）
5. 删除工作流（delete）- 验证级联删除
6. 时区处理（timestamps）- 验证UTC时区感知

测试原则：
- 使用真实的数据库（SQLite内存数据库）
- 每个测试独立运行，互不影响（transaction-per-test）
- 测试ORM模型和领域实体之间的转换
- 测试聚合根的完整性（节点、边的级联操作）
- 最小化mock，使用真实ORM + Repository逻辑

覆盖目标: 40.4% → ≥80%
测试数量: ~11 tests (P0)
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import NotFoundError
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.domain.value_objects.workflow_status import WorkflowStatus
from src.infrastructure.database.base import Base
from src.infrastructure.database.models import EdgeModel, NodeModel
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)

# ====================
# Fixtures
# ====================


@pytest.fixture
def in_memory_db_engine():
    """创建内存数据库引擎"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(in_memory_db_engine):
    """创建数据库会话（transaction-per-test模式）

    重要提示：
    - 每个测试运行在独立的事务中
    - 测试结束后自动回滚，确保隔离性
    - 使用session.flush()强制SQL执行，而非commit()
    """
    connection = in_memory_db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def workflow_repository(session: Session) -> SQLAlchemyWorkflowRepository:
    """创建WorkflowRepository实例"""
    return SQLAlchemyWorkflowRepository(session)


# ====================
# 测试数据构建器（使用固定ID）
# ====================


def make_node(*, node_id: str, node_type: NodeType, name: str, x: float, y: float) -> Node:
    """创建测试节点（固定ID以便验证）"""
    node = Node.create(
        type=node_type,
        name=name,
        config={"test_key": "test_value"},
        position=Position(x=x, y=y),
    )
    node.id = node_id
    return node


def make_edge(
    *,
    edge_id: str,
    source_node_id: str,
    target_node_id: str,
    condition: str | None = None,
) -> Edge:
    """创建测试边（固定ID以便验证）"""
    edge = Edge.create(
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        condition=condition,
    )
    edge.id = edge_id
    return edge


def make_workflow(
    *,
    workflow_id: str,
    name: str,
    description: str,
    nodes: list[Node],
    edges: list[Edge],
    status: WorkflowStatus = WorkflowStatus.DRAFT,
    source: str = "feagent",
    source_id: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> Workflow:
    """创建测试工作流（固定ID以便验证）"""
    workflow = Workflow.create(
        name=name,
        description=description,
        nodes=nodes,
        edges=edges,
        source=source,
        source_id=source_id,
    )
    workflow.id = workflow_id
    workflow.status = status
    if created_at is not None:
        workflow.created_at = created_at
    if updated_at is not None:
        workflow.updated_at = updated_at
    return workflow


# ====================
# 测试类：Save（保存工作流）
# ====================


class TestWorkflowRepositorySave:
    """测试工作流保存功能"""

    def test_save_new_workflow_persists_and_loads_nodes_edges(
        self, workflow_repository: SQLAlchemyWorkflowRepository, session: Session
    ):
        """
        测试：保存新工作流应成功持久化聚合根（包含节点和边）

        Given: 创建包含2个节点和1条边的工作流
        When: 调用repository.save并flush
        Then:
          - 工作流及所有子实体应被持久化
          - 重新加载时数据完整且正确
          - 节点位置、配置等细节正确round-trip
        """
        # Given: 创建测试数据
        node_start = make_node(
            node_id="node_start",
            node_type=NodeType.START,
            name="开始节点",
            x=10.0,
            y=20.0,
        )
        node_http = make_node(
            node_id="node_http",
            node_type=NodeType.HTTP,
            name="HTTP请求",
            x=100.0,
            y=200.0,
        )
        edge_flow = make_edge(
            edge_id="edge_flow",
            source_node_id="node_start",
            target_node_id="node_http",
            condition="success == true",
        )

        created_at = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        updated_at = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)

        workflow = make_workflow(
            workflow_id="wf_test_001",
            name="测试工作流",
            description="用于测试的工作流",
            nodes=[node_start, node_http],
            edges=[edge_flow],
            status=WorkflowStatus.DRAFT,
            source="feagent",
            source_id=None,
            created_at=created_at,
            updated_at=updated_at,
        )

        # When: 保存工作流
        workflow_repository.save(workflow)
        session.flush()

        # Then: 验证顶层字段
        loaded = workflow_repository.get_by_id("wf_test_001")
        assert loaded.id == "wf_test_001"
        assert loaded.name == "测试工作流"
        assert loaded.description == "用于测试的工作流"
        assert loaded.status == WorkflowStatus.DRAFT
        assert loaded.source == "feagent"
        assert loaded.source_id is None

        # Then: 验证节点聚合
        assert len(loaded.nodes) == 2
        loaded_node_ids = {n.id for n in loaded.nodes}
        assert loaded_node_ids == {"node_start", "node_http"}

        node_start_loaded = next(n for n in loaded.nodes if n.id == "node_start")
        assert node_start_loaded.type == NodeType.START
        assert node_start_loaded.name == "开始节点"
        assert node_start_loaded.position == Position(x=10.0, y=20.0)
        assert node_start_loaded.config == {"test_key": "test_value"}

        node_http_loaded = next(n for n in loaded.nodes if n.id == "node_http")
        assert node_http_loaded.type == NodeType.HTTP
        assert node_http_loaded.name == "HTTP请求"
        assert node_http_loaded.position == Position(x=100.0, y=200.0)
        assert node_http_loaded.config == {"test_key": "test_value"}

        # Then: 验证边聚合
        assert len(loaded.edges) == 1
        edge_loaded = loaded.edges[0]
        assert edge_loaded.id == "edge_flow"
        assert edge_loaded.source_node_id == "node_start"
        assert edge_loaded.target_node_id == "node_http"
        assert edge_loaded.condition == "success == true"

    def test_save_existing_workflow_updates_fields_via_merge(
        self, workflow_repository: SQLAlchemyWorkflowRepository, session: Session
    ):
        """
        测试：保存已存在的工作流应更新字段（merge语义）

        Given: 数据库中已存在工作流wf_update_test
        When: 修改name/description/status后再次save
        Then:
          - 所有修改应被持久化
          - 重新加载时字段值正确更新
        """
        # Given: 先保存初始版本
        node_v1 = make_node(
            node_id="node_v1",
            node_type=NodeType.START,
            name="开始",
            x=0.0,
            y=0.0,
        )

        workflow_v1 = make_workflow(
            workflow_id="wf_update_test",
            name="初始名称",
            description="初始描述",
            nodes=[node_v1],
            edges=[],
            status=WorkflowStatus.DRAFT,
            created_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            updated_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
        )
        workflow_repository.save(workflow_v1)
        session.flush()

        # When: 修改字段后再次保存
        workflow_v2 = make_workflow(
            workflow_id="wf_update_test",  # 相同ID
            name="更新后的名称",
            description="更新后的描述",
            nodes=[node_v1],
            edges=[],
            status=WorkflowStatus.PUBLISHED,  # 状态改变
            created_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            updated_at=datetime(2025, 1, 1, 11, 0, 0, tzinfo=UTC),
        )
        workflow_repository.save(workflow_v2)
        session.flush()

        # Then: 验证更新
        loaded = workflow_repository.get_by_id("wf_update_test")
        assert loaded.name == "更新后的名称"
        assert loaded.description == "更新后的描述"
        assert loaded.status == WorkflowStatus.PUBLISHED
        assert loaded.updated_at == datetime(2025, 1, 1, 11, 0, 0, tzinfo=UTC)


# ====================
# 测试类：GetById（根据ID获取）
# ====================


class TestWorkflowRepositoryGetById:
    """测试根据ID获取工作流功能"""

    def test_get_by_id_missing_raises_not_found_error(
        self, workflow_repository: SQLAlchemyWorkflowRepository
    ):
        """
        测试：get_by_id在工作流不存在时应抛出NotFoundError

        Given: 数据库中不存在指定ID的工作流
        When: 调用get_by_id
        Then: 应抛出NotFoundError，且包含正确的entity_type和entity_id
        """
        # When & Then
        with pytest.raises(NotFoundError) as exc_info:
            workflow_repository.get_by_id("wf_nonexistent")

        assert exc_info.value.entity_type == "Workflow"
        assert exc_info.value.entity_id == "wf_nonexistent"


# ====================
# 测试类：FindById（可选查找）
# ====================


class TestWorkflowRepositoryFindById:
    """测试可选查找工作流功能"""

    def test_find_by_id_missing_returns_none(
        self, workflow_repository: SQLAlchemyWorkflowRepository
    ):
        """
        测试：find_by_id在工作流不存在时应返回None

        Given: 数据库中不存在指定ID的工作流
        When: 调用find_by_id
        Then: 应返回None（不抛异常）
        """
        # When
        result = workflow_repository.find_by_id("wf_nonexistent")

        # Then
        assert result is None

    def test_find_by_id_existing_returns_workflow_with_children(
        self, workflow_repository: SQLAlchemyWorkflowRepository, session: Session
    ):
        """
        测试：find_by_id应返回完整的工作流聚合（包含子实体）

        Given: 数据库中存在包含节点和边的工作流
        When: 调用find_by_id
        Then: 应返回完整的工作流对象，包含所有节点和边
        """
        # Given
        node_a = make_node(
            node_id="node_a",
            node_type=NodeType.START,
            name="开始",
            x=0.0,
            y=0.0,
        )
        node_b = make_node(
            node_id="node_b",
            node_type=NodeType.END,
            name="结束",
            x=100.0,
            y=200.0,
        )
        edge_ab = make_edge(
            edge_id="edge_ab",
            source_node_id="node_a",
            target_node_id="node_b",
            condition=None,
        )

        workflow = make_workflow(
            workflow_id="wf_find_test",
            name="查找测试",
            description="测试find_by_id",
            nodes=[node_a, node_b],
            edges=[edge_ab],
        )

        workflow_repository.save(workflow)
        session.flush()

        # When
        loaded = workflow_repository.find_by_id("wf_find_test")

        # Then
        assert loaded is not None
        assert loaded.id == "wf_find_test"
        assert len(loaded.nodes) == 2
        assert {n.id for n in loaded.nodes} == {"node_a", "node_b"}
        assert len(loaded.edges) == 1
        assert loaded.edges[0].id == "edge_ab"


# ====================
# 测试类：FindAll（列出所有）
# ====================


class TestWorkflowRepositoryFindAll:
    """测试列出所有工作流功能"""

    def test_find_all_empty_returns_empty_list(
        self, workflow_repository: SQLAlchemyWorkflowRepository
    ):
        """
        测试：find_all在数据库为空时应返回空列表

        Given: 数据库中没有工作流
        When: 调用find_all
        Then: 应返回空列表（不是None）
        """
        # When
        result = workflow_repository.find_all()

        # Then
        assert result == []

    def test_find_all_returns_descending_created_at(
        self, workflow_repository: SQLAlchemyWorkflowRepository, session: Session
    ):
        """
        测试：find_all应按created_at降序返回工作流

        Given: 数据库中存在3个工作流，创建时间分别为T1 < T2 < T3
        When: 调用find_all
        Then: 返回顺序应为 [wf3, wf2, wf1]（最新的在前）
        """
        # Given: 创建3个工作流，设置不同的创建时间（每个工作流使用独立的节点）
        node_old = make_node(
            node_id="node_old",
            node_type=NodeType.START,
            name="开始",
            x=0,
            y=0,
        )
        node_mid = make_node(
            node_id="node_mid",
            node_type=NodeType.START,
            name="开始",
            x=0,
            y=0,
        )
        node_new = make_node(
            node_id="node_new",
            node_type=NodeType.START,
            name="开始",
            x=0,
            y=0,
        )

        wf1 = make_workflow(
            workflow_id="wf_old",
            name="最旧的工作流",
            description="",
            nodes=[node_old],
            edges=[],
            created_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC),
            updated_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC),
        )
        wf2 = make_workflow(
            workflow_id="wf_mid",
            name="中间的工作流",
            description="",
            nodes=[node_mid],
            edges=[],
            created_at=datetime(2025, 1, 2, 0, 0, 0, tzinfo=UTC),
            updated_at=datetime(2025, 1, 2, 0, 0, 0, tzinfo=UTC),
        )
        wf3 = make_workflow(
            workflow_id="wf_new",
            name="最新的工作流",
            description="",
            nodes=[node_new],
            edges=[],
            created_at=datetime(2025, 1, 3, 0, 0, 0, tzinfo=UTC),
            updated_at=datetime(2025, 1, 3, 0, 0, 0, tzinfo=UTC),
        )

        workflow_repository.save(wf1)
        workflow_repository.save(wf2)
        workflow_repository.save(wf3)
        session.flush()

        # When
        loaded = workflow_repository.find_all()

        # Then: 验证顺序（降序）
        assert [w.id for w in loaded] == ["wf_new", "wf_mid", "wf_old"]


# ====================
# 测试类：Exists（检查存在性）
# ====================


class TestWorkflowRepositoryExists:
    """测试检查工作流存在性功能"""

    def test_exists_true_for_existing_workflow(
        self, workflow_repository: SQLAlchemyWorkflowRepository, session: Session
    ):
        """
        测试：exists应对存在的工作流返回True

        Given: 数据库中存在指定ID的工作流
        When: 调用exists
        Then: 应返回True
        """
        # Given
        wf = make_workflow(
            workflow_id="wf_exists_test",
            name="存在性测试",
            description="",
            nodes=[
                make_node(
                    node_id="node_x",
                    node_type=NodeType.START,
                    name="开始",
                    x=0,
                    y=0,
                )
            ],
            edges=[],
        )
        workflow_repository.save(wf)
        session.flush()

        # When
        result = workflow_repository.exists("wf_exists_test")

        # Then
        assert result is True

    def test_exists_false_for_missing_workflow(
        self, workflow_repository: SQLAlchemyWorkflowRepository
    ):
        """
        测试：exists应对不存在的工作流返回False

        Given: 数据库中不存在指定ID的工作流
        When: 调用exists
        Then: 应返回False
        """
        # When
        result = workflow_repository.exists("wf_nonexistent")

        # Then
        assert result is False


# ====================
# 测试类：Delete（删除工作流）
# ====================


class TestWorkflowRepositoryDelete:
    """测试删除工作流功能"""

    def test_delete_existing_workflow_removes_workflow_and_children(
        self, workflow_repository: SQLAlchemyWorkflowRepository, session: Session
    ):
        """
        测试：delete应删除工作流及其所有子实体（级联删除）

        Given: 数据库中存在包含节点和边的工作流
        When: 调用delete并flush
        Then:
          - 工作流应被删除
          - 所有关联的节点应被删除
          - 所有关联的边应被删除
        """
        # Given: 创建包含子实体的工作流
        node_a = make_node(
            node_id="node_a",
            node_type=NodeType.START,
            name="开始",
            x=0,
            y=0,
        )
        node_b = make_node(
            node_id="node_b",
            node_type=NodeType.HTTP,
            name="HTTP",
            x=1,
            y=1,
        )
        edge_ab = make_edge(
            edge_id="edge_ab",
            source_node_id="node_a",
            target_node_id="node_b",
        )

        wf = make_workflow(
            workflow_id="wf_delete_test",
            name="待删除工作流",
            description="",
            nodes=[node_a, node_b],
            edges=[edge_ab],
        )
        workflow_repository.save(wf)
        session.flush()

        # Given: 验证子实体存在
        nodes_before = session.scalars(
            select(NodeModel).where(NodeModel.workflow_id == "wf_delete_test")
        ).all()
        edges_before = session.scalars(
            select(EdgeModel).where(EdgeModel.workflow_id == "wf_delete_test")
        ).all()
        assert len(nodes_before) == 2
        assert len(edges_before) == 1

        # When: 删除工作流
        workflow_repository.delete("wf_delete_test")
        session.flush()

        # Then: 验证工作流已删除
        assert workflow_repository.exists("wf_delete_test") is False
        assert workflow_repository.find_by_id("wf_delete_test") is None

        # Then: 验证子实体已被级联删除
        nodes_after = session.scalars(
            select(NodeModel).where(NodeModel.workflow_id == "wf_delete_test")
        ).all()
        edges_after = session.scalars(
            select(EdgeModel).where(EdgeModel.workflow_id == "wf_delete_test")
        ).all()
        assert nodes_after == []
        assert edges_after == []

    def test_delete_missing_is_idempotent(self, workflow_repository: SQLAlchemyWorkflowRepository):
        """
        测试：delete应是幂等的（删除不存在的工作流不抛异常）

        Given: 数据库中不存在指定ID的工作流
        When: 多次调用delete
        Then: 不应抛出异常
        """
        # When & Then: 多次删除不存在的工作流
        workflow_repository.delete("wf_nonexistent")
        workflow_repository.delete("wf_nonexistent")  # 第二次调用应无影响


# ====================
# 测试类：Timestamps（时区处理）
# ====================


class TestWorkflowRepositoryTimestamps:
    """测试时间戳时区处理功能"""

    def test_loaded_workflow_timestamps_are_utc_aware(
        self, workflow_repository: SQLAlchemyWorkflowRepository, session: Session
    ):
        """
        测试：加载的工作流时间戳应为UTC时区感知的datetime

        Given: 创建包含UTC时区感知时间戳的工作流
        When: 保存并重新加载
        Then:
          - 加载的时间戳应保持UTC时区信息
          - 时间值应与保存时一致
        """
        # Given
        created_at = datetime(2024, 6, 1, 10, 0, 0, tzinfo=UTC)
        updated_at = datetime(2024, 6, 1, 11, 0, 0, tzinfo=UTC)

        wf = make_workflow(
            workflow_id="wf_time_test",
            name="时区测试工作流",
            description="",
            nodes=[
                make_node(
                    node_id="node_t",
                    node_type=NodeType.START,
                    name="开始",
                    x=0,
                    y=0,
                )
            ],
            edges=[],
            created_at=created_at,
            updated_at=updated_at,
        )

        # When
        workflow_repository.save(wf)
        session.flush()

        loaded = workflow_repository.get_by_id("wf_time_test")

        # Then: 验证时区感知
        assert loaded.created_at.tzinfo is UTC
        assert loaded.updated_at.tzinfo is UTC

        # Then: 验证时间值
        assert loaded.created_at == created_at
        assert loaded.updated_at == updated_at
