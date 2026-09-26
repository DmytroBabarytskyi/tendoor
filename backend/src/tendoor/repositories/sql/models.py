"""ORM-моделі рівнів Silver/Gold. Схема змінюється лише через міграції Alembic."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Детерміновані імена обмежень, щоб autogenerate давав стабільні міграції
NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


TS = DateTime(timezone=True)
MONEY = Numeric(16, 2)
PRICE = Numeric(18, 6)


# ---------------------------------------------------------------- довідники


class Unit(Base):
    """Одиниця виміру (код UN/CEFACT) з перерахунком у базову одиницю."""

    __tablename__ = "unit"

    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    base_code: Mapped[str] = mapped_column(ForeignKey("unit.code"))
    factor: Mapped[Decimal] = mapped_column(Numeric(18, 9), default=1)


class Cpv(Base):
    """Код класифікатора ДК 021:2015 (CPV) з ієрархією через parent_code."""

    __tablename__ = "cpv"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    parent_code: Mapped[str | None] = mapped_column(ForeignKey("cpv.code"))
    description: Mapped[str | None] = mapped_column(Text)
    level: Mapped[int] = mapped_column(SmallInteger)


class ProcuringEntity(Base):
    __tablename__ = "procuring_entity"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    edrpou: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(String(80))
    kind: Mapped[str | None] = mapped_column(String(30))


class Supplier(Base):
    __tablename__ = "supplier"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    edrpou: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(Text)


# ---------------------------------------------------------------- закупівлі


class Tender(Base):
    __tablename__ = "tender"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    prozorro_id: Mapped[str] = mapped_column(String(32), unique=True)
    tender_code: Mapped[str] = mapped_column(String(32), index=True)
    procuring_entity_id: Mapped[int] = mapped_column(ForeignKey("procuring_entity.id"), index=True)
    title: Mapped[str | None] = mapped_column(Text)
    method_type: Mapped[str] = mapped_column(String(40))
    category: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(40))
    date_published: Mapped[datetime] = mapped_column(TS, index=True)
    value_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3), default="UAH")
    vat_included: Mapped[bool | None] = mapped_column(Boolean)
    date_modified: Mapped[datetime] = mapped_column(TS)


class Lot(Base):
    __tablename__ = "lot"
    __table_args__ = (UniqueConstraint("tender_id", "prozorro_lot_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tender.id", ondelete="CASCADE"))
    prozorro_lot_id: Mapped[str] = mapped_column(String(32))
    title: Mapped[str | None] = mapped_column(Text)
    value_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    status: Mapped[str | None] = mapped_column(String(30))


class Contract(Base):
    __tablename__ = "contract"
    __table_args__ = (UniqueConstraint("tender_id", "prozorro_contract_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tender.id", ondelete="CASCADE"))
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("lot.id", ondelete="SET NULL"))
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("supplier.id"))
    prozorro_contract_id: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(30))
    amount: Mapped[Decimal | None] = mapped_column(MONEY)
    vat_included: Mapped[bool | None] = mapped_column(Boolean)
    date_signed: Mapped[datetime | None] = mapped_column(TS)


class Item(Base):
    """Номенклатурна позиція — основний об'єкт аналізу цін."""

    __tablename__ = "item"
    __table_args__ = (
        UniqueConstraint("tender_id", "prozorro_item_id"),
        Index("ix_item_analysis", "base_unit_code", "cpv_code"),
        CheckConstraint("price_source IN ('unit_value', 'contract', 'expected')", name="price_source"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tender.id", ondelete="CASCADE"), index=True)
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("lot.id", ondelete="SET NULL"))
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("contract.id", ondelete="SET NULL"))
    prozorro_item_id: Mapped[str] = mapped_column(String(40))
    cpv_code: Mapped[str | None] = mapped_column(ForeignKey("cpv.code"), index=True)
    unit_code: Mapped[str | None] = mapped_column(ForeignKey("unit.code"))
    description: Mapped[str] = mapped_column(Text)
    description_clean: Mapped[str] = mapped_column(Text)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    unit_price: Mapped[Decimal | None] = mapped_column(PRICE)
    price_source: Mapped[str | None] = mapped_column(String(12))
    vat_included: Mapped[bool | None] = mapped_column(Boolean)
    # заповнюються тригером trg_item_normalize через довідник unit
    base_unit_code: Mapped[str | None] = mapped_column(String(8))
    quantity_base: Mapped[Decimal | None] = mapped_column(Numeric(24, 9))
    unit_price_base: Mapped[Decimal | None] = mapped_column(PRICE)


