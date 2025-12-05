"""测试 VaultRetriever（知识库检索器）- Step 5: 检索与监督整合

测试目标：
1. VaultRetriever 应该支持 fetch(query, limit_per_type) 方法
2. 加权评分：blocker > next_action > conclusion
3. 限制注入 ≤6 条
4. 记录 notes_injected 给 Coordinator
5. 不同类型得分排序正确
6. 超过配额时正确裁剪
"""

from src.domain.services.knowledge_note import (
    KnowledgeNote,
    NoteType,
)
from src.domain.services.knowledge_vault_retriever import (
    RetrievalResult,
    ScoredNote,
    VaultRetriever,
)


class TestVaultRetriever:
    """测试知识库检索器"""

    def test_create_vault_retriever_should_succeed(self):
        """测试：创建检索器应该成功"""
        retriever = VaultRetriever()

        assert retriever is not None
        assert hasattr(retriever, "fetch")

    def test_fetch_with_empty_vault_should_return_empty_list(self):
        """测试：空知识库检索应该返回空列表"""
        retriever = VaultRetriever()
        notes = []

        result = retriever.fetch(query="测试查询", notes=notes)

        assert isinstance(result, RetrievalResult)
        assert len(result.notes) == 0

    def test_fetch_should_return_relevant_notes(self):
        """测试：检索应该返回相关笔记"""
        retriever = VaultRetriever()
        notes = [
            KnowledgeNote.create(
                type=NoteType.BLOCKER,
                content="数据库连接失败",
                owner="user_123",
                tags=["database"],
            ),
            KnowledgeNote.create(
                type=NoteType.CONCLUSION,
                content="使用 PostgreSQL",
                owner="user_123",
                tags=["database"],
            ),
        ]

        result = retriever.fetch(query="database", notes=notes)

        assert len(result.notes) > 0

    def test_calculate_score_should_return_float(self):
        """测试：计算得分应该返回浮点数"""
        retriever = VaultRetriever()
        note = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="数据库连接失败",
            owner="user_123",
            tags=["database"],
        )

        score = retriever.calculate_score(note, query="database")

        assert isinstance(score, float)
        assert score >= 0.0

    def test_blocker_should_have_highest_weight(self):
        """测试：blocker 应该有最高权重"""
        retriever = VaultRetriever()

        blocker = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="测试内容",
            owner="user_123",
        )
        next_action = KnowledgeNote.create(
            type=NoteType.NEXT_ACTION,
            content="测试内容",
            owner="user_123",
        )
        conclusion = KnowledgeNote.create(
            type=NoteType.CONCLUSION,
            content="测试内容",
            owner="user_123",
        )

        blocker_score = retriever.calculate_score(blocker, query="测试")
        next_action_score = retriever.calculate_score(next_action, query="测试")
        conclusion_score = retriever.calculate_score(conclusion, query="测试")

        assert blocker_score > next_action_score
        assert next_action_score > conclusion_score

    def test_fetch_should_sort_by_score_descending(self):
        """测试：检索应该按得分降序排序"""
        retriever = VaultRetriever()
        notes = [
            KnowledgeNote.create(
                type=NoteType.CONCLUSION,
                content="结论：使用 PostgreSQL",
                owner="user_123",
                tags=["database"],
            ),
            KnowledgeNote.create(
                type=NoteType.BLOCKER,
                content="阻塞：数据库连接失败",
                owner="user_123",
                tags=["database"],
            ),
            KnowledgeNote.create(
                type=NoteType.NEXT_ACTION,
                content="计划：优化数据库查询",
                owner="user_123",
                tags=["database"],
            ),
        ]

        result = retriever.fetch(query="database", notes=notes)

        # blocker 应该排在第一位
        assert result.notes[0].type == NoteType.BLOCKER
        # next_action 应该排在第二位
        assert result.notes[1].type == NoteType.NEXT_ACTION
        # conclusion 应该排在第三位
        assert result.notes[2].type == NoteType.CONCLUSION

    def test_fetch_with_limit_per_type_should_respect_limit(self):
        """测试：fetch 应该尊重每种类型的限制"""
        retriever = VaultRetriever()
        notes = [
            KnowledgeNote.create(
                type=NoteType.BLOCKER,
                content=f"阻塞 {i}",
                owner="user_123",
                tags=["test"],
            )
            for i in range(5)
        ]

        result = retriever.fetch(query="test", notes=notes, limit_per_type=2)

        assert len(result.notes) <= 2

    def test_fetch_should_limit_total_injection_to_6(self):
        """测试：检索应该限制总注入数量为 6"""
        retriever = VaultRetriever()
        notes = [
            KnowledgeNote.create(
                type=NoteType.BLOCKER,
                content=f"笔记 {i}",
                owner="user_123",
                tags=["test"],
            )
            for i in range(10)
        ]

        result = retriever.fetch(query="test", notes=notes)

        assert len(result.notes) <= 6

    def test_fetch_should_prioritize_high_weight_types_when_limiting(self):
        """测试：限制时应该优先保留高权重类型"""
        retriever = VaultRetriever()
        notes = []

        # 创建多个不同类型的笔记
        for i in range(3):
            notes.append(
                KnowledgeNote.create(
                    type=NoteType.BLOCKER,
                    content=f"阻塞 {i}",
                    owner="user_123",
                    tags=["test"],
                )
            )
        for i in range(3):
            notes.append(
                KnowledgeNote.create(
                    type=NoteType.NEXT_ACTION,
                    content=f"计划 {i}",
                    owner="user_123",
                    tags=["test"],
                )
            )
        for i in range(3):
            notes.append(
                KnowledgeNote.create(
                    type=NoteType.CONCLUSION,
                    content=f"结论 {i}",
                    owner="user_123",
                    tags=["test"],
                )
            )

        result = retriever.fetch(query="test", notes=notes, max_total=6)

        # 应该优先包含 blocker
        blocker_count = sum(1 for n in result.notes if n.type == NoteType.BLOCKER)
        assert blocker_count >= 2

    def test_retrieval_result_should_contain_metadata(self):
        """测试：检索结果应该包含元数据"""
        retriever = VaultRetriever()
        notes = [
            KnowledgeNote.create(
                type=NoteType.BLOCKER,
                content="测试",
                owner="user_123",
            )
        ]

        result = retriever.fetch(query="test", notes=notes)

        assert hasattr(result, "notes")
        assert hasattr(result, "total_found")
        assert hasattr(result, "total_returned")
        assert hasattr(result, "query")

    def test_fetch_should_filter_by_approved_status(self):
        """测试：检索应该只返回已批准的笔记"""
        from src.domain.services.knowledge_note_lifecycle import NoteLifecycleManager

        retriever = VaultRetriever()
        lifecycle_manager = NoteLifecycleManager()

        # 创建已批准和未批准的笔记
        approved_note = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="已批准的笔记",
            owner="user_123",
            tags=["test"],
        )
        lifecycle_manager.submit_for_approval(approved_note)
        lifecycle_manager.approve_note(approved_note, approved_by="admin")

        draft_note = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="草稿笔记",
            owner="user_123",
            tags=["test"],
        )

        notes = [approved_note, draft_note]

        result = retriever.fetch(query="test", notes=notes, only_approved=True)

        # 应该只返回已批准的笔记
        assert len(result.notes) == 1
        assert result.notes[0].note_id == approved_note.note_id


