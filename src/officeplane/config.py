"""
OfficePlane Configuration
"""
import os


class Config:
    """Application configuration"""

    # Gotenberg — DOCX/HTML/MD → PDF conversion service
    GOTENBERG_URL: str = os.getenv("GOTENBERG_URL", "http://gotenberg:3000")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://officeplane:officeplane@db:5432/officeplane"
    )

    # API
    API_VERSION: str = os.getenv("OFFICEPLANE_VERSION", "0.2.0")

    # Instance manager driver type (used for document instance tracking, not PDF conversion)
    DEFAULT_DRIVER_TYPE: str = os.getenv("OFFICEPLANE_DEFAULT_DRIVER", "default")


config = Config()
