"""DDD patterns reference (Python 3.13+).

This file is a set of templates demonstrating a strict Hexagonal (Ports &
Adapters) architecture:
- Domain is pure Python (no frameworks).
- Application defines ports (Protocols) and use cases.
- Infrastructure implements ports (SQLAlchemy 2.0 async).

These snippets are meant as copy/paste starting points.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import Boolean, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ---------------------------------------------------------
# 1. DOMAIN LAYER (Pure Python)
# ---------------------------------------------------------


@dataclass
class User:
    """Domain entity (mutable) with behavior."""

    id: UUID
    email: str
    is_active: bool = True

    def activate(self) -> None:
        """Activate the user."""

        self.is_active = True


# ---------------------------------------------------------
# 2. APPLICATION LAYER (Ports & Use Cases)
# ---------------------------------------------------------


class UserDTO(BaseModel):
    """DTO returned by application use cases."""

    id: UUID
    email: str


class IUserRepository(Protocol):
    """Repository port for user persistence."""

    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def add(self, user: User) -> None: ...


class IUnitOfWork(Protocol):
    """Unit of Work port (transaction boundary)."""

    users: IUserRepository

    async def __aenter__(self) -> "IUnitOfWork": ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class CreateUserUseCase:
    """Application use case: create a user."""

    def __init__(self, *, uow: IUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, *, email: str) -> UserDTO:
        new_user = User(id=uuid4(), email=email)
        async with self._uow:
            await self._uow.users.add(new_user)
            await self._uow.commit()
        return UserDTO(id=new_user.id, email=new_user.email)


# ---------------------------------------------------------
# 3. INFRASTRUCTURE LAYER (SQLAlchemy 2.0)
# ---------------------------------------------------------


class Base(DeclarativeBase):
    """SQLAlchemy Declarative Base."""


class UserModel(Base):
    """ORM model (separate from the domain entity)."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True)

    email: Mapped[str] = mapped_column(String(255))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def to_domain(self) -> User:
        """Map ORM -> Domain."""

        return User(id=self.id, email=self.email, is_active=self.is_active)

    @staticmethod
    def from_domain(*, user: User) -> "UserModel":
        """Map Domain -> ORM."""

        return UserModel(id=user.id, email=user.email, is_active=user.is_active)


class SqlAlchemyUserRepository:
    """SQLAlchemy repository adapter implementing the repository port."""

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def add(self, *, user: User) -> None:
        model = UserModel.from_domain(user=user)
        self._session.add(model)

    async def get_by_id(self, *, user_id: UUID) -> User | None:
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None
