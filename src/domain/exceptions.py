"""领域层异常定义

为什么需要领域异常？
1. 业务语义清晰：DomainError 表示业务规则违反，不是技术错误
2. 异常分层：Domain 异常 vs Infrastructure 异常 vs API 异常
3. 统一处理：上层可以统一捕获 DomainError 并转换为 4xx 错误

设计原则：
- 继承自 Exception（Python 标准异常基类）
- 简单明了（不过度设计）
- 可扩展（未来可以添加错误码、详情等）
"""


class DomainError(Exception):
    """领域层异常基类

    用途：
    - 表示业务规则违反（如：start 不能为空）
    - 表示领域不变式违反（如：状态流转非法）

    为什么继承 Exception？
    - Python 标准做法
    - 可以被 try-except 捕获
    - 可以携带错误消息

    示例：
        if not start:
            raise DomainError("start 不能为空")

    未来扩展：
    - 可以添加 error_code 属性
    - 可以添加 details 字典
    - 可以添加子类（如 ValidationError、StateError）
    """

    pass


class NotFoundError(DomainError):
    """实体不存在异常

    用途：
    - 表示查询的实体不存在（如：Agent 不存在、Run 不存在）
    - 用于 Repository 的 get_by_id() 方法

    为什么需要单独的异常类？
    - 语义清晰：区分"实体不存在"和"业务规则违反"
    - 便于统一处理：API 层可以统一捕获并返回 404
    - 符合 HTTP 语义：404 Not Found

    示例：
        agent = await repository.get_by_id(agent_id)
        # 如果不存在，抛出 NotFoundError

    参数：
        entity_type: 实体类型（如："Agent"、"Run"）
        entity_id: 实体 ID
    """

    def __init__(self, entity_type: str, entity_id: str):
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} 不存在: {entity_id}")


# EntityNotFoundError是NotFoundError的别名，用于Repository层
EntityNotFoundError = NotFoundError
