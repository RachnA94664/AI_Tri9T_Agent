"""Generates seed_raw.json (valid data) and seed_invalid_examples.json (rows the validator must reject).

Domain: firmware/software for an EV charging station.
Run: python gen_seed.py
"""
import json
from pathlib import Path

OUT = Path(__file__).parent

REQUIREMENTS = [  # id, title, description, priority, status
    ("REQ-001", "Start charging session on authenticated connection", "The station shall start a charging session only after the vehicle is connected and the user is authenticated.", "critical", "verified"),
    ("REQ-002", "Stop charging on emergency stop", "Pressing the emergency stop shall cut power to the connector within 100 ms.", "critical", "verified"),
    ("REQ-003", "Detect ground fault", "The station shall detect ground fault current above 20 mA DC and open the contactor.", "critical", "implemented"),
    ("REQ-004", "Over-temperature derating", "If connector temperature exceeds 85 C the charging current shall be reduced by 50 percent.", "high", "implemented"),
    ("REQ-005", "RFID card authentication", "The station shall authenticate users via ISO 14443 RFID cards within 2 seconds.", "high", "verified"),
    ("REQ-006", "Display charging status", "The display shall show state of charge, power in kW and elapsed time, refreshed every second.", "medium", "implemented"),
    ("REQ-007", "Backend connectivity via OCPP 1.6", "The station shall communicate with the central backend using OCPP 1.6 JSON over WebSocket.", "high", "approved"),
    ("REQ-008", "Offline charging fallback", "If backend connectivity is lost, the station shall continue authorised sessions for up to 24 hours.", "high", "approved"),
    ("REQ-009", "Energy metering accuracy", "Energy measurement shall be accurate to within 1 percent of the delivered kWh.", "critical", "implemented"),
    ("REQ-010", "Firmware over-the-air update", "The station shall support signed firmware updates over the air with rollback on failure.", "high", "approved"),
    ("REQ-011", "Audit log of sessions", "Every charging session shall be recorded with start, stop, energy and user identifier.", "medium", "implemented"),
    ("REQ-012", "Load management across stations", "Total site current shall not exceed the configured grid limit by dynamically sharing power.", "high", "approved"),
    ("REQ-013", "User app remote start", "Users shall be able to start a session remotely from a mobile app.", "medium", "draft"),
    ("REQ-014", "Tamper detection", "The station shall raise an alarm when the enclosure is opened without authorisation.", "high", "draft"),
    ("REQ-015", "Legacy payment terminal support", "The station shall support the legacy serial payment terminal.", "low", "obsolete"),
]

