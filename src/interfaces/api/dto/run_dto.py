"""Run DTO（Data Transfer Objects）

定义 Run 相关的请求和响应模型
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ExecuteRunRequest(BaseModel):
    """执行 Run 请求 DTO

    业务场景：用户通过 API 触发 Agent 执行

    字段：
    - 当前简化实现：请求体为空
    - agent_id 从 URL 路径参数获取

    未来扩展：
    - input_data: 运行时输入数据（可选）
    - config: 运行时配置（可选）

    为什么请求体为空？
    1. 当前简化实现：Agent 执行不需要额外参数
    2. agent_id 已经在 URL 路径中
    3. 符合 RESTful 设计：POST /api/agents/{agent_id}/runs

    示例：
    >>> request = ExecuteRunRequest()
    >>> # agent_id 从路径参数获取
    """

    pass  # 当前为空，未来可以添加字段


class RunResponse(BaseModel):
    """Run 响应 DTO

    业务场景：API 返回 Run 信息给前端

    字段：
    - id: Run ID
    - agent_id: Agent ID
    - status: Run 状态（pending/running/succeeded/failed）
    - created_at: 创建时间
    - started_at: 启动时间（可选）
    - finished_at: 完成时间（可选）
    - error: 错误信息（可选）

    为什么需要单独的响应 DTO？
    1. 关注点分离：响应结构可能与 Domain 实体不同
    2. 版本兼容：可以添加/删除字段而不影响 Domain 层
    3. 安全性：只暴露需要的字段
    4. 文档生成：清晰的 API 文档

    示例：
    >>> from src.domain.entities import Run
    >>> run = Run.create(agent_id="agent-123")
    >>> response = RunResponse.from_entity(run)
    >>> print(response.status)
    pending
    """

    id: str
    agent_id: str
    status: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None

    @classmethod
    def from_entity(cls, run) -> "RunResponse":
        """从 Domain 实体创建响应 DTO

        这是 Assembler 模式的实现：
        - Domain Entity → DTO
        - 负责数据转换和映射

        为什么需要这个方法？
        1. 封装转换逻辑：集中管理 Entity → DTO 的转换
        2. 类型安全：明确的转换接口
        3. 易于维护：转换逻辑集中在一处
        4. 解耦：Domain 层不需要知道 DTO 的存在

        注意：
        - status 需要从 RunStatus 枚举转换为字符串
        - 可选字段（started_at、finished_at、error）可能为 None

        参数：
            run: Run 实体

        返回：
            RunResponse DTO

        示例：
        >>> run = Run.create(agent_id="agent-123")
        >>> response = RunResponse.from_entity(run)
        >>> print(response.status)
        pending
        """
        return cls(
            id=run.id,
            agent_id=run.agent_id,
            status=run.status.value,  # RunStatus 枚举转字符串
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
            error=run.error,
        )

    # Pydantic v2 配置
    # 注意：Pydantic v2 会自动将 datetime 序列化为 ISO 8601 格式
    # 不需要手动配置 json_encoders
    model_config = ConfigDict(
        # 允许从 ORM 模型创建（未来可能需要）
        from_attributes=True,
    )
