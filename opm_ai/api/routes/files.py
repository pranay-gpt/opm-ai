"""Deck browse route: GET /api/files lists .DATA decks on the server.

Exists because the browser cannot hand over a real filesystem path. The old
Browse button read one .DATA through a file input and POSTed the text to
/api/decks, which wrote it alone into a fresh mkdtemp. Any deck with an
INCLUDE died there: the include/ tree stayed behind on the user's disk and
Flow stopped at the first missing .grdecl.

Listing decks server-side keeps the deck in its own directory, so the relative
INCLUDE paths resolve exactly as they do when flow is run by hand, and a 73 MB
include tree costs nothing to "select".
"""

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from opm_ai.api.paths import get_allowed_roots, validate_path

router = APIRouter()

# A deck directory holding a full case (model2 has ~60 .DATA variants) is the
# realistic upper bound; the cap only stops a scan of a pathological tree.
# Listing is one level deep, so there is no recursion depth to bound.
MAX_ENTRIES = 500


class DeckEntry(BaseModel):
    name: str
    path: str
    size: int
    has_includes: bool


class DeckListResponse(BaseModel):
    root: str
    parent: str | None
    roots: list[str]
    dirs: list[str]
    decks: list[DeckEntry]
    truncated: bool


def _browsable_roots() -> list[Path]:
    """Allowlisted directories that exist, deck libraries before the temp dir.

    get_allowed_roots() puts the system temp dir first because that is what
    /api/decks writes into, but landing the picker there would show scratch
    files instead of decks. Reorder for presentation only; membership is
    unchanged, so this cannot widen what validate_path accepts.
    """
    tmp = Path(tempfile.gettempdir()).resolve()
    existing = [r for r in get_allowed_roots() if r.is_dir()]
    return [r for r in existing if r != tmp] + [r for r in existing if r == tmp]


def _has_includes(deck: Path) -> bool:
    """True if the deck references INCLUDE, so the UI can flag it.

    Read as bytes with errors replaced: decks are ASCII by convention but a
    stray byte in a comment must not break the listing. Only the head is
    scanned since one hit is enough to answer the question.
    """
    try:
        with deck.open("rb") as fh:
            head = fh.read(256 * 1024)
    except OSError:
        return False
    # startswith, not `"INCLUDE" in line`: the latter would fire on a comment
    # mentioning the keyword ("-- INCLUDE the faults here"), and INCLUDE always
    # opens its own line in a deck.
    for line in head.decode("utf-8", "replace").splitlines():
        if line.lstrip().upper().startswith("INCLUDE"):
            return True
    return False


@router.get("/files", response_model=DeckListResponse)
async def list_decks(path: str | None = Query(default=None)) -> DeckListResponse:
    """List subdirectories and .DATA decks under an allowlisted directory.

    `path` is validated against the same allowlist as /api/run, so this cannot
    be walked outside the configured roots via '..' or a symlink.
    """
    roots = _browsable_roots()
    if not roots:
        raise HTTPException(status_code=404, detail="No deck directories are configured")

    if path is None:
        target = roots[0]
    else:
        try:
            target = validate_path(path, must_be_file=False, must_exist=True)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not target.is_dir():
            raise HTTPException(status_code=400, detail=f"Not a directory: {target}")

    # Only offer "up" while it stays inside an allowed root, so the UI cannot
    # walk to a parent the API would then refuse to list.
    parent: str | None = None
    if target.parent != target:
        try:
            validate_path(target.parent, must_be_file=False, must_exist=True)
            parent = str(target.parent)
        except ValueError:
            parent = None

    dirs: list[str] = []
    decks: list[DeckEntry] = []
    truncated = False

    try:
        entries = sorted(target.iterdir(), key=lambda p: p.name.lower())
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Cannot read {target}: {exc}") from exc

    for entry in entries:
        if entry.name.startswith("."):
            continue
        try:
            if entry.is_dir():
                dirs.append(entry.name)
            elif entry.name.upper().endswith(".DATA"):
                if len(decks) >= MAX_ENTRIES:
                    truncated = True
                    continue
                decks.append(
                    DeckEntry(
                        name=entry.name,
                        path=str(entry),
                        size=entry.stat().st_size,
                        has_includes=_has_includes(entry),
                    )
                )
        except OSError:
            # A broken symlink or an unreadable entry must not fail the listing.
            continue

    return DeckListResponse(
        root=str(target),
        parent=parent,
        roots=[str(r) for r in roots],
        dirs=dirs,
        decks=decks,
        truncated=truncated,
    )
