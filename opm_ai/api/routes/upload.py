"""Deck upload route: POST /api/upload_deck.

Accepts a multipart upload with a .DATA deck file and an optional
sibling include/ folder. Writes everything into a fresh
``tempfile.mkdtemp`` directory and returns the deck's server-side
path so the existing ``/api/run`` flow works unchanged.

Why this route exists alongside ``/api/files`` (DeckPicker):

``/api/files`` is the right tool when the deck is already on the
server - selecting a path keeps the deck among its own siblings,
where its relative INCLUDE paths resolve exactly as they do when
flow is run by hand. ``/api/upload_deck`` is the right tool when
the user has the deck on their laptop and wants to push it to a
remote server (or a fresh container) without an out-of-band
``scp`` step. Both flows converge on the same wire contract:
``/api/run`` only cares about a real path on the server, not how
it got there.

Security model:

  - Uploads go to ``tempfile.mkdtemp(prefix="opm_ai_upload_")``,
    which is inside the system temp dir and therefore inside
    ``get_allowed_roots()``. The returned ``deck_path`` passes
    ``validate_deck_path`` for the same reason a DeckPicker path
    does.

  - The ``include`` parts' relative paths are sanitised: any
    absolute path, ``..`` component, or path that resolves
    outside the per-upload include/ dir is rejected with 400. A
    malicious client cannot escape the upload dir.

  - ``max_part_size`` is bumped to 256 MB and ``max_files`` to
    5000 because some ``.grdecl`` include files in model2 are
    30-50 MB and the include tree itself is ~73 MB across 1000+
    files. Starlette's defaults (1 MB / 1000) would reject any
    non-trivial deck.

  - The route is wired through the Vite dev proxy and the
    production reverse proxy the same as the other JSON routes;
    no CORS or size-limit changes needed.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from opm_ai.api.paths import validate_deck_path
from opm_ai.api.schemas import UploadResponse

router = APIRouter()

# Starlette defaults: 1 MB per part / 1000 files. Model2's
# include/ tree is 73 MB across 1000+ files; some .grdecl files
# are 30-50 MB. 256 MB / 5000 covers the realistic upper bound.
MAX_PART_SIZE = 256 * 1024 * 1024
MAX_FILES = 5000

# Reject any include part whose relative path isn't a plain
# forward-slash-separated file path. We strip the leading
# include/ if the browser included it (webkitdirectory usually
# does), then re-anchor.
_SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9_./-]+$")


def _safe_relpath(raw: str) -> str:
    """Sanitise an include file's relative path.

    Returns the path with any leading ``include/`` stripped, or
    raises 400 if the path is unsafe (absolute, contains ``..``,
    contains a backslash, contains NUL, or contains any other
    character outside ``[A-Za-z0-9_./-]``).
    """
    if not raw:
        raise HTTPException(status_code=400, detail="include file has empty path")

    # Backslashes are not allowed (this is a server-side *nix path).
    if "\\" in raw:
        raise HTTPException(
            status_code=400, detail=f"include path has backslash: {raw!r}"
        )

    # The browser's webkitRelativePath looks like
    # "include/foo/bar.GRDECL". Strip the leading include/ if
    # present so callers can put files at the top of the upload
    # dir.
    rel = raw
    if rel.startswith("/"):
        raise HTTPException(
            status_code=400, detail=f"include path is absolute: {raw!r}"
        )
    if rel.startswith("include/"):
        rel = rel[len("include/") :]

    if not rel:
        raise HTTPException(
            status_code=400,
            detail="include path is empty after stripping include/ prefix",
        )

    if not _SAFE_PATH_RE.match(rel):
        raise HTTPException(
            status_code=400,
            detail=f"include path contains unsafe characters: {raw!r}",
        )

    # Defence in depth on top of the regex: reject any '..' or
    # empty path component.
    parts = rel.split("/")
    if any(p == ".." or p == "" for p in parts):
        raise HTTPException(
            status_code=400,
            detail=f"include path has '..' or empty component: {raw!r}",
        )

    return rel


async def _write_upload_to_disk(
    upload_dir: Path,
    include_dir: Path,
    deck_part,
    include_parts: list,
) -> tuple[Path, int]:
    """Write the deck and include parts to disk.

    Returns ``(deck_path, byte_count)``. Raises 400 on any
    validation failure; the caller is responsible for cleaning
    up ``upload_dir`` in that case.
    """
    if not deck_part.filename:
        raise HTTPException(status_code=400, detail="deck part has no filename")

    deck_name = Path(deck_part.filename).name
    if not deck_name.upper().endswith(".DATA"):
        raise HTTPException(
            status_code=400,
            detail=f"deck filename must end in .DATA, got {deck_part.filename!r}",
        )

    deck_path = upload_dir / deck_name

    byte_count = 0
    try:
        with deck_path.open("wb") as out:
            while True:
                chunk = await deck_part.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                byte_count += len(chunk)
    finally:
        await deck_part.close()

    if byte_count == 0:
        deck_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="deck file is empty")

    seen: set[str] = set()
    for part in include_parts:
        rel = _safe_relpath(part.filename or "")
        if rel in seen:
            raise HTTPException(
                status_code=400,
                detail=f"duplicate include path: {rel!r}",
            )
        seen.add(rel)

        target = (include_dir / rel).resolve()
        # Defence in depth: even if _safe_relpath passed, double-
        # check the resolved path is inside include_dir. This
        # catches a symlink attack where the upload dir was
        # pre-populated with a symlink (it isn't, since we just
        # mkdtemp'd, but the check is cheap).
        if include_dir.resolve() not in target.parents and target != include_dir:
            raise HTTPException(
                status_code=400,
                detail=f"include path escapes upload dir: {rel!r}",
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as out:
            while True:
                chunk = await part.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                byte_count += len(chunk)
        await part.close()

    return deck_path, byte_count


@router.post(
    "/upload_deck",
    response_model=UploadResponse,
    # The route takes `request: Request` and calls `request.form()`
    # manually so we can override Starlette's multipart limits.
    # That means FastAPI can't auto-discover the request body
    # shape, so Swagger UI shows an empty body. Document it
    # manually here so devs reading /docs see the multipart
    # contract.
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "deck": {
                                "type": "string",
                                "format": "binary",
                                "description": (
                                    "Required. The .DATA deck file. "
                                    "Filename must end in .DATA and the file "
                                    "must be non-empty."
                                ),
                            },
                            "include": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "format": "binary",
                                },
                                "description": (
                                    "Optional. One part per include file. "
                                    "Each part's filename is the relative path "
                                    "under include/ (the leading 'include/' is "
                                    "stripped if the browser included it). "
                                    "MAX_PART_SIZE=256 MB, MAX_FILES=5000."
                                ),
                            },
                        },
                        "required": ["deck"],
                    }
                }
            },
        }
    },
)
async def upload_deck(request: Request) -> UploadResponse:
    """Upload a deck (.DATA) and an optional include/ folder.

    The deck part is required and must end in .DATA. The include
    parts are optional; zero or more files, each with a relative
    path under ``include/`` (or any safe subpath; the leading
    ``include/`` is stripped if the browser included it).

    Returns the deck's server-side path so the existing
    ``/api/run`` flow can consume it without further changes.
    """
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("multipart/form-data"):
        raise HTTPException(
            status_code=415,
            detail=f"expected multipart/form-data, got {content_type!r}",
        )

    form = await request.form(max_files=MAX_FILES, max_part_size=MAX_PART_SIZE)

    deck_part = form.get("deck")
    if deck_part is None:
        raise HTTPException(status_code=400, detail="missing 'deck' part")
    if not hasattr(deck_part, "read"):
        # Starlette returns a plain FormField for non-file parts.
        raise HTTPException(
            status_code=400, detail="'deck' part is not a file upload"
        )

    include_parts = [
        v
        for k, v in form.multi_items()
        if k == "include" and hasattr(v, "read")
    ]

    upload_dir = Path(tempfile.mkdtemp(prefix="opm_ai_upload_"))
    include_dir = upload_dir / "include"
    include_dir.mkdir()

    try:
        deck_path, byte_count = await _write_upload_to_disk(
            upload_dir, include_dir, deck_part, include_parts
        )
    except HTTPException:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"upload write failed: {e}")

    # The returned path must pass validate_deck_path so the
    # /api/run flow accepts it. mkdtemp under the system temp
    # dir is always inside get_allowed_roots() so this is a
    # sanity check rather than a real boundary.
    try:
        validate_deck_path(str(deck_path))
    except ValueError as e:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise HTTPException(
            status_code=500, detail=f"uploaded path rejected by allowlist: {e}"
        )

    include_dir_str = str(include_dir) if include_parts else None
    return UploadResponse(
        deck_path=str(deck_path),
        include_dir=include_dir_str,
        byte_count=byte_count,
    )