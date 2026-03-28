"""
Agent Teams — coordinated multi-agent work on documents.

Implements the Agent Teams pattern:
- Team Lead decomposes work into a shared task list
- Teammates claim tasks, work independently, communicate directly
- Redis backs the shared task list, mailbox, and coordination
"""
