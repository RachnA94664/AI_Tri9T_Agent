"""Turn database objects into plain dictionaries (safe to return from the API or agents)."""

import json

from app.db import models
from app.domain.risk import risk_level, risk_score


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def requirement_to_dict(req: models.Requirement) -> dict:
    return {
        "id": req.id,
        "title": req.title,
        "description": req.description,
        "priority": req.priority,
        "status": req.status,
        "version": req.version,
        "created_at": _iso(req.created_at),
        "updated_at": _iso(req.updated_at),
    }


def testcase_to_dict(tc: models.TestCase) -> dict:
    return {
        "id": tc.id,
        "requirement_id": tc.requirement_id,
        "title": tc.title,
        "steps": tc.steps,
        "expected_result": tc.expected_result,
        "status": tc.status,
    }


def risk_to_dict(risk: models.RiskItem) -> dict:
    score = risk_score(risk.severity, risk.likelihood)
    return {
        "id": risk.id,
        "title": risk.title,
        "description": risk.description,
        "severity": risk.severity,
        "likelihood": risk.likelihood,
        "status": risk.status,
        "score": score,  # derived, never stored
        "level": risk_level(score),  # derived, never stored
    }


def change_to_dict(change: models.PendingChange) -> dict:
    return {
        "id": change.id,
        "entity_type": change.entity_type,
        "entity_id": change.entity_id,
        "patch": json.loads(change.proposed_patch),
        "base_version": change.base_version,
        "proposed_by": change.proposed_by,
        "status": change.status,
        "created_at": _iso(change.created_at),
        "resolved_at": _iso(change.resolved_at),
    }


def audit_to_dict(entry: models.AuditLog) -> dict:
    return {
        "id": entry.id,
        "ts": _iso(entry.ts),
        "actor": entry.actor,
        "source": entry.source,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "action": entry.action,
        "old_value": json.loads(entry.old_value) if entry.old_value else None,
        "new_value": json.loads(entry.new_value) if entry.new_value else None,
        "request_id": entry.request_id,
    }
