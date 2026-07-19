"""Knowledge corpus ingestion for the educational explainer.

This module reads the OPM knowledge corpus from three sources:
1. Eclipse HTML reference manuals (ecl_rm, ecl_td)
2. Deck comment headers from OPM test fixtures
3. Built-in original teaching notes (shipped with package)
"""

from __future__ import annotations

import html.parser
import re
from pathlib import Path
from typing import Any


# ---- HTML Text Extractor (stdlib html.parser) ----

class HTMLTextExtractor(html.parser.HTMLParser):
    """Extract text content from HTML, stripping scripts/styles and collapsing whitespace."""

    def __init__(self) -> None:
        super().__init__()
        self._text_parts: list[str] = []
        self._in_script_or_style = False
        self._ignore_tags = {"script", "style", "noscript", "head", "title", "meta"}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self._ignore_tags:
            self._in_script_or_style = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._ignore_tags:
            self._in_script_or_style = False

    def handle_data(self, data: str) -> None:
        if not self._in_script_or_style:
            self._text_parts.append(data)

    def get_text(self) -> str:
        """Return extracted text with collapsed whitespace."""
        text = " ".join(self._text_parts)
        # Collapse whitespace: multiple spaces/newlines/tabs -> single space
        text = re.sub(r"\s+", " ", text)
        return text.strip()


def extract_text_from_html(html_content: str) -> str:
    """Extract clean text from HTML content using stdlib HTMLParser."""
    parser = HTMLTextExtractor()
    parser.feed(html_content)
    parser.close()
    return parser.get_text()


# ---- Corpus Readers ----

MAX_FILE_SIZE_KB = 4096
MAX_FILES_PER_DIR = 1500
MAX_CHUNK_CHARS = 4000
CHUNK_SPLIT_CHARS = 2000


def _split_into_chunks(text: str, max_chars: int = CHUNK_SPLIT_CHARS) -> list[str]:
    """Split text into chunks on double newlines, respecting max size."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    # Split on double newlines first
    paragraphs = re.split(r"\n\s*\n", text)
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 <= max_chars:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    # If any chunk still too large, hard-split
    final_chunks = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            final_chunks.append(chunk)
        else:
            # Hard split on sentences
            sentences = re.split(r"(?<=[.!?])\s+", chunk)
            current = ""
            for sent in sentences:
                if len(current) + len(sent) + 1 <= max_chars:
                    current += (" " + sent) if current else sent
                else:
                    if current:
                        final_chunks.append(current)
                    current = sent
            if current:
                final_chunks.append(current)

    return final_chunks


def read_eclipse_html(dir_path: Path, source_type: str = "ecl_rm") -> list[dict[str, Any]]:
    """Read Eclipse HTML reference manual files.

    Args:
        dir_path: Path to directory containing .html files (ecl_rm or ecl_td)
        source_type: "ecl_rm" or "ecl_td" for source_id prefix

    Returns:
        List of chunk dicts with keys: source_id, title, path, text, source_type
    """
    chunks = []
    html_files = list(dir_path.glob("*.html"))

    # Cap total files processed
    if len(html_files) > MAX_FILES_PER_DIR:
        html_files = html_files[:MAX_FILES_PER_DIR]

    for html_file in html_files:
        # Skip large files
        if html_file.stat().st_size > MAX_FILE_SIZE_KB * 1024:
            continue

        try:
            content = html_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        text = extract_text_from_html(content)
        if len(text) < 50:  # Skip nearly empty files
            continue

        source_id = f"{source_type}_{html_file.stem}"
        title = html_file.stem.replace("_", " ").replace("-", " ").title()

        # Split into chunks if needed
        text_chunks = _split_into_chunks(text)
        for i, chunk_text in enumerate(text_chunks):
            chunk_id = source_id if len(text_chunks) == 1 else f"{source_id}_part{i}"
            chunks.append({
                "source_id": chunk_id,
                "title": title,
                "path": str(html_file),
                "text": chunk_text,
                "source_type": source_type,
            })

    return chunks


def read_deck_comments(fixtures_dir: Path) -> list[dict[str, Any]]:
    """Read leading comment blocks from .DATA files in test fixtures.

    Reads the first contiguous comment block (lines starting with --) from each
    *.DATA file. Skips comment blocks shorter than 100 characters.

    Args:
        fixtures_dir: Path to tests/fixtures/ directory

    Returns:
        List of chunk dicts with keys: source_id, title, path, text, source_type
    """
    chunks = []
    data_files = list(fixtures_dir.rglob("*.DATA"))

    for data_file in data_files:
        try:
            content = data_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        # Extract first contiguous comment block (lines starting with --)
        lines = content.splitlines()
        comment_lines = []
        in_comment_block = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("--"):
                if not in_comment_block:
                    in_comment_block = True
                comment_lines.append(stripped[2:].strip())
            elif in_comment_block:
                # First non-comment line after comment block
                break

        comment_text = "\n".join(comment_lines).strip()
        if len(comment_text) < 100:
            continue

        # Create a nice title from the directory structure
        rel_path = data_file.relative_to(fixtures_dir)
        deck_name = rel_path.parts[0] if rel_path.parts else data_file.stem
        source_id = f"deck_comment_{deck_name}_{data_file.stem}".lower()
        title = f"{deck_name}: {data_file.stem}"

        chunks.append({
            "source_id": source_id,
            "title": title,
            "path": str(data_file),
            "text": comment_text,
            "source_type": "deck_comment",
        })

    return chunks


def read_teaching_notes() -> list[dict[str, Any]]:
    """Read built-in teaching notes shipped with the package.

    Reads markdown files from opm_ai/explainer/notes/ directory.
    These are original educational content written for this project.

    Returns:
        List of chunk dicts with keys: source_id, title, path, text, source_type
    """
    notes_dir = Path(__file__).parent / "notes"
    chunks = []

    if not notes_dir.exists():
        return chunks

    md_files = list(notes_dir.glob("*.md"))

    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # Simple title extraction from first heading or filename
        title_match = re.match(r"^#\s+(.+)$", content.strip(), re.MULTILINE)
        title = title_match.group(1) if title_match else md_file.stem.replace("-", " ").title()

        source_id = f"teaching_note_{md_file.stem}"

        # Split into chunks if needed
        text_chunks = _split_into_chunks(content)
        for i, chunk_text in enumerate(text_chunks):
            chunk_id = source_id if len(text_chunks) == 1 else f"{source_id}_part{i}"
            chunks.append({
                "source_id": chunk_id,
                "title": title,
                "path": str(md_file),
                "text": chunk_text,
                "source_type": "teaching_note",
            })

    return chunks