"""SQLAlchemy Task Repository 实现

第一性原理：Repository 是领域对象和数据存储之间的转换器

职责：
1. 转换（Translation）：领域实体 ⇄ ORM 模型
2. 持久化（Persistence）：保存、查询、删除
3. 异常转换（Exception Translation）：数据库异常 → 领域异常
4. 聚合完整性（Aggregate Integrity）：Task + TaskEvent 作为一个整体

设计模式：
- Adapter 模式：实现领域层定义的 Port 接口
- Assembler 模式：负责对象转换（ORM ⇄ Entity）
- Repository 模式：封装数据访问逻辑

Task 与 TaskEvent 的持久化：
- Task 是聚合根，TaskEvent 是聚合内的值对象
- 保存 Task 时，同时保存 TaskEvent（聚合完整性）
- TaskEvent 存储为 JSON 数组（不需要单独的表）
- 读取 Task 时，同时读取 TaskEvent（聚合完整性）

为什么 TaskEvent 用 JSON 存储？
1. TaskEvent 是值对象，没有独立的生命周期
2. TaskEvent 总是和 Task 一起查询，不需要单独查询
3. 简化数据库设计，避免额外的表和 JOIN
4. 符合聚合的完整性（Task 和 TaskEvent 作为一个整体）
"""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.domain.entities.task import Task, TaskStatus
from src.domain.exceptions import NotFoundError
from src.domain.value_objects.task_event import TaskEvent
from src.infrastructure.database.models import TaskModel


