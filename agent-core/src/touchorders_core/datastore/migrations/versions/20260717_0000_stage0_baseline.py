"""Stage 0 Alembic baseline.

Revision ID: 20260717_0000
Revises:
Create Date: 2026-07-17 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence


revision: str = "20260717_0000"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Record the baseline; schema ownership starts in Stage 1."""


def downgrade() -> None:
    """The baseline contains no application schema to remove."""
