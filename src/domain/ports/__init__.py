"""领域层 Ports - 定义领域层需要的外部依赖接口

为什么需要 Ports？
1. 依赖倒置（DIP）：让基础设施层依赖领域层，而不是反过来
2. 解耦：领域逻辑不依赖具体的数据库、ORM 或存储技术
3. 可测试性：Use Case 可以使用 Mock Repository 进行测试
4. 灵活性：可以轻松切换不同的存储实现（内存、SQL、NoSQL 等）

设计原则：
- 使用 Protocol（Python 3.8+）定义接口（结构化子类型）
- 只定义领域层需要的方法（不要过度设计）
- 方法签名使用领域对象（Entity、Value Object）
- 不依赖任何框架（纯 Python）
"""

from src.domain.ports.agent_repository import AgentRepository
from src.domain.ports.capability_definition_source import CapabilityDefinitionSource
from src.domain.ports.execution_event_sink import ExecutionEventSink
from src.domain.ports.idempotency_store import IdempotencyStore
from src.domain.ports.run_repository import RunRepository
from src.domain.ports.workflow_chat_llm import WorkflowChatLLM
from src.domain.ports.workflow_repository import WorkflowRepository
from src.domain.ports.workflow_run_execution_entry import WorkflowRunExecutionEntryPort

__all__ = [
    "AgentRepository",
    "CapabilityDefinitionSource",
    "ExecutionEventSink",
    "IdempotencyStore",
    "RunRepository",
    "WorkflowRunExecutionEntryPort",
    "WorkflowRepository",
    "WorkflowChatLLM",
]
