
**Coding Standards, Best Practices & Naming Conventions**
**Dynamic Trust Infrastructure — MVP**

These rules are intentionally lightweight so the team can move fast while keeping the codebase readable and maintainable.

---

### 1. General Principles

1. **Clarity over cleverness** — Code should be obvious to the next person reading it.
2. **Single Responsibility** — Functions, classes, and modules do one thing.
3. **Explicit is better than implicit** (especially in Python).
4. **Fail fast and clearly** — Validate early, return meaningful errors.
5. **Keep the demo path sacred** — Never break the main happy-path flows.
6. **Document only what is non-obvious** — Good names > long comments.
7. **Type everything** — Python (type hints) and TypeScript are mandatory.

---

### 2. Naming Conventions

#### Backend (FastAPI / Python)

| Item                | Convention                       | Example                                                   |
| ------------------- | -------------------------------- | --------------------------------------------------------- |
| Files / Modules     | `snake_case`                   | `trust_scoring.py`, `guarantor_service.py`            |
| Packages            | `snake_case`                   | `app/services/`, `app/api/v1/`                        |
| Classes             | `PascalCase`                   | `GuarantorInstrument`, `TrustScoreResult`             |
| Functions / Methods | `snake_case`                   | `calculate_trust_score()`, `create_instrument()`      |
| Variables           | `snake_case`                   | `worker_id`, `confidence_score`                       |
| Constants           | `UPPER_SNAKE_CASE`             | `MAX_DISPUTE_RATE`, `DEFAULT_WEIGHTS`                 |
| Pydantic Models     | `PascalCase`                   | `TrustQueryRequest`, `TrustQueryResponse`             |
| Enums               | `PascalCase` + `Enum`        | `TrustBand(str, Enum)`, `InstrumentStatus`            |
| Database tables     | `snake_case` (plural)          | `workers`, `guarantor_instruments`, `work_outcomes` |
| API route paths     | `kebab-case` or `snake_case` | `/trust/query`, `/guarantors/instruments`             |

**Boolean naming:** Use prefixes `is_`, `has_`, `can_`, `should_`
Examples: `is_active`, `has_active_guarantor`, `can_be_scored`

#### Frontend (Next.js / React / TypeScript)

| Item                   | Convention                                                 | Example                                      |
| ---------------------- | ---------------------------------------------------------- | -------------------------------------------- |
| Files / Components     | `PascalCase` for components                              | `TrustBandCard.tsx`, `GuarantorFlow.tsx` |
| Hooks                  | `camelCase` starting with `use`                        | `useTrustQuery.ts`                         |
| Utilities              | `camelCase`                                              | `formatConfidence.ts`                      |
| Variables / Functions  | `camelCase`                                              | `trustBand`, `handleConfirmJob`          |
| Types / Interfaces     | `PascalCase`                                             | `TrustQueryResponse`, `WorkerSummary`    |
| CSS classes (Tailwind) | Prefer Tailwind utilities. Custom classes in`kebab-case` | `trust-band-high`                          |
| Page routes            | `kebab-case`                                             | `/worker/portable-record`                  |

**Component props:** Destructure and type explicitly.

---

### 3. Project Structure (Recommended)

**Backend (FastAPI)**

```
app/
├── api/
│   └── v1/
│       ├── endpoints/
│       │   ├── trust.py
│       │   ├── guarantors.py
│       │   ├── outcomes.py
│       │   ├── credentials.py
│       │   └── independent.py
│       └── router.py
├── core/
│   ├── config.py
│   └── security.py
├── models/          # SQLAlchemy Python class that maps to a database table SQLAlchemy Defines table structure & talks to the DB
├── schemas/         # Pydantic Python class for request/response data Pydantic Validates & serialises data for the API
├── services/        # Business logic
│   ├── trust_scoring.py
│   ├── normalisation.py
│   ├── guarantor.py
│   └── escrow.py
├── db/ The actual database Neon (PostgreSQL) Permanent storage of data
└── main.py
```

**Frontend (Next.js)**

```
src/
├── app/                 # App Router
├── components/
│   ├── ui/              # shadcn or base components
│   ├── trust/
│   ├── guarantor/
│   └── layout/
├── features/            # Optional feature-based grouping
├── lib/
├── hooks/
├── types/
└── styles/
```

---

### 4. Backend Best Practices (FastAPI)

- **Pydantic models** for every request and response.
- **Dependency injection** for DB sessions and current platform/user.
- **Service layer** — Keep route handlers thin. Business logic lives in `services/`.
- **Consistent error responses**:
  ```json
  {
    "detail": "Human readable message",
    "code": "INSTRUMENT_NOT_ACTIVE"
  }
  ```
- Use `HTTPException` with proper status codes.
- All external calls (Vesti, KYC) go through a dedicated client/service with clear timeouts and error handling.
- Logging: Use structured logging. Log important state changes (instrument signed, score updated, escrow activated).
- Never commit secrets. Use environment variables + `.env.example`.

---

### 5. Frontend Best Practices (Next.js + React)

- Prefer **Server Components** where possible; use Client Components only when needed (interactivity).
- Keep components small and focused.
- Use **TanStack Query** (React Query) for server state.
- Tailwind: Use the design tokens/colors consistently. Avoid arbitrary values when a token exists.
- Loading, empty, and error states are mandatory for every data-driven view.
- Accessibility: Proper labels, semantic HTML, keyboard navigation for the main flows.

---

### 6. Database & Data Practices

- Use **Alembic** (or equivalent) for migrations. Never change production schema manually.
- Soft deletes where history matters (`deleted_at`).
- Index foreign keys and columns used in trust calculations.
- Store raw platform payloads (for normalisation debugging) in a JSONB column when useful.
- Audit important actions (guarantor signed, outcome recorded, escrow activated).

---

### 7. Git & Collaboration Standards

- **Branch naming:**`feature/trust-query``fix/guarantor-sign-bug``chore/update-deps`
- **Commit messages:** Conventional Commits style preferred`feat: add trust query endpoint``fix: correct confidence calculation for building history``docs: update API examples`
- Small, focused pull requests.
- At least one other person reviews before merging to main (even in a hackathon).
- Main branch must always be in a runnable state.

---

### 8. Testing Expectations (Pragmatic for MVP)

- **Must have:** Unit tests for the Trust Scoring Engine and normalisation logic.
- **Should have:** API tests for the main happy paths (trust query, create + sign guarantor, completion confirmation).
- **Nice to have:** Basic frontend component tests.
- Do not aim for 100% coverage. Aim for confidence in the critical path.

---

### 9. Code Review Checklist (Quick)

- [ ] Names are clear and consistent with the conventions above
- [ ] Types are complete
- [ ] No hardcoded secrets or magic numbers
- [ ] Error cases are handled
- [ ] The change does not break the main demo path
- [ ] Scoring or financial logic has a test or clear manual verification steps

---

### 10. Quick Reference Card

**Python:** `snake_case` functions, `PascalCase` classes, full type hints
**TypeScript:** `camelCase` values, `PascalCase` components & types
**API paths:** clear and resource-oriented
**Business logic:** lives in services, not in route handlers
**Scoring formula:** isolated and well-documented
**Demo path:** never broken
