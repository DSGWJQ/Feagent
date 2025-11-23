"""API DTO（Data Transfer Objects）

DTO 职责：
1. 数据验证：使用 Pydantic 验证请求数据
2. 数据序列化：将 Domain 实体转换为 JSON
3. 数据转换：DTO ⇄ Domain Entity

设计原则：
- 与 Domain 实体分离：DTO 是 API 层的概念，不是业务概念
- 使用 Pydantic v2：利用新特性（field_validator、model_dump）
- 明确的验证规则：不依赖隐式行为

为什么需要 DTO？
1. 关注点分离：API 层和 Domain 层的数据结构可能不同
2. 版本兼容：API 可以有多个版本，但 Domain 层保持稳定
3. 数据验证：Pydantic 提供强大的验证功能
4. 文档生成：FastAPI 自动生成 OpenAPI 文档

DTO vs Domain Entity：
- DTO：用于 API 层，关注数据传输和验证
- Domain Entity：用于业务逻辑，关注业务规则和不变式
"""

from src.interfaces.api.dto.agent_dto import (
    AgentResponse,
    CreateAgentRequest,
    TaskResponse,
)
from src.interfaces.api.dto.llm_provider_dto import (
    DisableLLMProviderRequest,
    EnableLLMProviderRequest,
    LLMProviderListResponse,
    LLMProviderResponse,
    RegisterLLMProviderRequest,
    UpdateLLMProviderRequest,
)
from src.interfaces.api.dto.run_dto import (
    ExecuteRunRequest,
    RunResponse,
)
from src.interfaces.api.dto.tool_dto import (
    CreateToolRequest,
    DeprecateToolRequest,
    PublishToolRequest,
    ToolListResponse,
    ToolParameterDTO,
    ToolResponse,
    UpdateToolRequest,
)
from src.interfaces.api.dto.workflow_features_dto import (
    ChatMessageRequest,
    ChatMessageResponse,
    EnhancedChatWorkflowResponse,
    ExecuteConcurrentWorkflowsRequest,
    ExecutionResultResponse,
    ScheduleWorkflowRequest,
    ScheduledWorkflowResponse,
)

__all__ = [
    "CreateAgentRequest",
    "AgentResponse",
    "TaskResponse",
    "ExecuteRunRequest",
    "RunResponse",
    # Tool DTOs
    "CreateToolRequest",
    "UpdateToolRequest",
    "PublishToolRequest",
    "DeprecateToolRequest",
    "ToolResponse",
    "ToolListResponse",
    "ToolParameterDTO",
    # LLMProvider DTOs
    "RegisterLLMProviderRequest",
    "UpdateLLMProviderRequest",
    "EnableLLMProviderRequest",
    "DisableLLMProviderRequest",
    "LLMProviderResponse",
    "LLMProviderListResponse",
    # Workflow Features DTOs
    "ScheduleWorkflowRequest",
    "ScheduledWorkflowResponse",
    "ExecuteConcurrentWorkflowsRequest",
    "ExecutionResultResponse",
    "ChatMessageRequest",
    "ChatMessageResponse",
    "EnhancedChatWorkflowResponse",
]
