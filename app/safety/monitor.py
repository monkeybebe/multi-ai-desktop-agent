"""Safety monitor - enforces safety constraints and fail-safes."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable

logger = logging.getLogger(__name__)


class AutomationState(str, Enum):
    """Current state of automation."""

    INACTIVE = "inactive"
    ACTIVE = "active"
    PAUSED = "paused"
    EMERGENCY_STOPPED = "emergency_stopped"


@dataclass
class SafetyEvent:
    """A recorded safety event."""

    timestamp: float
    event_type: str  # "start", "stop", "pause", "resume", "emergency", "action"
    description: str
    details: dict

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "description": self.description,
            "details": self.details,
        }


class SafetyMonitor:
    """Monitors and enforces safety constraints for desktop automation."""

    def __init__(self) -> None:
        self.state = AutomationState.INACTIVE
        self._permission_granted = False
        self._events: list[SafetyEvent] = []
        self._action_count = 0
        self._max_actions_per_minute = 60
        self._action_timestamps: list[float] = []
        self._stop_callbacks: list[Callable] = []
        self._lock = threading.Lock()

    @property
    def is_automation_allowed(self) -> bool:
        """Check if automation actions are currently allowed."""
        return (
            self._permission_granted
            and self.state == AutomationState.ACTIVE
            and not self._is_rate_limited()
        )

    @property
    def permission_granted(self) -> bool:
        return self._permission_granted

    def grant_permission(self) -> None:
        """Grant permission for screen control (user must explicitly do this)."""
        self._permission_granted = True
        self._log_event("permission", "User granted automation permission", {})
        logger.info("Automation permission GRANTED by user")

    def revoke_permission(self) -> None:
        """Revoke screen control permission."""
        self._permission_granted = False
        self.state = AutomationState.INACTIVE
        self._log_event("permission", "User revoked automation permission", {})
        logger.info("Automation permission REVOKED")

    def start_automation(self) -> bool:
        """Start automation. Returns False if permission not granted."""
        if not self._permission_granted:
            logger.warning("Cannot start automation without permission")
            return False

        self.state = AutomationState.ACTIVE
        self._log_event("start", "Automation started", {})
        return True

    def pause_automation(self) -> None:
        """Pause automation temporarily."""
        self.state = AutomationState.PAUSED
        self._log_event("pause", "Automation paused", {})

    def resume_automation(self) -> bool:
        """Resume paused automation."""
        if not self._permission_granted:
            return False

        if self.state == AutomationState.PAUSED:
            self.state = AutomationState.ACTIVE
            self._log_event("resume", "Automation resumed", {})
            return True
        return False

    def emergency_stop(self) -> None:
        """Emergency stop - immediately halt all automation."""
        self.state = AutomationState.EMERGENCY_STOPPED
        self._log_event(
            "emergency", "EMERGENCY STOP activated", {"action_count": self._action_count}
        )
        logger.warning("EMERGENCY STOP - All automation halted")

        # Call all registered stop callbacks
        for callback in self._stop_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error("Error in emergency stop callback: %s", e)

    def register_stop_callback(self, callback: Callable) -> None:
        """Register a callback to be called on emergency stop."""
        self._stop_callbacks.append(callback)

    def record_action(self, action_type: str, description: str) -> bool:
        """Record an action and check if it's allowed.

        Returns True if the action is allowed, False if rate-limited or blocked.
        """
        if not self.is_automation_allowed:
            return False

        with self._lock:
            now = time.time()
            self._action_timestamps.append(now)
            # Clean up old timestamps (older than 60 seconds)
            self._action_timestamps = [
                t for t in self._action_timestamps if now - t < 60
            ]
            self._action_count += 1

        self._log_event(
            "action",
            description,
            {"action_type": action_type, "total_actions": self._action_count},
        )
        return True

    def get_status(self) -> dict:
        """Get current safety status."""
        return {
            "state": self.state.value,
            "permission_granted": self._permission_granted,
            "is_automation_allowed": self.is_automation_allowed,
            "total_actions": self._action_count,
            "actions_last_minute": len(
                [t for t in self._action_timestamps if time.time() - t < 60]
            ),
            "rate_limited": self._is_rate_limited(),
            "max_actions_per_minute": self._max_actions_per_minute,
        }

    def get_events(self, limit: int = 50) -> list[dict]:
        """Get recent safety events."""
        return [e.to_dict() for e in self._events[-limit:]]

    def _is_rate_limited(self) -> bool:
        """Check if we've exceeded the action rate limit."""
        now = time.time()
        recent_actions = [t for t in self._action_timestamps if now - t < 60]
        return len(recent_actions) >= self._max_actions_per_minute

    def _log_event(self, event_type: str, description: str, details: dict) -> None:
        """Log a safety event."""
        event = SafetyEvent(
            timestamp=time.time(),
            event_type=event_type,
            description=description,
            details=details,
        )
        self._events.append(event)

        # Keep only last 1000 events
        if len(self._events) > 1000:
            self._events = self._events[-500:]
