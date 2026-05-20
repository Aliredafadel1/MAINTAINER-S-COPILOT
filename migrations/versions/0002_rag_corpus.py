"""rag corpus chunks table

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

EMBEDDING_DIM = 768


def upgrade() -> None:
    op.create_table(
        "corpus_chunks",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # GIN index for full-text (sparse) search
    op.execute("""
        ALTER TABLE corpus_chunks
        ADD COLUMN content_tsv TSVECTOR
        GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
    """)
    op.create_index(
        "ix_corpus_chunks_content_tsv",
        "corpus_chunks",
        ["content_tsv"],
        postgresql_using="gin",
    )

    # HNSW index for fast ANN vector search (pgvector >= 0.5)
    op.execute("""
        CREATE INDEX ix_corpus_chunks_embedding
        ON corpus_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    op.create_index(
        "ix_corpus_chunks_source", "corpus_chunks", ["source_type", "source_id"]
    )

    # Resize memories.embedding from 1536 → 768 to match local embedding model
    op.execute("ALTER TABLE memories DROP COLUMN IF EXISTS embedding")
    op.execute(f"ALTER TABLE memories ADD COLUMN embedding vector({EMBEDDING_DIM})")
    op.execute("""
        CREATE INDEX ix_memories_embedding
        ON memories
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memories_embedding")
    op.execute("ALTER TABLE memories DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE memories ADD COLUMN embedding vector(1536)")
    op.drop_table("corpus_chunks")
