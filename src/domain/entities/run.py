"""Run 实体 - Agent 的执行实例

业务定义：
- Run 是 Agent 的一次执行实例
- 一个 Agent 可以被执行多次，每次执行就是一个 Run
- Run 有明确的生命周期：PENDING → RUNNING → SUCCEEDED/FAILED
- Run 负责维护执行状态和时间戳

设计原则：
- 纯 Python 实现，不依赖任何框架（DDD 要求）
- 使用 dataclass 简化样板代码
- 通过工厂方法 create() 封装创建逻辑
- 通过状态转换方法维护状态机不变式
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import uuid4

from src.domain.exceptions import DomainError


class RunStatus(str, Enum):
    """Run 状态枚举

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
    """

    PENDING = "pending"  # 等待执行
    RUNNING = "running"  # 正在执行
    SUCCEEDED = "succeeded"  # 执行成功
    FAILED = "failed"  # 执行失败


@dataclass
class Run:
    """Run 实体

    属性说明：
    - id: 唯一标识符（UUID）
    - agent_id: 关联的 Agent ID（业务必需）
    - status: Run 状态（PENDING/RUNNING/SUCCEEDED/FAILED）
    - created_at: 创建时间（审计需要）
    - started_at: 开始执行时间（可选，启动时设置）
    - finished_at: 完成时间（可选，完成或失败时设置）
    - error: 错误信息（可选，失败时设置）

    为什么使用 dataclass？
    1. 自动生成 __init__、__repr__、__eq__ 等方法
    2. 类型注解清晰，IDE 友好
    3. 符合 Python 3.11+ 最佳实践
    4. 纯 Python，不依赖框架（符合 DDD 要求）

    为什么 Run 和 Agent 要一起设计？
    1. Run 的生命周期依赖 Agent（Run 必须属于某个 Agent）
    2. 它们是紧密关联的聚合（Agent 1:N Run）
    3. 需要一起考虑业务边界（如 Agent 删除后 Run 怎么办）
    """

    id: str
    agent_id: str
    status: RunStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None

    @classmethod
    def create(cls, agent_id: str) -> "Run":
        """创建 Run 的工厂方法

        为什么使用工厂方法而不是直接 __init__？
        1. 封装创建逻辑：自动生成 id、status、created_at
        2. 验证业务规则：确保 agent_id 不为空
        3. 符合 DDD 聚合根创建模式
        4. 提供默认值：started_at、finished_at、error 初始为 None

        参数：
            agent_id: 关联的 Agent ID（必需）

        返回：
            Run 实例

        抛出：
            DomainError: 当 agent_id 为空时

        实现说明：
        - 验证：先验证业务规则，再创建实例（Fail Fast 原则）
        - id: 使用 UUID 保证全局唯一性
        - status: 默认为 PENDING（新创建的 Run 等待执行）
        - created_at: 记录创建时间（用于审计和排序）
        - started_at/finished_at/error: 初始为 None（执行时才设置）
        """
        # 验证业务规则（不变式）
        # 为什么先验证？Fail Fast 原则：尽早发现错误，避免创建无效对象

        # 验证 agent_id 不能为空
        # 为什么用 strip()？防止用户输入纯空格绕过验证
        if not agent_id or not agent_id.strip():
            raise DomainError("agent_id 不能为空")

        # 验证通过，创建实例
        return cls(
            id=str(uuid4()),  # UUID 转字符串，方便序列化
            agent_id=agent_id.strip(),  # 去除首尾空格，规范化数据
            status=RunStatus.PENDING,  # 新创建的 Run 默认等待执行
            created_at=datetime.now(),
            started_at=None,  # 启动时才设置
            finished_at=None,  # 完成时才设置
            error=None,  # 失败时才设置
        )

    def start(self) -> None:
        """启动 Run（状态转换：PENDING → RUNNING）

        业务规则：
        - 只能从 PENDING 状态启动
        - 启动后记录 started_at 时间

        为什么需要这个方法？
        1. 封装状态转换逻辑：不允许外部直接修改 status
        2. 维护不变式：确保状态转换合法
        3. 自动设置时间戳：started_at 由系统自动设置

        抛出：
            DomainError: 当状态不是 PENDING 时

        实现说明：
        - 先验证状态，再转换（Fail Fast 原则）
        - 使用 datetime.now() 记录当前时间
        """
        # 验证状态转换是否合法
        if self.status != RunStatus.PENDING:
            raise DomainError(f"只能从 PENDING 状态启动 Run，当前状态：{self.status.value}")

        # 状态转换
        self.status = RunStatus.RUNNING
        self.started_at = datetime.now()

    def succeed(self) -> None:
        """完成 Run（状态转换：RUNNING → SUCCEEDED）

        业务规则：
        - 只能从 RUNNING 状态完成
        - 完成后记录 finished_at 时间

        为什么需要这个方法？
        1. 封装状态转换逻辑：不允许外部直接修改 status
        2. 维护不变式：确保状态转换合法
        3. 自动设置时间戳：finished_at 由系统自动设置

        抛出：
            DomainError: 当状态不是 RUNNING 时

        实现说明：
        - 先验证状态，再转换（Fail Fast 原则）
        - 使用 datetime.now() 记录当前时间
        """
        # 验证状态转换是否合法
        if self.status != RunStatus.RUNNING:
            raise DomainError(f"只能从 RUNNING 状态完成 Run，当前状态：{self.status.value}")

        # 状态转换
        self.status = RunStatus.SUCCEEDED
        self.finished_at = datetime.now()

    def fail(self, error: str) -> None:
        """失败 Run（状态转换：RUNNING → FAILED）

        业务规则：
        - 只能从 RUNNING 状态失败
        - 失败后记录 finished_at 时间和错误信息

        为什么需要这个方法？
        1. 封装状态转换逻辑：不允许外部直接修改 status
        2. 维护不变式：确保状态转换合法
        3. 自动设置时间戳和错误信息：由系统自动设置

        参数：
            error: 错误信息（必需）

        抛出：
            DomainError: 当状态不是 RUNNING 时

        实现说明：
        - 先验证状态，再转换（Fail Fast 原则）
        - 使用 datetime.now() 记录当前时间
        - 保存错误信息供后续分析
        """
        # 验证状态转换是否合法
        if self.status != RunStatus.RUNNING:
            raise DomainError(f"只能从 RUNNING 状态失败 Run，当前状态：{self.status.value}")

        # 状态转换
        self.status = RunStatus.FAILED
        self.finished_at = datetime.now()
        self.error = error
