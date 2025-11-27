#!/usr/bin/env python3
"""
离线脚本：文档向量化与导入

功能：
1. 扫描指定目录的文档（支持PDF、Word、Markdown、HTML、TXT等格式）
2. 将文档切分为合理的块
3. 生成向量嵌入
4. 存储到向量数据库

使用方法：
    python scripts/ingest_docs.py --path data/docs --workflow-id wf_xxx
    python scripts/ingest_docs.py --file doc.pdf --workflow-id wf_xxx
    python scripts/ingest_docs.py --url https://example.com --workflow-id wf_xxx
"""

import argparse
import asyncio
import hashlib
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import tiktoken
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
    UnstructuredWordDocumentLoader,
    WebBaseLoader,
)
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.domain.knowledge_base.entities.document import Document
from src.domain.knowledge_base.entities.document_chunk import DocumentChunk
from src.domain.knowledge_base.entities.knowledge_base import KnowledgeBase
from src.domain.value_objects.document_source import DocumentSource
from src.domain.value_objects.knowledge_base_type import KnowledgeBaseType
from src.infrastructure.knowledge_base.sqlite_knowledge_repository import SQLiteKnowledgeRepository

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DocumentIngester:
    """文档导入器"""

    def __init__(
        self,
        db_path: str = "data/knowledge_base.db",
        openai_api_key: str | None = None,
        model_name: str = "text-embedding-3-small",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        """初始化文档导入器

        参数：
            db_path: 数据库路径
            openai_api_key: OpenAI API密钥
            model_name: 嵌入模型名称
            chunk_size: 分块大小
            chunk_overlap: 分块重叠大小
        """
        self.db_path = db_path
        self.model_name = model_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # 初始化组件
        self.repository = SQLiteKnowledgeRepository(db_path)
        self.embeddings = OpenAIEmbeddings(
            model=model_name, openai_api_key=openai_api_key or os.getenv("OPENAI_API_KEY")
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
        self.tokenizer = tiktoken.encoding_for_model(model_name)

        # 确保数据库目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    def _count_tokens(self, text: str) -> int:
        """计算文本的token数量"""
        return len(self.tokenizer.encode(text))

    async def _generate_document_hash(self, content: str) -> str:
        """生成文档内容的哈希值"""
        return hashlib.md5(content.encode()).hexdigest()

    async def _load_document_from_file(self, file_path: str) -> str | None:
        """从文件加载文档内容"""
        try:
            file_ext = Path(file_path).suffix.lower()

            # 根据文件类型选择加载器
            if file_ext == ".pdf":
                loader = PyPDFLoader(file_path)
            elif file_ext in [".doc", ".docx"]:
                loader = UnstructuredWordDocumentLoader(file_path)
            elif file_ext in [".md", ".markdown"]:
                loader = UnstructuredMarkdownLoader(file_path)
            elif file_ext in [".html", ".htm"]:
                loader = UnstructuredHTMLLoader(file_path)
            elif file_ext in [".txt"]:
                loader = TextLoader(file_path, encoding="utf-8")
            else:
                logger.warning(f"Unsupported file type: {file_ext}")
                return None

            # 加载文档
            documents = loader.load()
            if documents:
                # 合并所有页面
                content = "\n\n".join([doc.page_content for doc in documents])
                return content

            return None

        except Exception as e:
            logger.error(f"Failed to load document {file_path}: {str(e)}")
            return None

    async def _load_document_from_url(self, url: str) -> str | None:
        """从URL加载文档内容"""
        try:
            loader = WebBaseLoader([url])
            documents = loader.load()
            if documents:
                return documents[0].page_content
            return None

        except Exception as e:
            logger.error(f"Failed to load document from URL {url}: {str(e)}")
            return None

    async def _chunk_document(self, content: str) -> list[str]:
        """将文档切分为多个块"""
        # 使用token数量来更精确地切分
        chunks = []
        current_chunk = ""
        current_tokens = 0

        lines = content.split("\n")
        for line in lines:
            line_tokens = self._count_tokens(line)

            # 如果当前块为空，直接添加
            if not current_chunk:
                current_chunk = line
                current_tokens = line_tokens
            # 如果添加后不超过限制，添加到当前块
            elif current_tokens + line_tokens + 1 <= self.chunk_size:
                current_chunk += "\n" + line
                current_tokens += line_tokens + 1
            # 否则保存当前块并开始新块
            else:
                chunks.append(current_chunk.strip())
                current_chunk = line
                current_tokens = line_tokens

        # 添加最后一个块
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        # 使用langchain的切分器作为后备
        if not chunks:
            chunks = self.text_splitter.split_text(content)

        logger.info(f"Split document into {len(chunks)} chunks")
        return chunks

    async def _generate_embeddings(self, chunks: list[str]) -> list[list[float]]:
        """生成文本块的向量嵌入"""
        logger.info(f"Generating embeddings for {len(chunks)} chunks...")

        # 批量生成嵌入（OpenAI支持批量处理）
        embeddings = await self.embeddings.aembed_documents(chunks)

        logger.info(f"Generated {len(embeddings)} embeddings")
        return embeddings

    async def ingest_file(self, file_path: str, workflow_id: str | None = None) -> str:
        """导入单个文件"""
        logger.info(f"Ingesting file: {file_path}")

        # 加载文档内容
        content = await self._load_document_from_file(file_path)
        if not content:
            raise ValueError(f"Failed to load document: {file_path}")

        # 生成文档ID和哈希
        doc_id = hashlib.md5(f"{file_path}:{workflow_id}".encode()).hexdigest()
        content_hash = await self._generate_document_hash(content)

        # 检查文档是否已存在
        existing_doc = await self.repository.find_document_by_id(doc_id)
        if existing_doc:
            # 检查内容是否有变化
            existing_hash = (
                existing_doc.metadata.get("content_hash") if existing_doc.metadata else None
            )
            if existing_hash == content_hash:
                logger.info(f"Document {file_path} already exists and unchanged")
                return doc_id

        # 创建文档实体
        document = Document.create(
            title=Path(file_path).name,
            content=content,
            source=DocumentSource.FILESYSTEM,
            file_path=file_path,
            workflow_id=workflow_id,
            metadata={
                "content_hash": content_hash,
                "file_size": os.path.getsize(file_path),
                "ingestion_time": datetime.now().isoformat(),
            },
        )

        # 切分文档
        chunks = await self._chunk_document(content)
        if not chunks:
            raise ValueError(f"Failed to chunk document: {file_path}")

        # 生成嵌入
        embeddings = await self._generate_embeddings(chunks)
        if len(embeddings) != len(chunks):
            raise ValueError(f"Embedding count mismatch: {len(embeddings)} != {len(chunks)}")

        # 保存文档和分块
        await self.repository.save_document(document)

        # 删除旧的分块（如果存在）
        await self.repository.delete_chunks_by_document_id(document.id)

        # 保存新的分块
        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings, strict=False)):
            chunk = DocumentChunk.create(
                document_id=document.id,
                content=chunk_text,
                embedding=embedding,
                chunk_index=i,
                metadata={
                    "token_count": self._count_tokens(chunk_text),
                },
            )
            await self.repository.save_document_chunk(chunk)

        # 更新文档状态
        document.mark_processed()
        await self.repository.update_document(document)

        logger.info(f"Successfully ingested {file_path} with {len(chunks)} chunks")
        return document.id

    async def ingest_url(self, url: str, workflow_id: str | None = None) -> str:
        """导入URL文档"""
        logger.info(f"Ingesting URL: {url}")

        # 加载文档内容
        content = await self._load_document_from_url(url)
        if not content:
            raise ValueError(f"Failed to load document from URL: {url}")

        # 生成文档ID
        doc_id = hashlib.md5(f"url:{url}:{workflow_id}".encode()).hexdigest()
        content_hash = await self._generate_document_hash(content)

        # 检查文档是否已存在
        existing_doc = await self.repository.find_document_by_id(doc_id)
        if existing_doc:
            existing_hash = (
                existing_doc.metadata.get("content_hash") if existing_doc.metadata else None
            )
            if existing_hash == content_hash:
                logger.info(f"URL {url} already exists and unchanged")
                return doc_id

        # 创建文档实体
        document = Document.create(
            title=url,
            content=content,
            source=DocumentSource.URL,
            workflow_id=workflow_id,
            metadata={
                "content_hash": content_hash,
                "ingestion_time": datetime.now().isoformat(),
            },
        )

        # 切分文档、生成嵌入并保存
        chunks = await self._chunk_document(content)
        embeddings = await self._generate_embeddings(chunks)

        await self.repository.save_document(document)
        await self.repository.delete_chunks_by_document_id(document.id)

        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings, strict=False)):
            chunk = DocumentChunk.create(
                document_id=document.id,
                content=chunk_text,
                embedding=embedding,
                chunk_index=i,
                metadata={
                    "token_count": self._count_tokens(chunk_text),
                },
            )
            await self.repository.save_document_chunk(chunk)

        document.mark_processed()
        await self.repository.update_document(document)

        logger.info(f"Successfully ingested URL {url} with {len(chunks)} chunks")
        return document.id

    async def ingest_directory(self, dir_path: str, workflow_id: str | None = None) -> list[str]:
        """导入整个目录"""
        logger.info(f"Ingesting directory: {dir_path}")

        # 支持的文件扩展名
        supported_extensions = {
            ".pdf",
            ".doc",
            ".docx",
            ".md",
            ".markdown",
            ".html",
            ".htm",
            ".txt",
        }

        # 扫描目录
        file_paths = []
        for root, _, files in os.walk(dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                if Path(file_path).suffix.lower() in supported_extensions:
                    file_paths.append(file_path)

        logger.info(f"Found {len(file_paths)} supported files")

        # 批量导入
        doc_ids = []
        for file_path in file_paths:
            try:
                doc_id = await self.ingest_file(file_path, workflow_id)
                doc_ids.append(doc_id)
            except Exception as e:
                logger.error(f"Failed to ingest {file_path}: {str(e)}")
                continue

        logger.info(f"Successfully ingested {len(doc_ids)} files from {dir_path}")
        return doc_ids

    async def create_knowledge_base(
        self,
        name: str,
        description: str,
        kb_type: KnowledgeBaseType = KnowledgeBaseType.WORKFLOW,
        owner_id: str | None = None,
    ) -> str:
        """创建知识库"""
        kb = KnowledgeBase.create(
            name=name,
            description=description,
            type=kb_type,
            owner_id=owner_id,
        )
        await self.repository.save_knowledge_base(kb)
        return kb.id


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Document ingestion script")

    # 输入选项
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--path", help="Directory path to ingest")
    group.add_argument("--file", help="Single file path to ingest")
    group.add_argument("--url", help="URL to ingest")

    # 可选参数
    parser.add_argument("--workflow-id", help="Associated workflow ID")
    parser.add_argument("--db-path", default="data/knowledge_base.db", help="Database path")
    parser.add_argument("--model", default="text-embedding-3-small", help="Embedding model")
    parser.add_argument("--chunk-size", type=int, default=1000, help="Chunk size in tokens")
    parser.add_argument("--chunk-overlap", type=int, default=200, help="Chunk overlap in tokens")

    args = parser.parse_args()

    # 创建导入器
    ingester = DocumentIngester(
        db_path=args.db_path,
        model_name=args.model,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    try:
        # 根据输入类型执行导入
        if args.path:
            doc_ids = await ingester.ingest_directory(args.path, args.workflow_id)
            logger.info(f"Ingested {len(doc_ids)} documents from directory")

        elif args.file:
            doc_id = await ingester.ingest_file(args.file, args.workflow_id)
            logger.info(f"Ingested document with ID: {doc_id}")

        elif args.url:
            doc_id = await ingester.ingest_url(args.url, args.workflow_id)
            logger.info(f"Ingested document with ID: {doc_id}")

    except Exception as e:
        logger.error(f"Ingestion failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
