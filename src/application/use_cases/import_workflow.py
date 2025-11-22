"""ImportWorkflowUseCase - 导入工作流用例

V2新功能：
支持从 Coze 平台导入工作流

业务场景：
用户上传 Coze 工作流 JSON，系统将其转换为 Feagent 工作流并保存

职责：
1. 接收输入参数（coze_json）
2. 调用 Workflow.from_coze_json() 创建领域实体
3. 调用 Repository.save() 持久化实体
4. 返回导入结果（workflow_id, name, source, source_id）

第一性原则：
- 用例是业务逻辑的编排者，不包含业务规则
- 业务规则在 Domain 层（Workflow.from_coze_json() 中）
- 用例只负责协调各个组件

设计模式：
- Command 模式：用例是一个命令，封装了一次业务操作
- Dependency Injection：通过构造函数注入 Repository

为什么不在用例中验证输入？
- 验证逻辑在 Domain 层（Workflow.from_coze_json()）
- 用例只负责编排，不重复验证
- 遵循 DRY 原则（Don't Repeat Yourself）
"""

from dataclasses import dataclass
from typing import Any, Dict

from src.domain.entities.workflow import Workflow
from src.domain.ports.workflow_repository import WorkflowRepository


@dataclass
class ImportWorkflowInput:
    """导入工作流的输入参数

    为什么使用 dataclass？
    1. 类型安全：明确定义输入参数类型
    2. 不可变性：使用 frozen=False 允许修改（如果需要）
    3. 自动生成 __init__、__repr__ 等方法
    4. IDE 友好：自动补全和类型检查

    为什么不使用 Pydantic？
    - Pydantic 是 API 层的 DTO（Data Transfer Object）
    - 这里是 Application 层的输入对象
    - 保持层次分离：API DTO → Application Input → Domain Entity

    属性说明：
    - coze_json: Coze 工作流 JSON 数据（必填）
    """

    coze_json: Dict[str, Any]


@dataclass
class ImportWorkflowOutput:
    """导入工作流的输出结果

    为什么需要 Output 对象？
    1. 类型安全：明确定义返回值结构
    2. 解耦：不直接返回 Domain Entity
    3. 灵活性：可以只返回必要的字段

    属性说明：
    - workflow_id: 生成的 Workflow ID
    - name: 工作流名称
    - source: 工作流来源（固定为 "coze"）
    - source_id: 原始 Coze workflow_id
    """

    workflow_id: str
    name: str
    source: str
    source_id: str | None


class ImportWorkflowUseCase:
    """导入工作流用例

    职责：
    1. 接收 ImportWorkflowInput 输入
    2. 调用 Workflow.from_coze_json() 创建领域实体
    3. 调用 Repository.save() 持久化实体
    4. 返回 ImportWorkflowOutput 输出

    依赖：
    - WorkflowRepository: Workflow 仓储接口（通过构造函数注入）

    为什么使用依赖注入？
    1. 解耦：用例不依赖具体的 Repository 实现
    2. 可测试性：测试时可以注入 Mock Repository
    3. 灵活性：可以轻松切换不同的 Repository 实现

    执行流程：
    1. 调用 Workflow.from_coze_json(coze_json) 创建实体
       - Domain 层负责所有业务规则验证
       - 节点类型映射
       - 边引用验证
       - source/source_id 设置
    2. 调用 Repository.save(workflow) 持久化
    3. 构造并返回 Output

    异常处理：
    - Domain 层的 DomainError 会向上传播
    - 调用者（API 层）负责捕获并转换为 HTTP 响应
    """

    def __init__(self, workflow_repository: WorkflowRepository):
        """初始化用例

        参数：
            workflow_repository: Workflow 仓储接口
        """
        self.workflow_repository = workflow_repository

    def execute(self, input_data: ImportWorkflowInput) -> ImportWorkflowOutput:
        """执行导入工作流用例

        参数：
            input_data: ImportWorkflowInput 输入参数

        返回：
            ImportWorkflowOutput 输出结果

        抛出：
            DomainError: 当验证失败时（从 Domain 层传播）
        """
        # 1. 调用 Domain 层创建 Workflow 实体
        #    - 所有业务规则验证在这里完成
        #    - 节点类型映射
        #    - 边引用验证
        workflow = Workflow.from_coze_json(input_data.coze_json)

        # 2. 持久化 Workflow
        self.workflow_repository.save(workflow)

        # 3. 构造并返回 Output
        return ImportWorkflowOutput(
            workflow_id=workflow.id,
            name=workflow.name,
            source=workflow.source,
            source_id=workflow.source_id,
        )
