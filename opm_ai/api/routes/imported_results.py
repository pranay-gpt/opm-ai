"""POST /api/imported-results — register a virtual job from uploaded files.

Mirrors the security model of opm_ai/api/routes/upload.py:

- Multipart with MAX_PART_SIZE=256 MB, MAX_FILES=5000.
- tempdir mkdtemp(prefix="opm_ai_imported_").
- Filenames go through _SAFE_PATH_RE.
- No `.DATA` requirement — these aren't decks, just Eclipse output files.

Validation policy (in _validate_imported_files):

- Required: either (CASE.SMSPEC + CASE.UNSMRY) OR a single CASE.ESMRY.
  Without summary data, /api/results/{id} cannot show anything, so we
  reject early.
- Accepted but optional: .EGRID, .GRID, .UNRST, .INIT, .RFT, .PRT.

On success: register a virtual job whose output_dir points at the
upload dir. All downstream endpoints (/results, /grid/info, etc.)
just work because they only depend on job.output_dir containing valid
Eclipse files.
"""
from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from loguru import logger

from opm_ai.api.job_store import register_virtual_job
from opm_ai.api.schemas import ImportedResultResponse


router = APIRouter()

MAX_PART_SIZE = 256 * 1024 * 1024
MAX_FILES = 5000

REQUIRED_FILES_HINT = (
    "Required: one *.SMSPEC + one *.UNSMRY (or one *.ESMRY). "
    "Optional: .EGRID, .GRID, .UNRST, .INIT, .RFT, .PRT."
)

_SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9_.-]+$")  # filenames only — no path separators

_OPTIONAL_EXTENSIONS = {".EGRID", ".FEGRID", ".GRID", ".FGRID", ".UNRST", ".INIT", ".RFT", ".PRT"}


def _safe_filename(raw: str) -> str:
    name = Path(raw).name  # strip any path the client tried to inject
    if not name or not _SAFE_PATH_RE.match(name):
        raise HTTPException(status_code=400, detail=f"unsafe filename: {raw!r}")
    return name


def _validate_imported_files(directory: Path) -> tuple[list[str], list[str]]:
    """Ensure at least one summary file pair is present; return (accepted, warnings).

    Raises ValueError on missing required files or unsafe filenames.
    """
    accepted: list[str] = []
    warnings: list[str] = []

    has_smspec = False
    has_unsmry = False
    has_esmry = False

    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        if not _SAFE_PATH_RE.match(path.name):
            raise ValueError(f"unsafe filename in upload: {path.name!r}")
        suffix = path.suffix.upper()
        if suffix == ".SMSPEC":
            has_smspec = True
            accepted.append(path.name)
        elif suffix == ".UNSMRY":
            has_unsmry = True
            accepted.append(path.name)
        elif suffix == ".ESMRY":
            has_esmry = True
            accepted.append(path.name)
        elif suffix in _OPTIONAL_EXTENSIONS:
            accepted.append(path.name)
        else:
            warnings.append(f"ignored file with unsupported extension: {path.name}")

    if not has_esmry and not (has_smspec and has_unsmry):
        raise ValueError(f"missing required summary files. {REQUIRED_FILES_HINT}")

    return sorted(accepted), warnings


@router.post("/imported-results", response_model=ImportedResultResponse)
async def post_imported_results(request: Request) -> ImportedResultResponse:
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("multipart/form-data"):
        raise HTTPException(
            status_code=415,
            detail=f"expected multipart/form-data, got {content_type!r}",
        )

    form = await request.form(max_files=MAX_FILES, max_part_size=MAX_PART_SIZE)

    file_parts = [
        v for k, v in form.multi_items()
        if k == "files" and hasattr(v, "read")
    ]
    if not file_parts:
        raise HTTPException(status_code=400, detail="no files in 'files' field")

    upload_dir = Path(tempfile.mkdtemp(prefix="opm_ai_imported_"))

    try:
        for part in file_parts:
            name = _safe_filename(part.filename or "")
            target = upload_dir / name
            byte_count = 0
            with target.open("wb") as out:
                while True:
                    chunk = await part.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    byte_count += len(chunk)
            await part.close()
            if byte_count == 0:
                target.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail=f"file is empty: {name}")

        try:
            accepted, warnings = _validate_imported_files(upload_dir)
        except ValueError as e:
            shutil.rmtree(upload_dir, ignore_errors=True)
            raise HTTPException(status_code=400, detail=str(e))

    except HTTPException:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(upload_dir, ignore_errors=True)
        logger.exception("imported-results write failed")
        raise HTTPException(status_code=500, detail=f"upload failed: {e}")

    job_id = register_virtual_job(upload_dir)

    return ImportedResultResponse(
        job_id=job_id,
        files_received=accepted,
        warnings=warnings,
    )


# Re-export for callers that need to know what's expected.
__all__ = ["router", "REQUIRED_FILES_HINT", "_validate_imported_files"]