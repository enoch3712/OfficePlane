"""
Document Instance Lifecycle Manager
Manages open/close state of LibreOffice document instances
"""
import asyncio
import os
import psutil
from datetime import datetime
from typing import Optional
from uuid import UUID

from prisma import Prisma
from prisma.enums import InstanceState
from .db import get_db


class InstanceManager:
    """Manages document instance lifecycle"""

    def __init__(self):
        self.instances: dict[str, dict] = {}  # In-memory tracking

    async def create_instance(
        self,
        driver_type: str = "libreoffice",
        document_id: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> dict:
        """Create a new document instance"""
        db = await get_db()

        # Build data dict with only non-None values
        data = {
            "driverType": driver_type,
            "state": InstanceState.OPENING,
            "hostName": os.uname().nodename,
        }

        if document_id:
            data["documentId"] = document_id
        if file_path:
            data["filePath"] = file_path

        instance = await db.documentinstance.create(data=data)

        # Simulate opening the instance (in real impl, launch LibreOffice)
        asyncio.create_task(self._open_instance(instance.id))

        return instance.model_dump()

    async def _open_instance(self, instance_id: str):
        """Background task to open an instance"""
        db = await get_db()

        try:
            # Simulate instance opening (in real impl: launch LibreOffice process)
            await asyncio.sleep(2)  # Simulate startup time

            # Mock PID for demonstration
            mock_pid = os.getpid()

            # Update instance to OPEN state
            instance = await db.documentinstance.update(
                where={"id": instance_id},
                data={
                    "state": InstanceState.OPEN,
                    "openedAt": datetime.utcnow(),
                    "lastUsedAt": datetime.utcnow(),
                    "processPid": mock_pid,
                },
            )

            # Track in memory
            self.instances[instance_id] = {
                "pid": mock_pid,
                "started_at": datetime.utcnow(),
            }

            # Start heartbeat monitoring
            asyncio.create_task(self._heartbeat_monitor(instance_id))

        except Exception as e:
            # Mark as error
            await db.documentinstance.update(
                where={"id": instance_id},
                data={
                    "state": InstanceState.ERROR,
                    "stateMessage": str(e),
                },
            )

    async def _heartbeat_monitor(self, instance_id: str):
        """Monitor instance health and update metrics"""
        db = await get_db()

        while True:
            try:
                instance = await db.documentinstance.find_unique(
                    where={"id": instance_id}
                )

                if not instance or instance.state not in [
                    InstanceState.OPEN,
                    InstanceState.IDLE,
                    InstanceState.IN_USE,
                ]:
                    break

                # Get process metrics if PID exists
                if instance.processPid:
                    try:
                        process = psutil.Process(instance.processPid)
                        memory_mb = process.memory_info().rss / 1024 / 1024
                        cpu_percent = process.cpu_percent(interval=0.1)

                        # Update metrics
                        await db.documentinstance.update(
                            where={"id": instance_id},
                            data={
                                "memoryMb": int(memory_mb),
                                "cpuPercent": cpu_percent,
                            },
                        )
                    except psutil.NoSuchProcess:
                        # Process died, mark as crashed
                        await db.documentinstance.update(
                            where={"id": instance_id},
                            data={
                                "state": InstanceState.CRASHED,
                                "stateMessage": "Process terminated unexpectedly",
                            },
                        )
                        break

                await asyncio.sleep(5)  # Heartbeat every 5 seconds

            except Exception as e:
                print(f"Heartbeat error for instance {instance_id}: {e}")
                break

    async def get_instance(self, instance_id: str) -> Optional[dict]:
        """Get instance by ID"""
        db = await get_db()
        instance = await db.documentinstance.find_unique(
            where={"id": instance_id}, include={"document": True}
        )
        return instance.model_dump() if instance else None

    async def list_instances(
        self, state: Optional[InstanceState] = None
    ) -> list[dict]:
        """List all instances, optionally filtered by state"""
        db = await get_db()

        where_clause = {"state": state} if state else {}

        instances = await db.documentinstance.find_many(
            where=where_clause,
            include={"document": True},
            order={"createdAt": "desc"},
        )

        return [inst.model_dump() for inst in instances]

    async def close_instance(self, instance_id: str) -> dict:
        """Close an instance"""
        db = await get_db()

        # Mark as closing
        instance = await db.documentinstance.update(
            where={"id": instance_id},
            data={"state": InstanceState.CLOSING},
        )

        # Simulate closing (in real impl: terminate LibreOffice process)
        asyncio.create_task(self._close_instance(instance_id))

        return instance.model_dump()

    async def _close_instance(self, instance_id: str):
        """Background task to close instance"""
        db = await get_db()

        try:
            await asyncio.sleep(1)  # Simulate graceful shutdown

            # Update to CLOSED state
            await db.documentinstance.update(
                where={"id": instance_id},
                data={
                    "state": InstanceState.CLOSED,
                    "closedAt": datetime.utcnow(),
                },
            )

            # Clean up in-memory tracking
            self.instances.pop(instance_id, None)

        except Exception as e:
            await db.documentinstance.update(
                where={"id": instance_id},
                data={
                    "state": InstanceState.ERROR,
                    "stateMessage": f"Failed to close: {str(e)}",
                },
            )

    async def delete_instance(self, instance_id: str):
        """Delete an instance record"""
        db = await get_db()
        await db.documentinstance.delete(where={"id": instance_id})

    async def use_instance(self, instance_id: str):
        """Mark instance as being used"""
        db = await get_db()
        await db.documentinstance.update(
            where={"id": instance_id},
            data={
                "state": InstanceState.IN_USE,
                "lastUsedAt": datetime.utcnow(),
            },
        )

    async def idle_instance(self, instance_id: str):
        """Mark instance as idle"""
        db = await get_db()
        await db.documentinstance.update(
            where={"id": instance_id},
            data={
                "state": InstanceState.IDLE,
                "lastUsedAt": datetime.utcnow(),
            },
        )


# Global instance manager
instance_manager = InstanceManager()
