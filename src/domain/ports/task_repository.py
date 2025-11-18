"""TaskRepository Port - 定义 Task 实体的持久化接口

为什么需要 TaskRepository Port？
1. 依赖倒置（DIP）：领域层定义接口，基础设施层实现接口
2. 解耦：领域层不依赖具体的数据库技术（SQLAlchemy、MongoDB 等）
3. 可测试性：Use Case 可以使用 Mock Repository 进行单元测试
4. 灵活性：可以轻松切换不同的存储实现

设计原则：
- 使用 Protocol（结构化子类型，不需要显式继承）
- 只定义领域层需要的方法（不要过度设计）
- 方法签名使用领域对象（Task 实体）
- 不依赖任何框架（纯 Python）

Task 与 TaskEvent 的持久化：
- Task 是聚合根，有独立的 Repository
- TaskEvent 是值对象，属于 Task 聚合，没有独立的 Repository
- 持久化 Task 时，同时持久化 TaskEvent（作为 Task 的一部分）
- 这是聚合的完整性保证

为什么使用 Protocol 而不是 ABC？
1. 更灵活：不需要显式继承，只要实现了方法就符合接口
2. 更 Pythonic：符合 Duck Typing 理念
3. 更简洁：不需要 @abstractmethod 装饰器
4. 类型检查友好：mypy 可以检查是否实现了所有方法
"""

from typing import Protocol

from src.domain.entities.task import Task