# ---------------------------------------------------------------- синхронізація


class SyncJob(Base):
    """Завдання синхронізації; worker забирає їх через FOR UPDATE SKIP LOCKED."""

    __tablename__ = "sync_job"
    __table_args__ = (CheckConstraint("status IN ('queued', 'running', 'done', 'failed')", name="status"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(10), default="queued", index=True)
    date_from: Mapped[date] = mapped_column(Date)
    date_to: Mapped[date] = mapped_column(Date)
    cpv_prefixes: Mapped[list[str]] = mapped_column(ARRAY(String(10)), default=list)
    categories: Mapped[list[str]] = mapped_column(ARRAY(String(20)), default=list)
    scanned: Mapped[int] = mapped_column(Integer, default=0)
    saved: Mapped[int] = mapped_column(Integer, default=0)
    normalized: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    last_offset: Mapped[str | None] = mapped_column(String(80))
    message: Mapped[str | None] = mapped_column(Text)
    stats: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(TS)
    finished_at: Mapped[datetime | None] = mapped_column(TS)


# ---------------------------------------------------------------- доступ і аудит (A4)


class Role(Base):
    __tablename__ = "role"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(60))


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("role.id"))
    email: Mapped[str] = mapped_column(String(120), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    # збільшується під час виходу/зміни пароля — усі видані refresh-токени стають недійсними
    token_version: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(TS)


class PipelineConfig(Base):
    """Параметри аналізу за замовчуванням (A4.3), значення — JSON."""

    __tablename__ = "pipeline_config"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB)
    description: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())


