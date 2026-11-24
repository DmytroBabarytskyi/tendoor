"""pipeline v2 model price and defaults

Revision ID: a5896bf9b67d
Revises: 7a683ace3d7d
Create Date: 2026-09-25 21:32:00.447351

"""

import importlib.util
import json
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a5896bf9b67d"
down_revision: str | Sequence[str] | None = "7a683ace3d7d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _sibling(name: str):
    """Попередня міграція як модуль: SQL представлення й параметри не дублюються."""
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_prev = _sibling("20260925_7a683ace3d7d_audit_verdicts_and_reports")
_v1 = _sibling("20260925_1d481cd45923_anomaly_detection_results")

# ціна й одиниця, з якими працювала модель, додаються в кінець (CREATE OR REPLACE VIEW дозволяє лише так)
QUEUE_V3 = _prev._QUEUE_BASE.format(
    extra=", v.id AS verdict_id, v.status AS verdict_status, v.reason AS verdict_reason,"
    " r.model_price, r.model_unit, r.pack_size",
    join=" LEFT JOIN verdict v ON v.item_id = r.item_id",
)

# v2: дрібніший текстовий поділ, нормалізація фасовки, калібратор на розмічених вердиктах
DETECTION_DEFAULTS_V2 = {
    **_v1.DETECTION_DEFAULTS,
    "text_split_min": 30,
    "text_subgroup_min": 5,
    "pack_normalize": True,
    "calibrate": True,
    "anomaly_threshold": None,
}


def _set_defaults(value: dict) -> None:
    op.execute(
        sa.text(
            "UPDATE pipeline_config SET value = CAST(:v AS jsonb) WHERE key = 'detection.defaults'"
        ).bindparams(v=json.dumps(value))
    )


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("anomaly_result", sa.Column("model_price", sa.Float(), nullable=True))
    op.add_column("anomaly_result", sa.Column("model_unit", sa.String(length=8), nullable=True))
    op.add_column("anomaly_result", sa.Column("pack_size", sa.Float(), nullable=True))
    op.execute("CREATE OR REPLACE VIEW v_anomaly_queue AS" + QUEUE_V3)
    _set_defaults(DETECTION_DEFAULTS_V2)


def downgrade() -> None:
    """Downgrade schema."""
    _set_defaults(_v1.DETECTION_DEFAULTS)
    op.execute("DROP VIEW v_anomaly_queue")
    op.execute("CREATE VIEW v_anomaly_queue AS" + _prev.QUEUE_V2)
    op.drop_column("anomaly_result", "pack_size")
    op.drop_column("anomaly_result", "model_unit")
    op.drop_column("anomaly_result", "model_price")
