"""retention of model runs

Revision ID: 363df6bc32e9
Revises: a5896bf9b67d
Create Date: 2026-09-26

"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "363df6bc32e9"
down_revision: str | Sequence[str] | None = "a5896bf9b67d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RETENTION = {"model_runs_days": 90}

PURGE_V1 = """
CREATE OR REPLACE PROCEDURE sp_purge_stale_runs(p_days integer, INOUT p_deleted integer DEFAULT 0)
LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM model_run m
    WHERE m.status <> 'running'
      AND NOT EXISTS (
          SELECT 1 FROM analysis_request a
          WHERE a.model_run_id = m.id AND a.created_at > now() - make_interval(days => p_days)
      );
    GET DIAGNOSTICS p_deleted = ROW_COUNT;
END;
$$;
"""

# Запуск видаляється, якщо ним не користувалися p_days днів (жоден запит за цей час на нього не посилався).
# Старі запити, що посилалися на нього, отримують пояснення — інтерфейс пропонує повторити аналіз
# з тими самими умовами. Групи й оцінки видаляються каскадно, вердикти аудиторів зберігаються
# (прив'язані до позиції).
PURGE_V2 = """
CREATE OR REPLACE PROCEDURE sp_purge_stale_runs(p_days integer, INOUT p_deleted integer DEFAULT 0)
LANGUAGE plpgsql AS $$
BEGIN
    CREATE TEMP TABLE _stale ON COMMIT DROP AS
    SELECT m.id FROM model_run m
    WHERE m.status <> 'running'
      AND COALESCE(m.finished_at, m.started_at) < now() - make_interval(days => p_days)
      AND NOT EXISTS (
          SELECT 1 FROM analysis_request a
          WHERE a.model_run_id = m.id AND a.created_at > now() - make_interval(days => p_days)
      );

    UPDATE analysis_request
    SET message = 'Результат видалено після ' || p_days
        || ' днів зберігання — повторіть аналіз з тими самими умовами'
    WHERE model_run_id IN (SELECT id FROM _stale);

    DELETE FROM model_run WHERE id IN (SELECT id FROM _stale);
    GET DIAGNOSTICS p_deleted = ROW_COUNT;
    DROP TABLE _stale;
END;
$$;
"""


def upgrade() -> None:
    op.execute(PURGE_V2)
    op.execute(
        sa.text(
            "INSERT INTO pipeline_config (key, value, description) VALUES (:k, CAST(:v AS jsonb), :d) "
            "ON CONFLICT (key) DO NOTHING"
        ).bindparams(
            k="retention",
            v=json.dumps(RETENTION),
            d="Термін зберігання результатів аналізу, днів (0 — не видаляти); "
            "очищення виконує worker раз на добу",
        )
    )


def downgrade() -> None:
    op.execute("DELETE FROM pipeline_config WHERE key = 'retention'")
    op.execute(PURGE_V1)
