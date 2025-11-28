"""SQLiteKnowledgeRepository - 使用SQLite存储知识库元数据

DDD规则：
- 实现Domain层定义的KnowledgeRepository接口
- 只负责存储元数据（文档、分块等），向量存储由外部向量引擎（如ChromaDB）管理
"""

import json
from datetime import datetime

import aiosqlite

from src.domain.knowledge_base.entities.document import Document
from src.domain.knowledge_base.entities.document_chunk import DocumentChunk
from src.domain.knowledge_base.entities.knowledge_base import KnowledgeBase
from src.domain.knowledge_base.ports.knowledge_repository import KnowledgeRepository
from src.domain.value_objects.document_source import DocumentSource
from src.domain.value_objects.document_status import DocumentStatus
from src.domain.value_objects.knowledge_base_type import KnowledgeBaseType


class SQLiteKnowledgeRepository(KnowledgeRepository):
    """使用SQLite的知识库仓储（仅存储元数据）"""

    def __init__(self, db_path: str):
        """初始化仓储

        参数：
            db_path: SQLite数据库路径
        """
        self.db_path = db_path

    async def _get_connection(self) -> aiosqlite.Connection:
        """获取数据库连接"""
        conn = await aiosqlite.connect(self.db_path)
        # 启用外键约束
        await conn.execute("PRAGMA foreign_keys = ON")
        return conn

    async def _ensure_tables(self, conn: aiosqlite.Connection) -> None:
        """确保所有表存在"""
        # 知识库表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_bases (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                type TEXT NOT NULL,
                owner_id TEXT,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP
            )
        """)

        # 文档表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP,
                metadata TEXT,
                file_path TEXT,
                workflow_id TEXT
            )
        """)

    # Knowledge Base operations
    async def save_knowledge_base(self, knowledge_base: KnowledgeBase) -> None:
        """保存知识库"""
        conn = await self._get_connection()
        await self._ensure_tables(conn)

        await conn.execute(
            """
            INSERT OR REPLACE INTO knowledge_bases
            (id, name, description, type, owner_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                knowledge_base.id,
                knowledge_base.name,
                knowledge_base.description,
                knowledge_base.type.value,
                knowledge_base.owner_id,
                knowledge_base.created_at,
                knowledge_base.updated_at,
            ),
        )
        await conn.commit()
        await conn.close()

    async def find_knowledge_base_by_id(self, id: str) -> KnowledgeBase | None:
        """根据ID查找知识库"""
        conn = await self._get_connection()
        await self._ensure_tables(conn)

        cursor = await conn.execute("SELECT * FROM knowledge_bases WHERE id = ?", (id,))
        row = await cursor.fetchone()
        await conn.close()

        if row:
            return KnowledgeBase(
                id=row[0],
                name=row[1],
                description=row[2],
                type=KnowledgeBaseType(row[3]),
                created_at=datetime.fromisoformat(row[4]),
                updated_at=datetime.fromisoformat(row[5]) if row[5] else None,
                owner_id=row[6],
            )
        return None

    async def find_knowledge_bases_by_owner(self, owner_id: str) -> list[KnowledgeBase]:
        """根据所有者ID查找知识库"""
        conn = await self._get_connection()
        await self._ensure_tables(conn)

        cursor = await conn.execute("SELECT * FROM knowledge_bases WHERE owner_id = ?", (owner_id,))
        rows = await cursor.fetchall()
        await conn.close()

        return [
            KnowledgeBase(
                id=row[0],
                name=row[1],
                description=row[2],
                type=KnowledgeBaseType(row[3]),
                created_at=datetime.fromisoformat(row[4]),
                updated_at=datetime.fromisoformat(row[5]) if row[5] else None,
                owner_id=row[6],
            )
            for row in rows
        ]

    # Document operations
    async def save_document(self, document: Document) -> None:
        """保存文档"""
        conn = await self._get_connection()
        await self._ensure_tables(conn)

        await conn.execute(
            """
            INSERT OR REPLACE INTO documents
            (id, title, content, source, status, created_at, updated_at, metadata, file_path, workflow_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document.id,
                document.title,
                document.content,
                document.source.value,
                document.status.value,
                document.created_at,
                document.updated_at,
                json.dumps(document.metadata) if document.metadata else None,
                document.file_path,
                document.workflow_id,
            ),
        )
        await conn.commit()
        await conn.close()

    async def find_document_by_id(self, id: str) -> Document | None:
        """根据ID查找文档"""
        conn = await self._get_connection()
        await self._ensure_tables(conn)

        cursor = await conn.execute("SELECT * FROM documents WHERE id = ?", (id,))
        row = await cursor.fetchone()
        await conn.close()

        if row:
            return Document(
                id=row[0],
                title=row[1],
                content=row[2],
                source=DocumentSource(row[3]),
                status=DocumentStatus(row[4]),
                created_at=datetime.fromisoformat(row[5]),
                updated_at=datetime.fromisoformat(row[6]) if row[6] else None,
                metadata=json.loads(row[7]) if row[7] else None,
                file_path=row[8],
                workflow_id=row[9],
            )
        return None

    async def find_documents_by_workflow_id(self, workflow_id: str) -> list[Document]:
        """查找指定工作流的所有文档"""
        conn = await self._get_connection()
        await self._ensure_tables(conn)

        cursor = await conn.execute("SELECT * FROM documents WHERE workflow_id = ?", (workflow_id,))
        rows = await cursor.fetchall()
        await conn.close()

        return [
            Document(
                id=row[0],
                title=row[1],
                content=row[2],
                source=DocumentSource(row[3]),
                status=DocumentStatus(row[4]),
                created_at=datetime.fromisoformat(row[5]),
                updated_at=datetime.fromisoformat(row[6]) if row[6] else None,
                metadata=json.loads(row[7]) if row[7] else None,
                file_path=row[8],
                workflow_id=row[9],
            )
            for row in rows
        ]

    async def update_document(self, document: Document) -> None:
        """更新文档"""
        await self.save_document(document)

    async def delete_document(self, id: str) -> None:
        """删除文档"""
        conn = await self._get_connection()
        await conn.execute("DELETE FROM documents WHERE id = ?", (id,))
        await conn.commit()
        await conn.close()

    # Document Chunk operations (for metadata only)
    async def save_document_chunk(self, chunk: DocumentChunk) -> None:
        """保存文档块（仅元数据）"""
        # 不存储向量，只存储基本元数据
        pass  # ChromaDB管理向量存储

    async def find_chunks_by_document_id(self, document_id: str) -> list[DocumentChunk]:
        """查找指定文档的所有块"""
        return []  # ChromaDB管理向量检索

    async def search_similar_chunks(
        self,
        query_embedding: list[float],
        workflow_id: str | None = None,
        limit: int = 5,
        threshold: float = 0.7,
    ) -> list[tuple[DocumentChunk, float]]:
        """搜索相似文档块"""
        return []  # ChromaDB管理相似度搜索

    async def delete_chunks_by_document_id(self, document_id: str) -> None:
        """删除指定文档的所有块"""
        pass  # ChromaDB管理块删除

    # Statistics
    async def count_documents_by_workflow(self, workflow_id: str) -> int:
        """统计指定工作流的文档数量"""
        conn = await self._get_connection()
        await self._ensure_tables(conn)

        cursor = await conn.execute(
            "SELECT COUNT(*) FROM documents WHERE workflow_id = ?", (workflow_id,)
        )
        result = await cursor.fetchone()
        await conn.close()
        return result[0] if result else 0
