"""测试：知识引用数据结构 - Phase 5 阶段1

测试目标：
1. KnowledgeReference 数据结构定义
2. KnowledgeReference 可序列化/反序列化
3. KnowledgeReferences 集合管理
4. CompressedContext 扩展第9段 knowledge_references

完成标准：
- KnowledgeReference 包含 source_id, title, content_preview, relevance_score, retrieved_at
- 支持 to_dict / from_dict 序列化
- CompressedContext.knowledge_references 字段可用
- to_summary_text 包含知识引用摘要

"""


# ==================== 测试1：KnowledgeReference 基础结构 ====================


class TestKnowledgeReferenceBasics:
    """测试 KnowledgeReference 基础功能"""

    def test_create_knowledge_reference_with_all_fields(self):
        """创建包含所有字段的 KnowledgeReference"""
        from src.domain.services.knowledge_reference import KnowledgeReference

        ref = KnowledgeReference(
            source_id="doc_001",
            title="Python 最佳实践",
            content_preview="使用 dataclass 定义数据结构...",
            relevance_score=0.95,
            document_id="kb_doc_001",
            chunk_id="chunk_001",
            source_type="knowledge_base",
        )

        assert ref.source_id == "doc_001"
        assert ref.title == "Python 最佳实践"
        assert ref.content_preview == "使用 dataclass 定义数据结构..."
        assert ref.relevance_score == 0.95
        assert ref.document_id == "kb_doc_001"
        assert ref.chunk_id == "chunk_001"
        assert ref.source_type == "knowledge_base"
        assert ref.retrieved_at is not None

    def test_create_knowledge_reference_with_defaults(self):
        """创建使用默认值的 KnowledgeReference"""
        from src.domain.services.knowledge_reference import KnowledgeReference

        ref = KnowledgeReference(
            source_id="doc_002",
            title="错误处理",
            content_preview="异常处理最佳实践...",
            relevance_score=0.8,
        )

        assert ref.source_id == "doc_002"
        assert ref.document_id is None
        assert ref.chunk_id is None
        assert ref.source_type == "unknown"
        assert ref.metadata == {}

    def test_knowledge_reference_to_dict(self):
        """KnowledgeReference 序列化为字典"""
        from src.domain.services.knowledge_reference import KnowledgeReference

        ref = KnowledgeReference(
            source_id="doc_001",
            title="测试文档",
            content_preview="这是预览内容",
            relevance_score=0.9,
            document_id="kb_001",
        )

        data = ref.to_dict()

        assert data["source_id"] == "doc_001"
        assert data["title"] == "测试文档"
        assert data["content_preview"] == "这是预览内容"
        assert data["relevance_score"] == 0.9
        assert data["document_id"] == "kb_001"
        assert "retrieved_at" in data

    def test_knowledge_reference_from_dict(self):
        """从字典反序列化 KnowledgeReference"""
        from src.domain.services.knowledge_reference import KnowledgeReference

        data = {
            "source_id": "doc_003",
            "title": "反序列化测试",
            "content_preview": "内容预览",
            "relevance_score": 0.75,
            "document_id": "kb_003",
            "source_type": "rag",
            "retrieved_at": "2024-01-15T10:30:00",
        }

        ref = KnowledgeReference.from_dict(data)

        assert ref.source_id == "doc_003"
        assert ref.title == "反序列化测试"
        assert ref.relevance_score == 0.75
        assert ref.source_type == "rag"

    def test_knowledge_reference_with_metadata(self):
        """KnowledgeReference 支持元数据"""
        from src.domain.services.knowledge_reference import KnowledgeReference

        ref = KnowledgeReference(
            source_id="doc_004",
            title="带元数据",
            content_preview="预览",
            relevance_score=0.85,
            metadata={
                "workflow_id": "wf_001",
                "category": "error_handling",
                "tags": ["python", "exceptions"],
            },
        )

        assert ref.metadata["workflow_id"] == "wf_001"
        assert ref.metadata["category"] == "error_handling"
        assert "python" in ref.metadata["tags"]


