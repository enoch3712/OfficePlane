"""
OfficePlane Configuration
"""
import os


class Config:
    """Application configuration"""

    # Driver Configuration
    DEFAULT_DRIVER_TYPE: str = os.getenv("OFFICEPLANE_DEFAULT_DRIVER", "libreoffice")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://officeplane:officeplane@db:5432/officeplane"
    )

    # API
    API_VERSION: str = os.getenv("OFFICEPLANE_VERSION", "0.2.0")


config = Config()
