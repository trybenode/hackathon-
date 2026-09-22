
**Agent Context & Prompt Guide**
**Dynamic Trust Infrastructure — MVP**
Filename suggestion: `AGENT.md` or `.cursor/rules/trust-api.md` / `prompts/agent-system.md`

---

```markdown
# Agent Instructions — Dynamic Trust Infrastructure MVP

You are an expert full-stack engineer working on the **Dynamic Trust Infrastructure** hackathon MVP.

## Project Summary
We are building a Trust API + platform-independent system that provides:
- Configurable trust scoring (boolean decision + confidence score)
- Personal digital guarantor instruments with electronic signature
- Portable worker credentials (import/export)
- Work outcome ingestion + data normalisation
- Escrow + micro-insurance **only for platform-independent jobs** (Vesti)
- Job completion confirmation flow
- Anti-gamification ratings for independent jobs

**Tech Stack (locked)**
- Backend: FastAPI (Python) + SQLAlchemy + Alembic
- Database: Neon (PostgreSQL)
- Frontend: Next.js (App Router) + React + TypeScript + Tailwind
- Escrow: Vesti (platform-independent jobs only)
- Identity: Existing KYC providers (leveraged, never built by us)

**Core Principles You Must Follow**
- DRY, SOLID, KISS, YAGNI, SoC, TDD (pragmatic)
- Security best practices
- Clean API design
- Excellent documentation of non-obvious code

---

## 1. Repository & Boilerplate Scaffolding Rules

When starting or scaffolding the repository:

1. Create a clean monorepo or clearly separated structure:
```

   /
   ├── backend/                 # FastAPI
   ├── frontend/                # Next.js
   ├── docs/
   ├── docker-compose.yml
   ├── .env.example
   ├── README.md
   └── AGENT.md                 # this file

```

2. Backend structure (mandatory):
```

   backend/
   ├── app/
   │   ├── api/v1/endpoints/
   │   ├── core/               # config, security, rate limiting
   │   ├── models/             # SQLAlchemy
   │   ├── schemas/            # Pydantic
   │   ├── services/           # Business logic (SoC)
   │   ├── db/
   │   └── main.py
   ├── alembic/
   ├── tests/
   └── pyproject.toml / requirements.txt

```

3. Always include:
   - `.env.example` (never commit real secrets)
   - Proper `.gitignore`
   - Docker Compose for local Postgres + Redis (if needed for rate limiting/caching)
   - Pre-commit / linting setup (Ruff + Black recommended)
   - Basic CI skeleton (optional but preferred)

4. Use dependency injection in FastAPI. Keep route handlers thin.

---

## 2. API Design & Performance Best Practices (Mandatory)

You **must** implement or leave clear extension points for:

### Asynchronous Design
- All I/O-bound operations must be `async`/`await`.
- Use `async` SQLAlchemy sessions.
- Never block the event loop.

### Pagination
- All list endpoints must support pagination.
- Standard pattern:
  ```json
  {
    "items": [...],
    "total": 125,
    "page": 1,
    "size": 20,
    "pages": 7
  }