# ==================== 测试2：KnowledgeReferences 集合管理 ====================


class TestKnowledgeReferencesCollection:
    """测试 KnowledgeReferences 集合"""

    def test_create_empty_collection(self):
        """创建空集合"""
        from src.domain.services.knowledge_reference import KnowledgeReferences

        refs = KnowledgeReferences()

        assert len(refs) == 0
        assert refs.is_empty()

    def test_add_reference_to_collection(self):
        """向集合添加引用"""
        from src.domain.services.knowledge_reference import (
            KnowledgeReference,
            KnowledgeReferences,
        )

        refs = KnowledgeReferences()
        ref = KnowledgeReference(
            source_id="doc_001",
            title="测试",
            content_preview="预览",
            relevance_score=0.9,
        )

        refs.add(ref)

        assert len(refs) == 1
        assert not refs.is_empty()

    def test_add_multiple_references(self):
        """添加多个引用"""
        from src.domain.services.knowledge_reference import (
            KnowledgeReference,
            KnowledgeReferences,
        )

        refs = KnowledgeReferences()

        for i in range(3):
            ref = KnowledgeReference(
                source_id=f"doc_{i}",
                title=f"文档{i}",
                content_preview=f"预览{i}",
                relevance_score=0.9 - i * 0.1,
            )
            refs.add(ref)

        assert len(refs) == 3

    def test_get_top_references_by_relevance(self):
        """按相关度获取前N个引用"""
        from src.domain.services.knowledge_reference import (
            KnowledgeReference,
            KnowledgeReferences,
        )

        refs = KnowledgeReferences()

        # 添加不同相关度的引用
        refs.add(KnowledgeReference("d1", "低", "内容", 0.5))
        refs.add(KnowledgeReference("d2", "高", "内容", 0.9))
        refs.add(KnowledgeReference("d3", "中", "内容", 0.7))

        top_2 = refs.get_top(2)

        assert len(top_2) == 2
        assert top_2[0].relevance_score >= top_2[1].relevance_score
        assert top_2[0].title == "高"

    def test_collection_to_list(self):
        """集合转换为列表"""
        from src.domain.services.knowledge_reference import (
            KnowledgeReference,
            KnowledgeReferences,
        )

        refs = KnowledgeReferences()
        refs.add(KnowledgeReference("d1", "T1", "P1", 0.8))
        refs.add(KnowledgeReference("d2", "T2", "P2", 0.7))

        ref_list = refs.to_list()

        assert len(ref_list) == 2
        assert all(isinstance(r, KnowledgeReference) for r in ref_list)

    def test_collection_to_dict_list(self):
        """集合序列化为字典列表"""
        from src.domain.services.knowledge_reference import (
            KnowledgeReference,
            KnowledgeReferences,
        )

        refs = KnowledgeReferences()
        refs.add(KnowledgeReference("d1", "T1", "P1", 0.8))

        dict_list = refs.to_dict_list()

        assert len(dict_list) == 1
        assert dict_list[0]["source_id"] == "d1"
        assert dict_list[0]["title"] == "T1"

    def test_create_collection_from_dict_list(self):
        """从字典列表创建集合"""
        from src.domain.services.knowledge_reference import KnowledgeReferences

        data = [
            {"source_id": "d1", "title": "T1", "content_preview": "P1", "relevance_score": 0.8},
            {"source_id": "d2", "title": "T2", "content_preview": "P2", "relevance_score": 0.7},
        ]

        refs = KnowledgeReferences.from_dict_list(data)

        assert len(refs) == 2

    def test_filter_by_source_type(self):
        """按来源类型过滤"""
        from src.domain.services.knowledge_reference import (
            KnowledgeReference,
            KnowledgeReferences,
        )

        refs = KnowledgeReferences()
        refs.add(KnowledgeReference("d1", "T1", "P1", 0.8, source_type="knowledge_base"))
        refs.add(KnowledgeReference("d2", "T2", "P2", 0.7, source_type="error_doc"))
        refs.add(KnowledgeReference("d3", "T3", "P3", 0.6, source_type="knowledge_base"))

        kb_refs = refs.filter_by_source_type("knowledge_base")

        assert len(kb_refs) == 2

    def test_get_summary_text(self):
        """获取引用摘要文本"""
        from src.domain.services.knowledge_reference import (
            KnowledgeReference,
            KnowledgeReferences,
        )

        refs = KnowledgeReferences()
        refs.add(KnowledgeReference("d1", "Python教程", "基础语法...", 0.9))
        refs.add(KnowledgeReference("d2", "错误处理", "异常捕获...", 0.85))

        summary = refs.get_summary_text()

        assert "Python教程" in summary
        assert "错误处理" in summary
        assert "0.9" in summary or "90%" in summary


