"""
决策载荷 Pydantic Schema 定义

本模块定义了 ConversationAgent 的 10 种决策类型的 payload schema，
使用 Pydantic 进行强类型验证，确保决策数据的结构正确性。

用法：
    from src.domain.agents.decision_payload import (
        RespondPayload,
        CreateNodePayload,
        CreateWorkflowPlanPayload,
    )

    # 验证 payload
    payload = RespondPayload(
        action_type="respond",
        response="您好！",
        intent="greeting",
        confidence=1.0
    )

    # 转换为字典
    payload_dict = payload.model_dump()
"""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ========================================
# 枚举定义
# ========================================


class ActionType(str, Enum):
    """决策动作类型（与 DecisionType 对应）"""

    RESPOND = "respond"
    CREATE_NODE = "create_node"
    CREATE_WORKFLOW_PLAN = "create_workflow_plan"
    EXECUTE_WORKFLOW = "execute_workflow"
    REQUEST_CLARIFICATION = "request_clarification"
    CONTINUE = "continue"
    MODIFY_NODE = "modify_node"
    ERROR_RECOVERY = "error_recovery"
    REPLAN_WORKFLOW = "replan_workflow"
    SPAWN_SUBAGENT = "spawn_subagent"


class IntentType(str, Enum):
    """意图类型"""

    GREETING = "greeting"
    SIMPLE_QUERY = "simple_query"
    COMPLEX_TASK = "complex_task"
    WORKFLOW_REQUEST = "workflow"
    UNKNOWN = "unknown"


class NodeType(str, Enum):
    """节点类型"""

    START = "START"
    END = "END"
    PYTHON = "PYTHON"
    LLM = "LLM"
    HTTP = "HTTP"
    DATABASE = "DATABASE"
    CONDITION = "CONDITION"
    LOOP = "LOOP"
    PARALLEL = "PARALLEL"
    CONTAINER = "CONTAINER"
    FILE = "FILE"  # Phase 4: 文件操作节点
    DATA_PROCESS = "DATA_PROCESS"  # Phase 4: 数据处理节点
    HUMAN = "HUMAN"  # Phase 4: 人机交互节点
    GENERIC = "GENERIC"  # Phase 4: 通用节点


class ExecutionMode(str, Enum):
    """执行模式"""

    SYNC = "sync"
    ASYNC = "async"


class RecoveryAction(str, Enum):
    """恢复动作"""

    RETRY = "RETRY"
    SKIP = "SKIP"
    ABORT = "ABORT"
    MODIFY = "MODIFY"


# ========================================
# Payload Schema 定义
# ========================================


class RespondPayload(BaseModel):
    """RESPOND 决策的 payload

    场景：简单问候、查询，直接回复用户

    示例：
        {
            "action_type": "respond",
            "response": "您好！我是智能助手。",
            "intent": "greeting",
            "confidence": 1.0,
            "requires_followup": False
        }
    """

    action_type: Literal[ActionType.RESPOND] = Field(ActionType.RESPOND, description="动作类型")
    response: str = Field(..., min_length=1, description="回复内容")
    intent: IntentType = Field(..., description="意图类型")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度")
    requires_followup: bool = Field(False, description="是否需要后续对话")

    @field_validator("response")
    @classmethod
    def response_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("response 不能为空字符串")
        return v


class RetryConfig(BaseModel):
    """重试配置"""

    max_retries: int = Field(3, ge=1, le=10, description="最大重试次数")
    retry_delay: float = Field(1.0, ge=0.1, le=60.0, description="重试延迟（秒）")


class NodeConfig(BaseModel):
    """节点配置基类"""

    class Config:
        extra = "allow"  # 允许额外字段


class HTTPNodeConfig(NodeConfig):
    """HTTP 节点配置"""

    url: str = Field(..., description="请求 URL")
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = Field("GET", description="HTTP 方法")
    params: dict[str, Any] | None = Field(None, description="查询参数")
    body: dict[str, Any] | None = Field(None, description="请求体")
    headers: dict[str, str] | None = Field(None, description="请求头")
    timeout: int = Field(30, ge=1, le=300, description="超时时间（秒）")


class LLMNodeConfig(NodeConfig):
    """LLM 节点配置"""

    model: str = Field("gpt-4", description="模型名称")
    prompt: str | None = Field(None, description="提示词")
    messages: list[dict[str, str]] | None = Field(None, description="消息列表")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: int = Field(1000, ge=1, le=10000, description="最大 token 数")

    @model_validator(mode="after")
    def check_prompt_or_messages(self) -> "LLMNodeConfig":
        if self.prompt is None and self.messages is None:
            raise ValueError("prompt 或 messages 必须提供其中之一")
        return self


