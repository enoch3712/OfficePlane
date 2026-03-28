---
name: ddd-architect
description: Design and build Python systems using Domain-Driven Design (DDD), Clean Architecture, and SOLID principles. Uses FastAPI and SQLAlchemy.
compatibility: Python 3.10+, SQLAlchemy 2.0+, FastAPI.
---

# DDD Architect (Python 3.13+)

## When to use this skill

Use this skill when the user asks to structure a complex Python application, requests "Clean Architecture," or mentions "Domain-Driven Design". Do NOT use this for simple scripts or micro-apps.

## 1. The Core Philosophy (The Dependency Rule)

In this architecture, dependencies point **inward**.

1. **Domain (Inner)**: Entities, Value Objects, Logic. No external dependencies (no SQL, no HTTP).
2. **Application (Middle)**: Use Cases, Orchestration, Interfaces (Ports).
3. **Infrastructure (Outer)**: Frameworks (FastAPI), Databases (SQLAlchemy), Adapters.

## 2. The Layers

### A. Domain Layer (`src/domain`)

**Strict Rule:** Pure Python only. No `sqlalchemy`, `pydantic`, or `fastapi` imports here.

- **Entities:** Mutable objects with an ID. Use standard `@dataclass`.
- **Value Objects:** Immutable objects defined by attributes (e.g., `Email`, `Money`). Use `@dataclass(frozen=True)`.
- **Aggregate Roots:** Entities that control access to a cluster of objects.
- **Domain Services:** Logic that doesn't fit into a single entity.

### B. Application Layer (`src/application`)

Orchestrates the domain.

- **Use Cases (Interactors):** Classes with a single `execute` or `__call__` method. They handle the "business transaction."
- **DTOs:** Pydantic models used to transfer data in/out of Use Cases.
- **Ports (Interfaces):** Abstract Base Classes (ABCs) or Protocols defining Repositories and Services.

### C. Infrastructure Layer (`src/infrastructure`)

Implements the Ports.

- **Persistence:** SQLAlchemy Models (ORM). *Note: These are NOT Domain Entities. You must map between ORM Models and Domain Entities.*
- **Repositories:** Implementations of the Application Ports using SQLAlchemy.
- **Unit of Work:** Managing database transactions.

### D. Interface Layer (`src/api`)

The Entry Point.

- **FastAPI Routes:** Accept JSON, convert to DTOs, call Use Case, return DTOs.

## 3. Implementation Patterns

### The Repository Pattern (SQLAlchemy 2.0)

Do not use legacy `session.query`. Use `await session.execute(select(...))`.

1. **Define Interface** (Application): `class UserRepository(Protocol): ...`
2. **Define Implementation** (Infra): `class SqlAlchemyUserRepository:`

### Dependency Injection

Use `fastapi.Depends` to inject the Unit of Work and Repositories into Routes.

## 4. Anti-Patterns (What to Avoid)

1. **Anemic Domain Models:** Entities that are just data holders. Put logic *inside* the Entity methods.
2. **Leaking Infrastructure:** Returning SQLAlchemy ORM objects directly from the API. Always return Pydantic DTOs.
3. **Fat Controllers:** Putting business logic in FastAPI routes. Routes should only parse input and call a Use Case.

## 5. Python 3.13 Specifics

- Use `typing.Self` for fluent interfaces.
- Use `typing.Annotated` for Dependency Injection.
- Use `|` union operators (e.g., `str | None`).
