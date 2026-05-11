---
sidebar_position: 6
title: "Source Trail: Provenance & Lineage"
---

# Source Trail: Provenance & Lineage

OfficePlane tracks two distinct but related graphs for every document: **provenance** (cross-document, "where did this content come from?") and **lineage** (intra-document, "how did this document evolve over time?"). Both graphs are returned together from `/api/documents/{id}/lineage`.

## The Two Graphs at a Glance

```
SOURCES                                         REVISION DAG
  doc_A ──┐                                     rev_0 (initial generation)
  doc_B ──┼──> DERIVATIONS ──> doc_C (generated)  │
  doc_D ──┘        │               │            rev_1 (edit: replace blk_02)
                   │               │               │
              [Provenance]    [Lineage]          rev_2 (edit: insert_after blk_05)
              cross-document  intra-document
```

---

## Provenance: Cross-Document "Where Did This Come From?"

Provenance answers: given a paragraph in `doc_C`, which source documents (and which sections of those documents) contributed to it, and what agent run produced the derivation?

The model is shaped after **W3C PROV-O** — the standard ontology for provenance information. Three concepts map directly:

| PROV-O term | OfficePlane equivalent | Description |
|-------------|----------------------|-------------|
| `prov:Entity` | `Document` / `Section` / `Block` | Any piece of content that can be cited |
| `prov:Activity` | `AgentRun` | A generation or edit job |
| `prov:Agent` | Skill name + model | The system that performed the activity |

### Derivation Model Fields

```json
{
  "id": "deriv_01j2kx",
  "generated_doc_id": "doc_C",
  "generated_section_id": "sec_01",
  "source_doc_id": "doc_A",
  "source_section_id": "sec_intro",
  "relationship": "derived_from",
  "agent_run_id": "run_abc",
  "skill_name": "synthesize-report",
  "model": "deepseek/deepseek-chat-v4-flash",
  "created_at": "2026-05-11T14:32:00Z"
}
```

`relationship` mirrors the `attributions` entries on the document (see [The Document Tree](/architecture/document-tree)). The derivation table is the normalized, queryable version of those same links.

---

## Lineage: Intra-Document Version History

Lineage answers: what sequence of edit operations produced the current state of `doc_C`, and what did it look like before each edit?

The model is a **commit DAG** — each revision points to its parent revision. A linear document history is a chain; merge operations produce a fork that can be visualized as a directed acyclic graph.

### DocumentRevision Model Fields

```json
{
  "id": "rev_02j3lz",
  "document_id": "doc_C",
  "parent_revision_id": "rev_01j2kx",
  "operation": "replace",
  "target_node_id": "blk_02",
  "patch": {
    "before": { "type": "paragraph", "content": "Draft text." },
    "after":  { "type": "paragraph", "content": "Final text, reviewed." }
  },
  "agent_run_id": "run_def",
  "skill_name": "document-edit",
  "created_at": "2026-05-11T15:10:00Z"
}
```

`patch` stores a minimal before/after diff at the node level. For large block types (`table`, `figure`), only the changed fields are stored rather than the full node snapshot.

The `operation` field corresponds to the five `document-edit` operations: `insert_after`, `insert_before`, `insert_as_child`, `replace`, `delete`. See [Editing Documents In Place](/features/editing-documents) for the full operation reference.

---

## Combined Lineage Endpoint

```bash
GET /api/documents/{id}/lineage
```

Returns both graphs in a single response:

```json
{
  "document_id": "doc_C",
  "provenance": {
    "derivations": [ { ...derivation... }, ... ]
  },
  "lineage": {
    "revisions": [ { ...revision... }, ... ],
    "head_revision_id": "rev_02j3lz"
  }
}
```

The UI renders this as two tabs: a **Provenance** graph (upstream source documents as nodes) and a **Revision DAG** (edit history as a timeline).

---

## Glossary

| Term | Definition | Standard |
|------|-----------|----------|
| **Provenance** | Record of the origins and history of data | [W3C PROV-O](https://www.w3.org/TR/prov-o/) |
| **Lineage** | Tracking of transformations applied to data over time | [OpenLineage](https://openlineage.io/) |
| **Entity / Activity / Agent** | Core PROV-O triple for any provenance statement | [W3C PROV-DM](https://www.w3.org/TR/prov-dm/) |
| **JSON-LD** | Linked Data encoding used to serialize PROV-O graphs | [JSON-LD 1.1](https://www.w3.org/TR/json-ld11/) |
| **CRDT / Automerge** | Conflict-free replicated data type; alternative merge strategy for concurrent edits | [Automerge](https://automerge.org/) |
| **Patch DAG** | Directed acyclic graph of patches (alternative to snapshot history) | [Pijul](https://pijul.org/), [Darcs](http://darcs.net/) |

The current implementation stores snapshot-style patches (`before`/`after` per node). A future migration may replace this with a patch DAG (Pijul/Darcs model) to enable efficient three-way merges across concurrent agent edits.
