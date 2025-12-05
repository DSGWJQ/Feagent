"""偏离告警 (DeviationAlert) - Step 5: 检索与监督整合

业务定义:
- 当 ConversationAgent 忽视高优先级笔记时触发告警
- 告警类型: WARNING (警告) 和 REPLAN_REQUIRED (需要重新规划)
- 严重程度: LOW, MEDIUM, HIGH (基于被忽视笔记的类型)

设计原则:
- 监督机制: 检测 agent 行动是否考虑了注入的笔记
- 分级告警: 不同类型笔记被忽视触发不同级别告警
- 可追溯性: 记录被忽视的笔记和告警原因

告警规则:
1. Blocker 被忽视 → REPLAN_REQUIRED + HIGH 严重程度
2. Next Action 被忽视 → WARNING + MEDIUM 严重程度
3. Conclusion 被忽视 → WARNING + LOW 严重程度
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.domain.services.knowledge_note import KnowledgeNote, NoteType


class AlertType(str, Enum):
    """告警类型枚举"""

    WARNING = "warning"  # 警告
    REPLAN_REQUIRED = "replan_required"  # 需要重新规划


class AlertSeverity(str, Enum):
    """告警严重程度枚举"""

    LOW = "low"  # 低
    MEDIUM = "medium"  # 中
    HIGH = "high"  # 高


@dataclass
class DeviationAlert:
    """偏离告警

    属性:
        alert_type: 告警类型
        ignored_notes: 被忽视的笔记列表
        reason: 告警原因
        severity: 严重程度
        timestamp: 告警时间戳
    """

    alert_type: AlertType
    ignored_notes: list[KnowledgeNote]
    reason: str
    severity: AlertSeverity = AlertSeverity.MEDIUM
    timestamp: datetime = field(default_factory=datetime.now)

    @staticmethod
    def create(
        alert_type: AlertType,
        ignored_notes: list[KnowledgeNote],
        reason: str,
        severity: AlertSeverity | None = None,
    ) -> "DeviationAlert":
        """创建偏离告警

        参数:
            alert_type: 告警类型
            ignored_notes: 被忽视的笔记列表
            reason: 告警原因
            severity: 严重程度 (可选, 默认根据笔记类型计算)

        返回:
            偏离告警实例
        """
        if severity is None:
            # 根据被忽视笔记的类型计算严重程度
            severity = DeviationDetector().calculate_severity(ignored_notes)

        return DeviationAlert(
            alert_type=alert_type,
            ignored_notes=ignored_notes,
            reason=reason,
            severity=severity,
            timestamp=datetime.now(),
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典

        返回:
            包含告警信息的字典
        """
        return {
            "alert_type": self.alert_type.value,
            "ignored_notes": [
                {
                    "note_id": note.note_id,
                    "type": note.type.value,
                    "content": note.content,
                }
                for note in self.ignored_notes
            ],
            "reason": self.reason,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
        }

    def get_alert_message(self) -> str:
        """获取告警消息

        返回:
            格式化的告警消息
        """
        note_types = [note.type.value for note in self.ignored_notes]
        return (
            f"[{self.alert_type.value.upper()}] {self.reason} "
            f"(严重程度: {self.severity.value}, "
            f"被忽视笔记类型: {', '.join(note_types)})"
        )


