"""WorkflowRepository Port - 定义 Workflow 实体的持久化接口

为什么需要 WorkflowRepository Port？
1. 依赖倒置（DIP）：领域层定义接口，基础设施层实现接口
2. 解耦：领域层不依赖具体的数据库技术（SQLAlchemy、MongoDB 等）
3. 可测试性：Use Case 可以使用 Mock Repository 进行单元测试
4. 灵活性：可以轻松切换不同的存储实现

设计原则：
- 使用 Protocol（结构化子类型，不需要显式继承）
- 只定义领域层需要的方法（不要过度设计）
- 方法签名使用领域对象（Workflow 实体）
- 不依赖任何框架（纯 Python）
"""

from typing import Protocol

from src.domain.entities.workflow import Workflow


class WorkflowRepository(Protocol):
    """Workflow 仓储接口

    职责：
    - 定义 Workflow 实体的持久化操作
    - 不关心具体实现（内存、SQL、NoSQL 等）

    方法命名规范：
    - save(): 保存实体（新增或更新）
    - get_by_id(): 根据 ID 获取实体（不存在抛异常）
    - find_by_id(): 根据 ID 查找实体（不存在返回 None）
    - find_all(): 查找所有 Workflow
    - exists(): 检查实体是否存在
    - delete(): 删除实体
    """

    def save(self, workflow: Workflow) -> None:
        """保存 Workflow 实体（新增或更新）

        业务语义：
        - 如果 Workflow 不存在，则新增
        - 如果 Workflow 已存在，则更新
        - 由实现层判断是新增还是更新（通过 ID 查询）
        - 保存时会级联保存 Node 和 Edge（聚合根特性）

        参数：
            workflow: Workflow 实体

        实现要求：
        - 必须是原子操作（事务内完成）
        - 保存失败应抛出异常
        - 级联保存 Node 和 Edge（聚合根）
        - 更新时需要处理 Node 和 Edge 的增删改
        """
        ...

    def get_by_id(self, workflow_id: str) -> Workflow:
        """根据 ID 获取 Workflow 实体（不存在抛异常）

        业务语义：
        - 期望 Workflow 一定存在
        - 不存在时抛出异常（NotFoundError）
        - 用于业务逻辑中需要确保实体存在的场景
        - 加载时会级联加载 Node 和 Edge（聚合根特性）

        参数：
            workflow_id: Workflow ID

        返回：
            Workflow 实体（包含所有 Node 和 Edge）

        抛出：
            NotFoundError: 当 Workflow 不存在时
        """
        ...

    def find_by_id(self, workflow_id: str) -> Workflow | None:
        """根据 ID 查找 Workflow 实体（不存在返回 None）

        业务语义：
        - Workflow 可能不存在
        - 不存在时返回 None（不抛异常）
        - 用于查询场景（如检查 Workflow 是否存在）
        - 加载时会级联加载 Node 和 Edge（聚合根特性）

        参数：
            workflow_id: Workflow ID

        返回：
            Workflow 实体（包含所有 Node 和 Edge）或 None
        """
        ...

    def find_all(self) -> list[Workflow]:
        """查找所有 Workflow

        业务语义：
        - 查询所有 Workflow（不过滤状态）
        - 如果没有 Workflow，返回空列表（不抛异常）
        - 按创建时间倒序排列（最新的在前）
        - 加载时会级联加载 Node 和 Edge（聚合根特性）

        返回：
            Workflow 列表（可能为空）

        实现要求：
        - 按 created_at 倒序排列
        - 返回所有状态的 Workflow（包括 DRAFT、PUBLISHED、ARCHIVED）
        - 级联加载 Node 和 Edge

        注意：
        - 如果数据量大，应该使用分页（find_all_paginated）
        - 这里为了简单，先返回所有数据
        """
        ...

    def exists(self, workflow_id: str) -> bool:
        """检查 Workflow 是否存在

        业务语义：
        - 快速检查 Workflow 是否存在
        - 不需要加载完整实体（性能优化）

        参数：
            workflow_id: Workflow ID

        返回：
            True 表示存在，False 表示不存在

        实现建议：
        - 使用 COUNT 或 EXISTS 查询（不加载实体）
        - 比 find_by_id() 更高效
        """
        ...

    def delete(self, workflow_id: str) -> None:
        """删除 Workflow 实体

        业务语义：
        - 物理删除 Workflow（不是软删除）
        - 如果 Workflow 不存在，不抛异常（幂等操作）
        - 删除时会级联删除 Node 和 Edge（聚合根特性）

        参数：
            workflow_id: Workflow ID

        实现要求：
        - 必须是原子操作（事务内完成）
        - 幂等：多次删除同一个 Workflow 不报错
        - 级联删除 Node 和 Edge

        注意：
        - 删除 Workflow 时，关联的执行记录怎么办？
        - 选项 1：级联删除（删除 Workflow 时删除所有执行记录）
        - 选项 2：禁止删除（如果有执行记录，抛出异常）
        - 选项 3：软删除（标记 Workflow 为 ARCHIVED）
        - 具体策略由业务决定，实现层负责执行
        """
        ...
