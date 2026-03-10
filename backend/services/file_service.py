"""
File service — handles deck export and version management.

Saves versioned JSON files to the configured export directory.
Filenames follow the pattern: {slug}_{YYYYMMDD}_{HHMMSS}_v{version}.json
"""
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiofiles
import aiofiles.os

from backend.schemas.output import DeckEnvelope
from backend.config.settings import get_settings

settings = get_settings()


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug (max 50 chars)."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    result = text[:50].rstrip("-")
    return result if result else "deck"


def _get_export_dir() -> Path:
    """Return the export directory, creating it if it doesn't exist."""
    export_dir = Path(settings.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir


async def save_deck(session_id: str, deck_envelope: DeckEnvelope) -> dict:
    """Save a deck envelope as a versioned JSON file.

    Filename format: {slug}_{YYYYMMDD}_{HHMMSS}_v{version}.json

    Version is auto-incremented: if 2 files already exist for this slug,
    the new file will be _v3.

    Args:
        session_id: Session identifier (used as fallback slug).
        deck_envelope: The DeckEnvelope to serialize and save.

    Returns:
        Dict with filename, filepath, version, saved_at, size_bytes.
    """
    export_dir = _get_export_dir()

    title = (deck_envelope.deck.title if deck_envelope.deck else None) or session_id
    slug = _slugify(title)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # Auto-increment version
    existing = list(export_dir.glob(f"{slug}_*_v*.json"))
    version = len(existing) + 1

    filename = f"{slug}_{timestamp}_v{version}.json"
    filepath = export_dir / filename

    deck_json = deck_envelope.model_dump_json(indent=2)

    async with aiofiles.open(filepath, mode="w", encoding="utf-8") as f:
        await f.write(deck_json)

    return {
        "filename": filename,
        "filepath": str(filepath),
        "version": version,
        "saved_at": datetime.utcnow().isoformat(),
        "size_bytes": len(deck_json.encode("utf-8")),
    }


async def load_deck(filepath: str) -> Optional[DeckEnvelope]:
    """Load a DeckEnvelope from a saved JSON file.

    Args:
        filepath: Absolute or relative path to the JSON file.

    Returns:
        Parsed DeckEnvelope, or None if file does not exist.
    """
    path = Path(filepath)
    if not path.exists():
        return None
    async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
        content = await f.read()
    return DeckEnvelope.model_validate_json(content)


async def list_versions(
    session_id: str,
    title_slug: Optional[str] = None,
) -> list[dict]:
    """List all exported deck versions, optionally filtered by title slug.

    Args:
        session_id: Session identifier (currently unused for filtering but
                    included for future per-session storage).
        title_slug: If provided, filter to files matching this slug prefix.

    Returns:
        List of version dicts sorted by modification time (newest first).
        Each dict has: filename, filepath, version, saved_at, size_bytes.
    """
    export_dir = _get_export_dir()

    if title_slug:
        pattern = f"{_slugify(title_slug)}_*_v*.json"
    else:
        pattern = "*_v*.json"

    files = sorted(
        export_dir.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    versions: list[dict] = []
    for f in files:
        try:
            # Parse version number from filename: slug_YYYYMMDD_HHMMSS_v{N}.json
            parts = f.stem.rsplit("_v", 1)
            version = int(parts[1]) if len(parts) == 2 else 0
            stat = f.stat()
            versions.append(
                {
                    "filename": f.name,
                    "filepath": str(f),
                    "version": version,
                    "saved_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "size_bytes": stat.st_size,
                }
            )
        except (ValueError, IndexError, OSError):
            continue

    return versions