class AuditLog(Base):
    """Журнал аудиту. Зміни таблиць пише тригер trg_audit, події входу — застосунок."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_entity", "entity", "entity_key"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(30))
    entity: Mapped[str] = mapped_column(String(40))
    entity_key: Mapped[str | None] = mapped_column(String(80))
    payload: Mapped[dict | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), index=True)


# ---------------------------------------------------------------- виявлення аномалій (A2, Gold)


class ModelRun(Base):
    """Навчений запуск конвеєра; cache_key = хеш (вибірка, версія даних, версія конвеєра, параметри)."""

    __tablename__ = "model_run"
    __table_args__ = (CheckConstraint("status IN ('running', 'done', 'failed')", name="status"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(64), unique=True)
    pipeline_version: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(10), server_default="running")
    params: Mapped[dict] = mapped_column(JSONB)
    metrics: Mapped[dict | None] = mapped_column(JSONB)
    artifact_path: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(TS)


class AnalysisRequest(Base):
    """Запит аудитора на аналіз вибірки (A2.1)."""

    __tablename__ = "analysis_request"
    __table_args__ = (CheckConstraint("status IN ('queued', 'running', 'done', 'failed')", name="status"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id", ondelete="SET NULL"), index=True)
    model_run_id: Mapped[int | None] = mapped_column(ForeignKey("model_run.id", ondelete="SET NULL"))
    cpv_prefixes: Mapped[list[str]] = mapped_column(ARRAY(String(10)))
    unit_codes: Mapped[list[str]] = mapped_column(ARRAY(String(8)), server_default="{}")
    date_from: Mapped[date] = mapped_column(Date)
    date_to: Mapped[date] = mapped_column(Date)
    params: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    cache_key: Mapped[str | None] = mapped_column(String(64))
    homogeneity: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    homogeneity_details: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(10), server_default="queued", index=True)
    from_cache: Mapped[bool] = mapped_column(Boolean, server_default="false")
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(TS)


class Category(Base):
    """Однорідна група позицій, сформована конвеєром у межах запуску."""

    __tablename__ = "category"
    __table_args__ = (UniqueConstraint("model_run_id", "label"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    model_run_id: Mapped[int] = mapped_column(ForeignKey("model_run.id", ondelete="CASCADE"))
    label: Mapped[int] = mapped_column(Integer)
    base_unit_code: Mapped[str] = mapped_column(String(8))
    cpv_code: Mapped[str | None] = mapped_column(String(10))
    top_terms: Mapped[list[str]] = mapped_column(ARRAY(Text))
    size: Mapped[int] = mapped_column(Integer)
    median_price: Mapped[Decimal | None] = mapped_column(PRICE)
    analysed: Mapped[bool] = mapped_column(Boolean)
    n_anomalies: Mapped[int] = mapped_column(Integer, server_default="0")
    details: Mapped[dict | None] = mapped_column(JSONB)


class AnomalyResult(Base):
    """Результат оцінки позиції в запуску: мітка аномалії, ризик-бал, координати для візуалізації."""

    __tablename__ = "anomaly_result"
    __table_args__ = (
        UniqueConstraint("model_run_id", "item_id"),
        Index("ix_anomaly_result_queue", "model_run_id", "is_anomaly", "risk_score"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    model_run_id: Mapped[int] = mapped_column(ForeignKey("model_run.id", ondelete="CASCADE"))
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("category.id", ondelete="CASCADE"))
    is_anomaly: Mapped[bool] = mapped_column(Boolean)
    is_extreme: Mapped[bool] = mapped_column(Boolean)
    is_noise: Mapped[bool] = mapped_column(Boolean)
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    robust_z: Mapped[float | None] = mapped_column(Float)
    price_ratio: Mapped[float | None] = mapped_column(Float)
    pc1: Mapped[float | None] = mapped_column(Float)
    pc2: Mapped[float | None] = mapped_column(Float)
    # ціна та одиниця, з якими працювала модель (v2 перераховує фасовку «штук» у грн/кг, грн/л)
    model_price: Mapped[float | None] = mapped_column(Float)
    model_unit: Mapped[str | None] = mapped_column(String(8))
    pack_size: Mapped[float | None] = mapped_column(Float)
    # внески ознак у ризик (значення Шеплі, пункти 0–100) — для підозрілих позицій
    contributions: Mapped[list | None] = mapped_column(JSONB)


# ---------------------------------------------------------------- аудит і звітність (A3)

VERDICT_STATUSES = ("confirmed", "not_anomaly", "needs_review")
VERDICT_REASONS = ("overpriced", "underpriced", "unit_error", "data_error", "justified", "other")


class Verdict(Base):
    """Висновок аудитора щодо ціни позиції. Прив'язаний до позиції, а не до запуску моделі,
    тож зберігається між перенавчаннями й слугує розміткою для оцінювання та донавчання."""

    __tablename__ = "verdict"
    __table_args__ = (
        CheckConstraint(f"status IN {VERDICT_STATUSES}", name="status"),
        CheckConstraint(f"reason IN {VERDICT_REASONS}", name="reason"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id", ondelete="CASCADE"), unique=True)
    anomaly_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("anomaly_result.id", ondelete="SET NULL")
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())


class VerdictHistory(Base):
    """Історія змін вердикту; заповнюється тригером trg_verdict_history."""

    __tablename__ = "verdict_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    verdict_id: Mapped[int] = mapped_column(ForeignKey("verdict.id", ondelete="CASCADE"), index=True)
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id", ondelete="SET NULL"))
    old_status: Mapped[str | None] = mapped_column(String(20))
    new_status: Mapped[str] = mapped_column(String(20))
    old_reason: Mapped[str | None] = mapped_column(String(20))
    new_reason: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())


class Report(Base):
    """Факт формування звіту (A3.2) — для історії перевірок; сам файл генерується на запит."""

    __tablename__ = "report"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    analysis_request_id: Mapped[int] = mapped_column(ForeignKey("analysis_request.id", ondelete="CASCADE"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id", ondelete="SET NULL"))
    format: Mapped[str] = mapped_column(String(10))
    n_rows: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())
