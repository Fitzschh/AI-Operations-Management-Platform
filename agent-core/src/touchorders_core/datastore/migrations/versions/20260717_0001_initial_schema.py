"""Create the Stage 1 persistence schema.

Revision ID: 20260717_0001
Revises: 20260717_0000
Create Date: 2026-07-17 00:01:00
"""

from __future__ import annotations

from alembic import op

from touchorders_core.datastore.orm import Base


revision: str = "20260717_0001"
down_revision: str | None = "20260717_0000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
