"""Models for August Access."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from .const import ACCESS_CODE_STATUS


@dataclass
class AccessCode:
    """Seam Access Code."""

    access_code_id: UUID
    user_name: str
    status: ACCESS_CODE_STATUS
    access_code: str
    is_managed: bool = field(default=False)
    starts_at: datetime | None = field(default=None)
    ends_at: datetime | None = field(default=None)
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
