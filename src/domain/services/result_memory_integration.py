"""
结果包与记忆更新集成模块 (Step 8)

该模块实现结果包解包、记忆更新和知识库写入：
1. RESULT_PACKAGE_SCHEMA - 结果包 JSON Schema
2. ResultUnpacker - 结果解包器
3. MemoryUpdater - 记忆更新器（中期/长期）
4. KnowledgeWriter - 知识库写入器
5. CoordinatorResultMonitor - 协调者监控与追踪
6. ResultProcessingPipeline - 完整处理流水线
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.domain.services.knowledge_manager import KnowledgeManager
    from src.domain.services.subagent_context_bridge import ResultPackage


# ============================================================================
# 结果包 Schema
# ============================================================================


RESULT_PACKAGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "result_id": {
            "type": "string",
            "description": "结果包唯一标识符",
        },
        "context_package_id": {
            "type": "string",
            "description": "关联的上下文包 ID",
        },
        "agent_id": {
            "type": "string",
            "description": "执行任务的 Agent ID",
        },
        "status": {
            "type": "string",
            "enum": ["completed", "failed", "cancelled", "in_progress"],
            "description": "执行状态",
        },
        "output": {
            "type": "object",
            "description": "输出数据",
        },
        "logs": {
            "type": "array",
            "items": {"type": "object"},
            "description": "执行日志",
        },
        "new_knowledge": {
            "type": "object",
            "description": "新知识/发现",
        },
        "errors": {
            "type": "array",
            "items": {"type": "object"},
            "description": "错误信息",
        },
    },
    "required": ["result_id", "context_package_id", "agent_id", "status", "output"],
}

VALID_STATUSES = {"completed", "failed", "cancelled", "in_progress"}


def validate_result_schema(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    验证结果包是否符合 Schema

    Args:
        data: 结果包数据

    Returns:
        (is_valid, errors) 元组
    """
    errors = []

    # 检查必需字段
    required = RESULT_PACKAGE_SCHEMA.get("required", [])
    for field_name in required:
        if field_name not in data:
            errors.append(f"缺少必需字段: {field_name}")

    # 检查状态
    if "status" in data and data["status"] not in VALID_STATUSES:
        errors.append(f"无效的 status: {data['status']}")

    return len(errors) == 0, errors


# ============================================================================
# 数据类
# ============================================================================


@dataclass
class UnpackedResult:
    """
    解包后的结果

    提供给父 Agent 使用的简化视图。
    """

    result_id: str
    context_package_id: str
    agent_id: str
    status: str
    output: dict[str, Any]
    logs: list[dict[str, Any]]
    new_knowledge: dict[str, Any]
    errors: list[dict[str, Any]]

    def is_success(self) -> bool:
        """判断是否成功"""
        return self.status == "completed"

    def has_errors(self) -> bool:
        """判断是否有错误"""
        return len(self.errors) > 0 or self.status == "failed"

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "result_id": self.result_id,
            "context_package_id": self.context_package_id,
            "agent_id": self.agent_id,
            "status": self.status,
            "output": self.output,
            "logs": self.logs,
            "new_knowledge": self.new_knowledge,
            "errors": self.errors,
        }


@dataclass
class ProcessingResult:
    """
    处理结果

    记录结果处理流水线的执行情况。
    """

    success: bool
    tracking_id: str
    result_id: str
    mid_term_updated: bool
    long_term_updated: bool
    knowledge_entry_ids: list[str]
    errors: list[str]


class UpdateStrategy(str, Enum):
    """更新策略"""

    INCREMENTAL = "incremental"  # 增量更新
    REPLACE = "replace"  # 替换更新


# ============================================================================
# 结果解包器
# ============================================================================


