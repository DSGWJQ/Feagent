"""SQLAlchemy Agent Repository 实现

第一性原理：Repository 是领域对象和数据存储之间的转换器

职责：
1. 转换（Translation）：领域实体 ⇄ ORM 模型
2. 持久化（Persistence）：保存、查询、删除
3. 异常转换（Exception Translation）：数据库异常 → 领域异常

设计模式：
- Adapter 模式：实现领域层定义的 Port 接口
- Assembler 模式：负责对象转换（ORM ⇄ Entity）
- Repository 模式：封装数据访问逻辑

为什么需要 Assembler？
- 关注点分离：转换逻辑独立于持久化逻辑
- 可测试性：可以单独测试转换逻辑
- 可维护性：转换逻辑集中管理
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domain.entities.agent import Agent
from src.domain.exceptions import NotFoundError
from src.infrastructure.database.models import AgentModel


class SQLAlchemyAgentRepository:
    """SQLAlchemy Agent Repository 实现

    实现领域层定义的 AgentRepository Port 接口

    依赖：
    - Session: SQLAlchemy 同步会话（依赖注入）

    为什么使用同步 Session？
    - 当前实现是同步的（Use Case 是同步的）
    - 简单易懂，易于调试
    - 未来可以迁移到异步

    为什么不显式继承 AgentRepository？
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

    def _to_entity(self, model: AgentModel) -> Agent:
        """将 ORM 模型转换为领域实体

        为什么需要这个方法？
        - ORM 模型是数据库表映射（Infrastructure 层）
        - 领域实体是业务逻辑载体（Domain 层）
        - 两者职责不同，需要转换

        转换策略：
        - 直接映射：字段名相同，直接赋值
        - 不加载关联对象：避免 N+1 查询问题

        参数：
            model: AgentModel ORM 模型

        返回：
            Agent 领域实体
        """
        return Agent(
            id=model.id,
            start=model.start,
            goal=model.goal,
            status=model.status,
            name=model.name,
            created_at=model.created_at,
        )

    def _to_model(self, entity: Agent) -> AgentModel:
        """将领域实体转换为 ORM 模型

        为什么需要这个方法？
        - 保存实体到数据库时需要 ORM 模型
        - 领域实体不应该知道数据库细节

        转换策略：
        - 直接映射：字段名相同，直接赋值
        - 不处理关联对象：runs 由 SQLAlchemy 管理

        参数：
            entity: Agent 领域实体

        返回：
            AgentModel ORM 模型
        """
        return AgentModel(
            id=entity.id,
            start=entity.start,
            goal=entity.goal,
            status=entity.status,
            name=entity.name,
            created_at=entity.created_at,
        )

    # ==================== Repository 方法 ====================
    # 职责：实现 AgentRepository Port 接口

    def save(self, agent: Agent) -> None:
        """保存 Agent 实体（新增或更新）

        第一性原理：save() 应该是幂等的
        - 如果实体不存在，则新增（INSERT）
        - 如果实体已存在，则更新（UPDATE）

        实现策略：
        1. 查询实体是否存在
        2. 如果存在，更新所有字段
        3. 如果不存在，新增实体
        4. 提交事务

        为什么不直接用 session.merge()？
        - merge() 会触发额外的 SELECT 查询
        - 手动判断更清晰，性能更好

        为什么要 session.commit()？
        - 确保数据持久化到数据库
        - 事务提交后才能被其他会话看到

        参数：
            agent: Agent 领域实体
        """
        # 查询实体是否存在
        result = self.session.execute(select(AgentModel).where(AgentModel.id == agent.id))
        existing_model = result.scalar_one_or_none()

        if existing_model:
            # 更新已存在的实体
            # 为什么逐个字段赋值？确保所有字段都被更新
            existing_model.start = agent.start
            existing_model.goal = agent.goal
            existing_model.status = agent.status
            existing_model.name = agent.name
            existing_model.created_at = agent.created_at
        else:
            # 新增实体
            new_model = self._to_model(agent)
            self.session.add(new_model)

        # 提交事务
        self.session.commit()

    def get_by_id(self, agent_id: str) -> Agent:
        """根据 ID 获取 Agent 实体（不存在抛异常）

        第一性原理：get 语义表示"期望存在"
        - 如果不存在，应该立即失败（Fail Fast）
        - 抛出 NotFoundError，让调用者知道出错了

        实现策略：
        1. 查询 ORM 模型
        2. 如果不存在，抛出 NotFoundError
        3. 如果存在，转换为领域实体

        为什么用 scalar_one_or_none()？
        - scalar_one(): 期望恰好一个结果，否则抛异常
        - scalar_one_or_none(): 期望 0 或 1 个结果
        - 我们需要区分"不存在"和"多个结果"

        参数：
            agent_id: Agent ID

        返回：
            Agent 领域实体

        抛出：
            NotFoundError: 当 Agent 不存在时
        """
        result = self.session.execute(select(AgentModel).where(AgentModel.id == agent_id))
        model = result.scalar_one_or_none()

        if model is None:
            raise NotFoundError(entity_type="Agent", entity_id=agent_id)

        return self._to_entity(model)

    def find_by_id(self, agent_id: str) -> Agent | None:
        """根据 ID 查找 Agent 实体（不存在返回 None）

        第一性原理：find 语义表示"可能不存在"
        - 不存在是正常情况，返回 None
        - 不抛异常，让调用者自己处理

        实现策略：
        1. 查询 ORM 模型
        2. 如果不存在，返回 None
        3. 如果存在，转换为领域实体

        参数：
            agent_id: Agent ID

        返回：
            Agent 领域实体或 None
        """
        result = self.session.execute(select(AgentModel).where(AgentModel.id == agent_id))
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_entity(model)

    def find_all(self) -> list[Agent]:
        """查找所有 Agent

        第一性原理：查询方法应该返回集合，即使为空
        - 空集合用 []，不用 None
        - 符合 Python 惯例

        实现策略：
        1. 查询所有 ORM 模型
        2. 按创建时间倒序排列（最新的在前）
        3. 转换为领域实体列表

        为什么按 created_at 倒序？
        - 用户通常关心最新的 Agent
        - 符合常见的 UI 展示习惯

        为什么用 scalars().all()？
        - scalars(): 返回标量结果（不是 Row 对象）
        - all(): 返回所有结果（list）

        返回：
            Agent 列表（可能为空）
        """
        result = self.session.execute(
            select(AgentModel).order_by(AgentModel.created_at.desc())
        )
        models = result.scalars().all()

        # 转换为领域实体列表
        return [self._to_entity(model) for model in models]

    def exists(self, agent_id: str) -> bool:
        """检查 Agent 是否存在

        第一性原理：exists 只需要知道"是否存在"，不需要加载实体
        - 性能优化：只查询 ID，不加载所有字段
        - 使用 COUNT 或 EXISTS 查询

        实现策略：
        1. 查询 ID 是否存在
        2. 返回布尔值

        为什么不用 find_by_id() is not None？
        - find_by_id() 会加载整个实体（浪费资源）
        - exists() 只查询 ID（更高效）

        SQL 对比：
        - find_by_id(): SELECT * FROM agents WHERE id = ?
        - exists(): SELECT 1 FROM agents WHERE id = ? LIMIT 1

        参数：
            agent_id: Agent ID

        返回：
            True 表示存在，False 表示不存在
        """
        result = self.session.execute(select(AgentModel.id).where(AgentModel.id == agent_id))
        return result.scalar_one_or_none() is not None

    def delete(self, agent_id: str) -> None:
        """删除 Agent 实体

        第一性原理：delete 应该是幂等的
        - 删除不存在的实体不应该抛异常
        - 多次删除同一个实体结果相同

        实现策略：
        1. 查询实体是否存在
        2. 如果存在，删除实体
        3. 如果不存在，什么都不做（幂等）
        4. 提交事务

        为什么不直接 DELETE FROM agents WHERE id = ?？
        - SQLAlchemy ORM 需要先加载对象才能删除
        - 这样可以触发级联删除（删除关联的 Run）

        级联删除：
        - AgentModel 定义了 cascade="all, delete-orphan"
        - 删除 Agent 时，自动删除所有关联的 Run
        - 这是在 ORM 模型中定义的，不需要手动处理

        参数：
            agent_id: Agent ID
        """
        # 查询实体是否存在
        result = self.session.execute(select(AgentModel).where(AgentModel.id == agent_id))
        model = result.scalar_one_or_none()

        # 如果存在，删除实体
        if model is not None:
            self.session.delete(model)
            # 提交事务
            self.session.commit()
