"""统一的SessionContext定义 - 单一来源

业务定义：
- 统一context_manager和context_bridge的SessionContext定义
- 提供唯一的数据结构定义，避免重复和不一致
- 支持向后兼容，提供两种add_message接口

设计原则：
- 单一职责：仅定义上下文数据结构
- 向后兼容：保持现有接口不变
- 类型安全：完整的类型注解

架构位置：
    domain/entities/session_context.py (本文件)
        ↑ 导入
    domain/services/context_manager.py (re-export)
        ↑ 导入
    domain/services/context_bridge.py (使用统一定义)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from src.domain.services.event_bus import Event

if TYPE_CHECKING:
    from src.domain.services.event_bus import EventBus
    from src.domain.services.short_term_buffer import ShortTermBuffer
    from src.domain.services.structured_dialogue_summary import StructuredDialogueSummary


@dataclass
class Goal:
    """目标实体

    用于目标栈管理，支持嵌套目标结构。

    属性：
    - id: 目标唯一标识
    - description: 目标描述
    - parent_id: 父目标ID（用于目标分解）
    - status: 目标状态
    """

    id: str
    description: str
    parent_id: str | None = None
    status: str = "pending"


@dataclass
class ShortTermSaturatedEvent(Event):
    """短期记忆饱和事件 (Step 2)

    当 SessionContext 的 usage_ratio 达到饱和阈值 0.92 时触发。
    订阅者可以执行上下文压缩。
    """

    def __init__(
        self,
        session_id: str,
        usage_ratio: float,
        total_tokens: int,
        context_limit: int,
        buffer_size: int,
        source: str = "session_context",
    ) -> None:
        super().__init__(source=source)
        self.session_id = session_id
        self.usage_ratio = usage_ratio
        self.total_tokens = total_tokens
        self.context_limit = context_limit
        self.buffer_size = buffer_size

    @property
    def event_type(self) -> str:
        """事件类型"""
        return "short_term_saturated"


class GlobalContext:
    """全局上下文 - 只读

    职责：
    - 存储用户信息和偏好
    - 存储系统配置
    - 整个会话期间不可修改

    为什么设计为只读？
    1. 保护系统配置不被Agent意外修改
    2. 确保多Agent共享时的一致性
    3. 作为所有下层上下文的稳定基础

    使用示例：
        global_ctx = GlobalContext(
            user_id="user_123",
            user_preferences={"language": "zh-CN"},
            system_config={"max_tokens": 10000}
        )
    """

    __slots__ = ("_user_id", "_user_preferences", "_system_config", "_global_goals", "_created_at")

    def __init__(
        self,
        user_id: str,
        user_preferences: dict[str, Any] | None = None,
        system_config: dict[str, Any] | None = None,
        global_goals: list[Any] | None = None,
    ):
        """初始化全局上下文

        参数：
            user_id: 用户ID
            user_preferences: 用户偏好设置
            system_config: 系统配置
            global_goals: 全局目标列表（用于跨会话目标管理）
        """
        object.__setattr__(self, "_user_id", user_id)
        object.__setattr__(self, "_user_preferences", user_preferences or {})
        object.__setattr__(self, "_system_config", system_config or {})
        object.__setattr__(self, "_global_goals", global_goals or [])
        object.__setattr__(self, "_created_at", datetime.now())

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def user_preferences(self) -> dict[str, Any]:
        return self._user_preferences.copy()  # 返回副本，防止修改

    @property
    def system_config(self) -> dict[str, Any]:
        return self._system_config.copy()  # 返回副本，防止修改

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def global_goals(self) -> list[Any]:
        return self._global_goals.copy()  # 返回副本，防止修改

    def __setattr__(self, key: str, value: Any) -> None:
        """禁止修改属性"""
        raise AttributeError(f"GlobalContext is immutable, cannot modify '{key}'")


@dataclass
class SessionContext:
    """会话上下文 - 统一定义

    职责：
    - 继承全局上下文（只读访问）
    - 管理对话历史
    - 管理目标栈（支持嵌套目标）
    - 记录决策历史
    - 跟踪上下文使用情况（token 使用和使用率）
    - 跟踪资源约束（时间限制、并发限制等）

    生命周期：单次用户会话

    向后兼容：
    - add_message(dict) - context_manager风格
    - add_message_simple(role, content) - context_bridge风格

    使用示例：
        session_ctx = SessionContext(
            session_id="session_abc",
            global_context=global_ctx
        )
        # context_manager风格
        session_ctx.add_message({"role": "user", "content": "..."})
        # context_bridge风格
        session_ctx.add_message_simple("user", "...")
    """

    session_id: str
    global_context: GlobalContext

    # 对话历史
    conversation_history: list[dict[str, Any]] = field(default_factory=list)

    # 目标栈 - 支持嵌套目标
    goal_stack: list[Goal] = field(default_factory=list)

    # 决策历史 - 用于审计
    decision_history: list[dict[str, Any]] = field(default_factory=list)

    # 摘要缓存
    conversation_summary: str | None = None

    # Token 使用跟踪（Step 1: 模型上下文能力确认）
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    usage_ratio: float = 0.0

    # 模型信息
    llm_provider: str | None = None
    llm_model: str | None = None
    context_limit: int = 0

    # Step 2: 短期记忆缓冲区
    short_term_buffer: list["ShortTermBuffer"] = field(default_factory=list)
    is_saturated: bool = False
    saturation_threshold: float = 0.92
    _event_bus: "EventBus | None" = field(default=None, repr=False)

    # Step 3: 会话冻结与备份
    _is_frozen: bool = field(default=False, repr=False)
    _backup: dict[str, Any] | None = field(default=None, repr=False)

    # 资源约束（工作流执行限制）
    resource_constraints: dict[str, Any] | None = field(default=None)

    # 画布状态（双向同步使用）
    canvas_state: dict[str, Any] | None = field(default=None)

    def add_message(
        self,
        message: dict[str, Any] | None = None,
        role: str | None = None,
        content: str | None = None,
    ) -> None:
        """添加消息到对话历史（支持双签名）

        支持两种调用方式：
        1. context_manager风格: add_message({"role": "user", "content": "..."})
        2. context_bridge风格: add_message(role="user", content="...")

        参数：
            message: 消息字典（包含role和content）
            role: 消息角色（user/assistant/system）
            content: 消息内容

        异常：
            ValueError: 如果参数组合无效
        """
        if message is not None:
            # context_manager风格：使用dict参数
            self.conversation_history.append(message)
        elif role is not None and content is not None:
            # context_bridge风格：使用role和content参数
            self.add_message_simple(role, content)
        else:
            raise ValueError(
                "Must provide either 'message' dict or both 'role' and 'content'. "
                "Examples: add_message({'role': 'user', 'content': '...'}) "
                "or add_message(role='user', content='...')"
            )

    def add_message_simple(self, role: str, content: str) -> None:
        """添加消息到对话历史（context_bridge兼容接口）

        参数：
            role: 消息角色（user/assistant/system）
            content: 消息内容

        说明：
            自动添加timestamp字段，兼容旧的context_bridge代码
        """
        self.add_message(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def push_goal(self, goal: Goal) -> None:
        """将目标压入栈

        参数：
            goal: 目标实体
        """
        self.goal_stack.append(goal)

    def pop_goal(self) -> Goal | None:
        """从栈顶弹出目标

        返回：
            弹出的目标，如果栈为空返回None
        """
        if self.goal_stack:
            return self.goal_stack.pop()
        return None

    def current_goal(self) -> Goal | None:
        """获取当前目标（栈顶）

        返回：
            栈顶目标，如果栈为空返回None
        """
        if self.goal_stack:
            return self.goal_stack[-1]
        return None

    def add_decision(self, decision: dict[str, Any]) -> None:
        """记录决策

        参数：
            decision: 决策字典
        """
        self.decision_history.append(decision)

    def set_model_info(self, provider: str, model: str, context_limit: int) -> None:
        """设置模型信息

        参数：
            provider: LLM 提供商名称
            model: 模型名称
            context_limit: 上下文窗口大小
        """
        self.llm_provider = provider
        self.llm_model = model
        self.context_limit = context_limit

        # 重新计算使用率
        self._recalculate_usage_ratio()

    def update_token_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        """更新 token 使用情况

        参数：
            prompt_tokens: 本轮使用的 prompt tokens
            completion_tokens: 本轮使用的 completion tokens
        """
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_tokens = self.total_prompt_tokens + self.total_completion_tokens

        # 重新计算使用率
        self._recalculate_usage_ratio()

    def _recalculate_usage_ratio(self) -> None:
        """重新计算使用率（内部方法）"""
        if self.context_limit > 0:
            self.usage_ratio = self.total_tokens / self.context_limit
        else:
            self.usage_ratio = 0.0

    def get_usage_ratio(self) -> float:
        """获取当前上下文使用率

        返回：
            使用率（0-1 之间，超过 1 表示超限）
        """
        return self.usage_ratio

    def is_approaching_limit(self, threshold: float = 0.8) -> bool:
        """判断是否接近上下文限制

        参数：
            threshold: 阈值（默认 0.8，即 80%）

        返回：
            是否接近限制
        """
        return self.usage_ratio >= threshold

    def get_remaining_tokens(self) -> int:
        """获取剩余可用 token 数

        返回：
            剩余 token 数（最小为 0）
        """
        remaining = self.context_limit - self.total_tokens
        return max(0, remaining)

    def get_token_usage_summary(self) -> dict[str, Any]:
        """获取 token 使用摘要

        返回：
            包含所有 token 使用信息的字典
        """
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "usage_ratio": self.usage_ratio,
            "context_limit": self.context_limit,
            "remaining_tokens": self.get_remaining_tokens(),
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
        }

    def reset_token_usage(self) -> None:
        """重置 token 使用计数器"""
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.usage_ratio = 0.0

    def set_event_bus(self, event_bus: "EventBus") -> None:
        """设置事件总线（Step 2）

        参数：
            event_bus: EventBus 实例
        """
        self._event_bus = event_bus

    def check_saturation(self, threshold: float | None = None) -> bool:
        """检查是否达到饱和阈值（Step 2）

        参数：
            threshold: 自定义阈值（可选，默认使用 saturation_threshold）

        返回：
            是否达到饱和阈值
        """
        if threshold is None:
            threshold = self.saturation_threshold

        return self.usage_ratio >= threshold

    def _trigger_saturation_event(self) -> None:
        """触发饱和事件（Step 2，内部方法）

        发布 ShortTermSaturatedEvent 并设置 is_saturated 标志。
        """
        import asyncio
        import logging

        logger = logging.getLogger(__name__)

        # 设置饱和标志（防止重复触发）
        self.is_saturated = True

        # 发布事件
        if self._event_bus:
            event = ShortTermSaturatedEvent(
                source="session_context",
                session_id=self.session_id,
                usage_ratio=self.usage_ratio,
                total_tokens=self.total_tokens,
                context_limit=self.context_limit,
                buffer_size=len(self.short_term_buffer),
            )

            # 异步发布事件
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._event_bus.publish(event))
                else:
                    loop.run_until_complete(self._event_bus.publish(event))
            except RuntimeError:
                # 如果没有事件循环，创建新的
                asyncio.run(self._event_bus.publish(event))

            logger.warning(
                f"🔴 Short-term memory saturated! "
                f"Session: {self.session_id}, "
                f"Usage: {self.usage_ratio:.1%}, "
                f"Buffer size: {len(self.short_term_buffer)} turns"
            )

    def reset_saturation(self) -> None:
        """重置饱和状态（Step 2）

        清除 is_saturated 标志，允许再次触发饱和事件。
        通常在上下文压缩完成后调用。
        """
        self.is_saturated = False

    def freeze(self) -> None:
        """冻结会话（Step 3）

        冻结会话后，不允许修改会话状态。
        用于在压缩过程中防止并发修改。
        """
        self._is_frozen = True

    def unfreeze(self) -> None:
        """解冻会话（Step 3）

        解冻会话，允许修改会话状态。
        """
        self._is_frozen = False

    def is_frozen(self) -> bool:
        """判断会话是否被冻结（Step 3）

        返回：
            是否被冻结
        """
        return self._is_frozen

    def create_backup(self) -> dict[str, Any]:
        """创建会话备份（Step 3）

        备份当前会话状态，用于压缩失败时回滚。

        返回：
            包含会话状态的备份字典
        """

        backup = {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "usage_ratio": self.usage_ratio,
            "short_term_buffer": [buffer.to_dict() for buffer in self.short_term_buffer],
            "conversation_summary": self.conversation_summary,
            "is_saturated": self.is_saturated,
        }

        self._backup = backup
        return backup

    def restore_from_backup(self, backup: dict[str, Any]) -> None:
        """从备份恢复会话状态（Step 3）

        参数：
            backup: 备份字典
        """
        from src.domain.services.short_term_buffer import ShortTermBuffer

        self.total_prompt_tokens = backup["total_prompt_tokens"]
        self.total_completion_tokens = backup["total_completion_tokens"]
        self.total_tokens = backup["total_tokens"]
        self.usage_ratio = backup["usage_ratio"]
        self.short_term_buffer = [
            ShortTermBuffer.from_dict(data) for data in backup["short_term_buffer"]
        ]
        self.conversation_summary = backup["conversation_summary"]
        self.is_saturated = backup["is_saturated"]

    def compress_buffer_with_summary(
        self, summary: "StructuredDialogueSummary", keep_recent_turns: int = 2
    ) -> None:
        """用摘要压缩 buffer（Step 3）

        将旧的对话轮次压缩为摘要，只保留最近的 N 轮。

        参数：
            summary: 结构化对话摘要
            keep_recent_turns: 保留最近的轮次数（默认 2）
        """
        # 保留最近的 N 轮
        if len(self.short_term_buffer) > keep_recent_turns:
            self.short_term_buffer = self.short_term_buffer[-keep_recent_turns:]

        # 存储摘要（转换为文本格式）
        self.conversation_summary = summary.to_text()

    def add_turn(self, buffer: "ShortTermBuffer") -> None:
        """添加对话轮次到短期缓冲区（Step 2）

        参数：
            buffer: ShortTermBuffer 实例

        说明：
            - 添加轮次到缓冲区
            - 检测是否达到饱和阈值
            - 如果达到阈值且未饱和，发布 ShortTermSaturatedEvent

        异常：
            RuntimeError: 如果会话被冻结
        """
        # Step 3: 检查会话是否被冻结
        if self._is_frozen:
            raise RuntimeError("Cannot add turn to frozen session (会话已冻结，无法添加轮次)")

        # 添加到缓冲区
        self.short_term_buffer.append(buffer)

        # 检测饱和
        if not self.is_saturated and self.check_saturation():
            self._trigger_saturation_event()


# 导出
__all__ = [
    "Goal",
    "GlobalContext",
    "SessionContext",
    "ShortTermSaturatedEvent",
]
