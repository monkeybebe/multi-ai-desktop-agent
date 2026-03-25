"""Screen capture module using mss."""

from __future__ import annotations

import base64
import io
import logging
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)


class ScreenCapture:
    """Captures screenshots of the user's desktop."""

    def __init__(self) -> None:
        self._mss_instance = None
        self._permission_granted = False

    @property
    def has_permission(self) -> bool:
        return self._permission_granted

    def grant_permission(self) -> None:
        """Grant screen capture permission."""
        self._permission_granted = True

    def revoke_permission(self) -> None:
        """Revoke screen capture permission."""
        self._permission_granted = False
        self._close()

    def _get_mss(self):
        """Lazy-import and create mss instance."""
        if self._mss_instance is None:
            try:
                import mss
                self._mss_instance = mss.mss()
            except Exception as e:
                logger.error("Failed to initialize screen capture: %s", e)
                raise RuntimeError(
                    "Screen capture unavailable. Ensure you have a display connected "
                    "or are running in a supported environment."
                ) from e
        return self._mss_instance

    def list_monitors(self) -> list[dict]:
        """List all available monitors.

        Returns:
            List of monitor info dicts with index, width, height, left, top
        """
        try:
            sct = self._get_mss()
            monitors = sct.monitors
            result = []
            for i, mon in enumerate(monitors):
                label = "All Monitors Combined" if i == 0 else f"Monitor {i}"
                result.append({
                    "index": i,
                    "label": label,
                    "width": mon["width"],
                    "height": mon["height"],
                    "left": mon["left"],
                    "top": mon["top"],
                })
            return result
        except Exception as e:
            logger.error("Failed to list monitors: %s", e)
            return [{"index": 0, "label": "Default (All)", "width": 0, "height": 0, "left": 0, "top": 0}]

    def _close(self) -> None:
        if self._mss_instance is not None:
            try:
                self._mss_instance.close()
            except Exception:
                pass
            self._mss_instance = None

    def capture_full_screen(self, monitor_index: int = 0) -> Optional[Image.Image]:
        """Capture the full screen (or a specific monitor).

        Args:
            monitor_index: 0 for all monitors combined, 1+ for specific monitors

        Returns:
            PIL Image of the screenshot, or None if capture fails
        """
        if not self._permission_granted:
            logger.warning("Screen capture attempted without permission")
            return None

        try:
            sct = self._get_mss()
            monitors = sct.monitors
            if monitor_index >= len(monitors):
                monitor_index = 0
            monitor = monitors[monitor_index]
            screenshot = sct.grab(monitor)
            return Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        except Exception as e:
            logger.error("Screen capture failed: %s", e)
            return None

    def capture_region(
        self, left: int, top: int, width: int, height: int
    ) -> Optional[Image.Image]:
        """Capture a specific region of the screen."""
        if not self._permission_granted:
            return None

        try:
            sct = self._get_mss()
            region = {"left": left, "top": top, "width": width, "height": height}
            screenshot = sct.grab(region)
            return Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        except Exception as e:
            logger.error("Region capture failed: %s", e)
            return None

    @staticmethod
    def image_to_base64(image: Image.Image, max_size: int = 1920) -> str:
        """Convert PIL Image to base64 string, resizing if needed.

        Args:
            image: PIL Image to convert
            max_size: Maximum dimension (width or height) before resize

        Returns:
            Base64-encoded PNG string
        """
        # Resize if too large to save on API costs
        w, h = image.size
        if w > max_size or h > max_size:
            ratio = max_size / max(w, h)
            new_size = (int(w * ratio), int(h * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    @staticmethod
    def base64_to_image(b64_string: str) -> Image.Image:
        """Convert base64 string back to PIL Image."""
        data = base64.b64decode(b64_string)
        return Image.open(io.BytesIO(data))
