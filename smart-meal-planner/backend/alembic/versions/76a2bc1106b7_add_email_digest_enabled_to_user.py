"""Add email_digest_enabled to User

Revision ID: 76a2bc1106b7
Revises: 6c67c7befdaf
Create Date: 2026-03-28 23:14:04.944263

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
import app


# revision identifiers, used by Alembic.
revision: str = '76a2bc1106b7'
down_revision: Union[str, None] = '6c67c7befdaf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('scraperlog', schema=None) as batch_op:
        batch_op.add_column(sa.Column('postal_code', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('screenshot_path', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('html_path', sqlmodel.sql.sqltypes.AutoString(), nullable=True))

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_digest_enabled', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.alter_column('household_size',
               existing_type=sa.INTEGER(),
               type_=app.core.crypto.EncryptedInt(),
               existing_nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('household_size',
               existing_type=app.core.crypto.EncryptedInt(),
               type_=sa.INTEGER(),
               existing_nullable=False)
        batch_op.drop_column('email_digest_enabled')

    with op.batch_alter_table('scraperlog', schema=None) as batch_op:
        batch_op.drop_column('html_path')
        batch_op.drop_column('screenshot_path')
        batch_op.drop_column('postal_code')