class TestScoredNote:
    """测试评分笔记数据结构"""

    def test_create_scored_note_should_succeed(self):
        """测试：创建评分笔记应该成功"""
        note = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="测试",
            owner="user_123",
        )

        scored_note = ScoredNote(note=note, score=0.85)

        assert scored_note.note == note
        assert scored_note.score == 0.85

    def test_scored_notes_should_be_sortable(self):
        """测试：评分笔记应该可排序"""
        note1 = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="笔记1",
            owner="user_123",
        )
        note2 = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="笔记2",
            owner="user_123",
        )

        scored_notes = [
            ScoredNote(note=note1, score=0.5),
            ScoredNote(note=note2, score=0.9),
        ]

        sorted_notes = sorted(scored_notes, key=lambda x: x.score, reverse=True)

        assert sorted_notes[0].score == 0.9
        assert sorted_notes[1].score == 0.5


class TestRetrievalResult:
    """测试检索结果数据结构"""

    def test_create_retrieval_result_should_succeed(self):
        """测试：创建检索结果应该成功"""
        notes = [
            KnowledgeNote.create(
                type=NoteType.BLOCKER,
                content="测试",
                owner="user_123",
            )
        ]

        result = RetrievalResult(
            notes=notes,
            total_found=5,
            total_returned=1,
            query="test",
        )

        assert result.notes == notes
        assert result.total_found == 5
        assert result.total_returned == 1
        assert result.query == "test"

    def test_retrieval_result_should_have_metadata_dict(self):
        """测试：检索结果应该有元数据字典"""
        notes = []
        result = RetrievalResult(
            notes=notes,
            total_found=0,
            total_returned=0,
            query="test",
        )

        metadata = result.get_metadata()

        assert isinstance(metadata, dict)
        assert "total_found" in metadata
        assert "total_returned" in metadata
        assert "query" in metadata


