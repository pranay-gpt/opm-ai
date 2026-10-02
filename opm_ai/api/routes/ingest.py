"""Ingest route: POST /api/ingest/parse.

Parses a pasted or uploaded keyword export (a bare GRDECL property
fragment, a PVT table, a plain numeric grid, or a full .DATA deck) into a
flat spec patch. Uniform and per-layer data only: genuine per-cell
variation is refused with the array named rather than silently
mean-averaged. Never raises - a bad upload returns a structured finding.
"""

from fastapi import APIRouter, HTTPException, Request

from opm_ai.api.schemas import IngestRequest, IngestResponse
from opm_ai.builder.interview.ingest import parse_paste

router = APIRouter()


@router.post("/ingest/parse", response_model=IngestResponse)
async def ingest_parse(request: IngestRequest) -> IngestResponse:
    """Parse a paste/upload into a spec patch.

    The client sends the text it read from the file (or pasted); the
    server sniffs the format, parses it, and returns the patch plus any
    findings. The client applies the patch onto the spec in the same
    way the interview does, so paste and upload produce byte-equal
    specs.
    """
    if not request.text:
        raise HTTPException(status_code=400, detail="text is required")
    result = parse_paste(request.text)
    return IngestResponse(
        detected=result.detected,
        patch=result.patch,
        findings=result.findings,
    )


@router.post("/ingest/upload", response_model=IngestResponse)
async def ingest_upload(request: Request) -> IngestResponse:
    """Upload a file and parse it through the same path as paste.

    The multipart route reads the file and forwards the bytes here, so
    the two paths are byte-identical by construction rather than by
    promise: the contract is one function, parse_paste.
    """
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("multipart/form-data"):
        raise HTTPException(
            status_code=415,
            detail=f"expected multipart/form-data, got {content_type!r}",
        )

    form = await request.form(max_files=1, max_part_size=256 * 1024 * 1024)
    part = form.get("file")
    if part is None or not hasattr(part, "read"):
        raise HTTPException(status_code=400, detail="missing 'file' part")

    try:
        data = await part.read()
    finally:
        await part.close()

    if not data:
        raise HTTPException(status_code=400, detail="file is empty")

    filename = part.filename or "upload.txt"
    result = parse_paste(data.decode("utf-8", errors="replace"))
    return IngestResponse(
        detected=result.detected,
        patch=result.patch,
        findings=[f"[{filename}] {f}" if f else f for f in result.findings],
    )