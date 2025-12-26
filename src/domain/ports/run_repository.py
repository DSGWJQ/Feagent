"""RunRepository Port - 定义 Run 实体的持久化接口

为什么需要 RunRepository Port?
    1. 依赖倒置 (DIP): 领域层定义接口，基础设施层实现接口
    2. 解耦: 领域层不依赖具体数据库技术 (SQLAlchemy、MongoDB 等)
    3. 可测试性: UseCase 可以使用 Mock Repository 进行单元测试
    4. 灵活性: 可替换不同存储实现

设计原则:
    - 使用 Protocol (结构化子类型，不需要显式继承)
    - 只定义领域层需要的方法 (不要过度设计)
    - 方法签名使用领域对象 (Run 实体)
    - Repository 不调用 commit()，事务由 UseCase 控制

Phase 1 事务规则:
    - save/update/delete 只使用 flush()，不调用 commit()
    - commit/rollback 由 UseCase 层的 TransactionManager 控制
"""

from datetime import datetime
from typing import Protocol

from src.domain.entities.run import Run
from src.domain.value_objects.run_status import RunStatus


class RunRepository(Protocol):
    """Run 仓储接口

    实现要求:
        - 所有写操作只 flush，不 commit
        - 事务边界由 UseCase 控制
    """

    def save(self, run: Run) -> None:
        """保存 Run (新增)

        语义:
            - 创建新的 Run 记录
            - Run.id 必须唯一

        实现要求:
            - 原子操作 (事务内完成)
            - 只 flush，不 commit
        """
        ...

    def get_by_id(self, run_id: str) -> Run:
        """按 ID 获取 Run (不存在抛异常)

        Args:
            run_id: Run ID

        Returns:
            Run 实体

        Raises:
            NotFoundError: 当 Run 不存在时
        """
        ...

    def find_by_id(self, run_id: str) -> Run | None:
        """按 ID 查找 Run (不存在返回 None)

        Args:
            run_id: Run ID

        Returns:
            Run 实体或 None
        """
        ...

    def list_by_workflow_id(
        self,
        workflow_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Run]:
        """查询指定 Workflow 下的 Run 列表

        Args:
            workflow_id: Workflow ID
            limit: 返回数量上限
            offset: 偏移量

        Returns:
            Run 列表，按 created_at 倒序排列 (最新在前)
        """
        ...

    def list_by_project_id(
        self,
        project_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Run]:
        """查询指定 Project 下的 Run 列表

        Args:
            project_id: Project ID
            limit: 返回数量上限
            offset: 偏移量

        Returns:
            Run 列表，按 created_at 倒序排列 (最新在前)
        """
        ...

    def update(self, run: Run) -> None:
        """更新 Run (必须已存在)

        语义:
            - Run 必须存在，否则抛 NotFoundError
            - 用于更新 status/finished_at 等字段

        实现要求:
            - 原子操作 (事务内完成)
            - 只 flush，不 commit

        Raises:
            NotFoundError: 当 Run 不存在时
        """
        ...

    def count_by_workflow_id(self, workflow_id: str) -> int:
        """统计指定 Workflow 下的 Run 数量

        Args:
            workflow_id: Workflow ID

        Returns:
            Run 数量
        """
        ...

    def update_status_if_current(
        self,
        run_id: str,
        *,
        current_status: RunStatus,
        target_status: RunStatus,
        finished_at: datetime | None = None,
    ) -> bool:
        """条件更新状态 (乐观并发控制 / Compare-And-Swap)

        仅当当前数据库中的状态等于 current_status 时，才更新为 target_status。
        用于解决并发场景下的状态竞态问题 (TOCTOU)。

        Args:
            run_id: Run ID
            current_status: 期望的当前状态
            target_status: 目标状态
            finished_at: 结束时间 (终态时设置，UTC aware)

        Returns:
            True 表示成功更新 1 行；False 表示状态不匹配（已被其他事务更新）

        示例:
            # 尝试 created → running，只有一个事务能成功
            success = repo.update_status_if_current(
                run_id,
                current_status=RunStatus.CREATED,
                target_status=RunStatus.RUNNING,
            )
        """
        ...
