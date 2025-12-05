"""上下文管理器 (Context Manager) - 多Agent协作系统的上下文管理

业务定义：
- 管理多层上下文：Global → Session → Workflow → Node
- 各层有不同的生命周期和访问权限
- 支持上下文继承和数据桥接

设计原则：
- 全局上下文只读，保护系统配置
- 会话上下文管理目标栈和对话历史
- 工作流上下文相互隔离，支持并发
- 节点上下文临时存在，执行完销毁

层级关系：
    GlobalContext (只读，整个会话)
        ↓ 继承
    SessionContext (读写，单次会话)
        ↓ 派生
    WorkflowContext (隔离，单个工作流)
        ↓ 临时
    NodeContext (临时，单个节点执行)
"""

from collections.abc import Callable
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
    """???????? (Step 2)

    ? SessionContext ? usage_ratio ??????? 0.92?????
    ????????????????
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
        """????"""
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

    __slots__ = ("_user_id", "_user_preferences", "_system_config", "_created_at")

    def __init__(
        self,
        user_id: str,
        user_preferences: dict[str, Any] | None = None,
        system_config: dict[str, Any] | None = None,
    ):
        """初始化全局上下文

        参数：
            user_id: 用户ID
            user_preferences: 用户偏好设置
            system_config: 系统配置
        """
        object.__setattr__(self, "_user_id", user_id)
        object.__setattr__(self, "_user_preferences", user_preferences or {})
        object.__setattr__(self, "_system_config", system_config or {})
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

    def __setattr__(self, key: str, value: Any) -> None:
        """禁止修改属性"""
        raise AttributeError(f"GlobalContext is immutable, cannot modify '{key}'")


@dataclass
class SessionContext:
    """会话上下文

    职责：
    - 继承全局上下文（只读访问）
    - 管理对话历史
    - 管理目标栈（支持嵌套目标）
    - 记录决策历史
    - 跟踪上下文使用情况（token 使用和使用率）

    生命周期：单次用户会话

    使用示例：
        session_ctx = SessionContext(
            session_id="session_abc",
            global_context=global_ctx
        )
        session_ctx.push_goal(goal)
        session_ctx.add_message({"role": "user", "content": "..."})
        session_ctx.set_model_info("openai", "gpt-4", 8192)
        session_ctx.update_token_usage(prompt_tokens=100, completion_tokens=50)
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

    def add_message(self, message: dict[str, Any]) -> None:
        """添加消息到对话历史

        参数：
            message: 消息字典，包含role和content
        """
        self.conversation_history.append(message)

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


@dataclass
class WorkflowContext:
    """工作流上下文

    职责：
    - 引用会话上下文（只读）
    - 存储节点输出数据
    - 管理工作流变量
    - 记录执行历史

    设计特点：
    - 每个工作流有独立的上下文，相互隔离
    - 支持并发执行多个工作流
    - 节点间通过此上下文传递数据

    生命周期：单个工作流执行

    使用示例：
        workflow_ctx = WorkflowContext(
            workflow_id="workflow_xyz",
            session_context=session_ctx
        )
        workflow_ctx.set_node_output("node_1", {"result": "success"})
        output = workflow_ctx.get_node_output("node_1", "result")
    """

    workflow_id: str
    session_context: SessionContext

    # 节点输出数据: node_id -> outputs
    node_data: dict[str, dict[str, Any]] = field(default_factory=dict)

    # 工作流变量
    variables: dict[str, Any] = field(default_factory=dict)

    # 执行历史
    execution_history: list[dict[str, Any]] = field(default_factory=list)

    def set_node_output(self, node_id: str, outputs: dict[str, Any]) -> None:
        """设置节点输出

        参数：
            node_id: 节点ID
            outputs: 输出数据字典
        """
        self.node_data[node_id] = outputs

    def get_node_output(self, node_id: str, key: str | None = None) -> Any:
        """获取节点输出

        参数：
            node_id: 节点ID
            key: 可选，获取特定的输出key

        返回：
            如果指定key，返回该key的值
            否则返回整个输出字典
        """
        outputs = self.node_data.get(node_id, {})
        if key is not None:
            return outputs.get(key)
        return outputs

    def set_variable(self, name: str, value: Any) -> None:
        """设置工作流变量

        参数：
            name: 变量名
            value: 变量值
        """
        self.variables[name] = value

    def get_variable(self, name: str, default: Any = None) -> Any:
        """获取工作流变量

        参数：
            name: 变量名
            default: 默认值（变量不存在时返回）

        返回：
            变量值，或默认值
        """
        return self.variables.get(name, default)


