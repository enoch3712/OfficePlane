---
name: detect-pii
description: Find PII (emails, phones, SSN, credit cards, IBANs, names, addresses, DOB) in an ingested document; return redaction plan
model: deepseek/deepseek-v4-flash
tier: flash
inputs:
  - name: document_id
    type: str
    required: true
  - name: categories
    type: list[str]
    required: false
    description: "Restrict to specific categories. Default: all. Valid: email, phone, us_ssn, credit_card, iban, person_name, address, dob, medical_id"
  - name: regex_only
    type: bool
    required: false
    description: "Skip the LLM pass — regex only. Faster but misses names/addresses."
  - name: max_findings
    type: int
    required: false
    description: "Cap on findings returned (default 200)"
outputs:
  - name: document_id
    type: str
  - name: title
    type: str
  - name: finding_count
    type: int
  - name: findings
    type: list[dict]
    description: "[{category, value, page_number, start, end, source: regex|llm, confidence, suggested_replacement}]"
  - name: category_counts
    type: dict
  - name: redaction_plan
    type: list[dict]
    description: "Spans suitable for feeding into the document-redact skill"
  - name: model
    type: str
---

# detect-pii

## Purpose

Scan an ingested document for sensitive personal information and return a structured
redaction plan. This skill is **read-only** — it does NOT mutate the document or its
pages. The redaction plan it returns is the input contract for the `document-redact`
skill, which applies the actual redactions.

This skill is critical for GDPR, HIPAA, and PCI-DSS compliance workflows.

## Two-pass detection

### Pass 1 — Regex (deterministic, cheap, no LLM)

Runs regex patterns against each page's text content to find well-shaped patterns:

| Category      | What it matches                                 | Confidence |
|---------------|-------------------------------------------------|------------|
| `email`       | Standard RFC-5321 email addresses               | 0.95       |
| `us_ssn`      | US Social Security Numbers (XXX-XX-XXXX)        | 0.95       |
| `iban`        | International Bank Account Numbers              | 0.95       |
| `phone`       | Phone numbers with optional country prefix      | 0.70       |
| `credit_card` | 13–19 digit card numbers with Luhn validation   | 0.85       |

### Pass 2 — LLM (contextual, catches harder cases)

Sends page text to DeepSeek to find patterns that regex cannot detect:

| Category      | What it matches                                  |
|---------------|--------------------------------------------------|
| `person_name` | Full names of natural persons (not institutions) |
| `address`     | Physical / postal addresses                      |
| `dob`         | Dates of birth                                   |
| `medical_id`  | Medical record numbers, patient IDs              |

The LLM pass deliberately skips emails, SSN, IBAN, phone, and credit cards — those
are already covered by the regex pass. Skip `regex_only: true` to bypass this pass.

## Categories vocabulary

Categories loosely follow GDPR Article 4 data-category vocabulary:

- `email` — online identifier
- `phone` — contact datum
- `us_ssn` — national identification number
- `credit_card` — financial data
- `iban` — financial data
- `person_name` — personal data (name)
- `address` — location data
- `dob` — demographic datum (date of birth)
- `medical_id` — health-related data (special category under GDPR Art. 9)

## Redaction plan

The `redaction_plan` output is a list of spans with `suggested_replacement` tokens:

```json
[
  {"page_number": 1, "value": "john.doe@example.com", "category": "email",
   "suggested_replacement": "[EMAIL]"},
  {"page_number": 1, "value": "John Doe", "category": "person_name",
   "suggested_replacement": "[PERSON]"}
]
```

Feed this list directly into `document-redact` to apply the redactions.

## When to use

- Pre-share compliance check before exporting a document to external parties.
- Automated GDPR right-to-erasure pipeline trigger.
- PCI audit: detect stored card numbers in uploaded files.
- HIPAA: locate patient names, DOBs, and medical IDs before cross-org sharing.

## Notes

- The LLM is instructed to be conservative (prefer lower confidence over false positives).
- Deduplication collapses duplicate (category, value, page) triples.
- `max_findings` caps the total returned (default 200, max 1000).
- `categories` filter applies to both regex and LLM passes.
