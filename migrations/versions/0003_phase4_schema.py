"""Phase 4 schema — align tables with Phase 4 ORM models.

Changes:
  users        : drop `role`, add `is_admin` bool
  conversations: add `title`, `updated_at`
  messages     : add `tool_calls` JSON
  memories     : add `metadata` JSON; drop source_type/source_id/chunk_index
  widgets      : full restructure (drop old cols, add owner_id/name/config/is_active)
  audit_log    : rename actor_id→user_id, timestamp→created_at; add resource_type/resource_id/details; drop target

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────────────────
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
    )
    # Promote any existing role='admin' rows
    op.execute("UPDATE users SET is_admin = true WHERE role = 'admin'")
    op.drop_column("users", "role")

    # ── conversations ──────────────────────────────────────────────────────────
    op.add_column("conversations", sa.Column("title", sa.String(255), nullable=True))
    op.add_column(
        "conversations",
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ── messages ───────────────────────────────────────────────────────────────
    op.add_column("messages", sa.Column("tool_calls", sa.JSON(), nullable=True))

    # ── memories ───────────────────────────────────────────────────────────────
    op.add_column(
        "memories",
        sa.Column(
            "metadata",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.drop_column("memories", "source_type")
    op.drop_column("memories", "source_id")
    op.drop_column("memories", "chunk_index")

    # ── widgets — full restructure ─────────────────────────────────────────────
    op.drop_column("widgets", "widget_id")
    op.drop_column("widgets", "theme")
    op.drop_column("widgets", "greeting")
    op.drop_column("widgets", "enabled_tools")
    op.add_column(
        "widgets",
        sa.Column(
            "owner_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,  # nullable so existing rows don't violate constraint
        ),
    )
    op.add_column("widgets", sa.Column("name", sa.String(255), nullable=True))
    op.add_column(
        "widgets",
        sa.Column(
            "config",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.add_column(
        "widgets",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.create_index("ix_widgets_owner_id", "widgets", ["owner_id"])

    # ── audit_log ──────────────────────────────────────────────────────────────
    # Add new columns first (nullable/with defaults so existing rows are ok)
    op.add_column(
        "audit_log",
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("audit_log", sa.Column("resource_type", sa.String(50), nullable=True))
    op.add_column("audit_log", sa.Column("resource_id", sa.String(255), nullable=True))
    op.add_column(
        "audit_log",
        sa.Column(
            "details",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.add_column(
        "audit_log",
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # Copy actor_id → user_id
    op.execute("UPDATE audit_log SET user_id = actor_id")
    # Drop old columns
    op.drop_column("audit_log", "actor_id")
    op.drop_column("audit_log", "target")
    op.drop_column("audit_log", "timestamp")


def downgrade() -> None:
    # audit_log
    op.add_column("audit_log", sa.Column("actor_id", sa.UUID(), nullable=True))
    op.add_column("audit_log", sa.Column("target", sa.String(255), nullable=True))
    op.add_column(
        "audit_log",
        sa.Column(
            "timestamp",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.execute("UPDATE audit_log SET actor_id = user_id")
    op.drop_column("audit_log", "user_id")
    op.drop_column("audit_log", "resource_type")
    op.drop_column("audit_log", "resource_id")
    op.drop_column("audit_log", "details")
    op.drop_column("audit_log", "created_at")

    # widgets
    op.drop_column("widgets", "owner_id")
    op.drop_column("widgets", "name")
    op.drop_column("widgets", "config")
    op.drop_column("widgets", "is_active")
    op.add_column("widgets", sa.Column("widget_id", sa.String(255), nullable=True))
    op.add_column(
        "widgets",
        sa.Column(
            "theme", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False
        ),
    )
    op.add_column("widgets", sa.Column("greeting", sa.Text(), nullable=True))
    op.add_column(
        "widgets", sa.Column("enabled_tools", sa.ARRAY(sa.Text()), nullable=True)
    )

    # memories
    op.drop_column("memories", "metadata")
    op.add_column("memories", sa.Column("source_type", sa.String(50), nullable=True))
    op.add_column("memories", sa.Column("source_id", sa.String(255), nullable=True))
    op.add_column("memories", sa.Column("chunk_index", sa.Integer(), nullable=True))

    # messages
    op.drop_column("messages", "tool_calls")

    # conversations
    op.drop_column("conversations", "title")
    op.drop_column("conversations", "updated_at")

    # users
    op.add_column(
        "users", sa.Column("role", sa.String(50), server_default="user", nullable=False)
    )
    op.execute("UPDATE users SET role = 'admin' WHERE is_admin = true")
    op.drop_column("users", "is_admin")
