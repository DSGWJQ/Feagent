"""上下文桥接器（ContextBridge）

高级上下文管理功能，实现分层上下文和工作流间上下文传递。

组件：
- GlobalContext: 全局上下文（只读）
- SessionContext: 会话上下文
- WorkflowContext: 工作流上下文
- NodeContext: 节点上下文
- ContextBridge: 上下文桥接器
- ContextSummarizer: 上下文摘要器
- ContextManager: 上下文管理器

功能：
- 分层上下文继承
- 工作流间上下文传递
- LLM智能摘要
- 上下文生命周期管理

设计原则：
- 全局上下文只读，保护系统配置
- 会话上下文管理对话和目标
- 工作流上下文相互隔离
- 节点上下文临时存在

"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class SummarizationError(Exception):
    """摘要错误"""

    pass


class GlobalContext:
    """全局上下文 - 只读

    存储用户信息和系统配置，整个会话期间不可修改。

    属性：
        user_id: 用户ID
        user_preferences: 用户偏好
        system_config: 系统配置
        global_goals: 全局目标列表
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
            user_preferences: 用户偏好
            system_config: 系统配置
            global_goals: 全局目标列表
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
        return self._user_preferences.copy()

    @property
    def system_config(self) -> dict[str, Any]:
        return self._system_config.copy()

    @property
    def global_goals(self) -> list[Any]:
        return self._global_goals.copy()

    @property
    def created_at(self) -> datetime:
        return self._created_at

    def is_readonly(self) -> bool:
        """检查是否只读"""
        return True

    def __setattr__(self, key: str, value: Any) -> None:
        """禁止修改属性"""
        raise AttributeError(f"GlobalContext is immutable, cannot modify '{key}'")


@dataclass
class SessionContext:
    """会话上下文

    管理对话历史、目标栈和决策历史。

    属性：
        session_id: 会话ID
        global_context: 全局上下文引用
        conversation_history: 对话历史
        goal_stack: 目标栈
        decision_history: 决策历史
    """

    session_id: str
    global_context: GlobalContext

    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    goal_stack: list[Any] = field(default_factory=list)
    decision_history: list[dict[str, Any]] = field(default_factory=list)
    conversation_summary: str | None = None

    def add_message(self, role: str, content: str) -> None:
        """添加消息到对话历史

        参数：
            role: 消息角色 (user/assistant/system)
            content: 消息内容
        """
        self.conversation_history.append(
            {"role": role, "content": content, "timestamp": datetime.now().isoformat()}
        )

    def push_goal(self, goal: Any) -> None:
        """将目标压入栈

        参数：
            goal: 目标实体
        """
        self.goal_stack.append(goal)

    def pop_goal(self) -> Any | None:
        """从栈顶弹出目标

        返回：
            弹出的目标，如果栈为空返回None
        """
        if self.goal_stack:
            return self.goal_stack.pop()
        return None

    def current_goal(self) -> Any | None:
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


@dataclass
class WorkflowContext:
    """工作流上下文

    存储节点输出和工作流变量。

    属性：
        workflow_id: 工作流ID
        session_context: 会话上下文引用
        node_data: 节点输出数据
        variables: 工作流变量
        execution_history: 执行历史
    """

    workflow_id: str
    session_context: SessionContext

    node_data: dict[str, dict[str, Any]] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)
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
            如果指定key，返回该key的值，否则返回整个输出字典
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
            default: 默认值

        返回：
            变量值，或默认值
        """
        return self.variables.get(name, default)


@dataclass
class NodeContext:
    """节点上下文

    临时存储节点输入输出和执行状态。

    属性：
        node_id: 节点ID
        workflow_context: 工作流上下文引用
        inputs: 输入数据
        outputs: 输出数据
        execution_state: 执行状态
    """

    node_id: str
    workflow_context: WorkflowContext

    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    execution_state: str = "pending"
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def set_inputs(self, inputs: dict[str, Any]) -> None:
        """设置输入数据

        参数：
            inputs: 输入数据字典
        """
        self.inputs = inputs

    def set_outputs(self, outputs: dict[str, Any]) -> None:
        """设置输出数据

        参数：
            outputs: 输出数据字典
        """
        self.outputs = outputs

    def start(self) -> None:
        """开始执行"""
        self.execution_state = "running"
        self.started_at = datetime.now()

    def complete(self) -> None:
        """完成执行"""
        self.execution_state = "completed"
        self.completed_at = datetime.now()

    def fail(self, error: str) -> None:
        """执行失败

        参数：
            error: 错误信息
        """
        self.execution_state = "failed"
        self.error = error
        self.completed_at = datetime.now()


class LLMClientProtocol(Protocol):
    """LLM客户端协议"""

    async def generate(self, prompt: str) -> str:
        """生成响应"""
        ...


class ContextSummarizer:
    """上下文摘要器

    使用LLM对上下文数据进行智能摘要。
    """

    def __init__(self, llm_client: LLMClientProtocol):
        """初始化

        参数：
            llm_client: LLM客户端
        """
        self.llm = llm_client

    async def summarize(self, data: dict[str, Any], max_tokens: int = 1000) -> dict[str, Any]:
        """摘要上下文数据

        参数：
            data: 要摘要的数据
            max_tokens: 最大token数

        返回：
            摘要结果

        异常：
            SummarizationError: 摘要失败时抛出
        """
        prompt = f"""
