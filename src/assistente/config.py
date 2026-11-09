"""Configurações centrais do Assistente/Jarvis."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


@dataclass
class Settings:
    pet_size: int = int(os.getenv("PET_SIZE", 128))
    gravity: float = float(os.getenv("PET_GRAVITY", 0.9))        # px/tick²
    walk_speed: float = float(os.getenv("PET_WALK_SPEED", 1.6))  # px/tick (~60 tick/s)
    sprite_path: Path | None = field(
        default_factory=lambda: next(
            (p for p in (ROOT / "assets" / "pet").glob("idle.*")), None
        )
    )
    # IA & Telegram (JARVIS remoto)
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_allowed_chat_id: str = os.getenv("TELEGRAM_ALLOWED_CHAT_ID", "")