class TestWeightedScoring:
    """测试加权评分机制"""

    def test_type_weights_should_be_defined(self):
        """测试：类型权重应该被定义"""
        retriever = VaultRetriever()

        assert hasattr(retriever, "TYPE_WEIGHTS")
        assert NoteType.BLOCKER in retriever.TYPE_WEIGHTS
        assert NoteType.NEXT_ACTION in retriever.TYPE_WEIGHTS
        assert NoteType.CONCLUSION in retriever.TYPE_WEIGHTS

    def test_blocker_weight_should_be_highest(self):
        """测试：blocker 权重应该最高"""
        retriever = VaultRetriever()

        blocker_weight = retriever.TYPE_WEIGHTS[NoteType.BLOCKER]
        next_action_weight = retriever.TYPE_WEIGHTS[NoteType.NEXT_ACTION]
        conclusion_weight = retriever.TYPE_WEIGHTS[NoteType.CONCLUSION]

        assert blocker_weight > next_action_weight
        assert next_action_weight > conclusion_weight

    def test_calculate_score_should_include_type_weight(self):
        """测试：计算得分应该包含类型权重"""
        retriever = VaultRetriever()

        blocker = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="相同内容",
            owner="user_123",
            tags=["test"],
        )
        conclusion = KnowledgeNote.create(
            type=NoteType.CONCLUSION,
            content="相同内容",
            owner="user_123",
            tags=["test"],
        )

        blocker_score = retriever.calculate_score(blocker, query="test")
        conclusion_score = retriever.calculate_score(conclusion, query="test")

        # 相同内容，blocker 得分应该更高
        assert blocker_score > conclusion_score

    def test_calculate_score_should_consider_relevance(self):
        """测试：计算得分应该考虑相关性"""
        retriever = VaultRetriever()

        highly_relevant = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="数据库连接失败 database connection error",
            owner="user_123",
            tags=["database", "error"],
        )
        less_relevant = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="其他问题",
            owner="user_123",
            tags=["other"],
        )

        high_score = retriever.calculate_score(highly_relevant, query="database")
        low_score = retriever.calculate_score(less_relevant, query="database")

        assert high_score > low_score


class TestInjectionLimit:
    """测试注入限制"""

    def test_limit_injection_should_respect_max_total(self):
        """测试：限制注入应该尊重最大总数"""
        retriever = VaultRetriever()
        notes = [
            KnowledgeNote.create(
                type=NoteType.BLOCKER,
                content=f"笔记 {i}",
                owner="user_123",
            )
            for i in range(10)
        ]

        limited = retriever.limit_injection(notes, max_total=6)

        assert len(limited) <= 6

    def test_limit_injection_should_preserve_order(self):
        """测试：限制注入应该保持顺序"""
        retriever = VaultRetriever()
        notes = [
            KnowledgeNote.create(
                type=NoteType.BLOCKER,
                content=f"笔记 {i}",
                owner="user_123",
            )
            for i in range(10)
        ]

        limited = retriever.limit_injection(notes, max_total=6)

        # 应该保留前 6 个
        assert len(limited) == 6
        for i in range(6):
            assert limited[i].content == f"笔记 {i}"
