"""知识协调器集成 (KnowledgeCoordinator) - Step 5: 检索与监督整合

业务定义:
- 协调者负责检索相关笔记并注入给 ConversationAgent
- 记录所有注入操作 (notes_injected)
- 使用 DeviationDetector 检测 agent 是否忽视高优先级笔记
- 记录偏离历史并提供查询接口

设计原则:
- 单一职责: 专注于知识检索和偏离监督
- 可追溯性: 记录所有注入和偏离操作
- 会话隔离: 按 session_id 隔离不同会话的数据
- 统计分析: 提供会话级别的统计摘要

核心能力:
1. 知识检索: 使用 VaultRetriever 检索相关笔记
2. 注入记录: 记录每次注入的笔记列表
3. 偏离检测: 使用 DeviationDetector 检测忽视行为
4. 历史查询: 查询注入历史和偏离历史
5. 统计摘要: 提供会话级别的统计信息
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.domain.services.knowledge_deviation_alert import (
    DeviationAlert,
    DeviationDetector,
)
from src.domain.services.knowledge_note import KnowledgeNote
from src.domain.services.knowledge_vault_retriever import (
    RetrievalResult,
    VaultRetriever,
)


@dataclass
class InjectionRecord:
    """注入记录

    属性:
        session_id: 会话ID
        query: 查询字符串
        injected_notes: 注入的笔记列表
        timestamp: 注入时间戳
    """

    session_id: str
    query: str
    injected_notes: list[KnowledgeNote]
    timestamp: datetime = field(default_factory=datetime.now)

    @staticmethod
    def create(
        session_id: str,
        query: str,
        injected_notes: list[KnowledgeNote],
    ) -> "InjectionRecord":
        """创建注入记录

        参数:
            session_id: 会话ID
            query: 查询字符串
            injected_notes: 注入的笔记列表

        返回:
            注入记录实例
        """
        return InjectionRecord(
            session_id=session_id,
            query=query,
            injected_notes=injected_notes,
            timestamp=datetime.now(),
        )


@dataclass
class DeviationRecord:
    """偏离记录

    属性:
        session_id: 会话ID
        alert: 偏离告警
        timestamp: 检测时间戳
    """

    session_id: str
    alert: DeviationAlert
    timestamp: datetime = field(default_factory=datetime.now)

    @staticmethod
    def create(
        session_id: str,
        alert: DeviationAlert,
    ) -> "DeviationRecord":
        """创建偏离记录

        参数:
            session_id: 会话ID
            alert: 偏离告警

        返回:
            偏离记录实例
        """
        return DeviationRecord(
            session_id=session_id,
            alert=alert,
            timestamp=datetime.now(),
        )


class KnowledgeCoordinator:
    """知识协调器

    职责:
    - 检索相关笔记并注入给 ConversationAgent
    - 记录注入历史
    - 检测 agent 是否忽视高优先级笔记
    - 记录偏离历史
    - 提供查询和统计接口
    """

    def __init__(self, max_injection: int = 6):
        """初始化知识协调器

        参数:
            max_injection: 最大注入数量 (默认 6)
        """
        self.retriever = VaultRetriever(default_max_total=max_injection)
        self.detector = DeviationDetector()

        # 注入历史: session_id -> list[InjectionRecord]
        self._injection_history: dict[str, list[InjectionRecord]] = {}

        # 偏离历史: session_id -> list[DeviationRecord]
        self._deviation_history: dict[str, list[DeviationRecord]] = {}

    def inject_notes(
        self,
        query: str,
        available_notes: list[KnowledgeNote],
        session_id: str,
        max_total: int | None = None,
    ) -> RetrievalResult:
        """检索并注入笔记

        参数:
            query: 查询字符串
            available_notes: 可用笔记列表
            session_id: 会话ID
            max_total: 最大注入数量 (可选)

        返回:
            检索结果
        """
        # 使用 VaultRetriever 检索笔记
        result = self.retriever.fetch(
            query=query,
            notes=available_notes,
            max_total=max_total,
            only_approved=False,  # 暂时不过滤状态
        )

        # 记录注入历史
        record = InjectionRecord.create(
            session_id=session_id,
            query=query,
            injected_notes=result.notes,
        )

        if session_id not in self._injection_history:
            self._injection_history[session_id] = []
        self._injection_history[session_id].append(record)

        return result

    def check_deviation(
        self,
        session_id: str,
        agent_actions: list[dict[str, Any]],
    ) -> DeviationAlert | None:
        """检查偏离

        参数:
            session_id: 会话ID
            agent_actions: agent 的行动列表

        返回:
            偏离告警 (如果检测到偏离) 或 None
        """
        # 获取最近一次注入的笔记
        if session_id not in self._injection_history:
            return None

        injection_records = self._injection_history[session_id]
        if not injection_records:
            return None

        latest_injection = injection_records[-1]
        injected_notes = latest_injection.injected_notes

        # 使用 DeviationDetector 检测偏离
        alert = self.detector.detect_deviation(
            injected_notes=injected_notes,
            agent_actions=agent_actions,
        )

        # 如果检测到偏离, 记录到历史
        if alert is not None:
            record = DeviationRecord.create(
                session_id=session_id,
                alert=alert,
            )

            if session_id not in self._deviation_history:
                self._deviation_history[session_id] = []
            self._deviation_history[session_id].append(record)

        return alert

    def get_injection_history(self, session_id: str) -> list[InjectionRecord]:
        """获取注入历史

        参数:
            session_id: 会话ID

        返回:
            注入记录列表
        """
        return self._injection_history.get(session_id, [])

    def get_deviation_history(self, session_id: str) -> list[DeviationRecord]:
        """获取偏离历史

        参数:
            session_id: 会话ID

        返回:
            偏离记录列表
        """
        return self._deviation_history.get(session_id, [])

    def get_session_summary(self, session_id: str) -> dict[str, Any]:
        """获取会话摘要

        参数:
            session_id: 会话ID

        返回:
            会话统计摘要
        """
        injection_records = self.get_injection_history(session_id)
        deviation_records = self.get_deviation_history(session_id)

        total_notes_injected = sum(len(record.injected_notes) for record in injection_records)

        return {
            "session_id": session_id,
            "total_injections": len(injection_records),
            "total_notes_injected": total_notes_injected,
            "total_deviations": len(deviation_records),
            "deviation_rate": (
                len(deviation_records) / len(injection_records) if injection_records else 0.0
            ),
        }

    def clear_session(self, session_id: str) -> None:
        """清除会话数据

        参数:
            session_id: 会话ID
        """
        if session_id in self._injection_history:
            del self._injection_history[session_id]
        if session_id in self._deviation_history:
            del self._deviation_history[session_id]


# 导出
__all__ = [
    "KnowledgeCoordinator",
    "InjectionRecord",
    "DeviationRecord",
]
