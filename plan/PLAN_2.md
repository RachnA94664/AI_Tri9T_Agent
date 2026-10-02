# Engineering Knowledge Agent: Implementation Plan

Stack: Python 3.11, FastAPI, SQLAlchemy 2 + Alembic, SQLite (Postgres-ready), Pydantic v2, OpenAI SDK (tool calling, structured outputs), React + Vite + TypeScript, pytest, ruff, mypy, GitHub Actions.

Key design principles:
- **Propose, then confirm:** agents can only create a pending change; a human or API confirm applies it.
- **Versioned schema:** Alembic migrations make the schema reproducible.
- **Verified agent behaviour:** an agent eval harness with a golden question set, plus a prompt-injection suite.
- **Observability:** structured logging, request IDs, per-turn tool trace, token and latency counters.
- **Hybrid router:** cheap deterministic patterns (e.g. an ID like `REQ-001`) first, LLM fallback; fewer calls, lower cost, more predictable.
- **Safe concurrent writes:** optimistic locking (`version` column) and an idempotency key on writes.
- **Explicit failure handling:** failure-mode table (section 9).

## 1. Scope: MVP vs stretch

**MVP (must ship, assignment deliverables):** DB + migrations + seed validation, REST API, rules and audit log, 3 agents (query, update, analysis) + orchestrator, impact workflow, React UI, tests, README, Git workflow with PRs.
**Stretch (only if time):** eval harness with scored report, Docker compose, CI badge, streaming responses, Postgres switch, ADR folder.
Rule: finish MVP end to end (thin vertical slice) before polishing any layer.

## 2. Architecture (layered, dependencies point inward)

```
React UI -> API routers -> Application services (use cases) -> Domain rules -> Repositories -> DB
                 ^                      ^
                 |                      |
            Agent layer ----(tools = thin adapters over use cases)
```

- **Domain** (`domain/`): pure Python, no I/O: enums, ID formats, status state machine, risk scoring. Unit-testable in milliseconds.
- **Repositories** (`repositories/`): all SQL lives here; return domain objects.
- **Services** (`services/`): use cases (`update_requirement_status`, `get_impact`). Own the transaction boundary and write the audit entry in the same transaction.
- **Agents** (`agents/`): never import repositories. They only call services via tool adapters. This is the guardrail that matters most.
- **API** (`api/`): HTTP only; maps domain errors to status codes (404, 409, 422).

```
backend/app/{domain,repositories,services,agents,api,db,core}/
backend/migrations/ (alembic)
backend/tests/{unit,integration,agents,evals}/
frontend/src/{api,components,pages,hooks}/
docs/adr/            # architecture decision records (short)
```

## 3. Database design

Tables: `requirements`, `test_cases`, `risk_items`, `requirement_risks` (M:N), `audit_log`, `pending_changes`.

- Business IDs (`REQ-001`) as primary keys, validated by a CHECK regex-equivalent and by the domain layer.
- `requirements.version INTEGER` for optimistic locking; `updated_at` maintained by the service.
- `risk_items`: store severity and likelihood; `risk_score` and `level` are **derived in the domain layer** (single source of truth), not stored, so they cannot drift. Thresholds: score >= 15 high, 8 to 14 medium, below 8 low.
- `pending_changes`: id, entity_type, entity_id, proposed_patch (JSON), base_version, proposed_by (agent or user), status (pending/applied/rejected/expired), created_at, resolved_at. This table is what makes human-in-the-loop auditable.
- `audit_log`: append-only (no update/delete in code; enforced with SQLite triggers that RAISE on UPDATE or DELETE). Columns: id, ts, actor, source (ui/agent/system), entity_type, entity_id, action, old_value, new_value, request_id.
- Indexes: `test_cases(requirement_id)`, `requirement_risks(risk_id)`, `audit_log(entity_type, entity_id)`.
- FK enforcement on (`PRAGMA foreign_keys=ON` on every connection, tested). `ON DELETE RESTRICT` everywhere.

## 4. Agent design

**Pattern: orchestrator with tool-using specialists**, not a free-form swarm. Fixed, inspectable control flow beats autonomy for a system that guards data.

