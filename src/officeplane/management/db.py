"""Database client using Prisma"""
from prisma import Prisma
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# Global Prisma client instance
_prisma_client: Prisma | None = None


async def get_db() -> Prisma:
    """Get or create Prisma client instance"""
    global _prisma_client

    if _prisma_client is None:
        _prisma_client = Prisma()
        await _prisma_client.connect()

    return _prisma_client


async def disconnect_db():
    """Disconnect Prisma client"""
    global _prisma_client

    if _prisma_client is not None:
        await _prisma_client.disconnect()
        _prisma_client = None


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[Prisma, None]:
    """Context manager for database access"""
    db = await get_db()
    try:
        yield db
    finally:
        pass  # Don't disconnect, keep connection alive
