"""Memory store - persists problems, answers, and outcomes for learning."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

import aiosqlite

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """A single memory entry recording a problem-answer-outcome cycle."""

    id: Optional[int] = None
    timestamp: float = 0.0
    instruction: str = ""
    screen_text: str = ""
    agent_responses: str = ""  # JSON string of all agent responses
    selected_answer: str = ""
    selected_agent: str = ""
    confidence: float = 0.0
    outcome: str = ""  # "correct", "incorrect", "unknown"
    feedback: str = ""
    metadata: str = ""  # JSON string

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "instruction": self.instruction,
            "screen_text": self.screen_text[:200] if self.screen_text else "",
            "selected_answer": self.selected_answer,
            "selected_agent": self.selected_agent,
            "confidence": self.confidence,
            "outcome": self.outcome,
            "feedback": self.feedback,
        }


class MemoryStore:
    """SQLite-backed memory store for learning from past interactions."""

    def __init__(self, db_path: str = ""):
        self.db_path = db_path or settings.get_db_path()
        self._initialized = False

    async def initialize(self) -> None:
        """Create the database table if it doesn't exist."""
        if self._initialized:
            return

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    instruction TEXT NOT NULL,
                    screen_text TEXT DEFAULT '',
                    agent_responses TEXT DEFAULT '[]',
                    selected_answer TEXT DEFAULT '',
                    selected_agent TEXT DEFAULT '',
                    confidence REAL DEFAULT 0.0,
                    outcome TEXT DEFAULT 'unknown',
                    feedback TEXT DEFAULT '',
                    metadata TEXT DEFAULT '{}'
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_timestamp
                ON memory(timestamp DESC)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_outcome
                ON memory(outcome)
            """)
            await db.commit()

        self._initialized = True
        logger.info("Memory store initialized at %s", self.db_path)

    async def store(
        self,
        instruction: str,
        screen_text: str = "",
        agent_responses: list[dict] | None = None,
        selected_answer: str = "",
        selected_agent: str = "",
        confidence: float = 0.0,
        outcome: str = "unknown",
        feedback: str = "",
        metadata: dict | None = None,
    ) -> int:
        """Store a new memory entry. Returns the entry ID."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO memory
                    (timestamp, instruction, screen_text, agent_responses,
                     selected_answer, selected_agent, confidence, outcome,
                     feedback, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    time.time(),
                    instruction,
                    screen_text,
                    json.dumps(agent_responses or []),
                    selected_answer,
                    selected_agent,
                    confidence,
                    outcome,
                    feedback,
                    json.dumps(metadata or {}),
                ),
            )
            await db.commit()
            return cursor.lastrowid or 0

    async def update_outcome(
        self, entry_id: int, outcome: str, feedback: str = ""
    ) -> bool:
        """Update the outcome of a memory entry."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE memory SET outcome = ?, feedback = ? WHERE id = ?",
                (outcome, feedback, entry_id),
            )
            await db.commit()
            return True

    async def get_recent(self, limit: int = 20) -> list[MemoryEntry]:
        """Get the most recent memory entries."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM memory ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [self._row_to_entry(row) for row in rows]

    async def get_by_outcome(
        self, outcome: str, limit: int = 20
    ) -> list[MemoryEntry]:
        """Get memory entries filtered by outcome."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM memory WHERE outcome = ? ORDER BY timestamp DESC LIMIT ?",
                (outcome, limit),
            )
            rows = await cursor.fetchall()
            return [self._row_to_entry(row) for row in rows]

    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Search memory entries by instruction text."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM memory
                WHERE instruction LIKE ?
                ORDER BY timestamp DESC LIMIT ?
                """,
                (f"%{query}%", limit),
            )
            rows = await cursor.fetchall()
            return [self._row_to_entry(row) for row in rows]

    async def get_context_for_instruction(
        self, instruction: str, limit: int = 5
    ) -> str:
        """Build context string from past similar interactions.

        This helps agents learn from previous mistakes.
        """
        entries = await self.search(instruction, limit=limit)

        if not entries:
            return ""

        context_parts = ["Previous related interactions:"]
        for entry in entries:
            outcome_str = f" (outcome: {entry.outcome})" if entry.outcome != "unknown" else ""
            context_parts.append(
                f"- Q: {entry.instruction[:100]}\n"
                f"  A: {entry.selected_answer[:100]}{outcome_str}"
            )
            if entry.feedback:
                context_parts.append(f"  Feedback: {entry.feedback}")

        return "\n".join(context_parts)

    async def get_stats(self) -> dict:
        """Get memory statistics."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM memory")
            row = await cursor.fetchone()
            total = row[0] if row else 0

            cursor = await db.execute(
                "SELECT outcome, COUNT(*) FROM memory GROUP BY outcome"
            )
            rows = await cursor.fetchall()
            by_outcome = {row[0]: row[1] for row in rows}

            cursor = await db.execute(
                "SELECT AVG(confidence) FROM memory WHERE outcome = 'correct'"
            )
            row = await cursor.fetchone()
            avg_confidence_correct = row[0] if row and row[0] else 0.0

            return {
                "total_entries": total,
                "by_outcome": by_outcome,
                "avg_confidence_when_correct": round(avg_confidence_correct, 3),
            }

    async def clear(self) -> None:
        """Clear all memory entries."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM memory")
            await db.commit()

    @staticmethod
    def _row_to_entry(row) -> MemoryEntry:
        return MemoryEntry(
            id=row["id"],
            timestamp=row["timestamp"],
            instruction=row["instruction"],
            screen_text=row["screen_text"],
            agent_responses=row["agent_responses"],
            selected_answer=row["selected_answer"],
            selected_agent=row["selected_agent"],
            confidence=row["confidence"],
            outcome=row["outcome"],
            feedback=row["feedback"],
            metadata=row["metadata"],
        )