class SQLAlchemyTaskRepository:
    """SQLAlchemy Task Repository 实现

    实现领域层定义的 TaskRepository Port 接口

    依赖：
    - Session: SQLAlchemy 同步会话（依赖注入）

    为什么使用同步 Session？
    - 当前实现是同步的（Use Case 是同步的）
    - 简单易懂，易于调试
    - 未来可以迁移到异步

    为什么不显式继承 TaskRepository？
    - 使用 Protocol（结构化子类型）
    - 只要方法签名匹配，就符合接口
    - 更灵活，不需要显式继承
    """

    def __init__(self, session: Session):
        """初始化 Repository

        参数：
            session: SQLAlchemy 同步会话

        为什么通过构造函数注入 session？
        - 依赖注入：由外部管理 session 生命周期
        - 事务控制：调用者控制事务边界
        - 可测试性：测试时可以注入 Mock session
        """
        self.session = session

    # ==================== Assembler 方法 ====================
    # 职责：ORM 模型 ⇄ 领域实体转换

    def _to_entity(self, model: TaskModel) -> Task:
        """将 ORM 模型转换为领域实体

        为什么需要这个方法？
        - ORM 模型是数据库表映射（Infrastructure 层）
        - 领域实体是业务逻辑载体（Domain 层）
        - 两者职责不同，需要转换

        转换策略：
        - 直接映射：字段名相同，直接赋值
        - 类型转换：status 从字符串转换为 TaskStatus 枚举
        - TaskEvent 转换：从 JSON 数组转换为 TaskEvent 对象列表

        参数：
            model: TaskModel ORM 模型

        返回：
            Task 领域实体（包含 TaskEvent）
        """
        # 转换 TaskEvent（从 JSON 到对象）
        events = []
        if model.events:
            for event_dict in model.events:
                # 从 JSON 字典创建 TaskEvent 对象
                # 注意：timestamp 是 ISO 格式字符串，需要转换为 datetime
                timestamp_str = event_dict["timestamp"]
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                events.append(
                    TaskEvent(
                        timestamp=timestamp,
                        message=event_dict["message"],
                    )
                )

        return Task(
            id=model.id,
            agent_id=model.agent_id,
            run_id=model.run_id,
            name=model.name,
            description=model.description,
            input_data=model.input_data,
            output_data=model.output_data,
            status=TaskStatus(model.status),  # 字符串 → 枚举
            error=model.error,
            retry_count=model.retry_count,
            created_at=model.created_at,
            started_at=model.started_at,
            finished_at=model.finished_at,
            events=events,  # TaskEvent 对象列表
        )

    def _to_model(self, entity: Task, model: TaskModel | None = None) -> TaskModel:
        """将领域实体转换为 ORM 模型

        为什么需要这个方法？
        - 保存实体到数据库时需要 ORM 模型
        - 领域实体不应该知道数据库细节

        转换策略：
        - 直接映射：字段名相同，直接赋值
        - 类型转换：status 从 TaskStatus 枚举转换为字符串
        - TaskEvent 转换：从 TaskEvent 对象列表转换为 JSON 数组
        - 更新模式：如果 model 存在，则更新字段；否则创建新模型

        参数：
            entity: Task 领域实体
            model: 已存在的 TaskModel（可选，用于更新）

        返回：
            TaskModel ORM 模型

        为什么支持更新模式？
        - save() 方法需要判断是新增还是更新
        - 更新时需要保留 ORM 模型的状态（如 _sa_instance_state）
        - 避免创建新对象导致的 SQLAlchemy 错误
        """
        # 转换 TaskEvent（从对象到 JSON）
        events_json = []
        for event in entity.events:
            # 将 TaskEvent 对象转换为 JSON 字典
            # 注意：timestamp 转换为 ISO 格式字符串（UTC 时区）
            events_json.append(
                {
                    "timestamp": event.timestamp.isoformat(),
                    "message": event.message,
                }
            )

        # 如果 model 不存在，创建新模型
        if model is None:
            model = TaskModel(id=entity.id)

        # 更新字段
        model.agent_id = entity.agent_id
        model.run_id = entity.run_id
        model.name = entity.name
        model.description = entity.description
        model.input_data = entity.input_data
        model.output_data = entity.output_data
        model.status = entity.status.value  # 枚举 → 字符串
        model.error = entity.error
        model.retry_count = entity.retry_count
        model.created_at = entity.created_at
        model.started_at = entity.started_at
        model.finished_at = entity.finished_at
        model.events = events_json  # TaskEvent JSON 数组

        return model

    # ==================== Repository 方法 ====================
    # 职责：持久化操作（CRUD）

    def save(self, task: Task) -> None:
        """保存 Task 实体（新增或更新）

        实现策略：
        1. 查询数据库，判断 Task 是否存在
        2. 如果存在，更新现有记录
        3. 如果不存在，插入新记录
        4. 同时保存 TaskEvent（作为 JSON 数组）

        为什么不用 merge()？
        - merge() 会触发额外的查询
        - 手动判断更清晰、可控

        聚合完整性：
        - Task 和 TaskEvent 作为一个整体保存
        - 不会出现 Task 保存成功但 TaskEvent 丢失的情况
        """
        # 查询是否存在
        stmt = select(TaskModel).where(TaskModel.id == task.id)
        result = self.session.execute(stmt)
        existing_model = result.scalar_one_or_none()

        if existing_model:
            # 更新现有记录
            model = self._to_model(task, existing_model)
        else:
            # 插入新记录
            model = self._to_model(task)
            self.session.add(model)

        # 提交由调用者控制（事务边界）
        self.session.flush()

    def get_by_id(self, task_id: str) -> Task:
        """根据 ID 获取 Task 实体（不存在抛异常）

        实现策略：
        1. 查询数据库
        2. 如果不存在，抛出 NotFoundError
        3. 如果存在，转换为领域实体（包括 TaskEvent）

        聚合完整性：
        - 返回完整的 Task 聚合（包括所有 TaskEvent）
        """
        stmt = select(TaskModel).where(TaskModel.id == task_id)
        result = self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            raise NotFoundError("Task", task_id)

        return self._to_entity(model)

    def find_by_id(self, task_id: str) -> Task | None:
        """根据 ID 查找 Task 实体（不存在返回 None）

        实现策略：
        1. 查询数据库
        2. 如果不存在，返回 None
        3. 如果存在，转换为领域实体（包括 TaskEvent）
        """
        stmt = select(TaskModel).where(TaskModel.id == task_id)
        result = self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_entity(model)

    def find_by_run_id(self, run_id: str) -> list[Task]:
        """根据 Run ID 查找所有 Task

        实现策略：
        1. 查询数据库（WHERE run_id = ?）
        2. 按 created_at 倒序排列（最新的在前）
        3. 转换为领域实体列表（每个 Task 包括 TaskEvent）

        聚合完整性：
        - 每个 Task 包含完整的 TaskEvent
        """
        stmt = (
            select(TaskModel)
            .where(TaskModel.run_id == run_id)
            .order_by(TaskModel.created_at.desc())  # 倒序
        )
        result = self.session.execute(stmt)
        models = result.scalars().all()

        return [self._to_entity(model) for model in models]

    def find_by_agent_id(self, agent_id: str) -> list[Task]:
        """根据 Agent ID 查找所有 Task

        实现策略：
        1. 查询数据库（WHERE agent_id = ?）
        2. 按 created_at 倒序排列（最新的在前）
        3. 转换为领域实体列表（每个 Task 包括 TaskEvent）

        聚合完整性：
        - 每个 Task 包含完整的 TaskEvent

        业务场景：
        - 用户创建 Agent 后，查看生成的工作流（Tasks）
        - 前端需要展示任务列表
        """
        stmt = (
            select(TaskModel)
            .where(TaskModel.agent_id == agent_id)
            .order_by(TaskModel.created_at.desc())  # 倒序
        )
        result = self.session.execute(stmt)
        models = result.scalars().all()

        return [self._to_entity(model) for model in models]

    def exists(self, task_id: str) -> bool:
        """检查 Task 是否存在

        实现策略：
        1. 使用 COUNT 查询（不加载实体）
        2. 返回 True/False

        性能优化：
        - 不加载完整实体，只查询是否存在
        - 比 find_by_id() 更高效
        """
        stmt = select(TaskModel.id).where(TaskModel.id == task_id)
        result = self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    def delete(self, task_id: str) -> None:
        """删除 Task 实体

        实现策略：
        1. 使用 DELETE 语句（不需要先查询）
        2. 幂等：如果不存在，不报错

        聚合完整性：
        - TaskEvent 存储在 Task 的 JSON 字段中
        - 删除 Task 时，TaskEvent 自动删除
        - 不需要额外的级联删除逻辑
        """
        stmt = delete(TaskModel).where(TaskModel.id == task_id)
        self.session.execute(stmt)
        self.session.flush()
