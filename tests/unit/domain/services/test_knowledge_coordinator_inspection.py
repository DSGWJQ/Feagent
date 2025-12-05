"""测试协调者知识库巡检 - Step 4: 长期知识库治理

测试目标：
1. 协调者定期巡检 blocker 笔记
2. 将已解决的 blocker 转为 conclusion
3. 更新或归档过期的 next_action 计划
4. 巡检任务可在模拟数据上运行
5. 记录巡检操作到审计日志
"""

from datetime import datetime, timedelta

from src.domain.services.knowledge_audit_log import AuditLogManager
from src.domain.services.knowledge_coordinator_inspector import (
    CoordinatorInspector,
    InspectionAction,
    InspectionResult,
)
from src.domain.services.knowledge_note import (
    KnowledgeNote,
    NoteStatus,
    NoteType,
)
from src.domain.services.knowledge_note_lifecycle import NoteLifecycleManager


class TestCoordinatorInspector:
    """测试协调者巡检器"""

    def test_inspect_blocker_should_identify_resolved_blockers(self):
        """测试：巡检 blocker 应该识别已解决的阻塞"""
        # 创建一个已解决的 blocker
        blocker = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="数据库连接失败 - 已解决：配置了正确的连接字符串",
            owner="user_123",
            tags=["database", "resolved"],
        )

        inspector = CoordinatorInspector()
        result = inspector.inspect_blocker(blocker)

        assert result.action == InspectionAction.CONVERT_TO_CONCLUSION
        assert result.note_id == blocker.note_id
        assert result.reason is not None

    def test_inspect_blocker_should_keep_unresolved_blockers(self):
        """测试：巡检 blocker 应该保留未解决的阻塞"""
        blocker = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="API 限流问题 - 正在联系供应商",
            owner="user_123",
            tags=["api", "pending"],
        )

        inspector = CoordinatorInspector()
        result = inspector.inspect_blocker(blocker)

        assert result.action == InspectionAction.KEEP
        assert result.note_id == blocker.note_id

    def test_convert_blocker_to_conclusion_should_create_new_conclusion_note(self):
        """测试：将 blocker 转为 conclusion 应该创建新的结论笔记"""
        blocker = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="数据库连接失败 - 已解决：配置了正确的连接字符串",
            owner="user_123",
            tags=["database", "resolved"],
        )

        inspector = CoordinatorInspector()
        lifecycle_manager = NoteLifecycleManager()

        # 批准 blocker
        lifecycle_manager.submit_for_approval(blocker)
        lifecycle_manager.approve_note(blocker, approved_by="admin_456")

        # 转换为 conclusion
        conclusion = inspector.convert_blocker_to_conclusion(blocker)

        assert conclusion.type == NoteType.CONCLUSION
        assert conclusion.status == NoteStatus.DRAFT
        assert "已解决" in conclusion.content or "解决" in conclusion.content
        assert conclusion.owner == blocker.owner
        assert "database" in conclusion.tags

    def test_inspect_next_action_should_identify_expired_plans(self):
        """测试：巡检 next_action 应该识别过期计划"""
        # 创建一个过期的 next_action（创建时间超过 30 天）
        old_action = KnowledgeNote.create(
            type=NoteType.NEXT_ACTION,
            content="完成用户认证模块",
            owner="user_123",
            tags=["authentication"],
        )
        # 模拟旧的创建时间
        old_action.created_at = datetime.now() - timedelta(days=35)

        inspector = CoordinatorInspector()
        result = inspector.inspect_next_action(old_action)

        assert result.action in [InspectionAction.ARCHIVE, InspectionAction.UPDATE]
        assert result.note_id == old_action.note_id

    def test_inspect_next_action_should_keep_recent_plans(self):
        """测试：巡检 next_action 应该保留最近的计划"""
        recent_action = KnowledgeNote.create(
            type=NoteType.NEXT_ACTION,
            content="实现支付功能",
            owner="user_123",
            tags=["payment"],
        )

        inspector = CoordinatorInspector()
        result = inspector.inspect_next_action(recent_action)

        assert result.action == InspectionAction.KEEP
        assert result.note_id == recent_action.note_id

    def test_archive_expired_plan_should_change_status_to_archived(self):
        """测试：归档过期计划应该将状态改为 archived"""
        old_action = KnowledgeNote.create(
            type=NoteType.NEXT_ACTION,
            content="完成用户认证模块",
            owner="user_123",
        )
        old_action.created_at = datetime.now() - timedelta(days=35)

        inspector = CoordinatorInspector()
        lifecycle_manager = NoteLifecycleManager()

        # 批准 action
        lifecycle_manager.submit_for_approval(old_action)
        lifecycle_manager.approve_note(old_action, approved_by="admin_456")

        # 归档
        inspector.archive_expired_plan(old_action, lifecycle_manager)

        assert old_action.status == NoteStatus.ARCHIVED

    def test_inspect_all_notes_should_return_inspection_results(self):
        """测试：巡检所有笔记应该返回巡检结果"""
        notes = [
            KnowledgeNote.create(
                type=NoteType.BLOCKER,
                content="问题已解决",
                owner="user_123",
                tags=["resolved"],
            ),
            KnowledgeNote.create(
                type=NoteType.BLOCKER,
                content="问题未解决",
                owner="user_123",
                tags=["pending"],
            ),
            KnowledgeNote.create(
                type=NoteType.NEXT_ACTION,
                content="新计划",
                owner="user_123",
            ),
        ]

        inspector = CoordinatorInspector()
        results = inspector.inspect_all_notes(notes)

        assert len(results) == 3
        assert any(r.action == InspectionAction.CONVERT_TO_CONCLUSION for r in results)
        assert any(r.action == InspectionAction.KEEP for r in results)

    def test_execute_inspection_actions_should_apply_all_actions(self):
        """测试：执行巡检操作应该应用所有操作"""
        blocker = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="数据库连接失败 - 已解决",
            owner="user_123",
            tags=["database", "resolved"],
        )

        inspector = CoordinatorInspector()
        lifecycle_manager = NoteLifecycleManager()
        audit_manager = AuditLogManager()

        # 批准 blocker
        lifecycle_manager.submit_for_approval(blocker)
        lifecycle_manager.approve_note(blocker, approved_by="admin_456")

        # 巡检
        result = inspector.inspect_blocker(blocker)

        # 创建笔记映射
        notes_map = {blocker.note_id: blocker}

        # 执行操作
        new_notes = inspector.execute_inspection_actions(
            [result], lifecycle_manager, audit_manager, notes_map
        )

        assert len(new_notes) == 1
        assert new_notes[0].type == NoteType.CONCLUSION

    def test_inspection_should_record_audit_log(self):
        """测试：巡检应该记录审计日志"""
        blocker = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="问题已解决",
            owner="user_123",
            tags=["resolved"],
        )

        inspector = CoordinatorInspector()
        lifecycle_manager = NoteLifecycleManager()
        audit_manager = AuditLogManager()

        # 批准 blocker
        lifecycle_manager.submit_for_approval(blocker)
        lifecycle_manager.approve_note(blocker, approved_by="admin_456")
        audit_manager.log_note_approval(blocker, approved_by="admin_456")

        # 巡检并执行
        result = inspector.inspect_blocker(blocker)
        inspector.execute_inspection_actions([result], lifecycle_manager, audit_manager)

        # 验证审计日志
        logs = audit_manager.get_all_logs()
        assert len(logs) > 0

    def test_is_blocker_resolved_should_detect_resolution_keywords(self):
        """测试：is_blocker_resolved 应该检测解决关键词"""
        inspector = CoordinatorInspector()

        resolved_contents = [
            "问题已解决：配置了正确的参数",
            "已修复：更新了依赖版本",
            "解决方案：使用了新的 API",
            "完成：实现了备用方案",
        ]

        for content in resolved_contents:
            blocker = KnowledgeNote.create(
                type=NoteType.BLOCKER,
                content=content,
                owner="user_123",
            )
            assert inspector.is_blocker_resolved(blocker) is True

    def test_is_blocker_resolved_should_detect_resolved_tag(self):
        """测试：is_blocker_resolved 应该检测 resolved 标签"""
        inspector = CoordinatorInspector()

        blocker = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="数据库连接问题",
            owner="user_123",
            tags=["database", "resolved"],
        )

        assert inspector.is_blocker_resolved(blocker) is True

    def test_is_plan_expired_should_detect_old_plans(self):
        """测试：is_plan_expired 应该检测过期计划"""
        inspector = CoordinatorInspector()

        old_action = KnowledgeNote.create(
            type=NoteType.NEXT_ACTION,
            content="完成任务",
            owner="user_123",
        )
        old_action.created_at = datetime.now() - timedelta(days=35)

        assert inspector.is_plan_expired(old_action, days=30) is True

    def test_is_plan_expired_should_keep_recent_plans(self):
        """测试：is_plan_expired 应该保留最近的计划"""
        inspector = CoordinatorInspector()

        recent_action = KnowledgeNote.create(
            type=NoteType.NEXT_ACTION,
            content="完成任务",
            owner="user_123",
        )

        assert inspector.is_plan_expired(recent_action, days=30) is False

    def test_get_inspection_summary_should_return_statistics(self):
        """测试：获取巡检摘要应该返回统计信息"""
        notes = [
            KnowledgeNote.create(
                type=NoteType.BLOCKER,
                content="问题已解决",
                owner="user_123",
                tags=["resolved"],
            ),
            KnowledgeNote.create(
                type=NoteType.BLOCKER,
                content="问题未解决",
                owner="user_123",
            ),
            KnowledgeNote.create(
                type=NoteType.NEXT_ACTION,
                content="新计划",
                owner="user_123",
            ),
        ]

        inspector = CoordinatorInspector()
        results = inspector.inspect_all_notes(notes)
        summary = inspector.get_inspection_summary(results)

        assert "total_inspected" in summary
        assert "actions_to_convert" in summary
        assert "actions_to_archive" in summary
        assert "actions_to_keep" in summary
        assert summary["total_inspected"] == 3


