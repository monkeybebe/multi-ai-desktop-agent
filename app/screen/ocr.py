"""OCR processing module using Tesseract."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """Result of OCR processing."""

    full_text: str
    blocks: list[dict]  # list of {text, x, y, w, h, confidence}
    language: str = "eng"

    def to_dict(self) -> dict:
        return {
            "full_text": self.full_text,
            "blocks": self.blocks,
            "language": self.language,
        }


class OCRProcessor:
    """Processes images using Tesseract OCR."""

    def __init__(self, language: str = "eng"):
        self.language = language
        self._available: Optional[bool] = None

    @property
    def is_available(self) -> bool:
        """Check if Tesseract is available on the system."""
        if self._available is None:
            try:
                import pytesseract
                pytesseract.get_tesseract_version()
                self._available = True
            except Exception:
                logger.warning(
                    "Tesseract OCR is not installed. OCR features will be limited. "
                    "Install with: sudo apt-get install tesseract-ocr (Linux) "
                    "or brew install tesseract (macOS)"
                )
                self._available = False
        return self._available

    def extract_text(self, image: Image.Image) -> str:
        """Extract plain text from an image.

        Args:
            image: PIL Image to process

        Returns:
            Extracted text string
        """
        if not self.is_available:
            return ""

        try:
            import pytesseract
            text = pytesseract.image_to_string(image, lang=self.language)
            return text.strip()
        except Exception as e:
            logger.error("OCR text extraction failed: %s", e)
            return ""

    def extract_detailed(self, image: Image.Image) -> OCRResult:
        """Extract text with position data from an image.

        Returns OCRResult with text blocks including bounding boxes.
        """
        if not self.is_available:
            return OCRResult(full_text="", blocks=[])

        try:
            import pytesseract

            full_text = pytesseract.image_to_string(image, lang=self.language).strip()

            # Get detailed data with bounding boxes
            data = pytesseract.image_to_data(
                image, lang=self.language, output_type=pytesseract.Output.DICT
            )

            blocks = []
            n_boxes = len(data["text"])
            for i in range(n_boxes):
                text = data["text"][i].strip()
                conf = int(data["conf"][i])
                if text and conf > 30:  # filter low-confidence noise
                    blocks.append(
                        {
                            "text": text,
                            "x": data["left"][i],
                            "y": data["top"][i],
                            "w": data["width"][i],
                            "h": data["height"][i],
                            "confidence": conf,
                        }
                    )

            return OCRResult(
                full_text=full_text,
                blocks=blocks,
                language=self.language,
            )
        except Exception as e:
            logger.error("OCR detailed extraction failed: %s", e)
            return OCRResult(full_text="", blocks=[])
