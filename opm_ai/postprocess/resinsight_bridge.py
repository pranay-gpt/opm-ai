"""ResInsight bridge for 3D visualization (optional, requires ResInsight gRPC)."""

from pathlib import Path
from typing import Optional


def _check_rips_available() -> bool:
    """Check if rips module is available and ResInsight server is reachable."""
    try:
        import rips
        # Try to create an instance to test gRPC connection
        instance = rips.Instance.find_or_start()
        return instance is not None
    except Exception:
        return False


_RIPS_AVAILABLE = _check_rips_available()


def is_resinsight_available() -> bool:
    """Return True if ResInsight/rips is available."""
    return _RIPS_AVAILABLE


def load_case(eclipse_case_path: Path) -> Optional[object]:
    """
    Load an Eclipse case into ResInsight.

    Args:
        eclipse_case_path: Path to .DATA or .EGRID file.

    Returns:
        EclipseCase object or None if ResInsight not available.
    """
    if not _RIPS_AVAILABLE:
        return None

    try:
        import rips
        instance = rips.Instance.find_or_start()
        project = instance.project
        case = project.load_case(str(eclipse_case_path))
        return case
    except Exception as e:
        print(f"Failed to load case in ResInsight: {e}")
        return None


def create_summary_plots(case, well_names: list[str] = None) -> list:
    """
    Create summary plots (WOPR, WWCT, BHP) in ResInsight.

    Args:
        case: EclipseCase from load_case().
        well_names: List of well names to plot. If None, plot all.

    Returns:
        List of created plot objects.
    """
    if not _RIPS_AVAILABLE or case is None:
        return []

    try:
        plots = []

        # Get available summary cases
        summary_cases = case.summary_cases()
        if not summary_cases:
            return plots

        sc = summary_cases[0]  # Use first summary case

        # Default curves to plot
        if well_names is None:
            # Try to get well names from case
            wells = case.wells()
            well_names = [w.name for w in wells] if wells else ['PROD', 'INJ']

        for well in well_names:
            # Oil rate
            try:
                curve_wopr = sc.create_summary_plot(f"WOPR:{well}", well)
                plots.append(curve_wopr)
            except Exception:
                pass

            # Water cut
            try:
                curve_wwct = sc.create_summary_plot(f"WWCT:{well}", well)
                plots.append(curve_wwct)
            except Exception:
                pass

            # BHP
            try:
                curve_bhp = sc.create_summary_plot(f"WBHP:{well}", well)
                plots.append(curve_bhp)
            except Exception:
                pass

        return plots

    except Exception as e:
        print(f"Failed to create summary plots: {e}")
        return []


def create_3d_snapshot(case, time_step: int = -1, property_name: str = "SOIL",
                       output_path: Optional[Path] = None) -> bool:
    """
    Create a 3D snapshot (saturation/pressure) and optionally export as PNG.

    Args:
        case: EclipseCase from load_case().
        time_step: Time step index (-1 for last).
        property_name: Cell property to visualize (SOIL, SWAT, PRESSURE, etc.).
        output_path: If provided, export PNG to this path.

    Returns:
        True if successful.
    """
    if not _RIPS_AVAILABLE or case is None:
        return False

    try:
        import rips

        instance = rips.Instance.find_or_start()
        project = instance.project

        # Get Eclipse view
        views = project.views()
        eclipse_view = None
        for v in views:
            if isinstance(v, rips.EclipseView):
                eclipse_view = v
                break

        if eclipse_view is None:
            eclipse_view = project.create_eclipse_view()

        # Set time step
        if time_step >= 0:
            eclipse_view.set_time_step(time_step)

        # Set cell result
        eclipse_view.set_cell_result(property_name)

        # Export snapshot if path provided
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            eclipse_view.export_snapshot(str(output_path))

        return True

    except Exception as e:
        print(f"Failed to create 3D snapshot: {e}")
        return False


def export_case_html(case, output_path: Path) -> bool:
    """
    Export ResInsight case to HTML for web viewing.

    Args:
        case: EclipseCase from load_case().
        output_path: Output .html file path.

    Returns:
        True if successful.
    """
    if not _RIPS_AVAILABLE or case is None:
        return False

    try:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        import rips
        instance = rips.Instance.find_or_start()
        project = instance.project

        # Export to HTML
        project.export_html(str(output_path))
        return True

    except Exception as e:
        print(f"Failed to export HTML: {e}")
        return False


def create_full_visualization_workflow(output_dir: Path, case_name: str = "CASE") -> dict:
    """
    Run full visualization workflow: load case, create plots, 3D snapshots, export HTML.

    Args:
        output_dir: Directory with simulation output (.EGRID, .UNSMRY, etc.).
        case_name: Base name of case files.

    Returns:
        Dict with results (success flags, output paths).
    """
    results = {
        "case_loaded": False,
        "summary_plots": [],
        "snapshots": [],
        "html_export": None,
    }

    if not _RIPS_AVAILABLE:
        results["error"] = "ResInsight (rips) not available"
        return results

    try:
        # Find case file
        egrid_files = list(output_dir.glob("*.EGRID"))
        data_files = list(output_dir.glob("*.DATA"))
        case_file = egrid_files[0] if egrid_files else (data_files[0] if data_files else None)

        if not case_file:
            results["error"] = "No .EGRID or .DATA file found"
            return results

        # Load case
        case = load_case(case_file)
        if case is None:
            results["error"] = "Failed to load case"
            return results

        results["case_loaded"] = True
        results["case_file"] = str(case_file)

        # Create summary plots
        plots = create_summary_plots(case)
        results["summary_plots"] = len(plots)

        # Create 3D snapshots for key properties at last time step
        snapshots_dir = output_dir / "resinsight_snapshots"
        snapshots_dir.mkdir(exist_ok=True)

        for prop in ["SOIL", "SWAT", "PRESSURE", "SGAS"]:
            snap_path = snapshots_dir / f"{case_name}_{prop}.png"
            if create_3d_snapshot(case, time_step=-1, property_name=prop, output_path=snap_path):
                results["snapshots"].append({"property": prop, "path": str(snap_path)})

        # Export HTML
        html_path = output_dir / f"{case_name}_resinsight.html"
        if export_case_html(case, html_path):
            results["html_export"] = str(html_path)

    except Exception as e:
        results["error"] = str(e)

    return results