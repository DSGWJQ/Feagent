"""ChatMessageRepository Port - 定义 ChatMessage 实体的持久化接口

为什么需要 ChatMessageRepository Port？
1. 依赖倒置（DIP）：领域层定义接口，基础设施层实现接口
2. 解耦：领域层不依赖具体的数据库技术（SQLAlchemy、MongoDB 等）
3. 可测试性：Use Case 可以使用 Mock Repository 进行单元测试
4. 灵活性：可以轻松切换不同的存储实现

设计原则：
- 使用 Protocol（结构化子类型，不需要显式继承）
- 只定义领域层需要的方法（不要过度设计）
- 方法签名使用领域对象（ChatMessage 实体）
- 不依赖任何框架（纯 Python）
"""

from typing import Protocol

from src.domain.entities.chat_message import ChatMessage


class ChatMessageRepository(Protocol):
    """ChatMessage 仓储接口

    职责：
    - 定义 ChatMessage 实体的持久化操作
    - 支持对话历史的存储、查询、搜索、删除
    - 不关心具体实现（内存、SQL、NoSQL 等）

    方法命名规范：
    - save(): 保存消息
    - find_by_workflow_id(): 查询工作流的历史记录
    - search(): 搜索消息
    - delete_by_workflow_id(): 清空工作流的历史
    - count_by_workflow_id(): 统计消息数量
    """

    def save(self, message: ChatMessage) -> None:
        """保存 ChatMessage 实体

        业务场景：
        1. 用户在工作流中发送消息 → 保存用户消息
        2. AI 回复用户 → 保存 AI 消息
        3. 每次对话都会调用此方法 2 次（1 次用户消息 + 1 次 AI 回复）

        业务语义：
        - 保存消息到持久化存储
        - 如果消息 ID 已存在，应该更新（幂等操作）
        - 如果消息 ID 不存在，则新增

        参数：
            message: ChatMessage 实体

        实现要求：
        - 必须是原子操作（事务内完成）
        - 保存失败应抛出异常
        - 实现时应验证 workflow_id 是否存在（外键约束）
        """
        ...

    def find_by_workflow_id(self, workflow_id: str, limit: int = 100) -> list[ChatMessage]:
        """根据工作流 ID 查询历史记录

        业务场景：
        1. 用户打开工作流的对话历史页面
        2. 前端调用 GET /api/workflows/{id}/chat-history
        3. 显示最近的 N 条对话记录

        业务语义：
        - 查询指定工作流的所有消息
        - 按时间顺序排列（旧 → 新）
        - 支持限制返回数量（避免数据量过大）
        - 如果工作流没有消息，返回空列表（不抛异常）

        参数：
            workflow_id: 工作流 ID
            limit: 最多返回多少条消息（默认 100）

        返回：
            ChatMessage 列表（按 timestamp 升序排列）

        实现要求：
        - 按 timestamp 升序排列（最旧的在前）
        - 限制返回数量（性能优化）
        - 返回空列表而不是 None（符合 Python 习惯）

        性能考虑：
        - 应该在 workflow_id 和 timestamp 上创建索引
        - 对于超大数据集，考虑分页查询
        """
        ...

    def search(
        self, workflow_id: str, query: str, threshold: float = 0.5
    ) -> list[tuple[ChatMessage, float]]:
        """在工作流的历史记录中搜索消息

        业务场景：
        1. 用户在历史记录中搜索关键词："HTTP节点"
        2. 前端调用 GET /api/workflows/{id}/chat-search?query=HTTP节点
        3. 返回包含关键词的消息列表（按相关性排序）

        业务语义：
        - 在指定工作流的消息中搜索
        - 支持关键词匹配（不是精确匹配）
        - 返回 (消息, 相关性分数) 的列表
        - 按相关性分数降序排列（最相关的在前）
        - 支持相关性阈值过滤（过滤掉不相关的结果）

        参数：
            workflow_id: 工作流 ID
            query: 搜索关键词
            threshold: 相关性阈值（0-1），低于此值的结果会被过滤

        返回：
            [(ChatMessage, relevance_score), ...] 按相关性降序排列
            - ChatMessage: 匹配的消息
            - relevance_score: 相关性分数（0-1），1 表示完全匹配

        实现要求：
        - 按相关性分数降序排列
        - 过滤掉低于阈值的结果
        - 如果没有匹配结果，返回空列表

        实现建议：
        - 简单实现：使用 LIKE 查询 + Jaccard 相似度
        - 高级实现：使用全文搜索（PostgreSQL FTS、Elasticsearch）
        - 企业级实现：使用向量数据库（Chroma、Pinecone）+ 语义搜索

        性能考虑：
        - 对于大数据集，考虑使用全文搜索索引
        - 对于中文搜索，考虑使用分词器
        """
        ...

    def delete_by_workflow_id(self, workflow_id: str) -> None:
        """清空工作流的对话历史

        业务场景：
        1. 用户点击"清空历史记录"按钮
        2. 前端调用 DELETE /api/workflows/{id}/chat-history
        3. 删除该工作流的所有消息

        业务语义：
        - 物理删除指定工作流的所有消息
        - 如果工作流没有消息，不抛异常（幂等操作）
        - 不影响其他工作流的消息（按 workflow_id 隔离）

        参数：
            workflow_id: 工作流 ID

        实现要求：
        - 必须是原子操作（事务内完成）
        - 幂等：多次删除同一个工作流的历史不报错
        - 只删除消息，不删除工作流本身

        安全考虑：
        - 考虑添加软删除（标记 deleted_at）
        - 考虑添加回收站机制（30 天后真正删除）
        - 考虑添加操作日志（谁、何时、删除了什么）
        """
        ...

    def count_by_workflow_id(self, workflow_id: str) -> int:
        """统计工作流的消息数量

        业务场景：
        1. 前端显示："共 25 条对话记录"
        2. 检查工作流是否有历史记录
        3. 统计分析（每个工作流平均对话数）

        业务语义：
        - 统计指定工作流的消息总数
        - 如果工作流没有消息，返回 0
        - 快速查询（不需要加载完整消息）

        参数：
            workflow_id: 工作流 ID

        返回：
            消息数量（整数，≥0）

        实现要求：
        - 使用 COUNT 查询（不加载消息内容）
        - 性能优化：比 len(find_by_workflow_id()) 更高效

        性能考虑：
        - 应该在 workflow_id 上创建索引
        - 对于超大数据集，考虑使用缓存
        """
        ...