1. **Router** (hybrid): regex/ID extraction and keyword rules handle obvious intents; ambiguous input goes to an LLM classifier returning a strict JSON enum (`lookup`, `list_filter`, `update`, `analysis`, `out_of_scope`) via structured outputs.
2. **Query agent** (read-only tools): `get_requirement`, `get_test_cases_for_requirement`, `list_risks(level)`, `list_requirements_without_tests`, `search_text`.
3. **Update agent**: only tool is `propose_requirement_change(id, patch)`. It returns a `pending_change` id plus a preview diff. It cannot apply.
4. **Analysis agent**: `get_impact(requirement_id)` (deterministic result) then summarises it.
5. **Responder**: formats final answer from tool outputs only.

Agent-level guardrails:
- **Grounding contract**: every answer returns `{answer, records[], tool_calls[]}`. The UI renders `records` as the source of truth; the prose is secondary. If `records` is empty the reply must say "not found". A post-check rejects answers that cite IDs not present in `records`.
- **Prompt-injection defence**: DB text (titles, descriptions) is passed as quoted data in tool results, system prompt states tool output is untrusted data and never instructions; the agent has no tool that can do harm even if tricked (least privilege, no delete, no apply).
- **Limits**: max tool-call loop depth (4), per-request token cap, timeout, one retry with backoff on 429/5xx, `temperature=0`.
- **Out-of-scope handling**: "delete REQ-001" gets a polite refusal from the router, no LLM write path exists.
- Prompts live in versioned files (`agents/prompts/*.md`), not inline strings.

## 5. Rules and guardrails

Enforced in layers (defence in depth); each rule has a test.

| Layer | Rules |
|---|---|
| DB | PK uniqueness, FKs, CHECK enums and 1-5 ranges, NOT NULL, append-only audit triggers |
| Domain | ID format, status state machine (draft -> approved -> implemented -> verified; any -> obsolete; obsolete terminal), derived risk level |
| Service | FK existence with clear errors, optimistic lock (`base_version` must match else 409), idempotency key, audit write in the same transaction, rollback on any failure |
| Agent | Read/propose-only tools, grounding check, iteration and token caps, confirmation required to apply |
| Seed pipeline | Validate every generated row with the same domain rules; rejected rows are reported in a summary and never inserted |

## 6. Automated workflow: impact analysis

Trigger: a pending change on a requirement is **confirmed and applied**.
Steps (deterministic service, in one transaction where it writes):
1. Compute diff (which fields changed).
2. Find linked test cases; mark those affected as `needs_rerun` (new status or flag; `pass` -> `not_run`), skipping `obsolete`.
3. Find linked risks via `requirement_risks`; flag for review.
4. Severity of impact: if priority is critical or the change is in `description`, impact is "high".
5. Persist an `impact_report` (JSON) linked to the audit entry; return it.
6. Analysis agent writes a 3-sentence human summary from that JSON (LLM only phrases, never decides).
Idempotent: re-applying the same change id is a no-op.

## 7. API contract (OpenAPI is the spec)

`GET /requirements`, `GET /requirements/{id}`, `GET /requirements/{id}/test-cases`, `GET /requirements/{id}/impact`, `GET /requirements/without-tests`, `GET /risks?level=`, `POST /changes` (propose), `POST /changes/{id}/confirm`, `POST /changes/{id}/reject`, `GET /audit-log`, `POST /chat`, `GET /health`.
Consistent error envelope `{error: {code, message, details}}`. Pagination on list endpoints.

## 8. Frontend

TypeScript, API client generated from or typed against OpenAPI. Views: Chat (answer + evidence table + tool trace), Browse (requirements, tests, risks), Pending changes (diff + Confirm/Reject), Impact report, Audit log. Loading, error and empty states for each. No UI library needed; keep CSS simple.

## 9. Failure modes and handling

