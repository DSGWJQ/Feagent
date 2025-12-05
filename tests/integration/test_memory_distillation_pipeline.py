"""测试中期记忆蒸馏流水线（Step 3）

测试目标：
1. 监听饱和事件并触发压缩流水线
2. 冻结会话、运行压缩器、生成摘要
3. 用摘要替换旧 buffer，保留最近两轮
4. 压缩失败时回滚到原状态
5. 完整流程：>92% token → 摘要落库 → 新上下文生效
"""

import asyncio

import pytest

from src.domain.services.context_manager import (
    GlobalContext,
    SessionContext,
    ShortTermSaturatedEvent,
)
from src.domain.services.event_bus import EventBus
from src.domain.services.short_term_buffer import ShortTermBuffer, TurnRole
from src.domain.services.structured_dialogue_summary import StructuredDialogueSummary


class TestMemoryDistillationPipeline:
    """测试记忆蒸馏流水线"""

    @pytest.mark.asyncio
    async def test_session_should_have_freeze_and_unfreeze_methods(self):
        """测试：SessionContext 应该有冻结和解冻方法"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)

        # 应该有冻结和解冻方法
        assert hasattr(session_ctx, "freeze")
        assert hasattr(session_ctx, "unfreeze")
        assert hasattr(session_ctx, "is_frozen")

        # 初始状态应该是未冻结
        assert session_ctx.is_frozen() is False

        # 冻结会话
        session_ctx.freeze()
        assert session_ctx.is_frozen() is True

        # 解冻会话
        session_ctx.unfreeze()
        assert session_ctx.is_frozen() is False

    @pytest.mark.asyncio
    async def test_frozen_session_should_reject_modifications(self):
        """测试：冻结的会话应该拒绝修改"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)

        # 冻结会话
        session_ctx.freeze()

        # 尝试添加轮次应该失败
        buffer = ShortTermBuffer(
            turn_id="turn_001",
            role=TurnRole.USER,
            content="Test",
            tool_refs=[],
            token_usage={"total_tokens": 10},
        )

        with pytest.raises(RuntimeError, match="frozen|冻结"):
            session_ctx.add_turn(buffer)

    @pytest.mark.asyncio
    async def test_session_should_support_backup_and_restore(self):
        """测试：SessionContext 应该支持备份和恢复"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)

        # 添加一些数据
        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)
        session_ctx.update_token_usage(prompt_tokens=1000, completion_tokens=500)

        buffer = ShortTermBuffer(
            turn_id="turn_001",
            role=TurnRole.USER,
            content="Test",
            tool_refs=[],
            token_usage={"total_tokens": 100},
        )
        session_ctx.add_turn(buffer)

        # 创建备份
        backup = session_ctx.create_backup()

        # 修改数据
        session_ctx.update_token_usage(prompt_tokens=2000, completion_tokens=1000)
        buffer2 = ShortTermBuffer(
            turn_id="turn_002",
            role=TurnRole.ASSISTANT,
            content="Response",
            tool_refs=[],
            token_usage={"total_tokens": 200},
        )
        session_ctx.add_turn(buffer2)

        # 验证数据已修改
        assert session_ctx.total_tokens == 4500  # 1000+500+2000+1000 (buffer tokens 不重复计算)
        assert len(session_ctx.short_term_buffer) == 2

        # 恢复备份
        session_ctx.restore_from_backup(backup)

        # 验证数据已恢复
        assert session_ctx.total_tokens == 1500  # 1000+500 (buffer tokens 不重复计算)
        assert len(session_ctx.short_term_buffer) == 1

    @pytest.mark.asyncio
    async def test_compress_buffer_should_generate_summary_and_keep_recent_turns(self):
        """测试：压缩 buffer 应该生成摘要并保留最近两轮"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)

        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

        # 添加多轮对话
        turns = [
            ("turn_001", TurnRole.USER, "请分析销售数据", 100),
            ("turn_002", TurnRole.ASSISTANT, "好的，我来分析", 150),
            ("turn_003", TurnRole.USER, "重点关注Q4", 80),
            ("turn_004", TurnRole.ASSISTANT, "Q4数据显示增长15%", 200),
            ("turn_005", TurnRole.USER, "生成报告", 60),
            ("turn_006", TurnRole.ASSISTANT, "报告已生成", 120),
        ]

        for turn_id, role, content, tokens in turns:
            session_ctx.update_token_usage(prompt_tokens=tokens, completion_tokens=0)
            buffer = ShortTermBuffer(
                turn_id=turn_id,
                role=role,
                content=content,
                tool_refs=[],
                token_usage={"total_tokens": tokens},
            )
            session_ctx.add_turn(buffer)

        # 创建摘要
        summary = StructuredDialogueSummary(
            session_id="session_001",
            core_goal="分析销售数据并生成报告",
            key_decisions=["重点关注Q4数据"],
            important_facts=["Q4增长15%"],
            compressed_from_turns=6,
            original_token_count=710,
            summary_token_count=100,
        )

        # 压缩 buffer（保留最近2轮）
        session_ctx.compress_buffer_with_summary(summary, keep_recent_turns=2)

        # 验证：应该只保留最近2轮
        assert len(session_ctx.short_term_buffer) == 2
        assert session_ctx.short_term_buffer[0].turn_id == "turn_005"
        assert session_ctx.short_term_buffer[1].turn_id == "turn_006"

        # 验证：摘要应该被存储
        assert session_ctx.conversation_summary is not None
        assert "分析销售数据" in session_ctx.conversation_summary

    @pytest.mark.asyncio
    async def test_saturation_event_should_trigger_compression_pipeline(self):
        """测试：饱和事件应该触发压缩流水线"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        event_bus = EventBus()

        session_ctx.set_event_bus(event_bus)
        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

        # 记录压缩是否被触发
        compression_triggered = []

        async def handle_saturation_with_compression(event: ShortTermSaturatedEvent):
            """处理饱和事件并执行压缩"""
            compression_triggered.append(event)

            # 冻结会话
            session_ctx.freeze()

            try:
                # 创建备份
                backup = session_ctx.create_backup()

                try:
                    # 生成摘要（模拟）
                    summary = StructuredDialogueSummary(
                        session_id=event.session_id,
                        core_goal="测试压缩流程",
                        compressed_from_turns=event.buffer_size,
                        original_token_count=event.total_tokens,
                        summary_token_count=500,
                    )

                    # 压缩 buffer
                    session_ctx.compress_buffer_with_summary(summary, keep_recent_turns=2)

                    # 重置饱和状态
                    session_ctx.reset_saturation()

                except Exception as e:
                    # 压缩失败，回滚
                    session_ctx.restore_from_backup(backup)
                    raise e

            finally:
                # 解冻会话
                session_ctx.unfreeze()

        event_bus.subscribe(ShortTermSaturatedEvent, handle_saturation_with_compression)

        # 模拟高 token 负载
        for i in range(10):
            session_ctx.update_token_usage(prompt_tokens=800, completion_tokens=0)
            buffer = ShortTermBuffer(
                turn_id=f"turn_{i:03d}",
                role=TurnRole.USER if i % 2 == 0 else TurnRole.ASSISTANT,
                content=f"Content {i}",
                tool_refs=[],
                token_usage={"total_tokens": 800},
            )
            session_ctx.add_turn(buffer)

            await asyncio.sleep(0.01)

        await asyncio.sleep(0.2)

        # 验证压缩被触发
        assert len(compression_triggered) == 1

        # 验证 buffer 被压缩（只保留最近2轮）
        assert len(session_ctx.short_term_buffer) == 2

        # 验证摘要被存储
        assert session_ctx.conversation_summary is not None

        # 验证会话已解冻
        assert session_ctx.is_frozen() is False

    @pytest.mark.asyncio
    async def test_compression_failure_should_rollback_to_backup(self):
        """测试：压缩失败应该回滚到备份状态"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)

        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

        # 添加一些数据
        for i in range(5):
            session_ctx.update_token_usage(prompt_tokens=100, completion_tokens=0)
            buffer = ShortTermBuffer(
                turn_id=f"turn_{i:03d}",
                role=TurnRole.USER,
                content=f"Content {i}",
                tool_refs=[],
                token_usage={"total_tokens": 100},
            )
            session_ctx.add_turn(buffer)

        # 记录原始状态
        original_buffer_size = len(session_ctx.short_term_buffer)
        original_tokens = session_ctx.total_tokens

        # 创建备份
        backup = session_ctx.create_backup()

        # 冻结会话
        session_ctx.freeze()

        try:
            # 模拟压缩失败
            raise RuntimeError("Compression failed")

        except Exception:
            # 回滚
            session_ctx.restore_from_backup(backup)

        finally:
            # 解冻
            session_ctx.unfreeze()

        # 验证状态已恢复
        assert len(session_ctx.short_term_buffer) == original_buffer_size
        assert session_ctx.total_tokens == original_tokens
        assert session_ctx.is_frozen() is False

    @pytest.mark.asyncio
    async def test_complete_flow_over_92_percent_to_summary_to_new_context(self):
        """测试：完整流程 >92% token → 摘要落库 → 新上下文生效"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        event_bus = EventBus()

        session_ctx.set_event_bus(event_bus)
        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

        # 记录流程步骤
        flow_steps = []

        async def handle_saturation_complete_flow(event: ShortTermSaturatedEvent):
            """完整的压缩流程"""
            flow_steps.append("saturation_detected")

            # 1. 冻结会话
            session_ctx.freeze()
            flow_steps.append("session_frozen")

            try:
                # 2. 创建备份
                backup = session_ctx.create_backup()
                flow_steps.append("backup_created")

                try:
                    # 3. 生成摘要
                    summary = StructuredDialogueSummary(
                        session_id=event.session_id,
                        core_goal="完整流程测试",
                        key_decisions=["测试决策"],
                        important_facts=["测试事实"],
                        compressed_from_turns=event.buffer_size,
                        original_token_count=event.total_tokens,
                        summary_token_count=300,
                    )
                    flow_steps.append("summary_generated")

                    # 4. 压缩 buffer
                    session_ctx.compress_buffer_with_summary(summary, keep_recent_turns=2)
                    flow_steps.append("buffer_compressed")

                    # 5. 重置饱和状态
                    session_ctx.reset_saturation()
                    flow_steps.append("saturation_reset")

                except Exception as e:
                    # 回滚
                    session_ctx.restore_from_backup(backup)
                    flow_steps.append("rollback_executed")
                    raise e

            finally:
                # 6. 解冻会话
                session_ctx.unfreeze()
                flow_steps.append("session_unfrozen")

        event_bus.subscribe(ShortTermSaturatedEvent, handle_saturation_complete_flow)

        # 模拟对话直到饱和（>92%）
        turns = [
            ("turn_001", TurnRole.USER, "请分析数据", 800),
            ("turn_002", TurnRole.ASSISTANT, "好的", 1000),
            ("turn_003", TurnRole.USER, "详细说明", 600),
            ("turn_004", TurnRole.ASSISTANT, "详细分析...", 1500),
            ("turn_005", TurnRole.USER, "继续", 500),
            ("turn_006", TurnRole.ASSISTANT, "继续分析...", 1800),
            ("turn_007", TurnRole.USER, "总结", 400),
            ("turn_008", TurnRole.ASSISTANT, "总结如下...", 1000),  # 总计 7600，触发饱和
        ]

        for turn_id, role, content, tokens in turns:
            session_ctx.update_token_usage(prompt_tokens=tokens, completion_tokens=0)
            buffer = ShortTermBuffer(
                turn_id=turn_id,
                role=role,
                content=content,
                tool_refs=[],
                token_usage={"total_tokens": tokens},
            )
            session_ctx.add_turn(buffer)

            await asyncio.sleep(0.01)

        await asyncio.sleep(0.2)

        # 验证完整流程
        assert "saturation_detected" in flow_steps
        assert "session_frozen" in flow_steps
        assert "backup_created" in flow_steps
        assert "summary_generated" in flow_steps
        assert "buffer_compressed" in flow_steps
        assert "saturation_reset" in flow_steps
        assert "session_unfrozen" in flow_steps
        assert "rollback_executed" not in flow_steps  # 没有回滚

        # 验证最终状态
        assert len(session_ctx.short_term_buffer) == 2  # 只保留最近2轮
        assert session_ctx.conversation_summary is not None  # 摘要已存储
        assert session_ctx.is_saturated is False  # 饱和状态已重置
        assert session_ctx.is_frozen() is False  # 会话已解冻

        # 验证新上下文生效（可以继续添加轮次）
        new_buffer = ShortTermBuffer(
            turn_id="turn_009",
            role=TurnRole.USER,
            content="新的问题",
            tool_refs=[],
            token_usage={"total_tokens": 100},
        )
        session_ctx.update_token_usage(prompt_tokens=100, completion_tokens=0)
        session_ctx.add_turn(new_buffer)

        assert len(session_ctx.short_term_buffer) == 3  # 成功添加新轮次


class TestCompressionRollback:
    """测试压缩回滚机制"""

    @pytest.mark.asyncio
    async def test_rollback_should_restore_all_fields(self):
        """测试：回滚应该恢复所有字段"""
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)

        session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

        # 设置初始状态
        session_ctx.update_token_usage(prompt_tokens=1000, completion_tokens=500)
        for i in range(3):
            buffer = ShortTermBuffer(
                turn_id=f"turn_{i:03d}",
                role=TurnRole.USER,
                content=f"Content {i}",
                tool_refs=[],
                token_usage={"total_tokens": 100},
            )
            session_ctx.add_turn(buffer)

        # 创建备份
        backup = session_ctx.create_backup()

        # 修改所有字段
        session_ctx.update_token_usage(prompt_tokens=2000, completion_tokens=1000)
        session_ctx.short_term_buffer.clear()
        session_ctx.conversation_summary = "新摘要"
        session_ctx.is_saturated = True

        # 回滚
        session_ctx.restore_from_backup(backup)

        # 验证所有字段已恢复
        assert session_ctx.total_tokens == 1500  # 1000+500 (buffer tokens 不重复计算)
        assert len(session_ctx.short_term_buffer) == 3
        assert session_ctx.conversation_summary != "新摘要"
        assert session_ctx.is_saturated is False
