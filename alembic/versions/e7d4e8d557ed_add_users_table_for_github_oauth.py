"""Add users table for GitHub OAuth

Revision ID: e7d4e8d557ed
Revises: 73c1a2b4c5d6
Create Date: 2025-11-27 22:05:21.791280

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7d4e8d557ed"
down_revision: str | None = "73c1a2b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the users table and wire tool/workflow ownership."""

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False, comment="User ID (UUID)"),
        sa.Column("github_id", sa.Integer(), nullable=False, comment="GitHub 用户 ID"),
        sa.Column(
            "github_username",
            sa.String(length=255),
            nullable=False,
            comment="GitHub 用户名",
        ),
        sa.Column(
            "github_avatar_url",
            sa.Text(),
            nullable=True,
            comment="GitHub 头像 URL",
        ),
        sa.Column(
            "github_profile_url",
            sa.Text(),
            nullable=True,
            comment="GitHub 个人主页",
        ),
        sa.Column("email", sa.String(length=255), nullable=False, comment="用户邮箱"),
        sa.Column("name", sa.String(length=255), nullable=True, comment="用户姓名"),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.sql.expression.true(),
            comment="是否激活",
        ),
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
            server_default="user",
            comment="用户角色（user/admin）",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=True, comment="更新时间"),
        sa.Column("last_login_at", sa.DateTime(), nullable=True, comment="最后登录时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("github_id"),
    )
    op.create_index("idx_users_created_at", "users", ["created_at"], unique=False)
    op.create_index("idx_users_email", "users", ["email"], unique=True)
    op.create_index("idx_users_github_id", "users", ["github_id"], unique=True)

    with op.batch_alter_table("tools") as batch_op:
        batch_op.add_column(
            sa.Column("user_id", sa.String(length=36), nullable=True, comment="创建者 ID")
        )
        batch_op.create_foreign_key(
            "fk_tools_user_id", "users", ["user_id"], ["id"], ondelete="SET NULL"
        )

    with op.batch_alter_table("workflows") as batch_op:
        batch_op.add_column(
            sa.Column("user_id", sa.String(length=36), nullable=True, comment="创建者 ID")
        )
        batch_op.create_foreign_key(
            "fk_workflows_user_id", "users", ["user_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    """Drop user relationships and the users table."""

    with op.batch_alter_table("workflows") as batch_op:
        batch_op.drop_constraint("fk_workflows_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("tools") as batch_op:
        batch_op.drop_constraint("fk_tools_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")

    op.drop_index("idx_users_github_id", table_name="users")
    op.drop_index("idx_users_email", table_name="users")
    op.drop_index("idx_users_created_at", table_name="users")
    op.drop_table("users")