# ==================== 测试3：CompressedContext 扩展 ====================


class TestCompressedContextKnowledgeExtension:
    """测试 CompressedContext 知识引用扩展"""

    def test_compressed_context_has_knowledge_references_field(self):
        """CompressedContext 包含 knowledge_references 字段"""
        from src.domain.services.context_compressor import CompressedContext

        ctx = CompressedContext(workflow_id="wf_001")

        # 验证字段存在
        assert hasattr(ctx, "knowledge_references")
        assert ctx.knowledge_references == []

    def test_compressed_context_with_knowledge_references(self):
        """创建包含知识引用的 CompressedContext"""
        from src.domain.services.context_compressor import CompressedContext

        refs = [
            {
                "source_id": "doc_001",
                "title": "Python 指南",
                "content_preview": "使用 dataclass...",
                "relevance_score": 0.9,
            }
        ]

        ctx = CompressedContext(
            workflow_id="wf_001",
            task_goal="实现数据结构",
            knowledge_references=refs,
        )

        assert len(ctx.knowledge_references) == 1
        assert ctx.knowledge_references[0]["title"] == "Python 指南"

    def test_compressed_context_to_dict_includes_knowledge(self):
        """to_dict 包含 knowledge_references"""
        from src.domain.services.context_compressor import CompressedContext

        ctx = CompressedContext(
            workflow_id="wf_001",
            knowledge_references=[{"source_id": "d1", "title": "T1", "relevance_score": 0.8}],
        )

        data = ctx.to_dict()

        assert "knowledge_references" in data
        assert len(data["knowledge_references"]) == 1

    def test_compressed_context_from_dict_restores_knowledge(self):
        """from_dict 恢复 knowledge_references"""
        from src.domain.services.context_compressor import CompressedContext

        data = {
            "workflow_id": "wf_002",
            "knowledge_references": [
                {"source_id": "d1", "title": "恢复测试", "relevance_score": 0.7}
            ],
        }

        ctx = CompressedContext.from_dict(data)

        assert len(ctx.knowledge_references) == 1
        assert ctx.knowledge_references[0]["title"] == "恢复测试"

    def test_to_summary_text_includes_knowledge_count(self):
        """to_summary_text 包含知识引用数量"""
        from src.domain.services.context_compressor import CompressedContext

        ctx = CompressedContext(
            workflow_id="wf_001",
            task_goal="测试目标",
            knowledge_references=[
                {"source_id": "d1", "title": "T1", "relevance_score": 0.9},
                {"source_id": "d2", "title": "T2", "relevance_score": 0.8},
            ],
        )

        summary = ctx.to_summary_text()

        # 应包含知识引用信息
        assert "知识" in summary or "引用" in summary or "2" in summary


# ==================== 测试4：知识引用创建工厂 ====================


