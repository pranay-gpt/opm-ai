"""Deck save route: POST /api/decks writes deck text to a temp .DATA file.

Enables the UI to lint/run decks that exist only in the browser (built or
edited text): save first, then pass the returned path to /api/lint or
/api/run. Files land in a fresh mkdtemp under the system temp dir, which is
already in the path-validation allowlist.
"""

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

MAX_DECK_BYTES = 2 * 1024 * 1024


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
    if Path(name).name != name or not name.endswith(".DATA"):
        raise HTTPException(
            status_code=400, detail="filename must be a bare name ending in .DATA"
        )

    out_dir = Path(tempfile.mkdtemp(prefix="opmai_deck_"))
    deck_path = out_dir / name
    deck_path.write_text(request.content)
    return DeckSaveResponse(deck_path=str(deck_path))
