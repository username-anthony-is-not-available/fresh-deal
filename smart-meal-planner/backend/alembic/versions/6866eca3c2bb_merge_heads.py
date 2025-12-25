"""Merge heads

Revision ID: 6866eca3c2bb
Revises: 02f789bc91b5, 12d32e8facce
Create Date: 2025-12-25 00:27:04.247113

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6866eca3c2bb'
down_revision: Union[str, None] = ('02f789bc91b5', '12d32e8facce')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
