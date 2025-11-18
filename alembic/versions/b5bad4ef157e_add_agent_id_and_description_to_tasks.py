"""add_agent_id_and_description_to_tasks

Revision ID: b5bad4ef157e
Revises: d8b5f2ee2ca7
Create Date: 2025-11-18 13:06:01.900956

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5bad4ef157e"
down_revision: str | None = "d8b5f2ee2ca7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """添加 agent_id 和 description 字段到 tasks 表

    修改内容：
    1. 添加 agent_id 列（外键，关联 agents.id）
    2. 添加 description 列（Text，可选）
    3. 修改 run_id 为可选（nullable=True）
    4. 添加 idx_tasks_agent_id 索引

    注意：
    - SQLite 不支持 ALTER CONSTRAINT，需要使用 batch_alter_table
    - 使用 batch mode 重建表，一次性完成所有修改
    - 需要指定 copy_from 参数来避免循环依赖错误
    """
    # 使用 batch_alter_table 来兼容 SQLite
    # copy_from 参数指定要复制的表结构，避免循环依赖
    with op.batch_alter_table("tasks", schema=None, copy_from=None) as batch_op:
        # 1. 添加 agent_id 列（必填，外键）
        batch_op.add_column(sa.Column("agent_id", sa.String(length=36), nullable=False))

        # 2. 添加 description 列（可选）
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))

        # 3. 修改 run_id 为可选
        batch_op.alter_column("run_id", existing_type=sa.String(length=36), nullable=True)

        # 4. 创建外键约束（agent_id → agents.id）
        batch_op.create_foreign_key(
            "fk_tasks_agent_id", "agents", ["agent_id"], ["id"], ondelete="CASCADE"
        )

        # 5. 创建索引
        batch_op.create_index("idx_tasks_agent_id", ["agent_id"])


def downgrade() -> None:
    """回滚迁移

    修改内容：
    1. 删除 idx_tasks_agent_id 索引
    2. 删除 agent_id 外键约束
    3. 删除 agent_id 列
    4. 删除 description 列
    5. 修改 run_id 为必填
    """
    # 使用 batch_alter_table 来兼容 SQLite
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        # 1. 删除索引
        batch_op.drop_index("idx_tasks_agent_id")

        # 2. 删除外键约束
        batch_op.drop_constraint("fk_tasks_agent_id", type_="foreignkey")

        # 3. 删除 agent_id 列
        batch_op.drop_column("agent_id")

        # 4. 删除 description 列
        batch_op.drop_column("description")

        # 5. 修改 run_id 为必填
        batch_op.alter_column(
            "run_id", existing_type=sa.String(length=36), nullable=False
        )  # 改为必填