TEST_CASES = [  # id, requirement_id, title, steps, expected_result, status
    ("TC-001", "REQ-001", "Charge with valid card and connected vehicle", "1. Connect vehicle. 2. Present valid RFID card.", "Session starts and power is delivered.", "pass"),
    ("TC-002", "REQ-001", "Reject start without authentication", "1. Connect vehicle. 2. Do not present card.", "No power delivered; display asks for card.", "pass"),
    ("TC-003", "REQ-001", "Reject start without vehicle", "1. Present valid card with no vehicle connected.", "Session does not start.", "pass"),
    ("TC-004", "REQ-002", "Emergency stop during charging", "1. Start session at full current. 2. Press emergency stop.", "Power cut within 100 ms.", "pass"),
    ("TC-005", "REQ-002", "Emergency stop latch", "1. Press emergency stop. 2. Release it.", "Station stays locked until manual reset.", "pass"),
    ("TC-006", "REQ-003", "Inject 30 mA DC fault", "1. Start session. 2. Inject 30 mA DC leakage.", "Contactor opens and fault code E03 is shown.", "pass"),
    ("TC-007", "REQ-003", "Inject 10 mA DC below threshold", "1. Start session. 2. Inject 10 mA DC.", "Session continues normally.", "pass"),
    ("TC-008", "REQ-004", "Derate at 90 C connector temperature", "1. Charge at 32 A. 2. Heat connector to 90 C.", "Current reduced to 16 A.", "fail"),
    ("TC-009", "REQ-004", "No derating at 70 C", "1. Charge at 32 A. 2. Hold connector at 70 C.", "Current stays at 32 A.", "pass"),
    ("TC-010", "REQ-005", "Card read time", "1. Present valid card. 2. Measure response.", "Authenticated in under 2 seconds.", "pass"),
    ("TC-011", "REQ-005", "Unknown card rejected", "1. Present unregistered card.", "Authentication denied.", "pass"),
    ("TC-012", "REQ-006", "Display update rate", "1. Start session. 2. Observe display for 10 s.", "Values refresh every second.", "pass"),
    ("TC-013", "REQ-006", "Display during fault", "1. Trigger ground fault.", "Display shows fault instead of charge values.", "not_run"),
    ("TC-014", "REQ-007", "OCPP boot notification", "1. Power on station with backend reachable.", "BootNotification accepted by backend.", "pass"),
    ("TC-015", "REQ-007", "OCPP heartbeat", "1. Wait for configured heartbeat interval.", "Heartbeat received by backend.", "pass"),
    ("TC-016", "REQ-007", "OCPP reconnect after drop", "1. Drop WebSocket. 2. Restore.", "Station reconnects within 60 s.", "blocked"),
    ("TC-017", "REQ-008", "Offline session within 24 h", "1. Disconnect backend. 2. Start authorised session.", "Session works and is queued for upload.", "not_run"),
    ("TC-018", "REQ-008", "Offline session after 24 h", "1. Disconnect backend for 25 h. 2. Try to start.", "New sessions are refused.", "not_run"),
    ("TC-019", "REQ-009", "Meter accuracy at 7 kW", "1. Charge at 7 kW against reference meter.", "Deviation below 1 percent.", "pass"),
    ("TC-020", "REQ-009", "Meter accuracy at 22 kW", "1. Charge at 22 kW against reference meter.", "Deviation below 1 percent.", "pass"),
    ("TC-021", "REQ-009", "Meter accuracy at low current", "1. Charge at 6 A against reference meter.", "Deviation below 1 percent.", "fail"),
    ("TC-022", "REQ-010", "Valid signed firmware update", "1. Push signed firmware package.", "Station updates and reports new version.", "pass"),
    ("TC-023", "REQ-010", "Unsigned firmware rejected", "1. Push unsigned package.", "Update rejected, version unchanged.", "pass"),
    ("TC-024", "REQ-010", "Rollback on failed update", "1. Push package that fails on boot.", "Station rolls back to previous version.", "not_run"),
    ("TC-025", "REQ-011", "Session record created", "1. Complete a session.", "Record exists with start, stop, kWh and user ID.", "pass"),
    ("TC-026", "REQ-011", "Records survive reboot", "1. Complete session. 2. Reboot station.", "Record still available.", "pass"),
    ("TC-027", "REQ-001", "Session start timing", "1. Connect and authenticate. 2. Measure time to power.", "Power within 5 seconds.", "pass"),
    ("TC-028", "REQ-003", "Fault after reset", "1. Trigger fault. 2. Reset. 3. Start session.", "Station charges normally after clearing fault.", "pass"),
    ("TC-029", "REQ-002", "Emergency stop when idle", "1. Press emergency stop with no session.", "Station enters locked state.", "pass"),
    ("TC-030", "REQ-009", "Meter data retention", "1. Record energy. 2. Power cycle.", "Total energy register is unchanged.", "pass"),
]

RISKS = [  # id, title, description, severity, likelihood, status
    ("RISK-001", "Electric shock from ground fault", "Undetected leakage current could injure users.", 5, 2, "mitigated"),
    ("RISK-002", "Fire from connector overheating", "Poor contact or derating failure could overheat the connector.", 5, 3, "open"),
    ("RISK-003", "Inaccurate billing", "Meter error causes customers to be over or under charged.", 4, 3, "open"),
    ("RISK-004", "Unauthorised charging", "Weak authentication allows free or fraudulent sessions.", 3, 3, "open"),
    ("RISK-005", "Malicious firmware", "An attacker installs unsigned firmware to take over the station.", 5, 2, "mitigated"),
    ("RISK-006", "Backend outage blocks all charging", "Station refuses sessions when the backend is unreachable.", 3, 4, "open"),
    ("RISK-007", "Grid overload at site", "Several stations draw more than the grid connection allows.", 4, 2, "open"),
    ("RISK-008", "Emergency stop failure", "Contactor welds closed and power is not cut.", 5, 1, "mitigated"),
    ("RISK-009", "Loss of session records", "Records lost on reboot cause disputes and compliance issues.", 3, 2, "mitigated"),
    ("RISK-010", "Vandalism or tampering", "Opened enclosure exposes live parts.", 4, 2, "open"),
    ("RISK-011", "Misleading display", "Wrong values shown cause user confusion.", 2, 3, "accepted"),
    ("RISK-012", "Obsolete terminal security hole", "Legacy serial terminal has known vulnerabilities.", 2, 2, "closed"),
]

