"""Models for August Access."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AccessCode:
    """Seam Access Code."""

    access_code_id: str
    user_name: str
    status: str
    access_code: str
    is_managed: bool = field(default=False)
    starts_at: datetime | None = field(default=None)
    ends_at: datetime | None = field(default=None)
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
