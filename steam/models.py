from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AchievementMeta:
    """Canonical Steam achievement metadata."""

    name: str
    display_name: str
    description: str
    hidden: bool
    icon: str
    icongray: str


@dataclass(slots=True)
class AchievementState:
    """Canonical user unlock/progress state."""

    achieved: bool
    cur_progress: int
    max_progress: int
    unlock_time: int


@dataclass(slots=True)
class GameSchema:
    """Canonical game schema payload."""

    appid: str
    name: str
    img: dict[str, str] = field(default_factory=dict)
    achievements: list[AchievementMeta] = field(default_factory=list)


@dataclass(slots=True)
class MergedAchievement:
    """Merged achievement row used by UI."""

    name: str
    display_name: str
    description: str
    hidden: bool
    icon: str
    icongray: str
    achieved: bool
    cur_progress: int
    max_progress: int
    unlock_time: int


@dataclass(slots=True)
class MergedGame:
    """Merged schema + state for one game."""

    appid: str
    name: str
    img: dict[str, str]
    achievements: list[MergedAchievement]
    unlocked: int
    total: int


@dataclass(slots=True)
class UnlockEvent:
    """Transition event for one newly unlocked achievement."""

    appid: str
    game: str
    achievement: str
    description: str
    unlock_time: int
    icon_path: str = ""


@dataclass(slots=True)
class SteamCandidate:
    """Discovered Steam stats tuple."""

    appid: str
    steam_user: str
    stats_file: Path


def to_dict(obj: Any) -> dict[str, Any]:
    """Serialize dataclass instance to dict."""

    return asdict(obj)