@dataclass
class NodeContext:
    """节点上下文

    职责：
    - 引用工作流上下文
    - 存储节点输入
    - 跟踪执行状态
    - 存储节点输出

    生命周期：单个节点执行（最短）

    使用示例：
        node_ctx = NodeContext(
            node_id="node_llm_1",
            workflow_context=workflow_ctx,
            inputs={"prompt": "分析数据"}
        )
        node_ctx.set_state("running")
        node_ctx.set_output("result", "分析完成")
        node_ctx.set_state("completed")
    """

    node_id: str
    workflow_context: WorkflowContext

    # 节点输入
    inputs: dict[str, Any] = field(default_factory=dict)

    # 节点输出
    outputs: dict[str, Any] = field(default_factory=dict)

    # 执行状态: pending | running | completed | failed
    execution_state: str = "pending"

    # 错误信息（如果失败）
    error: str | None = None

    # 时间戳
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def set_state(self, state: str) -> None:
        """设置执行状态

        参数：
            state: 状态值 (pending/running/completed/failed)
        """
        self.execution_state = state

        if state == "running":
            self.started_at = datetime.now()
        elif state in ("completed", "failed"):
            self.completed_at = datetime.now()

    def set_output(self, key: str, value: Any) -> None:
        """设置输出值

        参数：
            key: 输出key
            value: 输出值
        """
        self.outputs[key] = value


class ContextBridge:
    """上下文桥接器

    职责：
    - 在工作流上下文之间传递数据
    - 支持选择性传递（只传递需要的数据）
    - 支持数据摘要（减少token消耗）

    使用场景：
    - 目标分解后，子工作流之间传递结果
    - 工作流完成后，结果传递给下一个工作流

    使用示例：
        bridge = ContextBridge()
        bridge.transfer(source_workflow, target_workflow, keys=["result"])
    """

    def transfer(
        self, source: WorkflowContext, target: WorkflowContext, keys: list[str] | None = None
    ) -> dict[str, Any]:
        """传递数据

        参数：
            source: 源工作流上下文
            target: 目标工作流上下文
            keys: 要传递的key列表，None表示传递所有

        返回：
            传递的数据
        """
        # 收集要传递的数据
        transferred_data = {}

        # 从节点输出收集
        for _node_id, outputs in source.node_data.items():
            for key, value in outputs.items():
                if keys is None or key in keys:
                    transferred_data[key] = value

        # 从变量收集
        for var_name, var_value in source.variables.items():
            if keys is None or var_name in keys:
                transferred_data[var_name] = var_value

        # 注入到目标上下文
        target.set_variable("__transferred__", transferred_data)

        return transferred_data

    def transfer_with_summary(
        self,
        source: WorkflowContext,
        target: WorkflowContext,
        summary_fn: Callable[[Any], dict[str, Any]],
    ) -> dict[str, Any]:
        """传递数据并摘要

        参数：
            source: 源工作流上下文
            target: 目标工作流上下文
            summary_fn: 摘要函数，接收原始数据，返回摘要

        返回：
            摘要后的数据
        """
        # 收集所有数据
        all_data = []
        for _node_id, outputs in source.node_data.items():
            all_data.extend(outputs.values())

        for var_value in source.variables.values():
            all_data.append(var_value)

        # 应用摘要函数
        if all_data:
            # 如果数据是列表，展开传递
            if len(all_data) == 1:
                summarized = summary_fn(all_data[0])
            else:
                summarized = summary_fn(all_data)
        else:
            summarized = {}

        # 注入到目标上下文
        target.set_variable("__transferred__", summarized)

        return summarized


# 导出
__all__ = [
    "Goal",
    "GlobalContext",
    "SessionContext",
    "WorkflowContext",
    "NodeContext",
    "ContextBridge",
]
