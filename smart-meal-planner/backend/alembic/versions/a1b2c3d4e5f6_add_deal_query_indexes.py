"""add_deal_query_indexes

Revision ID: a1b2c3d4e5f6
Revises: 76a2bc1106b7
Create Date: 2026-11-11 19:25:00.000000

"""
from typing import Sequence, Union
from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "76a2bc1106b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_store_chain", "store", ["chain"], unique=False, if_not_exists=True)
    op.create_index("ix_store_postal_code", "store", ["postal_code"], unique=False, if_not_exists=True)
    op.create_index("ix_product_name", "product", ["name"], unique=False, if_not_exists=True)
    op.create_index("ix_product_category", "product", ["category"], unique=False, if_not_exists=True)
    op.create_index("ix_deal_product_id", "deal", ["product_id"], unique=False, if_not_exists=True)
    op.create_index("ix_deal_store_id", "deal", ["store_id"], unique=False, if_not_exists=True)
    op.create_index("ix_deal_discount_pct", "deal", ["discount_pct"], unique=False, if_not_exists=True)
    op.create_index("ix_deal_valid_from", "deal", ["valid_from"], unique=False, if_not_exists=True)
    op.create_index("ix_deal_valid_until", "deal", ["valid_until"], unique=False, if_not_exists=True)
    op.create_index("ix_deal_quality_score", "deal", ["quality_score"], unique=False, if_not_exists=True)
    op.create_index(
        "ix_deal_valid_window_discount",
        "deal",
        ["valid_from", "valid_until", "discount_pct"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_deal_store_product_valid",
        "deal",
        ["store_id", "product_id", "valid_until"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_pricerecord_product_store_ts",
        "pricerecord",
        ["product_id", "store_id", "timestamp"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_pricerecord_product_store_ts", table_name="pricerecord", if_exists=True)
    op.drop_index("ix_deal_store_product_valid", table_name="deal", if_exists=True)
    op.drop_index("ix_deal_valid_window_discount", table_name="deal", if_exists=True)
    op.drop_index("ix_deal_quality_score", table_name="deal", if_exists=True)
    op.drop_index("ix_deal_valid_until", table_name="deal", if_exists=True)
    op.drop_index("ix_deal_valid_from", table_name="deal", if_exists=True)
    op.drop_index("ix_deal_discount_pct", table_name="deal", if_exists=True)
    op.drop_index("ix_deal_store_id", table_name="deal", if_exists=True)
    op.drop_index("ix_deal_product_id", table_name="deal", if_exists=True)
    op.drop_index("ix_product_category", table_name="product", if_exists=True)
    op.drop_index("ix_product_name", table_name="product", if_exists=True)
    op.drop_index("ix_store_postal_code", table_name="store", if_exists=True)
    op.drop_index("ix_store_chain", table_name="store", if_exists=True)