class PythonNodeConfig(NodeConfig):
    """Python 节点配置"""

    code: str = Field(..., min_length=1, description="Python 代码")


class DatabaseNodeConfig(NodeConfig):
    """Database 节点配置"""

    query: str = Field(..., min_length=1, description="SQL 查询语句")
    connection: str = Field(..., description="数据库连接标识")


class CreateNodePayload(BaseModel):
    """CREATE_NODE 决策的 payload

    场景：创建单个工具节点

    示例：
        {
            "action_type": "create_node",
            "node_type": "HTTP",
            "node_name": "获取天气",
            "config": {...},
            "description": "调用天气API",
            "retry_config": {...}
        }
    """

    action_type: Literal[ActionType.CREATE_NODE] = Field(
        ActionType.CREATE_NODE, description="动作类型"
    )
    node_type: NodeType = Field(..., description="节点类型")
    node_name: str = Field(..., min_length=1, description="节点名称")
    config: dict[str, Any] = Field(..., description="节点配置")
    description: str | None = Field(None, description="节点描述")
    retry_config: RetryConfig | None = Field(None, description="重试配置")

    @field_validator("config")
    @classmethod
    def validate_config_by_type(cls, v: dict[str, Any], info) -> dict[str, Any]:
        """根据节点类型验证配置"""
        # 这里可以根据 node_type 进行更细粒度的验证
        # 为了简化，我们只检查配置不为空
        if not v:
            raise ValueError("config 不能为空")
        return v


class WorkflowNode(BaseModel):
    """工作流节点定义"""

    node_id: str = Field(..., description="节点唯一ID")
    type: NodeType = Field(..., description="节点类型")
    name: str = Field(..., min_length=1, description="节点名称")
    config: dict[str, Any] = Field(..., description="节点配置")
    input_mapping: dict[str, str] | None = Field(None, description="输入映射")
    output_mapping: dict[str, str] | None = Field(None, description="输出映射")


class WorkflowEdge(BaseModel):
    """工作流边定义"""

    source: str = Field(..., description="源节点ID")
    target: str = Field(..., description="目标节点ID")
    condition: str | None = Field(None, description="条件表达式")


class CreateWorkflowPlanPayload(BaseModel):
    """CREATE_WORKFLOW_PLAN 决策的 payload

    场景：创建完整工作流

    示例：
        {
            "action_type": "create_workflow_plan",
            "name": "销售数据分析",
            "description": "...",
            "nodes": [...],
            "edges": [...],
            "global_config": {...}
        }
    """

    action_type: Literal[ActionType.CREATE_WORKFLOW_PLAN] = Field(
        ActionType.CREATE_WORKFLOW_PLAN, description="动作类型"
    )
    name: str = Field(..., min_length=1, description="工作流名称")
    description: str = Field(..., min_length=1, description="工作流描述")
    nodes: list[WorkflowNode] = Field(..., min_length=1, description="节点列表")
    edges: list[WorkflowEdge] = Field(..., description="边列表")
    global_config: dict[str, Any] | None = Field(None, description="全局配置")

    @field_validator("nodes")
    @classmethod
    def nodes_not_empty(cls, v: list[WorkflowNode]) -> list[WorkflowNode]:
        if len(v) == 0:
            raise ValueError("至少需要一个节点")
        # 检查节点 ID 唯一性
        node_ids = [node.node_id for node in v]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("节点 ID 必须唯一")
        return v

    @model_validator(mode="after")
    def validate_edges(self) -> "CreateWorkflowPlanPayload":
        """验证边的有效性"""
        node_ids = {node.node_id for node in self.nodes}

        for edge in self.edges:
            if edge.source not in node_ids:
                raise ValueError(f"边的源节点 {edge.source} 不存在")
            if edge.target not in node_ids:
                raise ValueError(f"边的目标节点 {edge.target} 不存在")

        return self


