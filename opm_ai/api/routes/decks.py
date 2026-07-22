"""Deck save route: POST /api/decks writes deck text to a temp .DATA file.

Enables the UI to lint/run decks that exist only in the browser (built or
edited text): save first, then pass the returned path to /api/lint or
/api/run. Files land in a fresh mkdtemp under the system temp dir, which is
already in the path-validation allowlist. Stale dirs are swept on each save.
"""

import shutil
import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

MAX_DECK_BYTES = 2 * 1024 * 1024
DECK_DIR_TTL_S = 3600


def _sweep_stale_deck_dirs() -> None:
    # ponytail: sweep-on-write, no janitor thread; add one if save volume grows
    cutoff = time.time() - DECK_DIR_TTL_S
    for d in Path(tempfile.gettempdir()).glob("opmai_deck_*"):
        try:
            if d.is_dir() and d.stat().st_mtime < cutoff:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass


class DeckSaveRequest(BaseModel):
    content: str
    filename: str | None = None


class DeckSaveResponse(BaseModel):
    deck_path: str


@router.post("/decks", response_model=DeckSaveResponse)
async def save_deck(request: DeckSaveRequest) -> DeckSaveResponse:
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="content is empty")
    if len(request.content.encode()) > MAX_DECK_BYTES:
        raise HTTPException(status_code=413, detail="deck exceeds 2MB limit")

    name = request.filename or "DECK.DATA"
    if Path(name).name != name or "\\" in name or not name.endswith(".DATA"):
        raise HTTPException(
            status_code=400, detail="filename must be a bare name ending in .DATA"
        )

    _sweep_stale_deck_dirs()
    out_dir = Path(tempfile.mkdtemp(prefix="opmai_deck_"))
    deck_path = out_dir / name
    deck_path.write_text(request.content, encoding="utf-8")
    return DeckSaveResponse(deck_path=str(deck_path))
