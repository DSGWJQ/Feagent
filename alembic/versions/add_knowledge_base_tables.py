"""add knowledge base tables

Revision ID: 73c1a2b4c5d6
Revises: f74c741be529
Create Date: 2025-11-27 16:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "73c1a2b4c5d6"
down_revision: str | None = "f74c741be529"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 创建知识库表
    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_bases_owner_id", "knowledge_bases", ["owner_id"], unique=False)

    # 创建文档表
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("file_path", sa.String(length=1000), nullable=True),
        sa.Column("workflow_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            "workflows.id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_status", "documents", ["status"], unique=False)
    op.create_index("ix_documents_workflow_id", "documents", ["workflow_id"], unique=False)

    # 创建文档分块表
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_id"],
            "documents.id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_chunks_document_id", "document_chunks", ["document_id"], unique=False
    )
    op.create_index(
        "ix_document_chunks_document_chunk",
        "document_chunks",
        ["document_id", "chunk_index"],
        unique=True,
    )

    # 创建向量存储表（使用JSON存储向量，实际部署时会使用sqlite-vec或chroma）
    op.create_table(
        "document_embeddings",
        sa.Column("chunk_id", sa.String(length=36), nullable=False),
        sa.Column("embedding_vector", sa.Text(), nullable=False),  # JSON格式的向量
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            "document_chunks.id",
        ),
        sa.PrimaryKeyConstraint("chunk_id"),
    )
    op.create_index(
        "ix_document_embeddings_model", "document_embeddings", ["model_name"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_document_embeddings_model", table_name="document_embeddings")
    op.drop_table("document_embeddings")
    op.drop_index("ix_document_chunks_document_chunk", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_documents_workflow_id", table_name="documents")
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_knowledge_bases_owner_id", table_name="knowledge_bases")
    op.drop_table("knowledge_bases")