class ExecuteWorkflowPayload(BaseModel):
    """EXECUTE_WORKFLOW 决策的 payload

    场景：执行已有工作流

    示例：
        {
            "action_type": "execute_workflow",
            "workflow_id": "workflow_123",
            "input_params": {...},
            "execution_mode": "async",
            "notify_on_completion": True
        }
    """

    action_type: Literal[ActionType.EXECUTE_WORKFLOW] = Field(
        ActionType.EXECUTE_WORKFLOW, description="动作类型"
    )
    workflow_id: str = Field(..., min_length=1, description="工作流ID")
    input_params: dict[str, Any] | None = Field(None, description="运行时参数")
    execution_mode: ExecutionMode = Field(ExecutionMode.ASYNC, description="执行模式")
    notify_on_completion: bool = Field(True, description="是否在完成时通知")


class RequestClarificationPayload(BaseModel):
    """REQUEST_CLARIFICATION 决策的 payload

    场景：请求用户澄清需求

    示例：
        {
            "action_type": "request_clarification",
            "question": "您想分析哪个数据源？",
            "options": ["销售数据库", "用户行为日志"],
            "required_fields": ["data_source"],
            "context": {...}
        }
    """

    action_type: Literal[ActionType.REQUEST_CLARIFICATION] = Field(
        ActionType.REQUEST_CLARIFICATION, description="动作类型"
    )
    question: str = Field(..., min_length=1, description="澄清问题")
    options: list[str] | None = Field(None, description="选项列表")
    required_fields: list[str] | None = Field(None, description="必填字段列表")
    context: dict[str, Any] | None = Field(None, description="上下文信息")

    @field_validator("options")
    @classmethod
    def options_not_empty_if_provided(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and len(v) == 0:
            raise ValueError("如果提供 options，列表不能为空")
        return v


class ContinuePayload(BaseModel):
    """CONTINUE 决策的 payload

    场景：内部决策，继续推理

    示例：
        {
            "action_type": "continue",
            "thought": "需要先确定数据范围",
            "next_step": "询问用户时间范围",
            "progress": 0.3
        }
    """

    action_type: Literal[ActionType.CONTINUE] = Field(ActionType.CONTINUE, description="动作类型")
    thought: str = Field(..., min_length=1, description="当前思考内容")
    next_step: str | None = Field(None, description="下一步计划")
    progress: float | None = Field(None, ge=0.0, le=1.0, description="进度")


class ModifyNodePayload(BaseModel):
    """MODIFY_NODE 决策的 payload

    场景：修改节点配置

    示例：
        {
            "action_type": "modify_node",
            "node_id": "node_2",
            "updates": {"config.temperature": 0.9},
            "reason": "用户要求提高创造性"
        }
    """

    action_type: Literal[ActionType.MODIFY_NODE] = Field(
        ActionType.MODIFY_NODE, description="动作类型"
    )
    node_id: str = Field(..., min_length=1, description="节点ID")
    updates: dict[str, Any] = Field(..., min_length=1, description="更新内容")
    reason: str | None = Field(None, description="修改原因")

    @field_validator("updates")
    @classmethod
    def updates_not_empty(cls, v: dict[str, Any]) -> dict[str, Any]:
        if len(v) == 0:
            raise ValueError("updates 不能为空")
        return v


class RecoveryPlan(BaseModel):
    """恢复计划"""

    action: RecoveryAction = Field(..., description="恢复动作")
    delay: float | None = Field(None, ge=0.1, le=60.0, description="重试延迟（秒）")
    max_attempts: int | None = Field(None, ge=1, le=10, description="最大重试次数")
    modifications: dict[str, Any] | None = Field(None, description="节点修改")
    alternative_node: str | None = Field(None, description="替代节点")

    @model_validator(mode="after")
    def validate_retry_params(self) -> "RecoveryPlan":
        """验证重试参数"""
        if self.action == RecoveryAction.RETRY:
            if self.max_attempts is None:
                raise ValueError("RETRY 动作必须提供 max_attempts")
        if self.action == RecoveryAction.MODIFY:
            if self.modifications is None:
                raise ValueError("MODIFY 动作必须提供 modifications")
        return self


class ErrorRecoveryPayload(BaseModel):
    """ERROR_RECOVERY 决策的 payload

    场景：工作流执行失败，进行错误恢复

    示例：
        {
            "action_type": "error_recovery",
            "workflow_id": "workflow_123",
            "failed_node_id": "node_1",
            "failure_reason": "HTTP timeout",
            "error_code": "TIMEOUT",
            "recovery_plan": {...},
            "execution_context": {...}
        }
    """

    action_type: Literal[ActionType.ERROR_RECOVERY] = Field(
        ActionType.ERROR_RECOVERY, description="动作类型"
    )
    workflow_id: str = Field(..., min_length=1, description="工作流ID")
    failed_node_id: str = Field(..., min_length=1, description="失败节点ID")
    failure_reason: str = Field(..., min_length=1, description="失败原因")
    error_code: str | None = Field(None, description="错误代码")
    recovery_plan: RecoveryPlan = Field(..., description="恢复计划")
    execution_context: dict[str, Any] = Field(..., description="执行上下文")


class SuggestedChanges(BaseModel):
    """建议的修改"""

    remove_nodes: list[str] | None = Field(None, description="要移除的节点ID")
    add_nodes: list[WorkflowNode] | None = Field(None, description="要添加的节点")
    update_edges: list[WorkflowEdge] | None = Field(None, description="要更新的边")


class ReplanWorkflowPayload(BaseModel):
    """REPLAN_WORKFLOW 决策的 payload

    场景：工作流需要重新规划

    示例：
        {
            "action_type": "replan_workflow",
            "workflow_id": "workflow_123",
            "reason": "API持续超时",
            "execution_context": {...},
            "suggested_changes": {...},
            "preserve_nodes": ["node_2", "node_3"]
        }
    """

    action_type: Literal[ActionType.REPLAN_WORKFLOW] = Field(
        ActionType.REPLAN_WORKFLOW, description="动作类型"
    )
    workflow_id: str = Field(..., min_length=1, description="原工作流ID")
    reason: str = Field(..., min_length=1, description="重新规划原因")
    execution_context: dict[str, Any] = Field(..., description="执行上下文")
    suggested_changes: SuggestedChanges | None = Field(None, description="建议的修改")
    preserve_nodes: list[str] | None = Field(None, description="保留的节点")


class SpawnSubagentPayload(BaseModel):
    """SPAWN_SUBAGENT 决策的 payload

    场景：生成子 Agent

    示例：
        {
            "action_type": "spawn_subagent",
            "subagent_type": "researcher",
            "task_payload": {...},
            "priority": 8,
            "timeout": 120.0,
            "context_snapshot": {...}
        }
    """

    action_type: Literal[ActionType.SPAWN_SUBAGENT] = Field(
        ActionType.SPAWN_SUBAGENT, description="动作类型"
    )
    subagent_type: str = Field(..., min_length=1, description="子Agent类型")
    task_payload: dict[str, Any] = Field(..., description="子任务载荷")
    priority: int = Field(5, ge=0, le=10, description="优先级")
    timeout: float | None = Field(None, gt=0, description="超时时间（秒）")
    context_snapshot: dict[str, Any] | None = Field(None, description="上下文快照")


# ========================================
# 工厂函数
# ========================================


def create_payload_from_dict(
    action_type: str, payload_dict: dict[str, Any]
) -> (
    RespondPayload
    | CreateNodePayload
    | CreateWorkflowPlanPayload
    | ExecuteWorkflowPayload
    | RequestClarificationPayload
    | ContinuePayload
    | ModifyNodePayload
    | ErrorRecoveryPayload
    | ReplanWorkflowPayload
    | SpawnSubagentPayload
):
    """根据 action_type 创建对应的 Payload 对象

    Args:
        action_type: 动作类型字符串
        payload_dict: payload 字典

    Returns:
        对应的 Payload 对象

    Raises:
        ValueError: 如果 action_type 不合法或验证失败
    """
    payload_map = {
        ActionType.RESPOND: RespondPayload,
        ActionType.CREATE_NODE: CreateNodePayload,
        ActionType.CREATE_WORKFLOW_PLAN: CreateWorkflowPlanPayload,
        ActionType.EXECUTE_WORKFLOW: ExecuteWorkflowPayload,
        ActionType.REQUEST_CLARIFICATION: RequestClarificationPayload,
        ActionType.CONTINUE: ContinuePayload,
        ActionType.MODIFY_NODE: ModifyNodePayload,
        ActionType.ERROR_RECOVERY: ErrorRecoveryPayload,
        ActionType.REPLAN_WORKFLOW: ReplanWorkflowPayload,
        ActionType.SPAWN_SUBAGENT: SpawnSubagentPayload,
    }

    try:
        action_enum = ActionType(action_type)
    except ValueError as err:
        raise ValueError(f"未知的 action_type: {action_type}") from err

    payload_class = payload_map[action_enum]
    return payload_class(**payload_dict)
