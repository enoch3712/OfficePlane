from abc import ABC, abstractmethod

class OfficeDriver(ABC):
    """Convert an Office document to PDF bytes."""
    @abstractmethod
    def convert_to_pdf(self, filename: str, input_bytes: bytes) -> bytes:
        raise NotImplementedError