class TestKnowledgeReferenceFactory:
    """测试知识引用创建工厂方法"""

    def test_create_from_rag_result(self):
        """从 RAG 结果创建引用"""
        from src.domain.services.knowledge_reference import KnowledgeReference

        # 模拟 RAG 结果格式
        rag_source = {
            "document_id": "doc_123",
            "title": "API 设计原则",
            "source": "knowledge_base",
            "relevance_score": 0.92,
            "preview": "REST API 应该遵循...",
        }

        ref = KnowledgeReference.from_rag_source(rag_source)

        assert ref.document_id == "doc_123"
        assert ref.title == "API 设计原则"
        assert ref.relevance_score == 0.92
        assert ref.source_type == "knowledge_base"

    def test_create_from_error_context(self):
        """从错误上下文创建引用"""
        from src.domain.services.knowledge_reference import KnowledgeReference

        # 模拟错误相关的知识
        error_doc = {
            "error_type": "TimeoutError",
            "solution_title": "超时处理方案",
            "solution_preview": "增加重试机制...",
            "confidence": 0.85,
        }

        ref = KnowledgeReference.from_error_doc(error_doc)

        assert ref.title == "超时处理方案"
        assert ref.source_type == "error_solution"
        assert ref.relevance_score == 0.85

    def test_create_from_goal_context(self):
        """从目标上下文创建引用"""
        from src.domain.services.knowledge_reference import KnowledgeReference

        # 模拟目标相关的知识
        goal_doc = {
            "goal_keyword": "数据处理",
            "related_doc_id": "doc_456",
            "doc_title": "数据管道最佳实践",
            "preview": "使用 ETL 模式...",
            "match_score": 0.88,
        }

        ref = KnowledgeReference.from_goal_doc(goal_doc)

        assert ref.document_id == "doc_456"
        assert ref.title == "数据管道最佳实践"
        assert ref.source_type == "goal_related"
        assert ref.relevance_score == 0.88


# ==================== 测试5：知识引用去重和合并 ====================


class TestKnowledgeReferenceDeduplication:
    """测试知识引用去重和合并"""

    def test_deduplicate_by_source_id(self):
        """按 source_id 去重"""
        from src.domain.services.knowledge_reference import (
            KnowledgeReference,
            KnowledgeReferences,
        )

        refs = KnowledgeReferences()
        refs.add(KnowledgeReference("d1", "T1", "P1", 0.9))
        refs.add(KnowledgeReference("d1", "T1-更新", "P1-新", 0.95))  # 重复 source_id
        refs.add(KnowledgeReference("d2", "T2", "P2", 0.8))

        deduped = refs.deduplicate()

        assert len(deduped) == 2
        # 应保留相关度更高的版本
        d1_ref = next(r for r in deduped.to_list() if r.source_id == "d1")
        assert d1_ref.relevance_score == 0.95

    def test_merge_two_collections(self):
        """合并两个集合"""
        from src.domain.services.knowledge_reference import (
            KnowledgeReference,
            KnowledgeReferences,
        )

        refs1 = KnowledgeReferences()
        refs1.add(KnowledgeReference("d1", "T1", "P1", 0.9))

        refs2 = KnowledgeReferences()
        refs2.add(KnowledgeReference("d2", "T2", "P2", 0.8))
        refs2.add(KnowledgeReference("d3", "T3", "P3", 0.7))

        merged = refs1.merge(refs2)

        assert len(merged) == 3

    def test_merge_with_deduplication(self):
        """合并时自动去重"""
        from src.domain.services.knowledge_reference import (
            KnowledgeReference,
            KnowledgeReferences,
        )

        refs1 = KnowledgeReferences()
        refs1.add(KnowledgeReference("d1", "T1", "P1", 0.8))

        refs2 = KnowledgeReferences()
        refs2.add(KnowledgeReference("d1", "T1-新", "P1-新", 0.9))  # 重复
        refs2.add(KnowledgeReference("d2", "T2", "P2", 0.7))

        merged = refs1.merge(refs2, deduplicate=True)

        assert len(merged) == 2
        # 验证 d1 使用了更高分数的版本
        d1_ref = next(r for r in merged.to_list() if r.source_id == "d1")
        assert d1_ref.relevance_score == 0.9


# 导出
__all__ = [
    "TestKnowledgeReferenceBasics",
    "TestKnowledgeReferencesCollection",
    "TestCompressedContextKnowledgeExtension",
    "TestKnowledgeReferenceFactory",
    "TestKnowledgeReferenceDeduplication",
]