请对以下数据进行摘要，保留关键信息：

数据: {json.dumps(data, ensure_ascii=False, indent=2)}

要求:
1. 保留关键的输入输出值
2. 保留重要的中间结果
3. 总结执行过程
4. 控制输出在{max_tokens}个token以内

输出格式 (JSON):
{{
    "summary": "执行摘要",
    "key_outputs": {{}},
    "important_values": {{}}
}}
"""

        try:
            response = await self.llm.generate(prompt)
            return json.loads(response)
        except json.JSONDecodeError as e:
            raise SummarizationError(f"LLM返回的JSON格式无效: {e}") from e


class ContextBridge:
    """上下文桥接器

    在工作流之间传递上下文数据，支持可选的摘要功能。
    """

    def __init__(self, summarizer: ContextSummarizer | None = None):
        """初始化

        参数：
            summarizer: 可选的上下文摘要器
        """
        self.summarizer = summarizer

    async def transfer(
        self,
        source: WorkflowContext,
        target: WorkflowContext,
        summarize: bool = False,
        max_tokens: int = 1000,
    ) -> dict[str, Any]:
        """在工作流间传递上下文

        参数：
            source: 源工作流上下文
            target: 目标工作流上下文
            summarize: 是否进行摘要
            max_tokens: 摘要最大token数

        返回：
            传递的数据
        """
        # 收集数据
        data = {"outputs": source.node_data.copy(), "variables": source.variables.copy()}

        if summarize and self.summarizer:
            # 进行摘要
            data = await self.summarizer.summarize(data, max_tokens)

        # 注入到目标上下文
        target.variables["__transferred__"] = data

        return data


class ContextManager:
    """上下文管理器

    管理所有上下文的创建、获取和清理。
    """

    def __init__(self):
        """初始化"""
        self._global_contexts: dict[str, GlobalContext] = {}
        self._session_contexts: dict[str, SessionContext] = {}
        self._workflow_contexts: dict[str, WorkflowContext] = {}

    def create_global_context(
        self,
        user_id: str,
        user_preferences: dict[str, Any] | None = None,
        system_config: dict[str, Any] | None = None,
        global_goals: list[Any] | None = None,
    ) -> GlobalContext:
        """创建全局上下文

        参数：
            user_id: 用户ID
            user_preferences: 用户偏好
            system_config: 系统配置
            global_goals: 全局目标

        返回：
            创建的全局上下文
        """
        ctx = GlobalContext(
            user_id=user_id,
            user_preferences=user_preferences,
            system_config=system_config,
            global_goals=global_goals,
        )
        self._global_contexts[user_id] = ctx
        return ctx

    def create_session_context(
        self, session_id: str, global_context: GlobalContext
    ) -> SessionContext:
        """创建会话上下文

        参数：
            session_id: 会话ID
            global_context: 全局上下文

        返回：
            创建的会话上下文
        """
        ctx = SessionContext(session_id=session_id, global_context=global_context)
        self._session_contexts[session_id] = ctx
        return ctx

    def create_workflow_context(
        self, workflow_id: str, session_context: SessionContext
    ) -> WorkflowContext:
        """创建工作流上下文

        参数：
            workflow_id: 工作流ID
            session_context: 会话上下文

        返回：
            创建的工作流上下文
        """
        ctx = WorkflowContext(workflow_id=workflow_id, session_context=session_context)
        self._workflow_contexts[workflow_id] = ctx
        return ctx

    def get_global_context(self, user_id: str) -> GlobalContext | None:
        """获取全局上下文

        参数：
            user_id: 用户ID

        返回：
            全局上下文，不存在返回None
        """
        return self._global_contexts.get(user_id)

    def get_session_context(self, session_id: str) -> SessionContext | None:
        """获取会话上下文

        参数：
            session_id: 会话ID

        返回：
            会话上下文，不存在返回None
        """
        return self._session_contexts.get(session_id)

    def get_workflow_context(self, workflow_id: str) -> WorkflowContext | None:
        """获取工作流上下文

        参数：
            workflow_id: 工作流ID

        返回：
            工作流上下文，不存在返回None
        """
        return self._workflow_contexts.get(workflow_id)

    def cleanup_workflow_context(self, workflow_id: str) -> None:
        """清理工作流上下文

        参数：
            workflow_id: 工作流ID
        """
        if workflow_id in self._workflow_contexts:
            del self._workflow_contexts[workflow_id]

    def cleanup_session_context(self, session_id: str) -> None:
        """清理会话上下文

        参数：
            session_id: 会话ID
        """
        if session_id in self._session_contexts:
            del self._session_contexts[session_id]


# 导出
__all__ = [
    "GlobalContext",
    "SessionContext",
    "WorkflowContext",
    "NodeContext",
    "ContextBridge",
    "ContextSummarizer",
    "ContextManager",
    "SummarizationError",
    "LLMClientProtocol",
]
