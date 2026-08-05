# Plan: Deck Upload with include/ folder (Simulator page)

## Goal

Add a separate **Upload** button on the Simulator page (next to the
existing **Browse** button). The user picks a `.DATA` file and (in a
second control) the sibling `include/` folder via `webkitdirectory`.
The frontend sends both in a single multipart POST; the backend writes
them to a fresh run directory and returns the `.DATA`'s server-side
path so the existing `Run` flow works unchanged.

The existing **Browse** button (server-side path picker via
`DeckPicker`) is unchanged — that workflow still works for users
who have the deck on the server.

## Design decisions

| Decision | Choice | Rationale |
|---|---|---|
| UI | New `Upload` button next to `Browse` | User-picked. Preserves the server-side path picker. |
| Wire format | Single `multipart/form-data` POST | User-picked. One round-trip, atomic on the server. |
| `include/` packaging | Separate `file` parts with `webkitrelativepath` preserved | Avoids the need to walk the tree on the client; the browser hands over `File` objects with `.webkitRelativePath` set. |
| New endpoint | `POST /api/upload_deck` | Matches the existing `POST /api/run`, `POST /api/lint`, `POST /api/build` verb pattern. |
| Storage location | `tempfile.mkdtemp()` under `/tmp/opm_ai_uploads/` | Stays inside the existing allowlist (system temp dir is in `get_allowed_roots()`). Reuses the same scratch-disk pattern the deck-save route already uses. |
| Return shape | `{deck_path: str, include_dir: str, byte_count: int}` | The frontend fills the deck path input with `deck_path` and shows the include dir in a "Uploaded to" hint. |
| Cleanup | Lazy: reaped on next upload, or by a startup task | Matches the existing `tempfile`-mkdtemp pattern; no new scheduler. |
| `max_part_size` | 256 MB | Some `.grdecl` files in `model2` are 30-50 MB. The 73 MB include tree noted in `files.py` is the realistic upper bound. |
| `max_files` | 5000 | Some decks (model2) have ~1500+ include files. 5000 is a safe upper bound. |
| Filename collisions | Reject with 400 if the user uploads two files with the same relative path | The only way this happens is user error; bail early. |
| `include/` not present | Optional — accept the deck alone | User asked for "if present". Make it optional. |
| File size total | No aggregate cap beyond `max_part_size` * `max_files` | Reasonable for any plausible deck. |
| `validate_deck_path` on the returned path | Yes — the new endpoint must pass `validate_deck_path` on the path it returns, so the existing `/api/run` validation continues to accept it | This is the same contract the DeckPicker-served paths already meet. |

## Files

### Backend (new + modified)

1. **`opm_ai/api/routes/upload.py`** (new)
   - `POST /api/upload_deck` accepting `multipart/form-data` with
     two parts:
     - `deck: UploadFile` — required, the `.DATA` file. Filename
       must end in `.DATA` (case-insensitive) and the file must
       be non-empty.
     - `include: list[UploadFile]` — optional, zero or more files
       from the `include/` folder. Each file's
       `webkitRelativePath` (or the part's `filename`) gives the
       relative path under `include/`.
   - The route's decorator must override Starlette's multipart
     limits: `max_part_size=256*1024*1024`, `max_files=5000`.
   - Creates a fresh directory under
     `tempfile.mkdtemp(prefix="opm_ai_upload_", dir=tempfile.gettempdir())`.
   - Writes the `.DATA` to `<dir>/<basename>` (preserving the
     filename the user picked).
   - For each include file, writes to
     `<dir>/include/<webkitRelativePath>`, sanitising the relative
     path to disallow `..`, absolute paths, or symlink escapes.
   - Returns
     `UploadResponse(deck_path, include_dir=..., byte_count=...)`.
   - On error, removes the temp dir and re-raises.

2. **`opm_ai/api/schemas.py`** (modified)
   - Add `UploadResponse` Pydantic model with the three fields
     above. `deck_path` and `include_dir` are `str` (same wire
     convention as `SimulationResultDTO.output_dir`).

3. **`opm_ai/api/server.py`** (modified)
   - Add `from opm_ai.api.routes import upload` and
     `app.include_router(upload.router, prefix="/api")`.

### Frontend (new + modified)

4. **`frontend/src/components/DeckUploader.tsx`** (new)
   - Modal matching `DeckPicker`'s visual style. Two `<input>`
     controls:
     - `<input type="file" accept=".DATA">` for the deck.
     - `<input type="file" webkitdirectory directory multiple>`
       for the `include/` folder.
   - Shows the picked filenames and sizes, an Upload button, and
     progress / error state.
   - On submit: builds a `FormData` with the deck as
     `formData.append("deck", deckFile, deckFile.name)` and each
     include file as
     `formData.append("include", file, file.webkitRelativePath)`.
   - POSTs to `/api/upload_deck` and calls `onUpload(path)` on
     success.

5. **`frontend/src/api/client.ts`** (modified)
   - Add `uploadDeck(formData: FormData): Promise<UploadResponse>`
     that POSTs the FormData and returns the parsed JSON. The
     `Content-Type` header must NOT be set — the browser sets it
     with the correct `boundary=` for multipart, and setting it
     manually breaks the parser.

6. **`frontend/src/components/SimulationRunner.tsx`** (modified)
   - Add a new `uploading` state and a new `Uploading` button next
     to `Browse`. The button opens `<DeckUploader onUpload={...} />`
     which calls `setDeckPath(uploadedPath)` and closes the modal.

### Tests (new)

7. **`tests/integration/test_api_upload_deck.py`** (new) — covers
   - Happy path: `.DATA` only → 200, path returned, file exists.
   - Happy path: `.DATA` + `include/` folder (3 files) → 200, all
     files written, `include_dir` populated.
   - Reject: missing deck part → 400.
   - Reject: non-`.DATA` filename → 400.
   - Reject: empty deck file → 400.
   - Reject: include path escapes the upload dir (`../etc/passwd`)
     → 400.
   - Reject: duplicate relative path in include → 400.
   - Path-safety: the returned `deck_path` passes
     `validate_deck_path` (regression — same contract the
     DeckPicker-served paths meet).

## Out of scope

- Drag-and-drop. The file inputs are enough for v1; DnD can come
  later.
- Resume on failure. If the upload is interrupted, the partial
  temp dir is left behind. The next upload picks a fresh
  `mkdtemp`; a periodic reaper can come later if it becomes a
  problem.
- Multi-deck upload. The user uploads one deck at a time; the
  existing `lastDeckPath` state already handles switching.
- Auth / quotas. The dev server is single-user; production would
  need size + rate limits.

## Verification

- `python3 -m pytest tests/ -q` → 502 + new tests, all green.
- `cd frontend && npx tsc --noEmit -p tsconfig.json` → exit 0.
- Manual smoke test (can't run here):
  1. Start the dev server.
  2. Navigate to `/simulator`.
  3. Click **Upload**, pick `model2/3_MULTFLT_MODEL2.DATA` and
     the `model2/include/` folder.
  4. Verify the deck path fills in.
  5. Click **Run**, confirm the job completes and the
     include-resolving flow works (the same path the DeckPicker
     route already validates).
