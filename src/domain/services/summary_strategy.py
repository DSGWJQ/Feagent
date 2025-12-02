"""摘要策略与信息完整性 - 阶段6

业务定义：
- 分层摘要 + 原文引用策略
- ConversationAgent 发布信息时附 summary/evidence_refs 字段
- Coordinator 校验并允许下游根据引用 ID 获取原始数据

设计原则：
- 信息完整性：摘要包含关键信息，缺失时可通过引用补齐
- 可追溯性：每个摘要都有证据引用
- 分层策略：支持不同详细程度的摘要

核心功能：
- SummaryGenerator: 生成摘要
- EvidenceStore: 存储和检索证据
- SummaryValidator: 校验摘要完整性
- InformationCompletionService: 信息补全
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from src.domain.services.event_bus import Event, EventBus

logger = logging.getLogger(__name__)


# ==================== 枚举和数据结构 ====================


class SummaryLevel(str, Enum):
    """摘要级别

    - BRIEF: 简短摘要，只包含核心结论
    - STANDARD: 标准摘要，包含主要信息
    - DETAILED: 详细摘要，包含大部分信息
    """

    BRIEF = "brief"
    STANDARD = "standard"
    DETAILED = "detailed"


@dataclass
class SummaryInfo:
    """摘要信息

    属性：
    - summary: 摘要文本
    - evidence_refs: 证据引用ID列表
    - created_at: 创建时间
    - level: 摘要级别
    - source_id: 来源ID
    """

    summary: str
    evidence_refs: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    level: SummaryLevel = SummaryLevel.STANDARD
    source_id: str | None = None


@dataclass
class EvidenceReference:
    """证据引用

    属性：
    - ref_id: 引用ID
    - source_type: 来源类型（node_output, workflow_result, etc.）
    - source_id: 来源ID
    - data_path: 数据路径（用于定位特定字段）
    - created_at: 创建时间
    """

    ref_id: str
    source_type: str
    source_id: str
    data_path: str | None = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ValidationResult:
    """校验结果"""

    is_valid: bool = True
    errors: list[str] = field(default_factory=list)


# ==================== 证据存储 ====================


class EvidenceStore:
    """证据存储

    职责：
    1. 存储原始数据作为证据
    2. 根据引用ID检索证据
    3. 支持按路径检索嵌套数据
    4. 按来源列出引用

    使用示例：
        store = EvidenceStore()
        ref_id = store.store({"result": "data"}, source_id="node_1", source_type="node_output")
        data = store.retrieve(ref_id)
        value = store.retrieve(ref_id, data_path="result")
    """

    def __init__(self):
        """初始化证据存储"""
        self._storage: dict[str, dict[str, Any]] = {}
        self._references: dict[str, EvidenceReference] = {}
        self._source_index: dict[str, list[str]] = {}  # source_id -> [ref_ids]
        self._lock = threading.Lock()

    def store(
        self,
        data: dict[str, Any],
        source_id: str,
        source_type: str,
        data_path: str | None = None,
    ) -> str:
        """存储证据

        参数：
            data: 原始数据
            source_id: 来源ID
            source_type: 来源类型
            data_path: 数据路径（可选）

        返回：
            引用ID
        """
        with self._lock:
            ref_id = f"ref_{uuid4().hex[:12]}"

            # 存储数据
            self._storage[ref_id] = data

            # 创建引用
            reference = EvidenceReference(
                ref_id=ref_id,
                source_type=source_type,
                source_id=source_id,
                data_path=data_path,
            )
            self._references[ref_id] = reference

            # 更新来源索引
            if source_id not in self._source_index:
                self._source_index[source_id] = []
            self._source_index[source_id].append(ref_id)

            return ref_id

    def retrieve(self, ref_id: str, data_path: str | None = None) -> Any:
        """检索证据

        参数：
            ref_id: 引用ID
            data_path: 数据路径（可选，用于检索嵌套数据）

        返回：
            原始数据或特定路径的数据，不存在返回None
        """
        data = self._storage.get(ref_id)
        if data is None:
            return None

        if data_path is None:
            return data

        # 按路径解析
        return self._get_nested_value(data, data_path)

    def _get_nested_value(self, data: Any, path: str) -> Any:
        """获取嵌套值

        参数：
            data: 数据
            path: 点分隔的路径

        返回：
            嵌套值
        """
        parts = path.split(".")
        current = data

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None

            if current is None:
                return None

        return current

    def list_by_source(self, source_id: str) -> list[str]:
        """按来源列出引用ID

        参数：
            source_id: 来源ID

        返回：
            引用ID列表
        """
        return self._source_index.get(source_id, []).copy()

    def get_reference(self, ref_id: str) -> EvidenceReference | None:
        """获取引用详情

        参数：
            ref_id: 引用ID

        返回：
            引用详情
        """
        return self._references.get(ref_id)

    def exists(self, ref_id: str) -> bool:
        """检查引用是否存在

        参数：
            ref_id: 引用ID

        返回：
            是否存在
        """
        return ref_id in self._storage


# ==================== 摘要生成器 ====================


class SummaryGenerator:
    """摘要生成器

    职责：
    1. 从原始数据生成摘要
    2. 支持不同级别的摘要
    3. 自动创建证据引用

    使用示例：
        generator = SummaryGenerator()
        summary = generator.generate(raw_data, level=SummaryLevel.STANDARD)
    """

    # 不同级别的摘要最大长度
    LEVEL_MAX_LENGTH = {
        SummaryLevel.BRIEF: 50,
        SummaryLevel.STANDARD: 150,
        SummaryLevel.DETAILED: 500,
    }

    def __init__(
        self,
        max_summary_length: int | None = None,
        evidence_store: EvidenceStore | None = None,
    ):
        """初始化摘要生成器

        参数：
            max_summary_length: 最大摘要长度（覆盖级别设置）
            evidence_store: 证据存储（用于自动存储引用）
        """
        self.max_summary_length = max_summary_length
        self.evidence_store = evidence_store

    def generate(
        self,
        raw_data: dict[str, Any],
        level: SummaryLevel = SummaryLevel.STANDARD,
        source_id: str | None = None,
    ) -> SummaryInfo:
        """生成摘要

        参数：
            raw_data: 原始数据
            level: 摘要级别
            source_id: 来源ID

        返回：
            摘要信息
        """
        # 确定最大长度
        max_length = self.max_summary_length or self.LEVEL_MAX_LENGTH.get(level, 150)

        # 生成摘要文本
        summary_text = self._generate_summary_text(raw_data, max_length, level)

        # 生成证据引用
        evidence_refs = []
        if source_id:
            ref_id = f"ref_{source_id}_{uuid4().hex[:8]}"
            evidence_refs.append(ref_id)

            # 如果有证据存储，自动存储
            if self.evidence_store:
                stored_ref = self.evidence_store.store(
                    raw_data, source_id=source_id, source_type="generated"
                )
                evidence_refs = [stored_ref]
        else:
            # 生成默认引用
            evidence_refs.append(f"ref_auto_{uuid4().hex[:8]}")

        return SummaryInfo(
            summary=summary_text,
            evidence_refs=evidence_refs,
            level=level,
            source_id=source_id,
        )

    def _generate_summary_text(
        self,
        data: dict[str, Any],
        max_length: int,
        level: SummaryLevel,
    ) -> str:
        """生成摘要文本

        参数：
            data: 原始数据
            max_length: 最大长度
            level: 摘要级别

        返回：
            摘要文本
        """
        # 提取关键信息
        key_info = []

        # 提取常见字段
        if "content" in data:
            content = str(data["content"])
            if level == SummaryLevel.BRIEF:
                key_info.append(content[:30] + "..." if len(content) > 30 else content)
            else:
                key_info.append(content[:100] + "..." if len(content) > 100 else content)

        if "result" in data:
            result_data = data["result"]
            if isinstance(result_data, dict):
                for k, v in result_data.items():
                    if isinstance(v, int | float | str):
                        key_info.append(f"{k}: {v}")
            else:
                key_info.append(f"result: {result_data}")

        if "status" in data:
            key_info.append(f"状态: {data['status']}")

        if "type" in data:
            key_info.append(f"类型: {data['type']}")

        # 组合摘要
        if key_info:
            summary = "; ".join(key_info)
        else:
            # 默认摘要
            summary = f"数据包含 {len(data)} 个字段"

        # 截断到最大长度
        if len(summary) > max_length:
            summary = summary[: max_length - 3] + "..."

        return summary


# ==================== 摘要校验器 ====================


class SummaryValidator:
    """摘要校验器

    职责：
    1. 校验摘要完整性
    2. 验证证据引用存在
    3. 检查摘要是否为空

    使用示例：
        validator = SummaryValidator(evidence_store=store)
        result = validator.validate(summary_info)
    """

    def __init__(self, evidence_store: EvidenceStore | None = None):
        """初始化校验器

        参数：
            evidence_store: 证据存储（用于验证引用存在）
        """
        self.evidence_store = evidence_store

    def validate(self, summary: SummaryInfo) -> ValidationResult:
        """校验摘要

        参数：
            summary: 摘要信息

        返回：
            校验结果
        """
        errors = []

        # 检查摘要是否为空
        if not summary.summary or not summary.summary.strip():
            errors.append("摘要不能为空")

        # 检查是否有证据引用
        if not summary.evidence_refs:
            errors.append("缺少证据引用")

        # 如果有证据存储，验证引用存在
        if self.evidence_store and summary.evidence_refs:
            for ref_id in summary.evidence_refs:
                if not self.evidence_store.exists(ref_id):
                    errors.append(f"引用不存在: {ref_id}")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)


# ==================== 信息补全服务 ====================


class InformationCompletionService:
    """信息补全服务

    职责：
    1. 检测摘要缺失的关键信息
    2. 通过证据补全摘要
    3. 确保关键数值信息被包含

    使用示例：
        service = InformationCompletionService(evidence_store=store)
        missing = service.detect_missing_info(summary, raw_data)
        completed = service.complete(summary_info)
    """

    def __init__(self, evidence_store: EvidenceStore | None = None):
        """初始化服务

        参数：
            evidence_store: 证据存储
        """
        self.evidence_store = evidence_store

    def detect_missing_info(self, summary: str, raw_data: dict[str, Any]) -> list[str]:
        """检测缺失信息

        参数：
            summary: 摘要文本
            raw_data: 原始数据

        返回：
            缺失信息列表
        """
        missing = []

        # 提取原始数据中的关键值
        key_values = self._extract_key_values(raw_data)

        # 检查摘要中是否包含这些值
        for key, value in key_values.items():
            value_str = str(value)
            if value_str not in summary and key not in summary:
                missing.append(f"{key}: {value}")

        return missing

    def _extract_key_values(self, data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
        """提取关键值（数值和关键字符串）

        参数：
            data: 数据
            prefix: 键前缀

        返回：
            关键值字典
        """
        result = {}

        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, int | float):
                result[full_key] = value
            elif isinstance(value, str) and len(value) < 50:
                result[full_key] = value
            elif isinstance(value, dict):
                result.update(self._extract_key_values(value, full_key))

        return result

    def complete(self, summary_info: SummaryInfo) -> SummaryInfo:
        """补全摘要

        参数：
            summary_info: 原始摘要信息

        返回：
            补全后的摘要信息
        """
        if not self.evidence_store:
            return summary_info

        # 收集所有证据数据
        all_evidence_data = {}
        for ref_id in summary_info.evidence_refs:
            data = self.evidence_store.retrieve(ref_id)
            if data:
                all_evidence_data.update(data)

        # 检测缺失信息
        missing = self.detect_missing_info(summary_info.summary, all_evidence_data)

        if not missing:
            return summary_info

        # 补全摘要
        additions = []
        for item in missing[:3]:  # 最多补充3项
            additions.append(item)

        if additions:
            completed_summary = summary_info.summary
            if not completed_summary.endswith("。"):
                completed_summary += "。"
            completed_summary += " 补充信息：" + "; ".join(additions) + "。"

            return SummaryInfo(
                summary=completed_summary,
                evidence_refs=summary_info.evidence_refs,
                level=summary_info.level,
                source_id=summary_info.source_id,
            )

        return summary_info


# ==================== 事件和日志 ====================


@dataclass
class SummaryPublishedEvent(Event):
    """摘要发布事件

    当发布信息附带摘要时触发此事件。
    """

    summary: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    original_event_id: str = ""
    level: str = "standard"


class SummaryPublisher:
    """摘要发布器

    职责：
    1. 发布带摘要的事件
    2. 确保摘要和证据引用被包含

    使用示例：
        publisher = SummaryPublisher(event_bus=event_bus)
        await publisher.publish_summary(summary="...", evidence_refs=["..."])
    """

    def __init__(self, event_bus: EventBus):
        """初始化发布器

        参数：
            event_bus: 事件总线
        """
        self.event_bus = event_bus

    async def publish_summary(
        self,
        summary: str,
        evidence_refs: list[str],
        original_event_id: str = "",
        level: SummaryLevel = SummaryLevel.STANDARD,
    ) -> None:
        """发布摘要事件

        参数：
            summary: 摘要文本
            evidence_refs: 证据引用
            original_event_id: 原始事件ID
            level: 摘要级别
        """
        event = SummaryPublishedEvent(
            source="summary_publisher",
            summary=summary,
            evidence_refs=evidence_refs,
            original_event_id=original_event_id,
            level=level.value,
        )

        await self.event_bus.publish(event)


class SummaryLogger:
    """摘要日志记录器

    职责：
    1. 记录摘要发布日志
    2. 提供日志查询

    使用示例：
        logger = SummaryLogger()
        logger.log_summary(source="node_1", summary="...", evidence_refs=["..."])
        logs = logger.get_logs()
    """

    def __init__(self):
        """初始化日志记录器"""
        self._logs: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def log_summary(
        self,
        source: str,
        summary: str,
        evidence_refs: list[str],
        level: SummaryLevel = SummaryLevel.STANDARD,
    ) -> None:
        """记录摘要日志

        参数：
            source: 来源
            summary: 摘要文本
            evidence_refs: 证据引用
            level: 摘要级别
        """
        with self._lock:
            log_entry = {
                "source": source,
                "summary": summary,
                "evidence_refs": evidence_refs,
                "level": level.value,
                "timestamp": datetime.now().isoformat(),
            }
            self._logs.append(log_entry)

    def get_logs(self, source: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        """获取日志

        参数：
            source: 过滤来源（可选）
            limit: 限制数量（可选）

        返回：
            日志列表
        """
        with self._lock:
            logs = self._logs.copy()

            if source:
                logs = [log for log in logs if log["source"] == source]

            if limit:
                logs = logs[-limit:]

            return logs


# ==================== ConversationAgent集成 ====================


@dataclass
class DecisionWithSummary:
    """带摘要的决策

    用于ConversationAgent发布决策时附带摘要。
    """

    decision_type: str
    payload: dict[str, Any]
    summary: SummaryInfo
    decision_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)


class SummaryEnabledConversationAgent:
    """摘要增强的ConversationAgent

    在原有ConversationAgent基础上增加摘要功能。

    职责：
    1. 执行ReAct循环
    2. 发布决策时附带摘要
    3. 支持摘要事件订阅

    使用示例：
        agent = SummaryEnabledConversationAgent(
            session_context=session_ctx,
            llm=llm,
            event_bus=event_bus
        )
        result = await agent.run_async("创建节点")
    """

    def __init__(
        self,
        session_context: Any,
        llm: Any,
        event_bus: EventBus | None = None,
        max_iterations: int = 10,
        evidence_store: EvidenceStore | None = None,
    ):
        """初始化

        参数：
            session_context: 会话上下文
            llm: LLM接口
            event_bus: 事件总线
            max_iterations: 最大迭代次数
            evidence_store: 证据存储
        """
        self.session_context = session_context
        self.llm = llm
        self.event_bus = event_bus
        self.max_iterations = max_iterations
        self.evidence_store = evidence_store or EvidenceStore()
        self.summary_generator = SummaryGenerator(evidence_store=self.evidence_store)
        self.summary_publisher = SummaryPublisher(event_bus) if event_bus else None

    async def run_async(self, user_input: str) -> dict[str, Any]:
        """异步运行

        参数：
            user_input: 用户输入

        返回：
            执行结果
        """
        from src.domain.agents.conversation_agent import ReActResult

        result = ReActResult()

        for i in range(self.max_iterations):
            result.iterations = i + 1

            # 思考
            context = {"user_input": user_input, "iteration": i + 1}
            await self.llm.think(context)

            # 决定行动
            action = await self.llm.decide_action(context)
            action_type = action.get("action_type", "continue")

            # 生成摘要
            summary_info = self.summary_generator.generate(action, source_id=f"decision_{i}")

            # 发布摘要事件
            if self.summary_publisher and action_type in ["create_node", "execute_workflow"]:
                await self.summary_publisher.publish_summary(
                    summary=summary_info.summary,
                    evidence_refs=summary_info.evidence_refs,
                    original_event_id=f"action_{i}",
                )

            if action_type == "respond":
                result.completed = True
                result.final_response = action.get("response", "完成")
                break

            # 判断是否继续
            should_continue = await self.llm.should_continue(context)
            if not should_continue:
                result.completed = True
                result.final_response = action.get("response", "完成")
                break

        return {
            "completed": result.completed,
            "iterations": result.iterations,
            "final_response": result.final_response,
        }


# ==================== 摘要检索API ====================


class SummaryRetrievalAPI:
    """摘要检索API

    职责：
    1. 提供API获取原始数据
    2. 支持按引用ID检索
    3. 支持按来源列出引用

    使用示例：
        api = SummaryRetrievalAPI(evidence_store=store)
        data = api.get_raw_data(ref_id)
        refs = api.list_references(source_id="node_1")
    """

    def __init__(self, evidence_store: EvidenceStore):
        """初始化API

        参数：
            evidence_store: 证据存储
        """
        self.evidence_store = evidence_store

    def get_raw_data(self, ref_id: str, data_path: str | None = None) -> Any:
        """获取原始数据

        参数：
            ref_id: 引用ID
            data_path: 数据路径（可选）

        返回：
            原始数据
        """
        return self.evidence_store.retrieve(ref_id, data_path)

    def list_references(self, source_id: str) -> list[str]:
        """列出引用

        参数：
            source_id: 来源ID

        返回：
            引用ID列表
        """
        return self.evidence_store.list_by_source(source_id)

    def get_reference_details(self, ref_id: str) -> EvidenceReference | None:
        """获取引用详情

        参数：
            ref_id: 引用ID

        返回：
            引用详情
        """
        return self.evidence_store.get_reference(ref_id)


# 导出
__all__ = [
    # 枚举
    "SummaryLevel",
    # 数据结构
    "SummaryInfo",
    "EvidenceReference",
    "ValidationResult",
    # 核心服务
    "EvidenceStore",
    "SummaryGenerator",
    "SummaryValidator",
    "InformationCompletionService",
    # 事件和日志
    "SummaryPublishedEvent",
    "SummaryPublisher",
    "SummaryLogger",
    # Agent集成
    "DecisionWithSummary",
    "SummaryEnabledConversationAgent",
    # API
    "SummaryRetrievalAPI",
]
