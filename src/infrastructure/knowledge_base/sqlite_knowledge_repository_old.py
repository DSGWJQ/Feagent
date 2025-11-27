"""SQLiteKnowledgeRepository - 使用SQLite存储知识库元数据

DDD规则：
- 实现Domain层定义的KnowledgeRepository接口
- 只负责存储元数据（文档、分块等），向量存储由外部向量引擎（如ChromaDB）管理
"""

import json
from datetime import datetime

import aiosqlite
import numpy as np

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
        self._connection: aiosqlite.Connection | None = None

    async def _get_connection(self) -> aiosqlite.Connection:
        """获取或创建数据库连接"""
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.db_path)
            # 启用外键约束
            await self._connection.execute("PRAGMA foreign_keys = ON")
        return self._connection

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._connection:
            await self._connection.close()
            self._connection = None

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

        # 文档分块表
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                content TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL,
                metadata TEXT,
                FOREIGN KEY (document_id) REFERENCES documents(id)
            )
        """)

        # 向量表
        await conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS document_chunk_embeddings
            USING vec0(embedding float[1536], chunk_id TEXT PRIMARY KEY)
        """)

        # 创建索引
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_documents_workflow_id ON documents(workflow_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON document_chunks(document_id)"
        )

    async def save_knowledge_base(self, knowledge_base: KnowledgeBase) -> None:
        """保存知识库"""
        async with await self._get_connection() as conn:
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

    async def find_knowledge_base_by_id(self, id: str) -> KnowledgeBase | None:
        """根据ID查找知识库"""
        async with await self._get_connection() as conn:
            await self._ensure_tables(conn)

            cursor = await conn.execute("SELECT * FROM knowledge_bases WHERE id = ?", (id,))
            row = await cursor.fetchone()

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
        """查找指定所有者的知识库"""
        async with await self._get_connection() as conn:
            await self._ensure_tables(conn)

            cursor = await conn.execute(
                "SELECT * FROM knowledge_bases WHERE owner_id = ?", (owner_id,)
            )
            rows = await cursor.fetchall()

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

    async def find_document_by_id(self, id: str) -> Document | None:
        """根据ID查找文档"""
        async with await self._get_connection() as conn:
            await self._ensure_tables(conn)

            cursor = await conn.execute("SELECT * FROM documents WHERE id = ?", (id,))
            row = await cursor.fetchone()

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
        async with await self._get_connection() as conn:
            await self._ensure_tables(conn)

            cursor = await conn.execute(
                "SELECT * FROM documents WHERE workflow_id = ?", (workflow_id,)
            )
            rows = await cursor.fetchall()

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
        async with await self._get_connection() as conn:
            await self._ensure_tables(conn)

            # 先删除相关的分块和向量
            await conn.execute(
                "DELETE FROM document_chunk_embeddings WHERE chunk_id IN "
                "(SELECT id FROM document_chunks WHERE document_id = ?)",
                (id,),
            )
            await conn.execute("DELETE FROM document_chunks WHERE document_id = ?", (id,))
            await conn.execute("DELETE FROM documents WHERE id = ?", (id,))
            await conn.commit()

    async def save_document_chunk(self, chunk: DocumentChunk) -> None:
        """保存文档分块"""
        async with await self._get_connection() as conn:
            await self._ensure_tables(conn)

            # 保存分块数据
            await conn.execute(
                """
                INSERT OR REPLACE INTO document_chunks
                (id, document_id, content, chunk_index, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.id,
                    chunk.document_id,
                    chunk.content,
                    chunk.chunk_index,
                    chunk.created_at,
                    json.dumps(chunk.metadata) if chunk.metadata else None,
                ),
            )

            # 保存向量
            embedding_array = np.array(chunk.embedding, dtype=np.float32)
            await conn.execute(
                """
                INSERT OR REPLACE INTO document_chunk_embeddings
                (chunk_id, embedding)
                VALUES (?, ?)
                """,
                (chunk.id, embedding_array),
            )

            await conn.commit()

    async def find_chunks_by_document_id(self, document_id: str) -> list[DocumentChunk]:
        """查找指定文档的所有分块"""
        async with await self._get_connection() as conn:
            await self._ensure_tables(conn)

            cursor = await conn.execute(
                """
                SELECT dc.*, dce.embedding
                FROM document_chunks dc
                LEFT JOIN document_chunk_embeddings dce ON dc.id = dce.chunk_id
                WHERE dc.document_id = ?
                ORDER BY dc.chunk_index
                """,
                (document_id,),
            )
            rows = await cursor.fetchall()

            chunks = []
            for row in rows:
                embedding = None
                if row[6]:  # embedding is in the 7th column
                    # Convert bytes back to numpy array and then to list
                    embedding_array = np.frombuffer(row[6], dtype=np.float32)
                    embedding = embedding_array.tolist()

                chunks.append(
                    DocumentChunk(
                        id=row[0],
                        document_id=row[1],
                        content=row[2],
                        embedding=embedding or [],
                        chunk_index=row[3],
                        created_at=datetime.fromisoformat(row[4]),
                        metadata=json.loads(row[5]) if row[5] else None,
                    )
                )

            return chunks

    async def search_similar_chunks(
        self,
        query_embedding: list[float],
        workflow_id: str | None = None,
        limit: int = 5,
        threshold: float = 0.7,
    ) -> list[tuple[DocumentChunk, float]]:
        """搜索相似的文档分块"""
        async with await self._get_connection() as conn:
            await self._ensure_tables(conn)

            query_array = np.array(query_embedding, dtype=np.float32)

            if workflow_id:
                # 限定在特定工作流范围内搜索
                sql = """
                    SELECT dc.*, dce.embedding, distance
                    FROM document_chunk_embeddings dce
                    JOIN document_chunks dc ON dce.chunk_id = dc.id
                    JOIN documents d ON dc.document_id = d.id
                    WHERE d.workflow_id = ?
                    AND dce.embedding MATCH ?
                    ORDER BY distance
                    LIMIT ?
                """
                cursor = await conn.execute(sql, (workflow_id, query_array, limit))
            else:
                # 全局搜索
                sql = """
                    SELECT dc.*, dce.embedding, distance
                    FROM document_chunk_embeddings dce
                    JOIN document_chunks dc ON dce.chunk_id = dc.id
                    WHERE dce.embedding MATCH ?
                    ORDER BY distance
                    LIMIT ?
                """
                cursor = await conn.execute(sql, (query_array, limit))

            rows = await cursor.fetchall()

            results = []
            for row in rows:
                # 距离转换为相似度分数（假设使用余弦距离）
                similarity = 1 - row[7]  # distance is in the 8th column

                if similarity >= threshold:
                    embedding_array = np.frombuffer(row[6], dtype=np.float32)
                    embedding = embedding_array.tolist()

                    chunk = DocumentChunk(
                        id=row[0],
                        document_id=row[1],
                        content=row[2],
                        embedding=embedding,
                        chunk_index=row[3],
                        created_at=datetime.fromisoformat(row[4]),
                        metadata=json.loads(row[5]) if row[5] else None,
                    )

                    results.append((chunk, similarity))

            return results

    async def count_documents_by_workflow(self, workflow_id: str) -> int:
        """统计指定工作流的文档数量"""
        async with await self._get_connection() as conn:
            await self._ensure_tables(conn)

            cursor = await conn.execute(
                "SELECT COUNT(*) FROM documents WHERE workflow_id = ?", (workflow_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def delete_chunks_by_document_id(self, document_id: str) -> None:
        """删除指定文档的所有分块"""
        async with await self._get_connection() as conn:
            await self._ensure_tables(conn)

            # 先删除向量
            await conn.execute(
                "DELETE FROM document_chunk_embeddings WHERE chunk_id IN "
                "(SELECT id FROM document_chunks WHERE document_id = ?)",
                (document_id,),
            )
            # 再删除分块
            await conn.execute("DELETE FROM document_chunks WHERE document_id = ?", (document_id,))
            await conn.commit()
