"""Screen state parser - builds structured representation of screen content."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from PIL import Image

from app.screen.capture import ScreenCapture
from app.screen.ocr import OCRProcessor, OCRResult

logger = logging.getLogger(__name__)


@dataclass
class ScreenState:
    """Structured representation of the current screen."""

    timestamp: float
    image_b64: str = ""
    ocr_result: Optional[OCRResult] = None
    width: int = 0
    height: int = 0
    monitor_index: int = 0

    @property
    def text(self) -> str:
        if self.ocr_result:
            return self.ocr_result.full_text
        return ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "has_image": bool(self.image_b64),
            "text": self.text,
            "width": self.width,
            "height": self.height,
            "ocr_blocks": self.ocr_result.blocks if self.ocr_result else [],
        }


class ScreenParser:
    """Parses screen content into structured data."""

    def __init__(self, ocr_enabled: bool = True):
        self.capture = ScreenCapture()
        self.ocr = OCRProcessor()
        self.ocr_enabled = ocr_enabled
        self._last_state: Optional[ScreenState] = None

    @property
    def last_state(self) -> Optional[ScreenState]:
        return self._last_state

    def grant_permission(self) -> None:
        """Grant screen capture permission."""
        self.capture.grant_permission()

    def revoke_permission(self) -> None:
        """Revoke screen capture permission."""
        self.capture.revoke_permission()

    def parse_screen(self, monitor_index: int = 0) -> ScreenState:
        """Capture and parse the current screen.

        Args:
            monitor_index: Which monitor to capture (0 = all)

        Returns:
            ScreenState with image and OCR data
        """
        image = self.capture.capture_full_screen(monitor_index)

        if image is None:
            return ScreenState(
                timestamp=time.time(),
                monitor_index=monitor_index,
            )

        width, height = image.size
        image_b64 = ScreenCapture.image_to_base64(image)

        ocr_result = None
        if self.ocr_enabled and self.ocr.is_available:
            ocr_result = self.ocr.extract_detailed(image)

        state = ScreenState(
            timestamp=time.time(),
            image_b64=image_b64,
            ocr_result=ocr_result,
            width=width,
            height=height,
            monitor_index=monitor_index,
        )

        self._last_state = state
        return state

    def parse_image(self, image: Image.Image) -> ScreenState:
        """Parse an already-captured image (e.g., uploaded by user).

        Args:
            image: PIL Image to parse

        Returns:
            ScreenState with image and OCR data
        """
        width, height = image.size
        image_b64 = ScreenCapture.image_to_base64(image)

        ocr_result = None
        if self.ocr_enabled and self.ocr.is_available:
            ocr_result = self.ocr.extract_detailed(image)

        state = ScreenState(
            timestamp=time.time(),
            image_b64=image_b64,
            ocr_result=ocr_result,
            width=width,
            height=height,
        )

        self._last_state = state
        return state