class ResultUnpacker:
    """
    结果解包器

    从 ResultPackage 中提取数据，转换为 UnpackedResult。
    """

    def unpack(self, result_pkg: ResultPackage) -> UnpackedResult:
        """
        解包结果包

        Args:
            result_pkg: 结果包

        Returns:
            UnpackedResult 实例
        """
        # 构建错误列表
        errors = []
        if result_pkg.status == "failed":
            if result_pkg.error_code or result_pkg.error_message:
                errors.append(
                    {
                        "code": result_pkg.error_code or "UNKNOWN",
                        "message": result_pkg.error_message or "未知错误",
                    }
                )

        return UnpackedResult(
            result_id=result_pkg.result_id,
            context_package_id=result_pkg.context_package_id,
            agent_id=result_pkg.agent_id,
            status=result_pkg.status,
            output=result_pkg.output_data,
            logs=result_pkg.execution_logs,
            new_knowledge=result_pkg.knowledge_updates,
            errors=errors,
        )

    def unpack_from_json(self, json_str: str) -> UnpackedResult:
        """
        从 JSON 字符串解包

        Args:
            json_str: JSON 字符串

        Returns:
            UnpackedResult 实例
        """
        from src.domain.services.subagent_context_bridge import ResultPackage

        result_pkg = ResultPackage.from_json(json_str)
        return self.unpack(result_pkg)

    def extract_for_memory(self, result_pkg: ResultPackage) -> dict[str, Any]:
        """
        提取用于记忆存储的数据

        Args:
            result_pkg: 结果包

        Returns:
            可存储的记忆数据
        """
        return {
            "summary": result_pkg.output_data.get("summary", ""),
            "output": result_pkg.output_data,
            "knowledge": result_pkg.knowledge_updates,
            "agent_id": result_pkg.agent_id,
            "context_id": result_pkg.context_package_id,
            "timestamp": datetime.now().isoformat(),
        }


# ============================================================================
# 记忆更新器
# ============================================================================


