"""audit log is append only

Revision ID: 13cf4b0d8c97
Revises: a921589b9f76
Create Date: 2026-10-04 05:55:12.954382

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '13cf4b0d8c97'
down_revision: Union[str, Sequence[str], None] = 'a921589b9f76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make audit_log append-only: the database itself refuses UPDATE and DELETE."""
    op.execute(
        """
        CREATE TRIGGER audit_log_no_update
        BEFORE UPDATE ON audit_log
        BEGIN
            SELECT RAISE(ABORT, 'audit_log is append-only: updates are not allowed');
        END;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_no_delete
        BEFORE DELETE ON audit_log
        BEGIN
            SELECT RAISE(ABORT, 'audit_log is append-only: deletes are not allowed');
        END;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_delete")
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_update")
