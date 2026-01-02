import os

# Set mock driver before any imports from officeplane
os.environ.setdefault("OFFICEPLANE_DRIVER", "mock")
os.environ.setdefault("OUTPUT_MODE", "inline")
