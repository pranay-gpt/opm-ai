"""Summary file reader using resfo."""

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import resfo


def read_summary(output_dir: Path) -> pd.DataFrame:
    """
    Read OPM Flow summary output files (.SMSPEC, .UNSMRY or .ESMRY) into a DataFrame.

    Uses resfo to parse the binary summary files and reconstructs labeled column names
    like "WOPT:PROD" from the SMSPEC metadata (KEYWORDS, WGNAMES/NAMES, NUMS, UNITS)
    or from ESMRY KEYCHECK which already has fully qualified names.

    Args:
        output_dir: Directory containing summary files.

    Returns:
        DataFrame with TIME column and well vectors (e.g., WOPT:PROD, FOPR, etc.).
        Returns empty DataFrame if files not found or unreadable.
    """
    output_dir = Path(output_dir)

    # Find summary files
    esmry_files = list(output_dir.glob("*.ESMRY"))
    unsmry_files = list(output_dir.glob("*.UNSMRY"))
    smspec_files = list(output_dir.glob("*.SMSPEC"))

    if not (esmry_files or (smspec_files and unsmry_files)):
        return pd.DataFrame()

    # Try ESMRY first (formatted, has KEYCHECK with full column names)
    if esmry_files:
        return _read_esmry(esmry_files[0])

    # Fall back to UNSMRY + SMSPEC
    if unsmry_files and smspec_files:
        return _read_unsmry_with_smspec(unsmry_files[0], smspec_files[0])

    return pd.DataFrame()


def _read_esmry(esmry_path: Path) -> pd.DataFrame:
    """Read formatted ESMRY file using KEYCHECK for column names."""
    try:
        data = resfo.read(esmry_path)
    except Exception:
        return pd.DataFrame()

    # Extract components
    keycheck = None
    tstep = None
    vectors = {}

    for kw, arr in data:
        kw_stripped = kw.strip()
        if kw_stripped == 'KEYCHECK':
            keycheck = [x.decode('ascii').strip() if isinstance(x, bytes) else str(x).strip() for x in arr]
        elif kw_stripped == 'TSTEP':
            tstep = arr.astype(float)
        elif kw_stripped.startswith('V') and kw_stripped[1:].isdigit():
            vectors[int(kw_stripped[1:])] = arr.astype(float)

    if tstep is None or not vectors:
        return pd.DataFrame()

    # Build column names from KEYCHECK
    # KEYCHECK has the fully qualified names like "WBHP:INJ", "WOPR:PROD", etc.
    if keycheck and len(keycheck) == len(vectors):
        # Vector V0 corresponds to KEYCHECK[0], etc.
        df_data = {'TIME': tstep}
        for i in sorted(vectors.keys()):
            if i < len(keycheck):
                col_name = keycheck[i]
                df_data[col_name] = vectors[i]
            else:
                df_data[f"V{i}"] = vectors[i]
    else:
        # Fallback: generic names
        df_data = {'TIME': tstep}
        for i in sorted(vectors.keys()):
            df_data[f"V{i}"] = vectors[i]

    df = pd.DataFrame(df_data)

    # Ensure TIME is first column
    cols = ['TIME'] + [c for c in df.columns if c != 'TIME']
    df = df[cols]

    return df


def _read_unsmry_with_smspec(unsmry_path: Path, smspec_path: Path) -> pd.DataFrame:
    """Read unformatted UNSMRY using SMSPEC for metadata."""
    try:
        unsmry_data = resfo.read(unsmry_path)
        smspec_data = resfo.read(smspec_path)
    except Exception:
        return pd.DataFrame()

    # Parse SMSPEC for metadata
    metadata = {}
    for kw, arr in smspec_data:
        kw_stripped = kw.strip()
        if kw_stripped in ('KEYWORDS', 'WGNAMES', 'NAMES', 'NUMS', 'UNITS'):
            if arr.dtype.kind in ('S', 'U'):
                arr = np.array([x.decode('ascii').strip() if isinstance(x, bytes) else str(x).strip() for x in arr])
            metadata[kw_stripped] = arr

    # UNSMRY has SEQHDR, MINISTEP, PARAMS blocks
    # PARAMS contains the actual vector values for each time step
    time_steps = []
    all_vectors = []

    current_step = {}
    for kw, arr in unsmry_data:
        kw_stripped = kw.strip()
        if kw_stripped == 'SEQHDR':
            if current_step.get('PARAMS') is not None:
                all_vectors.append(current_step['PARAMS'])
                if 'MINISTEP' in current_step:
                    time_steps.append(float(current_step['MINISTEP'][0]))
            current_step = {'SEQHDR': arr}
        elif kw_stripped == 'MINISTEP':
            current_step['MINISTEP'] = arr
        elif kw_stripped == 'PARAMS':
            current_step['PARAMS'] = arr

    # Don't forget the last step
    if current_step.get('PARAMS') is not None:
        all_vectors.append(current_step['PARAMS'])
        if 'MINISTEP' in current_step:
            time_steps.append(float(current_step['MINISTEP'][0]))

    if not all_vectors:
        return pd.DataFrame()

    # Convert to array: each row is a time step, each column is a vector
    n_vectors = len(all_vectors[0])
    data_array = np.array(all_vectors).T  # Shape: (n_vectors, n_steps)

    # Build column names from metadata
    col_names = _build_column_names(metadata, n_vectors)

    # Create DataFrame
    df_data = {'TIME': np.array(time_steps)}
    for i in range(n_vectors):
        if i < len(col_names):
            df_data[col_names[i]] = data_array[i]
        else:
            df_data[f"V{i}"] = data_array[i]

    df = pd.DataFrame(df_data)
    cols = ['TIME'] + [c for c in df.columns if c != 'TIME']
    df = df[cols]

    return df


def _build_column_names(metadata: dict, n_vectors: int) -> list[str]:
    """
    Build column names like 'WOPT:PROD' from SMSPEC metadata.

    KEYWORDS: base keyword names (e.g., WOPT, FOPR, WBHP)
    WGNAMES/NAMES: well/group names (e.g., PROD, INJ)
    NUMS: connection indices (0 for field totals, >0 for well connections)
    UNITS: unit strings
    """
    keywords = metadata.get('KEYWORDS', [])
    wgnames = metadata.get('WGNAMES', metadata.get('NAMES', []))
    nums = metadata.get('NUMS', [])

    if len(keywords) != n_vectors:
        return [f"COL_{i}" for i in range(n_vectors)]

    col_names = []
    for i in range(n_vectors):
        kw = keywords[i].strip() if isinstance(keywords[i], str) else keywords[i].decode('ascii').strip()
        name = wgnames[i].strip() if i < len(wgnames) and isinstance(wgnames[i], str) else (
            wgnames[i].decode('ascii').strip() if i < len(wgnames) else ""
        )
        num = int(nums[i]) if i < len(nums) else 0

        if name and name != ":+:+:+:+":  # Skip placeholder
            if num > 0:
                col_name = f"{kw}:{name}"
            else:
                col_name = f"{kw}:{name}"  # Field total or well total
        else:
            col_name = kw  # No well name, just keyword (field total)

        col_names.append(col_name)

    return col_names