"""decision contributions

Revision ID: d0c94827e755
Revises: 363df6bc32e9
Create Date: 2026-09-26

"""

import importlib.util
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d0c94827e755"
down_revision: str | Sequence[str] | None = "363df6bc32e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _sibling(name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_verdicts = _sibling("20260925_7a683ace3d7d_audit_verdicts_and_reports")
_v2 = _sibling("20260925_a5896bf9b67d_pipeline_v2_model_price_and_defaults")

# внески ознак у ризик додаються в кінець представлення (CREATE OR REPLACE VIEW дозволяє лише так)
QUEUE_V4 = _verdicts._QUEUE_BASE.format(
    extra=", v.id AS verdict_id, v.status AS verdict_status, v.reason AS verdict_reason,"
    " r.model_price, r.model_unit, r.pack_size, r.contributions",
    join=" LEFT JOIN verdict v ON v.item_id = r.item_id",
)


def upgrade() -> None:
    op.add_column(
        "anomaly_result", sa.Column("contributions", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.execute("CREATE OR REPLACE VIEW v_anomaly_queue AS" + QUEUE_V4)


def downgrade() -> None:
    op.execute("DROP VIEW v_anomaly_queue")
    op.execute("CREATE VIEW v_anomaly_queue AS" + _v2.QUEUE_V3)
    op.drop_column("anomaly_result", "contributions")
