"""Configuration management for WA/D."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    # General
    app_name: str = "WA/D - Wisdom Assistor/Distributor"
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    data_dir: str = str(Path.home() / ".wad")

    # API Keys (users supply their own)
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    microsoft_api_key: str = ""

    # Model selection
    openai_model: str = "gpt-4o"
    anthropic_model: str = "claude-sonnet-4-20250514"
    gemini_model: str = "gemini-1.5-pro"

    # Screen capture settings
    capture_interval: float = 2.0  # seconds between auto-captures
    ocr_enabled: bool = True

    # Safety
    automation_enabled: bool = False
    failsafe_hotkey: str = "ctrl+shift+escape"
    require_permission_for_actions: bool = True

    # Memory
    max_memory_entries: int = 1000
    db_path: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    def get_db_path(self) -> str:
        if self.db_path:
            return self.db_path
        os.makedirs(self.data_dir, exist_ok=True)
        return str(Path(self.data_dir) / "wad_memory.db")


settings = Settings()
