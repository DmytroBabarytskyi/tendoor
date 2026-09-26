"""review workflow and registration

Revision ID: 77ba87d5f9da
Revises: d0c94827e755
Create Date: 2026-09-26

Життєвий цикл перевірки позиції (A3): в роботі → на погодженні → погоджено / повернено на доопрацювання.
Погоджує інший аудитор (принцип «чотирьох очей», обмеження БД).
Заявки на реєстрацію (A4): очікує → погоджено / відхилено адміністратором.
"""

import importlib.util
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "77ba87d5f9da"
down_revision: str | Sequence[str] | None = "d0c94827e755"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _sibling(name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_verdicts = _sibling("20260925_7a683ace3d7d_audit_verdicts_and_reports")
_contrib = _sibling("20260926_d0c94827e755_decision_contributions")

QUEUE_V5 = _verdicts._QUEUE_BASE.format(
    extra=", v.id AS verdict_id, v.status AS verdict_status, v.reason AS verdict_reason,"
    " r.model_price, r.model_unit, r.pack_size, r.contributions, v.state AS verdict_state",
    join=" LEFT JOIN verdict v ON v.item_id = r.item_id",
)

HISTORY_V2 = """
CREATE OR REPLACE FUNCTION trg_verdict_history() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.status IS NOT DISTINCT FROM OLD.status
       AND NEW.reason IS NOT DISTINCT FROM OLD.reason
       AND NEW.comment IS NOT DISTINCT FROM OLD.comment
       AND NEW.state IS NOT DISTINCT FROM OLD.state THEN
        RETURN NEW;
    END IF;
    INSERT INTO verdict_history (verdict_id, changed_by, old_status, new_status, old_reason, new_reason,
                                 old_state, new_state, comment)
    VALUES (NEW.id,
            coalesce(nullif(current_setting('app.user_id', true), '')::bigint, NEW.user_id),
            CASE WHEN TG_OP = 'UPDATE' THEN OLD.status END, NEW.status,
            CASE WHEN TG_OP = 'UPDATE' THEN OLD.reason END, NEW.reason,
            CASE WHEN TG_OP = 'UPDATE' THEN OLD.state END, NEW.state,
            -- рішення погоджувача записується з його коментарем, решта переходів — з коментарем аудитора
            CASE WHEN NEW.state IN ('approved', 'returned')
                      AND (TG_OP = 'INSERT' OR OLD.state IS DISTINCT FROM NEW.state)
                 THEN NEW.review_comment ELSE NEW.comment END);
    RETURN NEW;
END;
$$;
"""

HISTORY_V1 = """
CREATE OR REPLACE FUNCTION trg_verdict_history() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.status IS NOT DISTINCT FROM OLD.status
       AND NEW.reason IS NOT DISTINCT FROM OLD.reason
       AND NEW.comment IS NOT DISTINCT FROM OLD.comment THEN
        RETURN NEW;
    END IF;
    INSERT INTO verdict_history (verdict_id, changed_by, old_status, new_status, old_reason,
                                 new_reason, comment)
    VALUES (NEW.id,
            coalesce(nullif(current_setting('app.user_id', true), '')::bigint, NEW.user_id),
            CASE WHEN TG_OP = 'UPDATE' THEN OLD.status END, NEW.status,
            CASE WHEN TG_OP = 'UPDATE' THEN OLD.reason END, NEW.reason, NEW.comment);
    RETURN NEW;
END;
$$;
"""


def upgrade() -> None:
    # ---------------- вердикт: стан перевірки й погодження
    op.add_column("verdict", sa.Column("state", sa.String(12), nullable=False, server_default="submitted"))
    op.add_column("verdict", sa.Column("reviewer_id", sa.BigInteger(), nullable=True))
    op.add_column("verdict", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("verdict", sa.Column("review_comment", sa.Text(), nullable=True))
    op.create_foreign_key(
        op.f("fk_verdict_reviewer_id_app_user"),
        "verdict",
        "app_user",
        ["reviewer_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_verdict_state"), "verdict", ["state"])
    op.alter_column("verdict", "status", nullable=True)
    op.alter_column("verdict", "reason", nullable=True)
    op.create_check_constraint(
        op.f("ck_verdict_state"), "verdict", "state IN ('in_progress', 'submitted', 'returned', 'approved')"
    )
    # на погодження й після нього висновок має бути повним
    op.create_check_constraint(
        op.f("ck_verdict_complete"),
        "verdict",
        "state IN ('in_progress', 'returned') OR (status IS NOT NULL AND reason IS NOT NULL)",
    )
    # «чотири очі»: погоджувач не може бути автором висновку
    op.create_check_constraint(
        op.f("ck_verdict_four_eyes"),
        "verdict",
        "reviewer_id IS NULL OR user_id IS NULL OR reviewer_id <> user_id",
    )

    op.add_column("verdict_history", sa.Column("old_state", sa.String(12), nullable=True))
    op.add_column("verdict_history", sa.Column("new_state", sa.String(12), nullable=True))
    op.alter_column("verdict_history", "new_status", nullable=True)
    op.alter_column("verdict_history", "new_reason", nullable=True)
    op.execute(HISTORY_V2)
    op.execute("CREATE OR REPLACE VIEW v_anomaly_queue AS" + QUEUE_V5)

    # ---------------- заявки на реєстрацію
    op.create_table(
        "registration_request",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("email", sa.String(120), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("requested_role", sa.String(20), nullable=False),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column(
            "decided_by", sa.BigInteger(), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column(
            "user_id", sa.BigInteger(), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')", name=op.f("ck_registration_request_status")
        ),
        sa.CheckConstraint(
            "requested_role IN ('analyst', 'auditor')", name=op.f("ck_registration_request_role")
        ),
    )
    # одна заявка в розгляді на email
    op.create_index(
        "uq_registration_request_pending_email",
        "registration_request",
        [sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(op.f("ix_registration_request_status"), "registration_request", ["status"])
    op.execute(
        "CREATE TRIGGER trg_audit AFTER INSERT OR UPDATE OR DELETE ON registration_request "
        "FOR EACH ROW EXECUTE FUNCTION trg_audit()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit ON registration_request")
    op.drop_table("registration_request")

    op.execute("DROP VIEW v_anomaly_queue")
    op.execute("CREATE VIEW v_anomaly_queue AS" + _contrib.QUEUE_V4)
    op.execute(HISTORY_V1)
    op.execute("DELETE FROM verdict_history WHERE new_status IS NULL OR new_reason IS NULL")
    op.alter_column("verdict_history", "new_reason", nullable=False)
    op.alter_column("verdict_history", "new_status", nullable=False)
    op.drop_column("verdict_history", "new_state")
    op.drop_column("verdict_history", "old_state")

    op.drop_constraint(op.f("ck_verdict_four_eyes"), "verdict", type_="check")
    op.drop_constraint(op.f("ck_verdict_complete"), "verdict", type_="check")
    op.drop_constraint(op.f("ck_verdict_state"), "verdict", type_="check")
    op.execute("DELETE FROM verdict WHERE status IS NULL OR reason IS NULL")
    op.alter_column("verdict", "reason", nullable=False)
    op.alter_column("verdict", "status", nullable=False)
    op.drop_index(op.f("ix_verdict_state"), table_name="verdict")
    op.drop_constraint(op.f("fk_verdict_reviewer_id_app_user"), "verdict", type_="foreignkey")
    op.drop_column("verdict", "review_comment")
    op.drop_column("verdict", "reviewed_at")
    op.drop_column("verdict", "reviewer_id")
    op.drop_column("verdict", "state")