| Failure | Handling |
|---|---|
| LLM down / 429 / timeout | retry with backoff, then friendly error; deterministic browse endpoints still work |
| LLM returns wrong ID / hallucination | grounding post-check blocks it, answer falls back to raw records |
| Invalid tool arguments | Pydantic validation on tool input; error fed back once, then abort |
| Concurrent edit | version mismatch gives 409 and the UI shows the latest |
| Partial write | single transaction with rollback; audit and change commit together |
| Prompt injection in data | untrusted-data framing plus least-privilege tools; injection test in the suite |
| Bad seed data | validator rejects and reports; seed is atomic |

## 10. Testing strategy

- **Unit** (fast, majority): domain rules, state machine, scoring, validators.
- **Integration**: API with TestClient and a temp SQLite file; FK enforcement, rollback, audit atomicity, optimistic locking, impact workflow.
- **Agent tests**: LLM client behind an interface with a fake; assert the right tool calls, grounding, "not found", out-of-scope refusal, injection string in a record not obeyed.
- **Evals (stretch)**: `evals/golden.yaml` with ~25 questions and expected tool and record IDs; a script runs against the real model and reports pass rate. Not run in CI by default (cost); run manually.
- Coverage target: about 80 percent on domain and services. Mutation of rules is out of scope.

## 11. Observability and config

Structured JSON logs with `request_id`, tool name, latency, token usage. Config through `pydantic-settings` and `.env` (`.env.example` committed, `.env` gitignored). Never log the API key or full prompts at INFO.

## 12. Engineering workflow

- **Branches:** `main` (protected), `develop`, `feature/database`, `feature/domain-rules`, `feature/services-audit`, `feature/agents`, `feature/impact-workflow`, `feature/frontend`, `docs/readme`.
- Small PRs (target under 400 lines), PR template with checklist, squash or merge into `develop`, `develop` into `main` at the end. At least `feature/database` goes through a real PR with self-review comments.
- Conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`).
- **Quality gates:** ruff, mypy (on domain/services), pytest in GitHub Actions on every PR.
- **ADRs** (half page each): why SQLite, why tool calling not text-to-SQL, why propose/confirm, why derived risk score, why hybrid router.

## 13. Milestones (time-boxed, each ends with a green test run and a PR)

| # | Branch | Deliverable | Est. |
|---|---|---|---|
| 0 | `main` | repo skeleton, README stub, .gitignore, .env.example, CI, `develop` branch | 0.5 day |
| 1 | `feature/database` | models, Alembic migration, seed loader plus validator, seed and invalid-seed tests | 1 day |
| 2 | `feature/domain-rules` | state machine, ID rules, risk scoring, unit tests | 0.5 day |
| 3 | `feature/services-audit` | repositories, services, audit log, pending changes, optimistic lock, REST API | 1.5 days |
| 4 | `feature/agents` | LLM interface and fake, tools, router, 3 agents, grounding check, `/chat`, agent tests | 2 days |
| 5 | `feature/impact-workflow` | impact service wired to confirm, report persistence, analysis agent | 1 day |
| 6 | `feature/frontend` | React views, confirm/reject flow | 1.5 days |
| 7 | `docs/readme` | README, ADRs, example queries, limitations, optional eval harness | 1 day |

Total about 9 working days. If time is short, cut: evals, Docker, streaming, ADRs (keep a short "decisions" section in the README).

## 14. Definition of done (per assignment deliverables)

- [ ] Repo with multiple branches and at least one merged PR
- [ ] App runs from README steps on a clean machine (`make setup`, `make run`)
- [ ] Schema, migration and seed data (valid plus invalid sample rejected)
- [ ] Multi-agent system answering the 5 sample queries from DB data only
- [ ] Rules enforced and tested; audit log shows every change
- [ ] Impact workflow demonstrable from the UI
- [ ] Tests green in CI
- [ ] README with all 8 required sections plus decisions and limitations

## 15. Risks to the project itself

| Risk | Mitigation |
|---|---|
| Over-engineering for a warm-up | MVP vs stretch split; vertical slice first |
| LLM cost or key leakage | `.env` gitignored, secret scan in CI, `temperature=0`, request caps |
| Agent flakiness hurts demo | Deterministic router and tools, fixtures for demo questions, fake LLM in tests |
| Time overruns | milestone cut list above |
