---
name: document-export
description: Render a document to a requested output format and return a download path.
inputs:
  - name: document_id
    type: string
    required: true
    description: UUID of the Document to export.
  - name: format
    type: string
    required: true
    description: Output format — one of "docx", "pdf", "pptx", or "html".
  - name: version
    type: integer
    required: false
    description: Version number to export. Defaults to current version.
outputs:
  - name: export_path
    type: string
    description: Filesystem or object-store path to the rendered output file.
  - name: export_size_bytes
    type: integer
    description: Size of the exported file in bytes.
tools:
  - file-render
---

# document-export

## When to use
Use this skill when the user explicitly requests a file download or asks to convert a
document to a specific format. It should always be the last skill in a chain — run
`document-redact` first if a sanitized version is needed.

## How it works
- Load the `Document`, `Chapter`, `Section`, and `Page` rows (for the requested version
  via `DocumentInstance` if specified) from the DB to reconstruct content.
- Pass the reconstructed content and target format to `file-render`, which calls
  LibreOffice or the HTML renderer as appropriate.
- Store the output path and file size; optionally create a `DocumentInstance` row that
  records the exported artifact for later retrieval.

## Audit
Emits one `ExecutionHistory` row with `event_type=DOCUMENT_EXPORTED` and `actor_type=agent`
after the rendered file is confirmed written.