LINKS = [  # requirement_id, risk_id
    ("REQ-001", "RISK-004"), ("REQ-002", "RISK-008"), ("REQ-002", "RISK-001"), ("REQ-003", "RISK-001"),
    ("REQ-003", "RISK-002"), ("REQ-004", "RISK-002"), ("REQ-005", "RISK-004"), ("REQ-006", "RISK-011"),
    ("REQ-007", "RISK-006"), ("REQ-008", "RISK-006"), ("REQ-009", "RISK-003"), ("REQ-010", "RISK-005"),
    ("REQ-011", "RISK-009"), ("REQ-012", "RISK-007"), ("REQ-014", "RISK-010"), ("REQ-015", "RISK-012"),
]


def rows(data, keys):
    return [dict(zip(keys, r)) for r in data]


VALID = {
    "requirements": rows(REQUIREMENTS, ["id", "title", "description", "priority", "status"]),
    "test_cases": rows(TEST_CASES, ["id", "requirement_id", "title", "steps", "expected_result", "status"]),
    "risk_items": rows(RISKS, ["id", "title", "description", "severity", "likelihood", "status"]),
    "requirement_risks": [{"requirement_id": a, "risk_id": b} for a, b in LINKS],
}

INVALID = {
    "_note": "Each row below must be REJECTED by the seed validator (see _reason).",
    "requirements": [
        {"id": "REQ-001", "title": "Duplicate id", "description": "x", "priority": "high", "status": "draft", "_reason": "duplicate ID"},
        {"id": "R-16", "title": "Bad id format", "description": "x", "priority": "high", "status": "draft", "_reason": "ID format"},
        {"id": "REQ-016", "title": "", "description": "x", "priority": "high", "status": "draft", "_reason": "empty required field"},
        {"id": "REQ-017", "title": "Bad priority", "description": "x", "priority": "urgent", "status": "draft", "_reason": "invalid enum value"},
    ],
    "test_cases": [
        {"id": "TC-031", "requirement_id": "REQ-099", "title": "Orphan", "steps": "x", "expected_result": "x", "status": "not_run", "_reason": "references unknown requirement"},
    ],
    "risk_items": [
        {"id": "RISK-013", "title": "Out of range", "description": "x", "severity": 9, "likelihood": 2, "status": "open", "_reason": "severity must be 1-5"},
    ],
    "requirement_risks": [
        {"requirement_id": "REQ-001", "risk_id": "RISK-999", "_reason": "references unknown risk"},
    ],
}


def self_check():
    req_ids = {r["id"] for r in VALID["requirements"]}
    risk_ids = {r["id"] for r in VALID["risk_items"]}
    assert len(req_ids) == len(REQUIREMENTS) and len({t["id"] for t in VALID["test_cases"]}) == len(TEST_CASES)
    assert all(t["requirement_id"] in req_ids for t in VALID["test_cases"])
    assert all(a in req_ids and b in risk_ids for a, b in LINKS)
    tested = {t["requirement_id"] for t in VALID["test_cases"]}
    print("requirements without test cases:", sorted(req_ids - tested))
    print("high-risk items (score >= 15):", [(k[0], k[3] * k[4]) for k in RISKS if k[3] * k[4] >= 15])


if __name__ == "__main__":
    (OUT / "seed_raw.json").write_text(json.dumps(VALID, indent=2), encoding="utf-8")
    (OUT / "seed_invalid_examples.json").write_text(json.dumps(INVALID, indent=2), encoding="utf-8")
    self_check()
    print(f"{len(REQUIREMENTS)} requirements, {len(TEST_CASES)} test cases, {len(RISKS)} risks, {len(LINKS)} links written")