class TaskRepository(Protocol):
    """Task 仓储接口

    职责：
    - 定义 Task 实体的持久化操作
    - 不关心具体实现（内存、SQL、NoSQL 等）
    - 管理 Task 聚合的完整性（包括 TaskEvent）

    方法命名规范：
    - save(): 保存实体（新增或更新）
    - get_by_id(): 根据 ID 获取实体（不存在抛异常）
    - find_by_id(): 根据 ID 查找实体（不存在返回 None）
    - find_by_run_id(): 根据 Run ID 查找所有 Task
    - exists(): 检查实体是否存在
    - delete(): 删除实体

    为什么区分 get 和 find？
    - get: 期望一定存在，不存在抛异常（用于业务逻辑）
    - find: 可能不存在，返回 None（用于查询场景）

    为什么没有 create/update？
    - 统一使用 save()，由实现层判断是新增还是更新
    - 符合 Repository 模式的最佳实践
    """

    def save(self, task: Task) -> None:
        """保存 Task 实体（新增或更新）

        业务语义：
        - 如果 Task 不存在，则新增
        - 如果 Task 已存在，则更新
        - 由实现层判断是新增还是更新（通过 ID 查询）
        - 同时保存 Task 聚合内的 TaskEvent（聚合完整性）

        参数：
            task: Task 实体（包含 TaskEvent）

        实现要求：
        - 必须是原子操作（事务内完成）
        - 保存失败应抛出异常
        - 必须同时保存 TaskEvent（聚合完整性）

        为什么返回 None？
        - save() 是命令操作，不需要返回值
        - 如果需要获取保存后的实体，调用 get_by_id()

        聚合完整性：
        - Task 是聚合根，TaskEvent 是聚合内的值对象
        - 保存 Task 时，必须同时保存所有 TaskEvent
        - 不能单独保存 TaskEvent（违反聚合边界）
        """
        ...

    def get_by_id(self, task_id: str) -> Task:
        """根据 ID 获取 Task 实体（不存在抛异常）

        业务语义：
        - 期望 Task 一定存在
        - 不存在时抛出异常（NotFoundError）
        - 用于业务逻辑中需要确保实体存在的场景
        - 返回完整的 Task 聚合（包括 TaskEvent）

        参数：
            task_id: Task ID

        返回：
            Task 实体（包含 TaskEvent）

        抛出：
            NotFoundError: 当 Task 不存在时

        为什么不返回 None？
        - get 语义表示"期望存在"
        - 不存在是异常情况，应该抛异常
        - 避免调用方忘记检查 None

        聚合完整性：
        - 必须返回完整的 Task 聚合（包括所有 TaskEvent）
        - TaskEvent 按时间顺序排列
        """
        ...

    def find_by_id(self, task_id: str) -> Task | None:
        """根据 ID 查找 Task 实体（不存在返回 None）

        业务语义：
        - Task 可能不存在
        - 不存在时返回 None（不抛异常）
        - 用于查询场景（如检查 Task 是否存在）
        - 返回完整的 Task 聚合（包括 TaskEvent）

        参数：
            task_id: Task ID

        返回：
            Task 实体（包含 TaskEvent）或 None

        为什么需要 find？
        - 查询场景不应该抛异常
        - 调用方可以根据返回值判断是否存在

        聚合完整性：
        - 如果 Task 存在，必须返回完整的聚合（包括所有 TaskEvent）
        """
        ...

    def find_by_run_id(self, run_id: str) -> list[Task]:
        """根据 Run ID 查找所有 Task

        业务语义：
        - 查询某个 Run 的所有执行步骤
        - 如果没有 Task，返回空列表（不抛异常）
        - 按创建时间倒序排列（最新的在前）
        - 返回完整的 Task 聚合（包括 TaskEvent）

        参数：
            run_id: Run ID

        返回：
            Task 列表（可能为空，每个 Task 包含 TaskEvent）

        实现要求：
        - 按 created_at 倒序排列
        - 返回所有状态的 Task（不过滤）
        - 每个 Task 包含完整的 TaskEvent

        为什么返回 list 而不是 Iterator？
        - 简单场景下 list 更直观
        - 如果数据量大，实现层可以使用分页

        聚合完整性：
        - 每个 Task 必须包含完整的 TaskEvent
        - TaskEvent 按时间顺序排列
        """
        ...

    def find_by_agent_id(self, agent_id: str) -> list[Task]:
        """根据 Agent ID 查找所有 Task

        业务语义：
        - 查询某个 Agent 的所有计划任务（工作流）
        - 如果没有 Task，返回空列表（不抛异常）
        - 按创建时间倒序排列（最新的在前）
        - 返回完整的 Task 聚合（包括 TaskEvent）

        参数：
            agent_id: Agent ID

        返回：
            Task 列表（可能为空，每个 Task 包含 TaskEvent）

        实现要求：
        - 按 created_at 倒序排列
        - 返回所有状态的 Task（不过滤）
        - 每个 Task 包含完整的 TaskEvent

        业务场景：
        - 用户创建 Agent 后，查看生成的工作流（Tasks）
        - 前端需要展示任务列表

        聚合完整性：
        - 每个 Task 必须包含完整的 TaskEvent
        - TaskEvent 按时间顺序排列
        """
        ...

    def exists(self, task_id: str) -> bool:
        """检查 Task 是否存在

        业务语义：
        - 快速检查 Task 是否存在
        - 不需要加载完整实体（性能优化）

        参数：
            task_id: Task ID

        返回：
            True 表示存在，False 表示不存在

        实现建议：
        - 使用 COUNT 或 EXISTS 查询（不加载实体）
        - 比 find_by_id() 更高效
        """
        ...

    def delete(self, task_id: str) -> None:
        """删除 Task 实体

        业务语义：
        - 物理删除 Task（不是软删除）
        - 如果 Task 不存在，不抛异常（幂等操作）
        - 同时删除 Task 聚合内的 TaskEvent（级联删除）

        参数：
            task_id: Task ID

        实现要求：
        - 必须是原子操作（事务内完成）
        - 幂等：多次删除同一个 Task 不报错
        - 级联删除：同时删除所有 TaskEvent

        为什么幂等？
        - 删除操作应该是幂等的（多次删除结果一致）
        - 避免调用方需要先检查是否存在

        聚合完整性：
        - 删除 Task 时，必须同时删除所有 TaskEvent
        - 不能留下孤儿 TaskEvent（违反聚合完整性）

        注意：
        - 如果需要软删除，应该在 Task 实体中添加 deleted_at 字段
        - 然后通过 save() 更新状态，而不是调用 delete()
        """
        ...
