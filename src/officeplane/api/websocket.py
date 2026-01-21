"""WebSocket endpoint for real-time updates"""
import asyncio
import json
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime


class ConnectionManager:
    """Manages WebSocket connections and broadcasts"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"[WebSocket] Client connected. Total connections: {len(self.active_connections)}")

        # Send initial connection message
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "timestamp": datetime.now().isoformat(),
            "message": "Connected to OfficePlane"
        })

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        self.active_connections.discard(websocket)
        print(f"[WebSocket] Client disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients"""
        if not self.active_connections:
            return

        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"[WebSocket] Error broadcasting to client: {e}")
                disconnected.add(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

    async def send_personal(self, message: dict, websocket: WebSocket):
        """Send a message to a specific client"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"[WebSocket] Error sending personal message: {e}")
            self.disconnect(websocket)


# Global connection manager instance
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint handler"""
    await manager.connect(websocket)

    try:
        # Send a heartbeat every 30 seconds to keep connection alive
        async def heartbeat():
            while True:
                try:
                    await asyncio.sleep(30)
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": datetime.now().isoformat()
                    })
                except Exception:
                    break

        # Start heartbeat task
        heartbeat_task = asyncio.create_task(heartbeat())

        # Listen for messages from client
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)

                # Handle ping/pong for connection health
                if message.get("type") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    })
                else:
                    # Echo other messages back (for debugging)
                    await websocket.send_json({
                        "type": "echo",
                        "data": message,
                        "timestamp": datetime.now().isoformat()
                    })
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON",
                    "timestamp": datetime.now().isoformat()
                })

    except WebSocketDisconnect:
        print("[WebSocket] Client disconnected normally")
    except Exception as e:
        print(f"[WebSocket] Error: {e}")
    finally:
        heartbeat_task.cancel()
        manager.disconnect(websocket)


async def broadcast_task_event(task_id: str, event_type: str, data: dict = None):
    """Broadcast a task-related event to all connected clients"""
    await manager.broadcast({
        "type": "task",
        "event": event_type,
        "taskId": task_id,
        "data": data or {},
        "timestamp": datetime.now().isoformat()
    })


async def broadcast_document_event(document_id: str, event_type: str, data: dict = None):
    """Broadcast a document-related event to all connected clients"""
    await manager.broadcast({
        "type": "document",
        "event": event_type,
        "documentId": document_id,
        "data": data or {},
        "timestamp": datetime.now().isoformat()
    })


async def broadcast_system_event(event_type: str, data: dict = None):
    """Broadcast a system-level event to all connected clients"""
    await manager.broadcast({
        "type": "system",
        "event": event_type,
        "data": data or {},
        "timestamp": datetime.now().isoformat()
    })
