"""Parameter extraction from natural language descriptions."""

import re
from opm_ai.builder.models import (
    ModelSpec,
    ReservoirSpec,
    WellSpec,
    WellType,
    ScenarioType,
    ControlMode,
    InjectFluid,
)


def extract_parameters_offline(desc: str) -> ModelSpec:
    """
    Extract reservoir model parameters from natural language description using regex/heuristics.

    This is the offline (no-LLM) path used by tests and offline mode.

    Args:
        desc: Natural language description like "10x10x5 grid, simple depletion, one producer"

    Returns:
        ModelSpec with parsed parameters
    """
    spec = ModelSpec()
    desc_lower = desc.lower()

    # Parse grid dimensions: "10x10x5" or "10 x 10 x 5"
    grid_match = re.search(r"(\d+)\s*[xX]\s*(\d+)\s*[xX]\s*(\d+)", desc)
    if grid_match:
        spec.reservoir.nx = int(grid_match.group(1))
        spec.reservoir.ny = int(grid_match.group(2))
        spec.reservoir.nz = int(grid_match.group(3))

    # Parse scenario keywords
    if "depletion" in desc_lower:
        spec.scenario = ScenarioType.DEPLETION
    elif "5-spot" in desc_lower or "5 spot" in desc_lower or "five spot" in desc_lower:
        spec.scenario = ScenarioType.WATERFLOOD_5SPOT
    elif "line drive" in desc_lower or "line-drive" in desc_lower:
        spec.scenario = ScenarioType.WATERFLOOD_LINE_DRIVE
    elif "wag" in desc_lower:
        spec.scenario = ScenarioType.WAG
    elif "gas cap" in desc_lower or "gas-cap" in desc_lower:
        spec.scenario = ScenarioType.GAS_CAP
    elif "co2" in desc_lower or "co2 eor" in desc_lower:
        spec.scenario = ScenarioType.CO2_EOR
    elif "multilayer" in desc_lower or "multi layer" in desc_lower:
        spec.scenario = ScenarioType.MULTILAYER
    elif "buildup" in desc_lower or "build up" in desc_lower:
        spec.scenario = ScenarioType.BUILDUP

    # Parse wells
    wells = []

    # Producer patterns
    prod_match = re.search(r"(?:one|1|a|single)\s+(?:producer|production\s+well|prod)", desc_lower)
    prod_count_match = re.search(r"(\d+)\s*(?:producer|production\s+well|prod)", desc_lower)
    num_producers = 1
    if prod_count_match:
        num_producers = int(prod_count_match.group(1))
    elif prod_match:
        num_producers = 1

    # Injector patterns
    inj_match = re.search(r"(?:one|1|a|single)\s+(?:injector|injection\s+well|inj)", desc_lower)
    inj_count_match = re.search(r"(\d+)\s*(?:injector|injection\s+well|inj)", desc_lower)
    num_injectors = 0
    if inj_count_match:
        num_injectors = int(inj_count_match.group(1))
    elif inj_match:
        num_injectors = 1

    # SPE1-like pattern: injector + producer
    spe1_pattern = "spe1" in desc_lower or ("injector" in desc_lower and "producer" in desc_lower)

    # Default depletion: 1 producer at corner
    if num_producers > 0 and num_injectors == 0 and not spe1_pattern:
        for i in range(num_producers):
            wells.append(WellSpec(
                name=f"PROD{i+1}",
                well_type=WellType.PROD,
                i=spec.reservoir.nx if i == 0 else max(1, spec.reservoir.nx - i),
                j=spec.reservoir.ny if i == 0 else max(1, spec.reservoir.ny - i),
                k1=1,
                k2=spec.reservoir.nz,
                reference_depth=spec.reservoir.top_depth + sum(
                    spec.reservoir.dz if isinstance(spec.reservoir.dz, float) else spec.reservoir.dz[-1]
                    for _ in range(spec.reservoir.nz)
                ) / 2,
            ))

    # SPE1-like: injector at (1,1,1), producer at (nx, ny, nz)
    if spe1_pattern or (num_injectors > 0 and num_producers > 0):
        if not any(w.well_type == WellType.INJ for w in wells):
            wells.append(WellSpec(
                name="INJ",
                well_type=WellType.INJ,
                i=1,
                j=1,
                k1=1,
                k2=1,
                reference_depth=8335.0,
                inject_fluid=InjectFluid.GAS,
                inject_rate=100000.0,
                bhp_max=9014.0,
            ))
        if not any(w.well_type == WellType.PROD for w in wells):
            wells.append(WellSpec(
                name="PROD",
                well_type=WellType.PROD,
                i=spec.reservoir.nx,
                j=spec.reservoir.ny,
                k1=spec.reservoir.nz,
                k2=spec.reservoir.nz,
                reference_depth=8400.0,
            ))

    # Waterflood patterns
    if spec.scenario in (ScenarioType.WATERFLOOD_5SPOT, ScenarioType.WATERFLOOD_LINE_DRIVE):
        wells = []  # Reset for pattern
        # 5-spot: injector at center or corner, producers at corners
        if spec.scenario == ScenarioType.WATERFLOOD_5SPOT:
            wells.append(WellSpec(
                name="INJ",
                well_type=WellType.INJ,
                i=(spec.reservoir.nx // 2) + 1,
                j=(spec.reservoir.ny // 2) + 1,
                k1=1,
                k2=spec.reservoir.nz,
                reference_depth=spec.reservoir.top_depth + sum(spec.reservoir.dz) / 2,
                inject_fluid=InjectFluid.WATER,
                inject_rate=5000.0,
                bhp_max=5000.0,
            ))
            # Four corner producers
            corners = [(1, 1), (spec.reservoir.nx, 1), (1, spec.reservoir.ny), (spec.reservoir.nx, spec.reservoir.ny)]
            for idx, (i, j) in enumerate(corners):
                wells.append(WellSpec(
                    name=f"PROD{idx+1}",
                    well_type=WellType.PROD,
                    i=i,
                    j=j,
                    k1=1,
                    k2=spec.reservoir.nz,
                    reference_depth=spec.reservoir.top_depth + sum(spec.reservoir.dz),
                ))
        else:  # Line drive
            wells.append(WellSpec(
                name="INJ",
                well_type=WellType.INJ,
                i=1,
                j=(spec.reservoir.ny // 2) + 1,
                k1=1,
                k2=spec.reservoir.nz,
                reference_depth=spec.reservoir.top_depth + sum(spec.reservoir.dz) / 2,
                inject_fluid=InjectFluid.WATER,
                inject_rate=5000.0,
                bhp_max=5000.0,
            ))
            wells.append(WellSpec(
                name="PROD",
                well_type=WellType.PROD,
                i=spec.reservoir.nx,
                j=(spec.reservoir.ny // 2) + 1,
                k1=1,
                k2=spec.reservoir.nz,
                reference_depth=spec.reservoir.top_depth + sum(spec.reservoir.dz),
            ))

    spec.wells = wells
    return spec