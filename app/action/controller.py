"""Action Controller - desktop automation via PyAutoGUI."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """Types of desktop actions."""

    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    MOVE = "move"
    TYPE = "type"
    HOTKEY = "hotkey"
    SCROLL = "scroll"
    DRAG = "drag"


@dataclass
class ActionResult:
    """Result of a desktop action."""

    success: bool
    action_type: str
    description: str
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "action_type": self.action_type,
            "description": self.description,
            "error": self.error,
        }


class ActionController:
    """Controls desktop interactions using PyAutoGUI."""

    def __init__(self) -> None:
        self._enabled = False
        self._paused = False
        self._pyautogui = None
        self._action_log: list[ActionResult] = []

    @property
    def is_enabled(self) -> bool:
        return self._enabled and not self._paused

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def action_log(self) -> list[ActionResult]:
        return self._action_log

    def enable(self) -> None:
        """Enable automation (requires user consent)."""
        self._enabled = True
        self._setup_pyautogui()
        logger.info("Action controller ENABLED")

    def disable(self) -> None:
        """Disable all automation."""
        self._enabled = False
        logger.info("Action controller DISABLED")

    def pause(self) -> None:
        """Pause automation temporarily."""
        self._paused = True
        logger.info("Action controller PAUSED")

    def resume(self) -> None:
        """Resume automation."""
        self._paused = False
        logger.info("Action controller RESUMED")

    def emergency_stop(self) -> None:
        """Emergency stop - immediately disable all automation."""
        self._enabled = False
        self._paused = True
        logger.warning("EMERGENCY STOP activated")

    def _setup_pyautogui(self) -> None:
        """Configure PyAutoGUI with safety settings."""
        try:
            import pyautogui

            pyautogui.FAILSAFE = True  # Move mouse to corner to abort
            pyautogui.PAUSE = 0.1  # Small delay between actions
            self._pyautogui = pyautogui
        except ImportError:
            logger.error(
                "PyAutoGUI not available. Install with: pip install pyautogui"
            )
            self._enabled = False

    def _check_enabled(self) -> Optional[ActionResult]:
        """Check if actions are allowed. Returns error result if not."""
        if not self._enabled:
            return ActionResult(
                success=False,
                action_type="check",
                description="Automation is disabled",
                error="Enable automation in settings first",
            )
        if self._paused:
            return ActionResult(
                success=False,
                action_type="check",
                description="Automation is paused",
                error="Resume automation to continue",
            )
        if self._pyautogui is None:
            return ActionResult(
                success=False,
                action_type="check",
                description="PyAutoGUI not available",
                error="PyAutoGUI is not installed",
            )
        return None

    def click(self, x: int, y: int, button: str = "left") -> ActionResult:
        """Click at a specific screen position."""
        check = self._check_enabled()
        if check:
            return check

        try:
            self._pyautogui.click(x=x, y=y, button=button)
            result = ActionResult(
                success=True,
                action_type=ActionType.CLICK,
                description=f"Clicked ({button}) at ({x}, {y})",
            )
        except Exception as e:
            result = ActionResult(
                success=False,
                action_type=ActionType.CLICK,
                description=f"Failed to click at ({x}, {y})",
                error=str(e),
            )

        self._action_log.append(result)
        return result

    def double_click(self, x: int, y: int) -> ActionResult:
        """Double-click at a specific position."""
        check = self._check_enabled()
        if check:
            return check

        try:
            self._pyautogui.doubleClick(x=x, y=y)
            result = ActionResult(
                success=True,
                action_type=ActionType.DOUBLE_CLICK,
                description=f"Double-clicked at ({x}, {y})",
            )
        except Exception as e:
            result = ActionResult(
                success=False,
                action_type=ActionType.DOUBLE_CLICK,
                description=f"Failed to double-click at ({x}, {y})",
                error=str(e),
            )

        self._action_log.append(result)
        return result

    def right_click(self, x: int, y: int) -> ActionResult:
        """Right-click at a specific position."""
        check = self._check_enabled()
        if check:
            return check

        try:
            self._pyautogui.rightClick(x=x, y=y)
            result = ActionResult(
                success=True,
                action_type=ActionType.RIGHT_CLICK,
                description=f"Right-clicked at ({x}, {y})",
            )
        except Exception as e:
            result = ActionResult(
                success=False,
                action_type=ActionType.RIGHT_CLICK,
                description=f"Failed to right-click at ({x}, {y})",
                error=str(e),
            )

        self._action_log.append(result)
        return result

    def move_to(self, x: int, y: int, duration: float = 0.3) -> ActionResult:
        """Move mouse to a specific position."""
        check = self._check_enabled()
        if check:
            return check

        try:
            self._pyautogui.moveTo(x=x, y=y, duration=duration)
            result = ActionResult(
                success=True,
                action_type=ActionType.MOVE,
                description=f"Moved mouse to ({x}, {y})",
            )
        except Exception as e:
            result = ActionResult(
                success=False,
                action_type=ActionType.MOVE,
                description=f"Failed to move mouse to ({x}, {y})",
                error=str(e),
            )

        self._action_log.append(result)
        return result

    def type_text(self, text: str, interval: float = 0.02) -> ActionResult:
        """Type text at the current cursor position."""
        check = self._check_enabled()
        if check:
            return check

        try:
            self._pyautogui.typewrite(text, interval=interval)
            result = ActionResult(
                success=True,
                action_type=ActionType.TYPE,
                description=f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}",
            )
        except Exception as e:
            result = ActionResult(
                success=False,
                action_type=ActionType.TYPE,
                description="Failed to type text",
                error=str(e),
            )

        self._action_log.append(result)
        return result

    def press_hotkey(self, *keys: str) -> ActionResult:
        """Press a keyboard shortcut (e.g., 'ctrl', 'c')."""
        check = self._check_enabled()
        if check:
            return check

        try:
            self._pyautogui.hotkey(*keys)
            result = ActionResult(
                success=True,
                action_type=ActionType.HOTKEY,
                description=f"Pressed hotkey: {'+'.join(keys)}",
            )
        except Exception as e:
            result = ActionResult(
                success=False,
                action_type=ActionType.HOTKEY,
                description=f"Failed to press hotkey: {'+'.join(keys)}",
                error=str(e),
            )

        self._action_log.append(result)
        return result

    def scroll(self, clicks: int, x: int | None = None, y: int | None = None) -> ActionResult:
        """Scroll at current or specified position.

        Args:
            clicks: Positive = up, negative = down
            x, y: Optional position to scroll at
        """
        check = self._check_enabled()
        if check:
            return check

        try:
            kwargs = {"clicks": clicks}
            if x is not None:
                kwargs["x"] = x
            if y is not None:
                kwargs["y"] = y
            self._pyautogui.scroll(**kwargs)
            direction = "up" if clicks > 0 else "down"
            result = ActionResult(
                success=True,
                action_type=ActionType.SCROLL,
                description=f"Scrolled {direction} {abs(clicks)} clicks",
            )
        except Exception as e:
            result = ActionResult(
                success=False,
                action_type=ActionType.SCROLL,
                description="Failed to scroll",
                error=str(e),
            )

        self._action_log.append(result)
        return result

    def drag_to(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: float = 0.5,
    ) -> ActionResult:
        """Drag from one position to another."""
        check = self._check_enabled()
        if check:
            return check

        try:
            self._pyautogui.moveTo(start_x, start_y)
            self._pyautogui.drag(
                end_x - start_x, end_y - start_y, duration=duration
            )
            result = ActionResult(
                success=True,
                action_type=ActionType.DRAG,
                description=f"Dragged from ({start_x},{start_y}) to ({end_x},{end_y})",
            )
        except Exception as e:
            result = ActionResult(
                success=False,
                action_type=ActionType.DRAG,
                description="Failed to drag",
                error=str(e),
            )

        self._action_log.append(result)
        return result

    def get_mouse_position(self) -> tuple[int, int]:
        """Get current mouse position."""
        if self._pyautogui:
            pos = self._pyautogui.position()
            return (pos.x, pos.y)
        return (0, 0)

    def get_screen_size(self) -> tuple[int, int]:
        """Get screen dimensions."""
        if self._pyautogui:
            size = self._pyautogui.size()
            return (size.width, size.height)
        return (0, 0)