class TestInspectionResult:
    """测试巡检结果数据结构"""

    def test_create_inspection_result_should_succeed(self):
        """测试：创建巡检结果应该成功"""
        result = InspectionResult(
            note_id="note_001",
            action=InspectionAction.CONVERT_TO_CONCLUSION,
            reason="Blocker 已解决",
        )

        assert result.note_id == "note_001"
        assert result.action == InspectionAction.CONVERT_TO_CONCLUSION
        assert result.reason == "Blocker 已解决"

    def test_inspection_action_should_have_all_actions(self):
        """测试：InspectionAction 应该包含所有操作类型"""
        actions = list(InspectionAction)

        assert InspectionAction.KEEP in actions
        assert InspectionAction.CONVERT_TO_CONCLUSION in actions
        assert InspectionAction.ARCHIVE in actions
        assert InspectionAction.UPDATE in actions


class TestInspectionIntegration:
    """测试巡检与其他组件的集成"""

    def test_complete_inspection_workflow_should_succeed(self):
        """测试：完整的巡检工作流应该成功"""
        # 创建测试数据
        blocker1 = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="数据库连接失败 - 已解决：配置了正确的连接字符串",
            owner="user_123",
            tags=["database", "resolved"],
        )
        blocker2 = KnowledgeNote.create(
            type=NoteType.BLOCKER,
            content="API 限流问题 - 正在处理",
            owner="user_123",
            tags=["api"],
        )

        # 初始化组件
        inspector = CoordinatorInspector()
        lifecycle_manager = NoteLifecycleManager()
        audit_manager = AuditLogManager()

        # 批准笔记
        for blocker in [blocker1, blocker2]:
            audit_manager.log_note_creation(blocker)
            lifecycle_manager.submit_for_approval(blocker)
            audit_manager.log_note_submission(blocker)
            lifecycle_manager.approve_note(blocker, approved_by="admin_456")
            audit_manager.log_note_approval(blocker, approved_by="admin_456")

        # 执行巡检
        results = inspector.inspect_all_notes([blocker1, blocker2])

        # 验证结果
        assert len(results) == 2
        convert_results = [r for r in results if r.action == InspectionAction.CONVERT_TO_CONCLUSION]
        keep_results = [r for r in results if r.action == InspectionAction.KEEP]

        assert len(convert_results) == 1  # blocker1 应该被转换
        assert len(keep_results) == 1  # blocker2 应该保留

        # 创建笔记映射
        notes_map = {
            blocker1.note_id: blocker1,
            blocker2.note_id: blocker2,
        }

        # 执行操作
        new_notes = inspector.execute_inspection_actions(
            results, lifecycle_manager, audit_manager, notes_map
        )

        # 验证新笔记
        assert len(new_notes) == 1
        assert new_notes[0].type == NoteType.CONCLUSION
        assert new_notes[0].status == NoteStatus.DRAFT

        # 验证审计日志
        all_logs = audit_manager.get_all_logs()
        assert len(all_logs) >= 6  # 至少有创建、提交、批准各2次
