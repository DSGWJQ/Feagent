"""Task 实体 - Run 的执行步骤

业务定义：
- Task 是 Run 中的单个执行步骤
- 一个 Run 包含多个 Task（如：分析数据、生成报告、发送邮件）
- Task 有明确的生命周期：PENDING → RUNNING → SUCCEEDED/FAILED
- Task 支持重试、超时、幂等
- Task 记录执行事件（TaskEvent）用于审计和调试

第一性原理：
1. Task 是什么？
   - Task 是 Run 的组成部分，代表一个原子操作
   - Task 是可重试的（失败后可以重新执行）
   - Task 是可观测的（记录所有执行事件）

2. Task 的核心职责：
   - 维护状态（PENDING/RUNNING/SUCCEEDED/FAILED）
   - 记录执行历史（TaskEvent 列表）
   - 支持重试逻辑（retry_count）
   - 记录时间戳（created_at/started_at/finished_at）

3. Task 与 Run 的关系：
   - Task 属于 Run（外键关系）
   - Run 的状态依赖 Task 的状态（所有 Task 成功 → Run 成功）
   - Task 失败不一定导致 Run 失败（可以重试）

设计原则：
- 纯 Python 实现，不依赖任何框架（DDD 要求）
- 使用 dataclass 简化样板代码
- 通过工厂方法 create() 封装创建逻辑
- 通过状态转换方法维护状态机不变式
- TaskEvent 作为值对象，由 Task 管理生命周期
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from src.domain.exceptions import DomainError
from src.domain.value_objects.task_event import TaskEvent


class TaskStatus(str, Enum):
    """Task 状态枚举

    为什么使用 Enum？
    1. 类型安全：防止使用无效的状态字符串
    2. IDE 友好：自动补全和类型检查
    3. 可维护：状态集中定义，易于修改

    为什么继承 str？
    1. 序列化友好：可以直接转换为 JSON
    2. 数据库友好：可以直接存储为字符串
    3. 兼容性好：可以和字符串比较

    状态机：
    PENDING → RUNNING → SUCCEEDED/FAILED
    FAILED → PENDING（重试）
    """

    PENDING = "pending"  # 等待执行
    RUNNING = "running"  # 正在执行
    SUCCEEDED = "succeeded"  # 执行成功
    FAILED = "failed"  # 执行失败


@dataclass
class Task:
    """Task 实体

    属性说明：
    - id: 唯一标识符（UUID）
    - agent_id: 关联的 Agent ID（业务必需，表示这是哪个 Agent 的任务）
    - run_id: 关联的 Run ID（可选，执行时设置）
    - name: 任务名称（业务必需，简短描述）
    - description: 任务描述（可选，详细说明）
    - status: Task 状态（PENDING/RUNNING/SUCCEEDED/FAILED）
    - input_data: 输入数据（可选，JSON 格式）
    - output_data: 输出数据（可选，JSON 格式）
    - error: 错误信息（可选，失败时设置）
    - retry_count: 重试次数（默认 0）
    - created_at: 创建时间（审计需要）
    - started_at: 开始执行时间（可选，启动时设置）
    - finished_at: 完成时间（可选，完成或失败时设置）
    - events: 执行事件列表（TaskEvent 值对象）

    为什么使用 dataclass？
    1. 自动生成 __init__、__repr__、__eq__ 等方法
    2. 类型注解清晰，IDE 友好
    3. 符合 Python 3.11+ 最佳实践
    4. 纯 Python，不依赖框架（符合 DDD 要求）

    为什么 Task 需要记录事件？
    1. 审计需求：记录完整的执行历史
    2. 调试需求：出错时可以回溯执行过程
    3. 监控需求：实时观察 Task 执行进度
    4. 业务需求：某些业务需要详细的执行日志

    为什么添加 agent_id？
    - Task 可以在创建 Agent 时生成（作为计划）
    - Task 也可以在执行 Run 时创建（作为执行步骤）
    - agent_id 表示这个 Task 属于哪个 Agent

    为什么 run_id 改为可选？
    - 创建 Agent 时生成的 Task，run_id 为 None（还没执行）
    - 执行 Run 时，设置 run_id（表示在哪次执行中运行）

    为什么添加 description？
    - name 是简短的任务名称（如"读取 CSV 文件"）
    - description 是详细的任务描述（如"使用 pandas 读取 CSV 文件到 DataFrame"）
    - 提供更好的用户体验和可读性
    """

    id: str
    agent_id: str
    run_id: str | None
    name: str
    description: str | None
    status: TaskStatus
    input_data: dict | None
    output_data: dict | None
    error: str | None
    retry_count: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    events: list[TaskEvent] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        agent_id: str,
        name: str,
        description: str | None = None,
        run_id: str | None = None,
        input_data: dict | None = None,
    ) -> "Task":
        """创建 Task（工厂方法）

        为什么使用工厂方法而不是直接 __init__？
        1. 封装创建逻辑：自动生成 ID、设置默认值
        2. 业务语义清晰：create() 比 __init__() 更符合业务语言
        3. 验证逻辑集中：在一个地方验证所有业务规则
        4. 易于测试：可以 mock 工厂方法

        参数：
            agent_id: Agent ID（必填）
            name: 任务名称（必填）
            description: 任务描述（可选）
            run_id: Run ID（可选，执行时设置）
            input_data: 输入数据（可选）

        返回：
            Task 实例

        异常：
            DomainError: agent_id 或 name 为空

        示例：
        >>> # 创建计划任务（还没执行）
        >>> task = Task.create(
        ...     agent_id="agent-123",
        ...     name="分析销售数据",
        ...     description="使用 pandas 读取 CSV 文件并计算销售总额"
        ... )
        >>> task.run_id is None
        True
        >>> task.status
        <TaskStatus.PENDING: 'pending'>

        >>> # 创建执行任务（关联到 Run）
        >>> task = Task.create(
        ...     agent_id="agent-123",
        ...     name="分析销售数据",
        ...     description="使用 pandas 读取 CSV 文件并计算销售总额",
        ...     run_id="run-456",
        ...     input_data={"file_path": "/data/sales.csv"}
        ... )
        >>> task.run_id
        'run-456'
        """
        # 验证：agent_id 不能为空
        if not agent_id or not agent_id.strip():
            raise DomainError("agent_id 不能为空")

        # 验证：name 不能为空
        if not name or not name.strip():
            raise DomainError("name 不能为空")

        # 去除首尾空格
        agent_id = agent_id.strip()
        name = name.strip()

        # 处理 run_id（可选）
        if run_id is not None:
            run_id = run_id.strip() if run_id.strip() else None

        # 处理 description（可选）
        if description is not None:
            description = description.strip() if description.strip() else None

        return cls(
            id=str(uuid4()),
            agent_id=agent_id,
            run_id=run_id,
            name=name,
            description=description,
            status=TaskStatus.PENDING,
            input_data=input_data,
            output_data=None,
            error=None,
            retry_count=0,
            created_at=datetime.now(UTC),
            started_at=None,
            finished_at=None,
            events=[],
        )

    def start(self) -> None:
        """开始执行 Task（PENDING → RUNNING）

        业务规则：
        - 只有 PENDING 状态的 Task 才能启动
        - 启动时记录 started_at

        异常：
            DomainError: 当前状态不是 PENDING

        示例：
        >>> task = Task.create(run_id="run-123", name="测试任务")
        >>> task.start()
        >>> task.status
        <TaskStatus.RUNNING: 'running'>
        """
        if self.status != TaskStatus.PENDING:
            raise DomainError(f"Task 已经在运行中，当前状态：{self.status.value}")

        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now(UTC)

    def succeed(self, output_data: dict | None = None) -> None:
        """Task 执行成功（RUNNING → SUCCEEDED）

        业务规则：
        - 只有 RUNNING 状态的 Task 才能完成
        - 完成时记录 finished_at
        - 可以保存输出数据

        参数：
            output_data: 输出数据（可选）

        异常：
            DomainError: 当前状态不是 RUNNING

        示例：
        >>> task = Task.create(run_id="run-123", name="测试任务")
        >>> task.start()
        >>> task.succeed(output_data={"result": "success"})
        >>> task.status
        <TaskStatus.SUCCEEDED: 'succeeded'>
        """
        if self.status != TaskStatus.RUNNING:
            raise DomainError(f"Task 必须先启动才能完成，当前状态：{self.status.value}")

        self.status = TaskStatus.SUCCEEDED
        self.finished_at = datetime.now(UTC)
        self.output_data = output_data

    def fail(self, error: str) -> None:
        """Task 执行失败（RUNNING → FAILED）

        业务规则：
        - 只有 RUNNING 状态的 Task 才能失败
        - 失败时记录 finished_at 和 error

        参数：
            error: 错误信息（必填）

        异常：
            DomainError: 当前状态不是 RUNNING

        示例：
        >>> task = Task.create(run_id="run-123", name="测试任务")
        >>> task.start()
        >>> task.fail(error="文件不存在")
        >>> task.status
        <TaskStatus.FAILED: 'failed'>
        """
        if self.status == TaskStatus.SUCCEEDED:
            raise DomainError("Task 已经完成，不能再失败")

        if self.status != TaskStatus.RUNNING:
            raise DomainError(f"Task 必须先启动才能失败，当前状态：{self.status.value}")

        self.status = TaskStatus.FAILED
        self.finished_at = datetime.now(UTC)
        self.error = error

    def retry(self) -> None:
        """重试 Task（FAILED → PENDING）

        业务规则：
        - 只有 FAILED 状态的 Task 才能重试
        - 重试时重置状态为 PENDING
        - 清除错误信息和 finished_at
        - 增加重试次数
        - 保留 started_at（记录第一次启动时间）

        异常：
            DomainError: 当前状态不是 FAILED

        示例：
        >>> task = Task.create(run_id="run-123", name="测试任务")
        >>> task.start()
        >>> task.fail(error="第一次失败")
        >>> task.retry()
        >>> task.status
        <TaskStatus.PENDING: 'pending'>
        >>> task.retry_count
        1
        """
        if self.status != TaskStatus.FAILED:
            raise DomainError(f"只有失败的 Task 才能重试，当前状态：{self.status.value}")

        self.status = TaskStatus.PENDING
        self.error = None
        self.finished_at = None
        self.retry_count += 1

    def increment_retry_count(self) -> None:
        """增加重试次数

        业务需求：
        - 记录重试次数用于限流和监控
        - 可以在重试前调用（用于统计）

        示例：
        >>> task = Task.create(run_id="run-123", name="测试任务")
        >>> task.increment_retry_count()
        >>> task.retry_count
        1
        """
        self.retry_count += 1

    def add_event(self, message: str) -> None:
        """添加执行事件

        业务需求：
        - 记录 Task 执行过程中的关键事件
        - 用于审计、调试、监控

        参数：
            message: 事件消息

        异常：
            ValueError: message 为空

        示例：
        >>> task = Task.create(run_id="run-123", name="测试任务")
        >>> task.add_event("开始下载文件")
        >>> task.add_event("文件下载完成")
        >>> len(task.events)
        2
        """
        event = TaskEvent.create(message)
        self.events.append(event)
