"""RunRepository Port - 定义 Run 实体的持久化接口

为什么需要 RunRepository Port？
1. 依赖倒置（DIP）：领域层定义接口，基础设施层实现接口
2. 解耦：领域层不依赖具体的数据库技术（SQLAlchemy、MongoDB 等）
3. 可测试性：Use Case 可以使用 Mock Repository 进行单元测试
4. 灵活性：可以轻松切换不同的存储实现

设计原则：
- 使用 Protocol（结构化子类型，不需要显式继承）
- 只定义领域层需要的方法（不要过度设计）
- 方法签名使用领域对象（Run 实体）
- 不依赖任何框架（纯 Python）

为什么使用 Protocol 而不是 ABC？
1. 更灵活：不需要显式继承，只要实现了方法就符合接口
2. 更 Pythonic：符合 Duck Typing 理念
3. 更简洁：不需要 @abstractmethod 装饰器
4. 类型检查友好：mypy 可以检查是否实现了所有方法
"""

from typing import Protocol

from src.domain.entities.run import Run


class RunRepository(Protocol):
    """Run 仓储接口

    职责：
    - 定义 Run 实体的持久化操作
    - 不关心具体实现（内存、SQL、NoSQL 等）

    方法命名规范：
    - save(): 保存实体（新增或更新）
    - get_by_id(): 根据 ID 获取实体（不存在抛异常）
    - find_by_id(): 根据 ID 查找实体（不存在返回 None）
    - find_by_agent_id(): 根据 Agent ID 查找所有 Run
    - exists(): 检查实体是否存在
    - delete(): 删除实体

    为什么区分 get 和 find？
    - get: 期望一定存在，不存在抛异常（用于业务逻辑）
    - find: 可能不存在，返回 None（用于查询场景）

    为什么没有 create/update？
    - 统一使用 save()，由实现层判断是新增还是更新
    - 符合 Repository 模式的最佳实践
    """

    def save(self, run: Run) -> None:
        """保存 Run 实体（新增或更新）

        业务语义：
        - 如果 Run 不存在，则新增
        - 如果 Run 已存在，则更新
        - 由实现层判断是新增还是更新（通过 ID 查询）

        参数：
            run: Run 实体

        实现要求：
        - 必须是原子操作（事务内完成）
        - 保存失败应抛出异常

        为什么返回 None？
        - save() 是命令操作，不需要返回值
        - 如果需要获取保存后的实体，调用 get_by_id()
        """
        ...

    def get_by_id(self, run_id: str) -> Run:
        """根据 ID 获取 Run 实体（不存在抛异常）

        业务语义：
        - 期望 Run 一定存在
        - 不存在时抛出异常（NotFoundError）
        - 用于业务逻辑中需要确保实体存在的场景

        参数：
            run_id: Run ID

        返回：
            Run 实体

        抛出：
            NotFoundError: 当 Run 不存在时

        为什么不返回 None？
        - get 语义表示"期望存在"
        - 不存在是异常情况，应该抛异常
        - 避免调用方忘记检查 None
        """
        ...

    def find_by_id(self, run_id: str) -> Run | None:
        """根据 ID 查找 Run 实体（不存在返回 None）

        业务语义：
        - Run 可能不存在
        - 不存在时返回 None（不抛异常）
        - 用于查询场景（如检查 Run 是否存在）

        参数：
            run_id: Run ID

        返回：
            Run 实体或 None

        为什么需要 find？
        - 查询场景不应该抛异常
        - 调用方可以根据返回值判断是否存在
        """
        ...

    def find_by_agent_id(self, agent_id: str) -> list[Run]:
        """根据 Agent ID 查找所有 Run

        业务语义：
        - 查询某个 Agent 的所有执行记录
        - 如果没有 Run，返回空列表（不抛异常）
        - 按创建时间倒序排列（最新的在前）

        参数：
            agent_id: Agent ID

        返回：
            Run 列表（可能为空）

        实现要求：
        - 按 created_at 倒序排列
        - 返回所有状态的 Run（不过滤）

        为什么返回 list 而不是 Iterator？
        - 简单场景下 list 更直观
        - 如果数据量大，实现层可以使用分页
        """
        ...

    def exists(self, run_id: str) -> bool:
        """检查 Run 是否存在

        业务语义：
        - 快速检查 Run 是否存在
        - 不需要加载完整实体（性能优化）

        参数：
            run_id: Run ID

        返回：
            True 表示存在，False 表示不存在

        实现建议：
        - 使用 COUNT 或 EXISTS 查询（不加载实体）
        - 比 find_by_id() 更高效
        """
        ...

    def delete(self, run_id: str) -> None:
        """删除 Run 实体

        业务语义：
        - 物理删除 Run（不是软删除）
        - 如果 Run 不存在，不抛异常（幂等操作）

        参数：
            run_id: Run ID

        实现要求：
        - 必须是原子操作（事务内完成）
        - 幂等：多次删除同一个 Run 不报错

        为什么幂等？
        - 删除操作应该是幂等的（多次删除结果一致）
        - 避免调用方需要先检查是否存在

        注意：
        - 如果需要软删除，应该在 Run 实体中添加 deleted_at 字段
        - 然后通过 save() 更新状态，而不是调用 delete()
        """
        ...
