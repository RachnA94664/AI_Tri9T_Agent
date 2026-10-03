"""SQLAlchemy models = the database schema.

Every rule that can be enforced by the database is enforced here (primary
keys, foreign keys, CHECK constraints), as a second line of defence behind the
domain and service layers.
"""

from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain import enums


def _in(column: str, values: tuple[str, ...]) -> str:
    """Build `column IN ('a','b')` for a CHECK constraint."""
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Requirement(Base):
    __tablename__ = "requirements"
    __table_args__ = (
        CheckConstraint(f"id GLOB '{enums.REQ_ID_GLOB}'", name="ck_requirements_id_format"),
        CheckConstraint(_in("priority", enums.PRIORITIES), name="ck_requirements_priority"),
        CheckConstraint(_in("status", enums.REQUIREMENT_STATUSES), name="ck_requirements_status"),
        CheckConstraint("length(trim(title)) > 0", name="ck_requirements_title_not_blank"),
    )

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    version: Mapped[int] = mapped_column(Integer, default=1)  # optimistic locking
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    test_cases: Mapped[list["TestCase"]] = relationship(back_populates="requirement")
    risk_links: Mapped[list["RequirementRisk"]] = relationship(back_populates="requirement")


class TestCase(Base):
    __tablename__ = "test_cases"
    __test__ = False  # stop pytest treating this class as a test class
    __table_args__ = (
        CheckConstraint(f"id GLOB '{enums.TC_ID_GLOB}'", name="ck_test_cases_id_format"),
        CheckConstraint(_in("status", enums.TEST_STATUSES), name="ck_test_cases_status"),
        CheckConstraint("length(trim(title)) > 0", name="ck_test_cases_title_not_blank"),
        Index("ix_test_cases_requirement_id", "requirement_id"),
    )

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    requirement_id: Mapped[str] = mapped_column(ForeignKey("requirements.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(200))
    steps: Mapped[str] = mapped_column(Text, default="")
    expected_result: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="not_run")

    requirement: Mapped[Requirement] = relationship(back_populates="test_cases")


class RiskItem(Base):
    """Risk score and level are NOT stored: they are derived in the domain layer."""

    __tablename__ = "risk_items"
    __table_args__ = (
        CheckConstraint(f"id GLOB '{enums.RISK_ID_GLOB}'", name="ck_risk_items_id_format"),
        CheckConstraint("severity BETWEEN 1 AND 5", name="ck_risk_items_severity"),
        CheckConstraint("likelihood BETWEEN 1 AND 5", name="ck_risk_items_likelihood"),
        CheckConstraint(_in("status", enums.RISK_STATUSES), name="ck_risk_items_status"),
        CheckConstraint("length(trim(title)) > 0", name="ck_risk_items_title_not_blank"),
    )

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[int] = mapped_column(Integer)
    likelihood: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="open")

    requirement_links: Mapped[list["RequirementRisk"]] = relationship(back_populates="risk")


class RequirementRisk(Base):
    """Many-to-many join table between requirements and risk items."""

    __tablename__ = "requirement_risks"
    __table_args__ = (Index("ix_requirement_risks_risk_id", "risk_id"),)

    requirement_id: Mapped[str] = mapped_column(
        ForeignKey("requirements.id", ondelete="RESTRICT"), primary_key=True
    )
    risk_id: Mapped[str] = mapped_column(
        ForeignKey("risk_items.id", ondelete="RESTRICT"), primary_key=True
    )

    requirement: Mapped[Requirement] = relationship(back_populates="risk_links")
    risk: Mapped[RiskItem] = relationship(back_populates="requirement_links")


class AuditLog(Base):
    """Append-only history of every modification (triggers added in Phase 4)."""

    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(_in("source", enums.AUDIT_SOURCES), name="ck_audit_log_source"),
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    actor: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(16))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(32))
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON text
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON text
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class PendingChange(Base):
    """A proposed update waiting for a human to confirm or reject it."""

    __tablename__ = "pending_changes"
    __table_args__ = (
        CheckConstraint(_in("status", enums.PENDING_STATUSES), name="ck_pending_changes_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(32))
    proposed_patch: Mapped[str] = mapped_column(Text)  # JSON text
    base_version: Mapped[int] = mapped_column(Integer)
    proposed_by: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
