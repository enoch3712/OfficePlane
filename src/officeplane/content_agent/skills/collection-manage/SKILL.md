---
name: collection-manage
description: Create folders, move documents between folders, and manage ACL inheritance.
inputs:
  - name: action
    type: string
    required: true
    description: One of "create-folder", "move", "set-acl", or "list".
  - name: collection_id
    type: string
    required: false
    description: UUID of the target collection/folder. Required for "move", "set-acl", and "list".
  - name: document_id
    type: string
    required: false
    description: UUID of the Document to move. Required for "move".
  - name: acl
    type: object
    required: false
    description: "ACL patch object (e.g. {read: [...], write: [...]}). Required for set-acl."
outputs:
  - name: collection_id
    type: string
    description: UUID of the created or modified collection.
  - name: document_ids
    type: array
    description: List of Document UUIDs in the collection; populated for "list" action.
tools:
  - db-query
---

# collection-manage

## When to use
Use this skill to organize the document store: creating new folder hierarchies, relocating
documents after ingestion, or updating access permissions on a folder. It must be called
before documents are assigned to a collection during bulk-import workflows.

## How it works
- For "create-folder": insert a new collection record into the collections table via
  `db-query`; inherit parent ACL if a parent `collection_id` is supplied.
- For "move": update the `Document.collection_id` foreign key via `db-query`; validate
  the target collection exists first.
- For "set-acl": write the ACL patch to the collection's permissions column; propagate
  inherited permissions to all child `Document` rows via `db-query`.
- For "list": return all `Document` UUIDs and titles within the given `collection_id`.

## Audit
Emits one `ExecutionHistory` row with `event_type=DOCUMENT_EDITED` and `actor_type=agent`
for "create-folder", "move", and "set-acl". "list" is read-only and emits no row.
