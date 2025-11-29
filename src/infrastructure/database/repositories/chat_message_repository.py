"""ChatMessage Repository 实现 - SQLAlchemy 适配器

职责：
- 实现 ChatMessageRepository Port（依赖倒置）
- 提供 ChatMessage 实体的持久化操作
- ORM Model ⇄ Domain Entity 转换
"""

from datetime import UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domain.entities.chat_message import ChatMessage
from src.domain.ports.chat_message_repository import ChatMessageRepository
from src.infrastructure.database.models import ChatMessageModel


class SQLAlchemyChatMessageRepository(ChatMessageRepository):
    """SQLAlchemy ChatMessage Repository 实现

    职责：
    - 实现 ChatMessageRepository Port 接口
    - 管理 ChatMessage 实体的 CRUD 操作
    - 处理 ORM Model 与 Domain Entity 的转换
    """

    def __init__(self, session: Session):
        """初始化 Repository

        参数：
            session: SQLAlchemy Session（事务边界）
        """
        self.session = session

    def save(self, message: ChatMessage) -> None:
        """保存 ChatMessage 实体

        业务场景：
        - 用户发送消息 → 保存用户消息
        - AI 回复用户 → 保存 AI 消息

        实现：
        - 如果 ID 存在，执行 merge（更新）
        - 如果 ID 不存在，执行 add（新增）
        - 提交事务由外部控制（Use Case 负责事务边界）
        """
        # Entity → ORM Model
        model = ChatMessageModel(
            id=message.id,
            workflow_id=message.workflow_id,
            content=message.content,
            is_user=message.is_user,
            timestamp=message.timestamp,
        )

        # Merge：如果存在则更新，不存在则新增
        self.session.merge(model)

    def find_by_workflow_id(self, workflow_id: str, limit: int = 100) -> list[ChatMessage]:
        """根据工作流 ID 查询历史记录

        业务场景：
        - 用户打开工作流的对话历史页面
        - 显示最近的 N 条对话记录

        实现：
        - 按 timestamp 升序排列（旧 → 新）
        - 限制返回数量（性能优化）
        """
        stmt = (
            select(ChatMessageModel)
            .where(ChatMessageModel.workflow_id == workflow_id)
            .order_by(ChatMessageModel.timestamp.asc())  # 旧 → 新
            .limit(limit)
        )

        models = self.session.execute(stmt).scalars().all()

        # ORM Model → Entity
        return [self._model_to_entity(model) for model in models]

    def search(
        self, workflow_id: str, query: str, threshold: float = 0.5
    ) -> list[tuple[ChatMessage, float]]:
        """在工作流的历史记录中搜索消息

        业务场景：
        - 用户在历史记录中搜索关键词："HTTP节点"
        - 返回包含关键词的消息列表（按相关性排序）

        实现：
        - 简单实现：使用 LIKE 查询 + Jaccard 相似度
        - 按相关性分数降序排列
        """
        # 1. 使用 LIKE 查询匹配消息
        stmt = select(ChatMessageModel).where(
            ChatMessageModel.workflow_id == workflow_id,
            ChatMessageModel.content.ilike(f"%{query}%"),  # 不区分大小写
        )

        models = self.session.execute(stmt).scalars().all()

        # 如果没有匹配结果，直接返回空列表
        if not models:
            return []

        # 2. 计算相关性分数（改进的混合算法）
        results: list[tuple[ChatMessage, float]] = []
        query_words = set(self._tokenize(query.lower()))

        for model in models:
            msg_words = set(self._tokenize(model.content.lower()))

            if not msg_words:
                continue

            # 基础分数：Jaccard 相似度
            intersection = len(query_words & msg_words)
            union = len(query_words | msg_words)
            jaccard_score = intersection / union if union > 0 else 0.0

            # 增强分数：如果包含完整的查询词，给予额外加分
            # 这对中文查询特别有用（例如 "HTTP节点"）
            contains_query = query.lower() in model.content.lower()
            boost_score = 0.6 if contains_query else 0.0

            # 最终相关性 = Jaccard 相似度 + 包含查询词的加分
            # 确保分数在 [0, 1] 范围内
            relevance = min(1.0, jaccard_score + boost_score)

            # 过滤低于阈值的结果
            if relevance >= threshold:
                entity = self._model_to_entity(model)
                results.append((entity, relevance))

        # 3. 按相关性分数降序排列
        results.sort(key=lambda x: x[1], reverse=True)

        return results

    def delete_by_workflow_id(self, workflow_id: str) -> None:
        """清空工作流的对话历史

        业务场景：
        - 用户点击"清空历史记录"按钮
        - 删除该工作流的所有消息

        实现：
        - 物理删除（不是软删除）
        - 幂等操作：多次删除不报错
        """
        # 删除所有匹配的消息
        self.session.query(ChatMessageModel).filter(
            ChatMessageModel.workflow_id == workflow_id
        ).delete()

    def count_by_workflow_id(self, workflow_id: str) -> int:
        """统计工作流的消息数量

        业务场景：
        - 前端显示："共 25 条对话记录"

        实现：
        - 使用 COUNT 查询（不加载消息内容）
        - 性能优化：比 len(find_by_workflow_id()) 更高效
        """
        count = (
            self.session.query(ChatMessageModel)
            .filter(ChatMessageModel.workflow_id == workflow_id)
            .count()
        )

        return count

    @staticmethod
    def _model_to_entity(model: ChatMessageModel) -> ChatMessage:
        """ORM Model → Domain Entity

        转换规则：
        - 字段一一对应
        - 确保 timestamp 是 UTC 时间
        """
        # 确保 timestamp 是 UTC aware datetime
        timestamp = model.timestamp
        if timestamp.tzinfo is None:
            # 如果是 naive datetime，假设为 UTC
            timestamp = timestamp.replace(tzinfo=UTC)

        return ChatMessage(
            id=model.id,
            workflow_id=model.workflow_id,
            content=model.content,
            is_user=model.is_user,
            timestamp=timestamp,
        )

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """简单的分词器（将文本分为单词）

        用于搜索功能的相关性计算

        参数：
            text: 要分词的文本

        返回：
            分词后的单词列表
        """
        import re

        words = re.findall(r"\w+", text)
        return words
