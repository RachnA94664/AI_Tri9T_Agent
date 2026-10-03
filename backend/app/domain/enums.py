"""Allowed values for status-like fields. One place to change them.

The database CHECK constraints are built from these tuples, so the two can
never disagree.
"""

PRIORITIES = ("low", "medium", "high", "critical")
REQUIREMENT_STATUSES = ("draft", "approved", "implemented", "verified", "obsolete")
TEST_STATUSES = ("not_run", "pass", "fail", "blocked")
RISK_STATUSES = ("open", "mitigated", "accepted", "closed")
PENDING_STATUSES = ("pending", "applied", "rejected", "expired")
RISK_LEVELS = ("low", "medium", "high")  # derived from severity x likelihood, never stored
AUDIT_SOURCES = ("ui", "agent", "system")

# ID formats, as SQLite GLOB patterns (used in CHECK constraints)
REQ_ID_GLOB = "REQ-[0-9][0-9][0-9]"
TC_ID_GLOB = "TC-[0-9][0-9][0-9]"
RISK_ID_GLOB = "RISK-[0-9][0-9][0-9]"
