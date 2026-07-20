"""Path validation helper for API routes.

Provides a shared helper to resolve and validate user-supplied filesystem paths
against an allowlist of permitted root directories.
"""

import tempfile
from pathlib import Path
from typing import Optional

from opm_ai.settings import settings


def get_allowed_roots() -> list[Path]:
    """
    Get the list of allowed root directories for path validation.

    Returns:
        List of Path objects representing allowed root directories.
        Includes:
        - Configured decks directory (from settings if available)
        - Configured results directory (from settings if available)
        - System temp directory (tempfile.gettempdir())
        - Fixtures directory (for testing)
    """
    roots = []

    # Add system temp directory (always allowed for smoke tests)
    roots.append(Path(tempfile.gettempdir()).resolve())

    # Add configured directories from settings if they exist
    if hasattr(settings, 'decks_path') and settings.decks_path:
        roots.append(Path(settings.decks_path).resolve())
    if hasattr(settings, 'results_path') and settings.results_path:
        roots.append(Path(settings.results_path).resolve())
    if hasattr(settings, 'fixtures_path') and settings.fixtures_path:
        roots.append(Path(settings.fixtures_path).resolve())

    # Deduplicate while preserving order
    seen = set()
    unique_roots = []
    for root in roots:
        root_str = str(root)
        if root_str not in seen:
            seen.add(root_str)
            unique_roots.append(root)

    return unique_roots


def validate_path(
    user_path: str | Path,
    allowed_roots: Optional[list[Path]] = None,
    must_be_file: bool = True,
    required_suffix: Optional[str] = None,
    must_exist: bool = False,
) -> Path:
    """
    Resolve and validate a user-supplied path against allowed roots.

    Args:
        user_path: User-supplied path (string or Path)
        allowed_roots: Optional custom allowed roots. If None, uses get_allowed_roots()
        must_be_file: If True, reject paths that are existing directories
        required_suffix: If set, require the path to have this suffix (e.g., '.DATA')
        must_exist: If True, require the path to already exist

    Returns:
        Resolved Path object that is within allowed roots

    Raises:
        ValueError: If path is outside allowed roots, is a directory when must_be_file=True,
                    doesn't have required suffix, or doesn't exist when must_exist=True
    """
    path = Path(user_path)

    # Resolve to absolute path (follows symlinks, resolves ..)
    try:
        resolved = path.resolve(strict=must_exist)
    except FileNotFoundError:
        # If must_exist is False, resolve without strict to get the absolute path
        if not must_exist:
            resolved = path.resolve(strict=False)
        else:
            raise ValueError(f"Path does not exist: {path}")

    # Check required suffix
    if required_suffix and not resolved.name.endswith(required_suffix):
        raise ValueError(f"Path must have '{required_suffix}' suffix: {resolved}")

    # Check if it's an existing directory when must_be_file is True
    if must_be_file and resolved.exists() and resolved.is_dir():
        raise ValueError(f"Path is a directory, expected a file: {resolved}")

    # Get allowed roots
    roots = allowed_roots if allowed_roots is not None else get_allowed_roots()

    # Check if resolved path is within any allowed root
    for root in roots:
        try:
            resolved.relative_to(root)
            # Path is within this root - validation passed
            return resolved
        except ValueError:
            # Not within this root, continue checking
            continue

    # If we get here, path is not within any allowed root
    roots_str = ", ".join(str(r) for r in roots)
    raise ValueError(
        f"Path '{resolved}' is outside allowed directories. "
        f"Allowed roots: {roots_str}"
    )


def validate_deck_path(deck_path: str | Path, must_exist: bool = True) -> Path:
    """
    Validate a deck path for /api/lint, /api/run, etc.

    Deck paths must:
    - Exist (if must_exist=True)
    - Have .DATA suffix
    - Be within allowed roots
    """
    return validate_path(
        deck_path,
        must_be_file=True,
        required_suffix=".DATA",
        must_exist=must_exist,
    )


def validate_output_path(output_path: str | Path, must_exist: bool = False) -> Path:
    """
    Validate an output path for /api/build output_path.

    Output paths must:
    - Have .DATA suffix
    - Be within allowed roots
    - Not be an existing directory
    """
    return validate_path(
        output_path,
        must_be_file=True,
        required_suffix=".DATA",
        must_exist=must_exist,
    )


def validate_run_deck_path(deck_path: str | Path) -> Path:
    """
    Validate a deck path for /api/run.

    Run deck paths must exist and have .DATA suffix.
    """
    return validate_deck_path(deck_path, must_exist=True)