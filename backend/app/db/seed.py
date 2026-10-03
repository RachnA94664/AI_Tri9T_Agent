"""Load and VALIDATE seed data before inserting it.

Generated data (from an LLM or a script) is never trusted. Every row is checked
against the same rules the database enforces; bad rows are reported and skipped.

Run:  python -m app.db.seed [--file PATH] [--if-empty]
"""

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models
from app.db.session import SessionLocal
from app.domain import enums
from app.domain.ids import is_valid_id

DEFAULT_FILE = Path(__file__).resolve().parents[2] / "data" / "seed_raw.json"


def _one_of(value: str, allowed: tuple[str, ...], name: str) -> str:
    if value not in allowed:
        raise ValueError(f"{name} must be one of {allowed}, got {value!r}")
    return value


def _not_blank(value: str, name: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


class RequirementRow(BaseModel):
    id: str
    title: str
    description: str = ""
    priority: str
    status: str

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not is_valid_id("requirement", v):
            raise ValueError(f"id must look like REQ-001, got {v!r}")
        return v

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        return _not_blank(v, "title")

    @field_validator("priority")
    @classmethod
    def _priority(cls, v: str) -> str:
        return _one_of(v, enums.PRIORITIES, "priority")

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        return _one_of(v, enums.REQUIREMENT_STATUSES, "status")


class TestCaseRow(BaseModel):
    __test__ = False  # not a pytest test class
    id: str
    requirement_id: str
    title: str
    steps: str = ""
    expected_result: str = ""
    status: str

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not is_valid_id("test_case", v):
            raise ValueError(f"id must look like TC-001, got {v!r}")
        return v

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        return _not_blank(v, "title")

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        return _one_of(v, enums.TEST_STATUSES, "status")


class RiskRow(BaseModel):
    id: str
    title: str
    description: str = ""
    severity: int
    likelihood: int
    status: str

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not is_valid_id("risk", v):
            raise ValueError(f"id must look like RISK-001, got {v!r}")
        return v

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        return _not_blank(v, "title")

    @field_validator("severity", "likelihood")
    @classmethod
    def _range(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError(f"must be between 1 and 5, got {v}")
        return v

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        return _one_of(v, enums.RISK_STATUSES, "status")


class LinkRow(BaseModel):
    requirement_id: str
    risk_id: str


@dataclass
class SeedReport:
    inserted: dict[str, int] = field(default_factory=dict)
    rejected: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"inserted {n} {name}" for name, n in self.inserted.items()]
        lines += [f"REJECTED {r}" for r in self.rejected]
        return "\n".join(lines)


def _validate_rows(
    rows: list[dict[str, Any]], model: type[BaseModel], label: str, report: SeedReport
) -> list[BaseModel]:
    """Validate each row, never raising: bad rows go into the report."""
    good: list[BaseModel] = []
    for i, raw in enumerate(rows):
        # Ignore helper keys such as "_reason" used in the invalid-example file.
        data = {k: v for k, v in raw.items() if not k.startswith("_")}
        try:
            good.append(model(**data))
        except ValidationError as exc:
            reason = "; ".join(e["msg"] for e in exc.errors())
            report.rejected.append(f"{label}[{i}] {data.get('id', data)}: {reason}")
    return good


def _drop_duplicates(
    items: list[Any], label: str, report: SeedReport, existing: set[str]
) -> list[Any]:
    """Reject IDs repeated in the file OR already present in the database."""
    seen: set[str] = set(existing)
    unique = []
    for item in items:
        if item.id in seen:
            report.rejected.append(f"{label} {item.id}: duplicate ID")
            continue
        seen.add(item.id)
        unique.append(item)
    return unique


def load_seed(session: Session, data: dict[str, Any]) -> SeedReport:
    """Validate then insert, all in ONE transaction (all or nothing for the inserts)."""
    report = SeedReport()
    existing_req = set(session.scalars(select(models.Requirement.id)))
    existing_risk = set(session.scalars(select(models.RiskItem.id)))
    existing_tc = set(session.scalars(select(models.TestCase.id)))
    existing_links = {
        (r, k)
        for r, k in session.execute(
            select(models.RequirementRisk.requirement_id, models.RequirementRisk.risk_id)
        )
    }

    reqs = _drop_duplicates(
        _validate_rows(data.get("requirements", []), RequirementRow, "requirements", report),
        "requirements",
        report,
        existing_req,
    )
    risks = _drop_duplicates(
        _validate_rows(data.get("risk_items", []), RiskRow, "risk_items", report),
        "risk_items",
        report,
        existing_risk,
    )
    tcs = _drop_duplicates(
        _validate_rows(data.get("test_cases", []), TestCaseRow, "test_cases", report),
        "test_cases",
        report,
        existing_tc,
    )
    links = _validate_rows(data.get("requirement_risks", []), LinkRow, "requirement_risks", report)

    # A link or test case may point at a record that is new OR already stored.
    req_ids = {r.id for r in reqs} | existing_req
    risk_ids = {r.id for r in risks} | existing_risk

    valid_tcs = []
    for t in tcs:
        if t.requirement_id not in req_ids:
            report.rejected.append(f"test_cases {t.id}: unknown requirement {t.requirement_id}")
        else:
            valid_tcs.append(t)

    valid_links, seen_links = [], set(existing_links)
    for link in links:
        key = (link.requirement_id, link.risk_id)
        if link.requirement_id not in req_ids:
            report.rejected.append(f"requirement_risks {key}: unknown requirement")
        elif link.risk_id not in risk_ids:
            report.rejected.append(f"requirement_risks {key}: unknown risk")
        elif key in seen_links:
            report.rejected.append(f"requirement_risks {key}: duplicate link")
        else:
            seen_links.add(key)
            valid_links.append(link)

    # Insert parents first so foreign keys are satisfied.
    session.add_all(models.Requirement(**r.model_dump()) for r in reqs)
    session.add_all(models.RiskItem(**r.model_dump()) for r in risks)
    session.flush()
    session.add_all(models.TestCase(**t.model_dump()) for t in valid_tcs)
    session.add_all(models.RequirementRisk(**link.model_dump()) for link in valid_links)
    session.commit()

    report.inserted = {
        "requirements": len(reqs),
        "test_cases": len(valid_tcs),
        "risk_items": len(risks),
        "requirement_risks": len(valid_links),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and load seed data.")
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE)
    parser.add_argument(
        "--if-empty", action="store_true", help="skip if requirements already exist"
    )
    args = parser.parse_args()

    data = json.loads(args.file.read_text(encoding="utf-8"))
    with SessionLocal() as session:
        if args.if_empty and session.scalar(select(func.count()).select_from(models.Requirement)):
            print("database already has data; skipping seed")
            return
        print(load_seed(session, data).summary())


if __name__ == "__main__":
    main()