class DeviationDetector:
    """偏离检测器

    职责:
    - 检测 ConversationAgent 是否忽视了注入的笔记
    - 判断被忽视笔记的严重程度
    - 生成相应的告警
    """

    # 笔记类型对应的严重程度
    TYPE_SEVERITY_MAP = {
        NoteType.BLOCKER: AlertSeverity.HIGH,
        NoteType.NEXT_ACTION: AlertSeverity.MEDIUM,
        NoteType.CONCLUSION: AlertSeverity.LOW,
        NoteType.PROGRESS: AlertSeverity.LOW,
        NoteType.REFERENCE: AlertSeverity.LOW,
    }

    def detect_deviation(
        self,
        injected_notes: list[KnowledgeNote],
        agent_actions: list[dict[str, Any]],
    ) -> DeviationAlert | None:
        """检测偏离

        参数:
            injected_notes: 注入给 agent 的笔记列表
            agent_actions: agent 的行动列表 (包含 type 和 content)

        返回:
            偏离告警 (如果检测到偏离) 或 None
        """
        # 检查哪些笔记被忽视了
        ignored_notes = []
        for note in injected_notes:
            if self.is_note_ignored(note, agent_actions):
                ignored_notes.append(note)

        # 如果没有被忽视的笔记, 返回 None
        if not ignored_notes:
            return None

        # 计算严重程度
        severity = self.calculate_severity(ignored_notes)

        # 确定告警类型
        alert_type = self._determine_alert_type(ignored_notes)

        # 生成告警原因
        reason = self._generate_reason(ignored_notes)

        return DeviationAlert.create(
            alert_type=alert_type,
            ignored_notes=ignored_notes,
            reason=reason,
            severity=severity,
        )

    def is_note_ignored(self, note: KnowledgeNote, agent_actions: list[dict[str, Any]]) -> bool:
        """判断笔记是否被忽视

        参数:
            note: 笔记实例
            agent_actions: agent 的行动列表

        返回:
            是否被忽视
        """
        # 提取笔记的关键词
        keywords = self._extract_keywords(note)

        # 检查 agent 行动中是否提到了这些关键词
        for action in agent_actions:
            content = action.get("content", "").lower()

            # 检查标签匹配
            for tag in note.tags:
                if tag.lower() in content:
                    return False  # 找到标签匹配, 说明没有被忽视

            # 检查内容关键词匹配
            note_content_lower = note.content.lower()
            # 对于中文，检查内容中的连续字符串
            if len(note_content_lower) > 2:
                # 提取2-4字的子串作为关键词
                for i in range(len(note_content_lower) - 1):
                    for length in [2, 3, 4]:
                        if i + length <= len(note_content_lower):
                            substring = note_content_lower[i : i + length]
                            if substring in content and len(substring.strip()) == length:
                                return False  # 找到内容匹配

            # 检查其他关键词
            for keyword in keywords:
                if keyword.lower() in content:
                    return False  # 找到匹配, 说明没有被忽视

        return True  # 没有找到匹配, 说明被忽视了

    def calculate_severity(self, ignored_notes: list[KnowledgeNote]) -> AlertSeverity:
        """计算严重程度

        参数:
            ignored_notes: 被忽视的笔记列表

        返回:
            严重程度 (取最高级别)
        """
        if not ignored_notes:
            return AlertSeverity.LOW

        # 找到最高严重程度
        max_severity = AlertSeverity.LOW
        severity_order = {
            AlertSeverity.LOW: 1,
            AlertSeverity.MEDIUM: 2,
            AlertSeverity.HIGH: 3,
        }

        for note in ignored_notes:
            note_severity = self.TYPE_SEVERITY_MAP.get(note.type, AlertSeverity.LOW)
            if severity_order[note_severity] > severity_order[max_severity]:
                max_severity = note_severity

        return max_severity

    def _determine_alert_type(self, ignored_notes: list[KnowledgeNote]) -> AlertType:
        """确定告警类型

        参数:
            ignored_notes: 被忽视的笔记列表

        返回:
            告警类型
        """
        # 如果有 blocker 被忽视, 需要重新规划
        for note in ignored_notes:
            if note.type == NoteType.BLOCKER:
                return AlertType.REPLAN_REQUIRED

        # 否则只是警告
        return AlertType.WARNING

    def _generate_reason(self, ignored_notes: list[KnowledgeNote]) -> str:
        """生成告警原因

        参数:
            ignored_notes: 被忽视的笔记列表

        返回:
            告警原因描述
        """
        note_types = [note.type.value for note in ignored_notes]
        type_counts = {}
        for note_type in note_types:
            type_counts[note_type] = type_counts.get(note_type, 0) + 1

        type_desc = ", ".join([f"{count} 个 {t}" for t, count in type_counts.items()])
        return f"ConversationAgent 忽视了 {len(ignored_notes)} 条高优先级笔记 ({type_desc})"

    def _extract_keywords(self, note: KnowledgeNote) -> list[str]:
        """提取笔记的关键词

        参数:
            note: 笔记实例

        返回:
            关键词列表
        """
        keywords = []

        # 添加标签作为关键词
        keywords.extend(note.tags)

        # 从内容中提取关键词 (简单实现: 分词)
        content_words = note.content.split()
        # 过滤掉太短的词
        keywords.extend([w for w in content_words if len(w) > 2])

        return keywords


# 导出
__all__ = [
    "DeviationAlert",
    "AlertType",
    "AlertSeverity",
    "DeviationDetector",
]
