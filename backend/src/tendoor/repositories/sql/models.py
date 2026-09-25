"""ORM-моделі рівнів Silver/Gold. Схема змінюється лише через міграції Alembic."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
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
