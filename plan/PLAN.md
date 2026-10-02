# Engineering Knowledge Agent: Implementation Plan

Stack: Python 3.11+, FastAPI, SQLite (SQLAlchemy), React (Vite), OpenAI API (function calling), pytest.

## 1. Architecture

```
React UI  --HTTP-->  FastAPI  -->  Orchestrator agent  -->  Specialist agents
                        |                                       |
                        |                                  Tool layer (only path to DB)
                        |                                       |
                        +-----------  Service layer + validators  --> SQLite
                                                   |
                                              audit_log table
```

Key principle: **the LLM never touches the DB directly.** It can only call typed tools. Tools call the service layer, which enforces all rules. Answers are built from tool results, so records cannot be invented.

```
AI_Tri9T_Agent/
  backend/app/
    main.py                 # FastAPI app, routers
    config.py               # env settings (OPENAI_API_KEY, DB path)
    db/                     # models.py, session.py, schema.sql, seed.py
    schemas/                # Pydantic request/response models
    services/               # requirements.py, test_cases.py, risks.py, audit.py, impact.py
    validation/             # rules.py (ID format, status transitions, FK checks)
    agents/                 # orchestrator.py, query_agent.py, update_agent.py, analysis_agent.py, tools.py
    api/                    # routes_entities.py, routes_chat.py
  backend/tests/            # unit (rules, services), integration (API), agent tests (mocked LLM)
  backend/data/seed_raw.json  # LLM-generated dummy data, validated before insert
  frontend/src/             # Chat panel, Entity tables, Update form, Impact/Audit views
  docs / README.md
```

## 2. Database design (SQLite)

- **requirements**: id (PK, `REQ-001`), title, description, priority (low/medium/high/critical), status (draft/approved/implemented/verified/obsolete), created_at, updated_at
- **test_cases**: id (PK, `TC-001`), requirement_id (FK to requirements), title, steps, expected_result, status (not_run/pass/fail/blocked)
- **risk_items**: id (PK, `RISK-001`), title, description, severity (1-5), likelihood (1-5), risk_score (computed = severity x likelihood), level (low/medium/high derived from score), status (open/mitigated/accepted/closed)
- **requirement_risks**: requirement_id, risk_id (many-to-many join; composite PK)
- **audit_log**: id, timestamp, actor (user/agent name), entity_type, entity_id, action, old_value (JSON), new_value (JSON), source (ui/agent)

Constraints at DB level: PKs, FKs (`PRAGMA foreign_keys=ON`), CHECK on enums and 1-5 ranges, NOT NULL on required fields.

## 3. Agent design (multi-agent)

| Agent | Responsibility | Tools |
|---|---|---|
| **Orchestrator** | Classifies intent (lookup / update / analysis / unknown) and routes; composes the final reply | `route_to_agent` |
| **Query agent** (read-only) | Answers questions from DB | `get_requirement`, `list_test_cases_for_requirement`, `list_high_risks`, `list_requirements_without_tests`, `search` |
| **Update agent** | Proposes changes; the change is applied only through the validated service layer | `update_requirement_status`, `update_requirement_fields` |
| **Analysis agent** | Impact analysis after a change | `get_impact(requirement_id)` |

Grounding rules: system prompts require "answer only from tool output"; if a tool returns nothing, the reply says "not found". Replies include the raw records so the UI can show the evidence. Updates return a structured result (applied or rejected, with the reason).

## 4. Rules and guardrails

1. IDs are unique and match a format (`REQ-\d{3}`, `TC-\d{3}`, `RISK-\d{3}`).
2. A test case must reference an existing requirement (FK plus a service-level check with a clear error).
3. Required fields and enum values validated (Pydantic and DB CHECKs).
4. Status transitions follow a state machine (e.g. draft to approved to implemented to verified; no jumping from draft to verified; obsolete is terminal).
5. A requirement cannot be deleted while it has test cases (the agent has no delete tool at all).
6. Agents can only update status/fields; they cannot create or delete in v1 (least privilege).
7. Every write is logged in `audit_log` in the same transaction as the change.
8. Seed data from the LLM is validated against the same rules before insertion; invalid rows are reported and skipped.
9. Update tool calls need explicit confirmation in the UI before applying (human in the loop).

## 5. Automated workflow

When a requirement is modified (status or fields), the system automatically runs impact analysis: it finds linked test cases (flagged "needs re-run" -> status `not_run`) and linked risk items (flagged for review), writes an audit entry, and returns an impact report. The Analysis agent turns the report into a short summary for the user. The rule logic is deterministic; the LLM only phrases it.

## 6. API

`GET /requirements`, `GET /requirements/{id}`, `PATCH /requirements/{id}`, `GET /requirements/{id}/test-cases`, `GET /requirements/{id}/impact`, `GET /risks?level=high`, `GET /requirements/without-tests`, `GET /audit-log`, `POST /chat` (message to agent reply plus tool trace plus data).

## 7. UI (React)

Chat box with answers; a "retrieved data" table beside each answer; an update form with confirm step; an audit log tab; an impact report panel after updates. Plain CSS, no heavy UI library.

## 8. Git workflow

Branches: `main` (protected, merge via PR only), `develop`, `feature/database`, `feature/validation-rules`, `feature/agents`, `feature/impact-workflow`, `feature/frontend`, `docs/readme`.
Each feature branch merges into `develop` via PR; at least one (database) is done as a real GitHub PR; `develop` then merges into `main` via PR. Meaningful commits (conventional style: `feat:`, `test:`, `docs:`).

## 9. Build order

1. `feature/database`: models, schema, seed generation script plus validator, seed data, DB tests
2. `feature/validation-rules`: rules and service layer, audit log, tests
3. `feature/agents`: tools, query/update/analysis agents, orchestrator, mocked-LLM tests
4. `feature/impact-workflow`: impact service wired into updates
5. `feature/frontend`: React UI
6. `docs/readme`: README (what, architecture, DB, agents, rules, run steps, example queries, limitations, decisions and why)

## 10. Testing

pytest: validators (valid/invalid IDs, transitions, FK failure), services (audit written, rollback on failure), API (TestClient with temp DB), agents (LLM mocked so tests are deterministic; verify tools called and "not found" handling). One small optional live-LLM smoke test, skipped without a key.

## 11. Decisions to note in the README

SQLite for zero setup; a service layer between agents and DB so rules live in one place; tool calling (not text-to-SQL) to prevent invention and unsafe queries; deterministic impact logic with the LLM only for phrasing; read/update agents split for least privilege; the API key is read from `.env` (gitignored).

## 12. Known limitations (to document)

Single-user, no auth; SQLite concurrency; the LLM can misroute intent (mitigated by tool-only answers and confirmation on writes); no create/delete via agents in v1.
