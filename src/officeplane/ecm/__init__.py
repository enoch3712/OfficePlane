"""
ECM (Agentic Enterprise Content Management) — atomic multi-agent sessions.

An ECMSession groups multiple skill jobs into a single atomic unit:
  - All jobs run concurrently in isolated staging workspaces
  - On success: outputs are moved atomically, results persisted together
  - On any failure: full rollback via compensation log

Usage:
    session = ECMSession()
    session.add_job("generate-pptx-quality", {"prompt": "Q4 review"})
    session.add_job("generate-docx-styled", {"prompt": "Executive summary"})
    result = await session.commit()   # atomic — both succeed or both roll back
"""

from officeplane.ecm.session import ECMSession, SessionState, SessionResult  # noqa: F401
