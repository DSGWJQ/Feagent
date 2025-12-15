"""SQLiteKnowledgeRepository单元测试

测试范围:
1. KnowledgeBase: save, find_by_id, find_by_owner
2. Document: save, find_by_id, find_by_workflow_id, update, delete, count

测试原则:
- 使用真实的 SQLite 文件数据库 (tmp_path)
- 每个测试独立运行 (tmp_path per test)
- 测试实体 <-> 存储 的字段 round-trip
- 覆盖 JSON metadata 序列化/反序列化
- 覆盖异步执行路径

覆盖目标: 0% → 85-95% (P0 tests)
测试数量: 9 tests (P0)
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.domain.knowledge_base.entities.document import Document
from src.domain.knowledge_base.entities.knowledge_base import KnowledgeBase
from src.domain.value_objects.document_source import DocumentSource
from src.domain.value_objects.document_status import DocumentStatus
from src.domain.value_objects.knowledge_base_type import KnowledgeBaseType
from src.infrastructure.knowledge_base.sqlite_knowledge_repository import (
    SQLiteKnowledgeRepository,
)

# ====================
# Fixtures
# ====================


@pytest.fixture
def sqlite_db_path(tmp_path: Path) -> str:
    """创建临时SQLite数据库路径"""
    return str(tmp_path / "test_kb.db")


@pytest.fixture
async def repo(sqlite_db_path: str) -> SQLiteKnowledgeRepository:
    """创建SQLiteKnowledgeRepository实例"""
    return SQLiteKnowledgeRepository(db_path=sqlite_db_path)


# ====================
# Test data builders
# ====================


def make_knowledge_base(
    *,
    kb_id: str,
    name: str = "测试知识库",
    description: str = "用于测试的知识库",
    kb_type: KnowledgeBaseType = KnowledgeBaseType.SYSTEM,
    owner_id: str | None = "owner_001",
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> KnowledgeBase:
    """创建测试知识库（固定ID + 确定性时间戳）"""
    created_at = created_at or datetime(2025, 1, 1, 0, 0, 0)
    return KnowledgeBase(
        id=kb_id,
        name=name,
        description=description,
        type=kb_type,
        created_at=created_at,
        updated_at=updated_at,
        owner_id=owner_id,
    )


def make_document(
    *,
    doc_id: str,
    title: str = "测试文档",
    content: str = "用于测试的文档内容",
    source: DocumentSource = DocumentSource.UPLOAD,
    status: DocumentStatus = DocumentStatus.PENDING,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    metadata: dict | None = None,
    file_path: str | None = None,
    workflow_id: str | None = None,
) -> Document:
    """创建测试文档（固定ID + 确定性时间戳）"""
    created_at = created_at or datetime(2025, 2, 1, 12, 0, 0)
    return Document(
        id=doc_id,
        title=title,
        content=content,
        source=source,
        status=status,
        created_at=created_at,
        updated_at=updated_at,
        metadata=metadata,
        file_path=file_path,
        workflow_id=workflow_id,
    )


# ====================
# Test classes: KnowledgeBase
# ====================


class TestKnowledgeBaseOperations:
    """测试知识库操作"""

    @pytest.mark.asyncio
    async def test_save_and_find_knowledge_base_round_trip_all_fields(
        self, repo: SQLiteKnowledgeRepository
    ):
        """测试：保存并查找知识库应成功 round-trip 所有字段

        Given: 一个包含 owner_id/updated_at/type 等字段的 KnowledgeBase
        When: 调用 save_knowledge_base 后再 find_knowledge_base_by_id
        Then: 返回实体应与保存实体字段一致
        """
        # Given
        created_at = datetime(2025, 3, 1, 10, 0, 0, tzinfo=UTC).replace(tzinfo=None)
        updated_at = datetime(2025, 3, 2, 11, 30, 0, tzinfo=UTC).replace(tzinfo=None)
        kb = make_knowledge_base(
            kb_id="kb_round_trip",
            name="KB Round Trip",
            description="desc",
            kb_type=KnowledgeBaseType.WORKFLOW,
            owner_id="owner_abc",
            created_at=created_at,
            updated_at=updated_at,
        )

        # When
        await repo.save_knowledge_base(kb)
        loaded = await repo.find_knowledge_base_by_id("kb_round_trip")

        # Then
        assert loaded is not None
        assert loaded.id == "kb_round_trip"
        assert loaded.name == "KB Round Trip"
        assert loaded.description == "desc"
        assert loaded.type == KnowledgeBaseType.WORKFLOW
        assert loaded.owner_id == "owner_abc"
        assert loaded.created_at == created_at
        assert loaded.updated_at == updated_at

    @pytest.mark.asyncio
    async def test_find_knowledge_base_by_id_missing_returns_none(
        self, repo: SQLiteKnowledgeRepository
    ):
        """测试：查找不存在的知识库应返回 None

        Given: 数据库中不存在该知识库
        When: 调用 find_knowledge_base_by_id
        Then: 返回 None
        """
        # When
        loaded = await repo.find_knowledge_base_by_id("kb_missing")

        # Then
        assert loaded is None

    @pytest.mark.asyncio
    async def test_find_knowledge_bases_by_owner_returns_all_and_empty_when_none(
        self, repo: SQLiteKnowledgeRepository
    ):
        """测试：按所有者查找应返回所有匹配项，无匹配时返回空列表

        Given: owner_a 有2个KB，owner_b 有1个KB
        When: 分别查找 owner_a、owner_missing
        Then: owner_a 返回2个，owner_missing 返回空列表
        """
        # Given
        kb_a1 = make_knowledge_base(kb_id="kb_a1", owner_id="owner_a", name="A1")
        kb_a2 = make_knowledge_base(kb_id="kb_a2", owner_id="owner_a", name="A2")
        kb_b1 = make_knowledge_base(kb_id="kb_b1", owner_id="owner_b", name="B1")

        await repo.save_knowledge_base(kb_a1)
        await repo.save_knowledge_base(kb_a2)
        await repo.save_knowledge_base(kb_b1)

        # When
        owner_a_kbs = await repo.find_knowledge_bases_by_owner("owner_a")
        owner_missing_kbs = await repo.find_knowledge_bases_by_owner("owner_missing")

        # Then
        assert {kb.id for kb in owner_a_kbs} == {"kb_a1", "kb_a2"}
        assert owner_missing_kbs == []


# ====================
# Test classes: Document
# ====================


class TestDocumentOperations:
    """测试文档操作"""

    @pytest.mark.asyncio
    async def test_save_and_find_document_round_trip_with_metadata_and_optionals(
        self, repo: SQLiteKnowledgeRepository
    ):
        """测试：保存并查找文档应成功 round-trip（含 metadata 和可选字段）

        Given: 一个包含 metadata/file_path/workflow_id 的 Document
        When: 调用 save_document 后再 find_document_by_id
        Then: 返回实体字段应与保存一致（含 metadata JSON round-trip）
        """
        # Given
        created_at = datetime(2025, 4, 1, 9, 0, 0)
        updated_at = datetime(2025, 4, 1, 10, 0, 0)
        doc = make_document(
            doc_id="doc_round_trip",
            title="Doc Round Trip",
            content="hello",
            source=DocumentSource.URL,
            status=DocumentStatus.PROCESSING,
            created_at=created_at,
            updated_at=updated_at,
            metadata={"k": "v", "n": 1},
            file_path="/tmp/doc.md",
            workflow_id="wf_001",
        )

        # When
        await repo.save_document(doc)
        loaded = await repo.find_document_by_id("doc_round_trip")

        # Then
        assert loaded is not None
        assert loaded.id == "doc_round_trip"
        assert loaded.title == "Doc Round Trip"
        assert loaded.content == "hello"
        assert loaded.source == DocumentSource.URL
        assert loaded.status == DocumentStatus.PROCESSING
        assert loaded.created_at == created_at
        assert loaded.updated_at == updated_at
        assert loaded.metadata == {"k": "v", "n": 1}
        assert loaded.file_path == "/tmp/doc.md"
        assert loaded.workflow_id == "wf_001"

    @pytest.mark.asyncio
    async def test_find_document_by_id_missing_returns_none(self, repo: SQLiteKnowledgeRepository):
        """测试：查找不存在的文档应返回 None

        Given: 数据库中不存在该文档
        When: 调用 find_document_by_id
        Then: 返回 None
        """
        # When
        loaded = await repo.find_document_by_id("doc_missing")

        # Then
        assert loaded is None

    @pytest.mark.asyncio
    async def test_find_documents_by_workflow_id_returns_only_matching(
        self, repo: SQLiteKnowledgeRepository
    ):
        """测试：按 workflow_id 查找应只返回匹配的文档

        Given: wf_1 有2个文档，wf_2 有1个文档，还有1个文档 workflow_id=None
        When: 调用 find_documents_by_workflow_id("wf_1")
        Then: 只返回 wf_1 的2个文档
        """
        # Given
        doc_wf1_a = make_document(doc_id="doc_wf1_a", workflow_id="wf_1", title="A")
        doc_wf1_b = make_document(doc_id="doc_wf1_b", workflow_id="wf_1", title="B")
        doc_wf2 = make_document(doc_id="doc_wf2", workflow_id="wf_2", title="C")
        doc_none = make_document(doc_id="doc_none", workflow_id=None, title="D")

        await repo.save_document(doc_wf1_a)
        await repo.save_document(doc_wf1_b)
        await repo.save_document(doc_wf2)
        await repo.save_document(doc_none)

        # When
        wf1_docs = await repo.find_documents_by_workflow_id("wf_1")

        # Then
        assert {d.id for d in wf1_docs} == {"doc_wf1_a", "doc_wf1_b"}
        assert all(d.workflow_id == "wf_1" for d in wf1_docs)

    @pytest.mark.asyncio
    async def test_update_document_overwrites_existing_row(self, repo: SQLiteKnowledgeRepository):
        """测试：update_document 应覆盖已存在的记录（REPLACE语义）

        Given: 已保存一条 Document（doc_id相同）
        When: 修改字段后调用 update_document，再次加载
        Then: 加载结果应反映最新字段值
        """
        # Given
        original = make_document(
            doc_id="doc_update",
            title="Old",
            content="old content",
            source=DocumentSource.UPLOAD,
            status=DocumentStatus.PENDING,
            created_at=datetime(2025, 5, 1, 0, 0, 0),
            updated_at=None,
            metadata={"v": 1},
            workflow_id="wf_u",
        )
        await repo.save_document(original)

        updated = make_document(
            doc_id="doc_update",
            title="New",
            content="new content",
            source=DocumentSource.URL,
            status=DocumentStatus.PROCESSED,
            created_at=original.created_at,
            updated_at=datetime(2025, 5, 2, 0, 0, 0),
            metadata={"v": 2, "extra": True},
            workflow_id="wf_u",
            file_path="/path/new.txt",
        )

        # When
        await repo.update_document(updated)
        loaded = await repo.find_document_by_id("doc_update")

        # Then
        assert loaded is not None
        assert loaded.title == "New"
        assert loaded.content == "new content"
        assert loaded.source == DocumentSource.URL
        assert loaded.status == DocumentStatus.PROCESSED
        assert loaded.updated_at == datetime(2025, 5, 2, 0, 0, 0)
        assert loaded.metadata == {"v": 2, "extra": True}
        assert loaded.file_path == "/path/new.txt"
        assert loaded.workflow_id == "wf_u"

    @pytest.mark.asyncio
    async def test_delete_document_is_idempotent_and_removes_row(
        self, repo: SQLiteKnowledgeRepository
    ):
        """测试：delete_document 应删除记录，且在表存在前提下对缺失记录幂等

        Given: 已保存一条 Document
        When: 连续两次调用 delete_document，再查找该文档
        Then: 查找返回 None 且不抛异常
        """
        # Given
        doc = make_document(doc_id="doc_delete", workflow_id="wf_d")
        await repo.save_document(doc)

        # When
        await repo.delete_document("doc_delete")
        await repo.delete_document("doc_delete")
        loaded = await repo.find_document_by_id("doc_delete")

        # Then
        assert loaded is None


class TestDocumentCount:
    """测试文档计数功能"""

    @pytest.mark.asyncio
    async def test_count_documents_by_workflow_returns_correct_counts(
        self, repo: SQLiteKnowledgeRepository
    ):
        """测试：count_documents_by_workflow 应返回正确计数

        Given: wf1 有2个文档，wf2 有1个文档
        When: 分别调用 count_documents_by_workflow(wf1/wf2/missing)
        Then: 返回 2 / 1 / 0
        """
        # Given
        await repo.save_document(make_document(doc_id="doc_c1", workflow_id="wf1"))
        await repo.save_document(make_document(doc_id="doc_c2", workflow_id="wf1"))
        await repo.save_document(make_document(doc_id="doc_c3", workflow_id="wf2"))

        # When
        wf1_count = await repo.count_documents_by_workflow("wf1")
        wf2_count = await repo.count_documents_by_workflow("wf2")
        missing_count = await repo.count_documents_by_workflow("wf_missing")

        # Then
        assert wf1_count == 2
        assert wf2_count == 1
        assert missing_count == 0
