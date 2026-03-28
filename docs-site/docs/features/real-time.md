---
sidebar_position: 6
title: Real-Time Updates
---

# Real-Time Updates

OfficePlane provides two real-time channels: **WebSocket** for dashboard updates and **SSE** (Server-Sent Events) for streaming long-running operations.

## WebSocket

The WebSocket connection at `/ws` delivers live events for the entire system:

```typescript
const ws = new WebSocket('ws://localhost:8001/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data.type, data.payload);
};
```

### Event Types

| Event | Payload | When |
|-------|---------|------|
| `instance_update` | Instance state change | Instance opened, closed, crashed |
| `task_update` | Task state change | Task queued, running, completed, failed |
| `document_uploaded` | Document metadata | New document ingested |
| `document_updated` | Document metadata | Document modified |
| `metrics_update` | CPU, memory, active count | Periodic system metrics |

### Auto-Reconnect

The frontend `useWebSocket` hook handles reconnection automatically:

```typescript
import { useWebSocket } from '@/hooks/useWebSocket';

function Dashboard() {
  const { isConnected, lastEvent } = useWebSocket({
    onEvent: (event) => {
      switch (event.type) {
        case 'task_update':
          refreshTaskList();
          break;
        case 'document_uploaded':
          refreshDocumentList();
          break;
      }
    },
  });

  return <div>Status: {isConnected ? 'Connected' : 'Reconnecting...'}</div>;
}
```

## Server-Sent Events (SSE)

SSE is used for streaming long-running operations — content generation, agent teams, and hook execution.

### Content Generation SSE

```bash
GET /api/generate/{job_id}/stream
```

```
event: start
data: {"job_id": "gen-123"}

event: delta
data: {"text": "Creating slide structure..."}

event: tool_call
data: {"tool": "pptxgenjs", "args": {...}}

event: tool_result
data: {"output": "Slide created"}

event: stop
data: {"document_id": "doc-456", "duration_ms": 42000}
```

### Team SSE

```bash
GET /api/teams/{team_id}/stream
```

```
event: team_started
data: {"num_teammates": 3}

event: task_claimed
data: {"teammate": "researcher", "task": "market analysis"}

event: task_completed
data: {"teammate": "researcher", "duration_ms": 15000}

event: team_completed
data: {"document_id": "doc-789"}
```

### Hook SSE

```
event: hook_triggered
data: {"hook_id": "hook-abc", "document_id": "doc-123"}

event: hook_delta
data: {"text": "Reviewing section for compliance..."}

event: hook_result
data: {"action": "flag", "findings": "Clause 3.2 may conflict with GDPR Article 17"}
```

## Architecture

SSE events flow through Redis pub/sub, decoupling workers from HTTP handlers:

```
┌──────────────┐     PUBLISH      ┌───────────────┐     SUBSCRIBE     ┌──────────────┐
│  Worker      │ ────────────────>│  Redis         │ <────────────────│  API Handler │
│  (agent)     │                  │  Pub/Sub       │                  │  (SSE)       │
└──────────────┘                  │                │                  └──────┬───────┘
                                  │  Channel:      │                         │
                                  │  officeplane:  │                         ▼
                                  │  sse:{job_id}  │                  ┌──────────────┐
                                  └───────────────┘                  │  Client      │
                                                                     │  (browser)   │
                                                                     └──────────────┘
```

This means:
- Workers don't need to know about HTTP connections
- Multiple clients can subscribe to the same job
- Events are buffered in Redis if the client temporarily disconnects

## Frontend Hook

The `useSSE` hook provides a React-friendly interface:

```typescript
import { useSSE } from '@/hooks/useSSE';

function GenerationView({ jobId }) {
  const { events, status, error } = useSSE({
    url: `/api/generate/${jobId}/stream`,
    onEvent: (event) => {
      if (event.type === 'stop') {
        loadDocument(event.data.document_id);
      }
    },
  });

  return (
    <div>
      {events.map((e, i) => (
        <div key={i}>{e.data.text || e.type}</div>
      ))}
    </div>
  );
}
```