class MemoryUpdater:
    """
    记忆更新器

    根据结果包更新中期和长期记忆。
    """

    def __init__(self, strategy: UpdateStrategy = UpdateStrategy.INCREMENTAL):
        """
        初始化更新器

        Args:
            strategy: 更新策略
        """
        self.strategy = strategy

    def prepare_mid_term_update(
        self,
        unpacked: UnpackedResult,
    ) -> dict[str, Any]:
        """
        准备中期记忆更新

        Args:
            unpacked: 解包后的结果

        Returns:
            中期记忆更新数据
        """
        return {
            "source_result_id": unpacked.result_id,
            "source_context_id": unpacked.context_package_id,
            "agent_id": unpacked.agent_id,
            "content": unpacked.output,
            "update_type": "task_completion",
            "strategy": self.strategy.value,
            "timestamp": datetime.now().isoformat(),
        }

    def prepare_long_term_updates(
        self,
        unpacked: UnpackedResult,
    ) -> list[dict[str, Any]]:
        """
        准备长期记忆更新

        Args:
            unpacked: 解包后的结果

        Returns:
            长期记忆更新列表
        """
        # 失败的结果不产生长期记忆更新
        if not unpacked.is_success():
            return []

        updates = []

        # 从 new_knowledge 中提取更新项
        if unpacked.new_knowledge:
            # 处理 facts 列表
            facts = unpacked.new_knowledge.get("facts", [])
            if isinstance(facts, list):
                for fact in facts:
                    updates.append(
                        {
                            "type": "fact",
                            "content": str(fact),
                            "source_result_id": unpacked.result_id,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

            # 处理 insights
            insights = unpacked.new_knowledge.get("insights")
            if insights:
                updates.append(
                    {
                        "type": "insight",
                        "content": str(insights),
                        "source_result_id": unpacked.result_id,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            # 处理 conclusions
            conclusions = unpacked.new_knowledge.get("conclusions")
            if conclusions:
                updates.append(
                    {
                        "type": "conclusion",
                        "content": str(conclusions),
                        "source_result_id": unpacked.result_id,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            # 处理其他字段
            for key, value in unpacked.new_knowledge.items():
                if key not in ("facts", "insights", "conclusions") and value:
                    updates.append(
                        {
                            "type": "knowledge",
                            "key": key,
                            "content": str(value),
                            "source_result_id": unpacked.result_id,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

        return updates

    def apply_to_session(
        self,
        unpacked: UnpackedResult,
        session: Any,
    ) -> None:
        """
        将更新应用到会话

        Args:
            unpacked: 解包后的结果
            session: 会话对象
        """
        mid_term_update = self.prepare_mid_term_update(unpacked)

        # 尝试调用 session 的 update_mid_term 方法
        if hasattr(session, "update_mid_term"):
            session.update_mid_term(mid_term_update)
        elif hasattr(session, "mid_term_context"):
            # 直接更新 mid_term_context
            session.mid_term_context[unpacked.result_id] = mid_term_update


# ============================================================================
# 知识库写入器
# ============================================================================


class KnowledgeWriter:
    """
    知识库写入器

    将结果包中的新知识写入知识库。
    """

    def __init__(self, knowledge_manager: KnowledgeManager):
        """
        初始化写入器

        Args:
            knowledge_manager: 知识库管理器
        """
        self._knowledge_manager = knowledge_manager

    def write_from_result(
        self,
        unpacked: UnpackedResult,
        tags: list[str] | None = None,
    ) -> list[str]:
        """
        从结果中写入知识

        Args:
            unpacked: 解包后的结果
            tags: 额外标签

        Returns:
            创建的知识条目 ID 列表
        """
        if not unpacked.new_knowledge:
            return []

        entry_ids = []
        base_tags = tags or []

        # 遍历新知识并创建条目
        for key, value in unpacked.new_knowledge.items():
            if not value:
                continue

            # 根据类型确定内容
            if isinstance(value, list):
                content = "\n".join(str(item) for item in value)
            else:
                content = str(value)

            # 创建知识条目
            entry_id = self._knowledge_manager.create(
                title=f"Task Result: {key}",
                content=content,
                category="task_result",
                tags=base_tags + [key, unpacked.agent_id],
                metadata={
                    "source_result_id": unpacked.result_id,
                    "source_context_id": unpacked.context_package_id,
                    "source_agent_id": unpacked.agent_id,
                    "created_from": "result_package",
                    "timestamp": datetime.now().isoformat(),
                },
            )
            entry_ids.append(entry_id)

        return entry_ids


# ============================================================================
# 协调者结果监控
# ============================================================================


class CoordinatorResultMonitor:
    """
    协调者结果监控

    监控结果包处理过程，提供追踪 ID 和审计日志。
    """

    def __init__(self, coordinator_id: str):
        """
        初始化监控器

        Args:
            coordinator_id: 协调者 ID
        """
        self.coordinator_id = coordinator_id
        self._tracking_map: dict[str, str] = {}  # result_id -> tracking_id
        self._event_logs: dict[str, list[dict[str, Any]]] = {}  # result_id -> events

    def generate_tracking_id(self, result_id: str) -> str:
        """
        生成追踪 ID

        Args:
            result_id: 结果包 ID

        Returns:
            追踪 ID
        """
        tracking_id = f"track_{uuid.uuid4().hex[:8]}_{result_id[:8]}"
        self._tracking_map[result_id] = tracking_id
        return tracking_id

    def get_tracking_id(self, result_id: str) -> str:
        """
        获取追踪 ID

        Args:
            result_id: 结果包 ID

        Returns:
            追踪 ID
        """
        return self._tracking_map.get(result_id, "")

    def _add_event(
        self,
        result_id: str,
        event: dict[str, Any],
    ) -> None:
        """添加事件到日志"""
        if result_id not in self._event_logs:
            self._event_logs[result_id] = []
        self._event_logs[result_id].append(event)

    def log_result_received(
        self,
        result_pkg: ResultPackage,
    ) -> dict[str, Any]:
        """
        记录结果接收

        Args:
            result_pkg: 结果包

        Returns:
            日志条目
        """
        tracking_id = self.generate_tracking_id(result_pkg.result_id)

        entry = {
            "event": "result_received",
            "result_id": result_pkg.result_id,
            "context_package_id": result_pkg.context_package_id,
            "agent_id": result_pkg.agent_id,
            "status": result_pkg.status,
            "coordinator_id": self.coordinator_id,
            "tracking_id": tracking_id,
            "timestamp": datetime.now().isoformat(),
        }

        self._add_event(result_pkg.result_id, entry)
        return entry

    def log_memory_updated(
        self,
        result_id: str,
        tracking_id: str,
        update_type: str,
    ) -> dict[str, Any]:
        """
        记录记忆更新

        Args:
            result_id: 结果包 ID
            tracking_id: 追踪 ID
            update_type: 更新类型

        Returns:
            日志条目
        """
        entry = {
            "event": "memory_updated",
            "result_id": result_id,
            "tracking_id": tracking_id,
            "update_type": update_type,
            "coordinator_id": self.coordinator_id,
            "timestamp": datetime.now().isoformat(),
        }

        self._add_event(result_id, entry)
        return entry

    def log_knowledge_written(
        self,
        result_id: str,
        tracking_id: str,
        entry_ids: list[str],
    ) -> dict[str, Any]:
        """
        记录知识写入

        Args:
            result_id: 结果包 ID
            tracking_id: 追踪 ID
            entry_ids: 创建的知识条目 ID 列表

        Returns:
            日志条目
        """
        entry = {
            "event": "knowledge_written",
            "result_id": result_id,
            "tracking_id": tracking_id,
            "entry_ids": entry_ids,
            "entry_count": len(entry_ids),
            "coordinator_id": self.coordinator_id,
            "timestamp": datetime.now().isoformat(),
        }

        self._add_event(result_id, entry)
        return entry

    def get_processing_trace(self, result_id: str) -> list[dict[str, Any]]:
        """
        获取处理追踪

        Args:
            result_id: 结果包 ID

        Returns:
            事件列表
        """
        return self._event_logs.get(result_id, [])


# ============================================================================
# 结果处理流水线
# ============================================================================


class ResultProcessingPipeline:
    """
    结果处理流水线

    完整处理结果包：解包 → 记忆更新 → 知识写入 → 监控记录。
    """

    def __init__(
        self,
        coordinator_id: str,
        knowledge_manager: KnowledgeManager,
        update_strategy: UpdateStrategy = UpdateStrategy.INCREMENTAL,
    ):
        """
        初始化流水线

        Args:
            coordinator_id: 协调者 ID
            knowledge_manager: 知识库管理器
            update_strategy: 更新策略
        """
        self._coordinator_id = coordinator_id
        self._unpacker = ResultUnpacker()
        self._memory_updater = MemoryUpdater(strategy=update_strategy)
        self._knowledge_writer = KnowledgeWriter(knowledge_manager)
        self._monitor = CoordinatorResultMonitor(coordinator_id)

    def process(self, result_pkg: ResultPackage) -> ProcessingResult:
        """
        处理结果包

        Args:
            result_pkg: 结果包

        Returns:
            ProcessingResult 实例
        """
        errors = []

        # 1. 记录结果接收
        self._monitor.log_result_received(result_pkg)
        tracking_id = self._monitor.get_tracking_id(result_pkg.result_id)

        # 2. 解包
        unpacked = self._unpacker.unpack(result_pkg)

        # 3. 准备中期记忆更新
        mid_term_updated = False
        try:
            self._memory_updater.prepare_mid_term_update(unpacked)
            mid_term_updated = True
            self._monitor.log_memory_updated(
                result_pkg.result_id,
                tracking_id,
                "mid_term",
            )
        except Exception as e:
            errors.append(f"中期记忆更新失败: {e}")

        # 4. 准备长期记忆更新
        long_term_updated = False
        long_term_updates = []
        try:
            long_term_updates = self._memory_updater.prepare_long_term_updates(unpacked)
            if long_term_updates:
                long_term_updated = True
                self._monitor.log_memory_updated(
                    result_pkg.result_id,
                    tracking_id,
                    "long_term",
                )
        except Exception as e:
            errors.append(f"长期记忆更新失败: {e}")

        # 5. 写入知识库
        knowledge_entry_ids = []
        if unpacked.is_success() and unpacked.new_knowledge:
            try:
                knowledge_entry_ids = self._knowledge_writer.write_from_result(
                    unpacked,
                    tags=["auto_generated", f"coordinator_{self._coordinator_id}"],
                )
                if knowledge_entry_ids:
                    self._monitor.log_knowledge_written(
                        result_pkg.result_id,
                        tracking_id,
                        knowledge_entry_ids,
                    )
            except Exception as e:
                errors.append(f"知识库写入失败: {e}")

        return ProcessingResult(
            success=len(errors) == 0,
            tracking_id=tracking_id,
            result_id=result_pkg.result_id,
            mid_term_updated=mid_term_updated,
            long_term_updated=long_term_updated,
            knowledge_entry_ids=knowledge_entry_ids,
            errors=errors,
        )

    def get_audit_log(self, result_id: str) -> list[dict[str, Any]]:
        """
        获取审计日志

        Args:
            result_id: 结果包 ID

        Returns:
            审计日志列表
        """
        return self._monitor.get_processing_trace(result_id)


# ============================================================================
# 导出
# ============================================================================


__all__ = [
    "RESULT_PACKAGE_SCHEMA",
    "validate_result_schema",
    "UnpackedResult",
    "ProcessingResult",
    "UpdateStrategy",
    "ResultUnpacker",
    "MemoryUpdater",
    "KnowledgeWriter",
    "CoordinatorResultMonitor",
    "ResultProcessingPipeline",
]