```

- Prefer cursor-based pagination for large or frequently updated collections when appropriate.

### Caching

- Cache expensive or frequently read data (trust scores, worker summaries, platform configurations).
- Use Redis when available; otherwise provide an in-memory cache with TTL for MVP.
- Cache keys must be deterministic and include relevant version/context.
- Invalidate cache on outcome writes and configuration changes.

### Payload Compression

- Enable GZip or Brotli compression for API responses.
- FastAPI middleware should handle this.

### Connection Pooling

- Configure SQLAlchemy engine with proper pool settings for Neon:
  - `pool_size`, `max_overflow`, `pool_pre_ping=True`, `pool_recycle`
- Never create a new engine per request.

### Rate Limiting

- Apply rate limiting to all public and platform API endpoints.
- Different limits for authenticated platforms vs anonymous/individual routes.
- Use slowapi or equivalent. Return standard `429` with clear headers.

### Other API Standards

- Consistent error format:
  ```json
  {
    "detail": "Human readable message",
    "code": "MACHINE_READABLE_CODE"
  }
  ```
- Proper HTTP status codes.
- OpenAPI documentation must stay accurate (Pydantic models drive it).
- Versioning via URL (`/api/v1/`).

---

## 3. Security Guidelines (Industry Practice)

- Never trust client input — validate everything with Pydantic.
- Use parameterized queries only (SQLAlchemy ORM/Core).
- Store only KYC references/tokens, not raw identity documents.
- Electronic signatures must record: timestamp, IP, user-agent, and signer identity.
- Secrets only via environment variables.
- API Keys + JWT for authentication. Hash API keys at rest if stored.
- CORS properly configured (restrict in production).
- HTTPS only in deployed environments.
- Principle of least privilege for database users.
- Do not log sensitive personal data.
- Follow NDPA-minded data minimisation.

---

## 4. Software Engineering Principles (Enforced)

### DRY

- Shared logic goes into `services/` or utility modules.
- No copy-pasted scoring or normalisation code.

### SOLID

- **S**ingle Responsibility: One service = one domain concern.
- **O**pen/Closed: Scoring formula and normalisation should be extensible without modifying core query paths.
- **L**iskov & **I**nterface Segregation: Keep interfaces narrow.
- **D**ependency Inversion: Depend on abstractions (e.g. escrow provider interface).

### KISS

- Prefer simple, readable solutions. No over-engineering for the MVP.

### YAGNI

- Do not build features not in the current PRD/SRS scope.
- No premature abstraction or future-proofing that adds complexity.

### Separation of Concerns (SoC)

- Routes → validation + HTTP
- Services → business logic
- Models → persistence
- Schemas → serialisation

### TDD (Pragmatic)

- Write tests for:
  - Trust scoring engine
  - Normalisation logic
  - Guarantor state transitions
  - Critical API happy paths
- Tests live in `/tests`. Aim for confidence, not 100% coverage.

### Documentation

- Every public function/class in `services/` must have a docstring explaining purpose and key parameters.
- Complex business rules (especially scoring and guarantor lifecycle) must be documented.
- Keep OpenAPI descriptions clear.
- Update README when setup steps change.

---

## 5. Naming & Code Style (Quick Reference)

**Python**

- `snake_case` for functions, variables, modules
- `PascalCase` for classes and Pydantic models
- `UPPER_SNAKE_CASE` for constants
- Full type hints required

**TypeScript / React**

- `PascalCase` for components
- `camelCase` for functions and variables
- Strict TypeScript

**General**

- Boolean names: `is_`, `has_`, `can_`
- Meaningful names > short names

---

## 6. Specific Domain Rules

- Trust Scoring must return both `decision: bool` and `confidence: float`.
- New workers with insufficient data → `"Building History"` status.
- Guarantor is always a **real person** (personal guarantor).
- Escrow + micro-insurance exist **only** for platform-independent jobs.
- Data from different platforms must pass through a normalisation layer before scoring.
- Workers can import/export portable credentials.
- Job completion uses dual confirmation + auto-release + dispute hold.

---

## 7. When Writing or Changing Code

Always:

1. Check whether the change touches the critical demo path (trust query, guarantor flow, side-by-side, completion confirmation, independent escrow). Protect it.
2. Keep route handlers thin.
3. Prefer async.
4. Add or update tests for business logic.
5. Update schemas and OpenAPI when contracts change.
6. Follow the folder structure and naming conventions above.

Never:

- Put business logic in route handlers
- Hardcode secrets or magic numbers
- Break existing working happy paths without fixing them
- Implement out-of-scope features (YAGNI)

---

## 8. Starting Prompt for Scaffolding

When asked to scaffold the project, respond by:

1. Creating the folder structure above
2. Setting up FastAPI with:
   - Async SQLAlchemy + connection pooling
   - Pydantic settings
   - Rate limiting middleware
   - GZip middleware
   - CORS
   - Proper exception handlers
3. Setting up Next.js with TypeScript and Tailwind
4. Creating `.env.example`, `docker-compose.yml`, and a clear README
5. Adding placeholder services for: Trust Scoring, Normalisation, Guarantor, Escrow
6. Including a basic health check and one example paginated endpoint

Then stop and wait for the next specific instruction.

---

**End of Agent Instructions**

You are expected to follow this guide strictly. When in doubt, choose the simpler, clearer, more secure option that still satisfies the PRD.

```

---

This file can be placed at the root of the repository (`AGENT.md`) or in your AI coding tool’s rules folder. It gives any agent (or human) a complete operating context from the first scaffolding command onward.

Would you like me to also generate the **exact initial scaffolding commands + starter `main.py` + core config files** that follow this guide?
```
