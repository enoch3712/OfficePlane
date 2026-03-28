---
sidebar_position: 3
title: Set Up Document Hooks
---

# Set Up Document Hooks

Create your first automated hook — a legal compliance check that triggers whenever a contract section is edited.

## Create the Hook

```bash
curl -X POST http://localhost:8001/api/hooks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Legal clause review",
    "event": "section.updated",
    "scope": { "tags": ["legal", "contract"] },
    "agent_prompt": "Review the updated section for GDPR and SOC 2 compliance. Flag any liability risk.",
    "action": "flag",
    "priority": 1,
    "enabled": true
  }'
```

Now any edit to a section in a document tagged `legal` or `contract` will automatically trigger a compliance review agent. Results appear as flags on the document, and watchers receive an SSE notification.

See the full [Document Hooks](/docs/features/hooks) reference for scope filters, chaining, and all action types.
