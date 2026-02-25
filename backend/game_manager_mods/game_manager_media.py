from pathlib import Path


def _find_media_by_name(self, media_dir: Path, game_name: str, media_type: str) -> str:
    if not media_dir.exists():
        return ""
    base = game_name.replace(" ", "_")
    pattern = f"{base}_{media_type}.*"
    matches = list(media_dir.glob(pattern))
    if not matches:
        return ""
    return matches[0].name


def _find_media_by_candidates(self, media_dir: Path, candidates, media_type: str) -> str:
    for name in candidates:
        if not name:
            continue
        found = self._find_media_by_name(media_dir, name, media_type)
        if found:
            return found
    return ""
