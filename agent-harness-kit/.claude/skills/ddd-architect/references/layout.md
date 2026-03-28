# Recommended DDD Directory Structure

```text
src/
├── domain/                 # PURE PYTHON (No frameworks)
│   ├── models/             # Entities and Aggregates
│   │   ├── order.py
│   │   └── user.py
│   ├── value_objects.py
│   └── events.py           # Domain Events
│
├── application/            # ORCHESTRATION
│   ├── commands/           # Write operations (Use Cases)
│   ├── queries/            # Read operations
│   └── interfaces/         # Abstract Base Classes (Ports)
│       ├── i_repository.py
│       └── i_uow.py
│
├── infrastructure/         # IMPLEMENTATION
│   ├── db/
│   │   ├── models.py       # SQLAlchemy ORM Models (Table definitions)
│   │   ├── session.py      # Engine and SessionFactory
│   │   └── migrations/     # Alembic
│   ├── repositories/       # SQLAlchemy implementations of interfaces
│   └── uow.py              # Unit of Work implementation
│
├── api/                    # ENTRY POINT
│   ├── v1/
│   │   └── endpoints/
│   ├── dependencies.py     # DI wiring
│   └── main.py             # FastAPI App
│
└── tests/                  # MIRRORS SRC STRUCTURE
```
