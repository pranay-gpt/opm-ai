"""Parameter extraction from natural language descriptions."""

import json
import re
from pathlib import Path

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
        # Expand dz to match nz layers (repeat SPE1 pattern: 20, 30, 50)
        default_dz = [20.0, 30.0, 50.0]
        spec.reservoir.dz = [default_dz[i % len(default_dz)] for i in range(spec.reservoir.nz)]
        # Expand permx, permy, permz to match nz layers (repeat SPE1 pattern: 500, 50, 200)
        default_permx = [500.0, 50.0, 200.0]
        spec.reservoir.permx = [default_permx[i % len(default_permx)] for i in range(spec.reservoir.nz)]
        default_permy = [500.0, 50.0, 200.0]
        spec.reservoir.permy = [default_permy[i % len(default_permy)] for i in range(spec.reservoir.nz)]
        default_permz = [500.0, 50.0, 200.0]
        spec.reservoir.permz = [default_permz[i % len(default_permz)] for i in range(spec.reservoir.nz)]

    # Parse scenario keywords
    if "depletion" in desc_lower:
        spec.scenario = ScenarioType.DEPLETION
    elif "line drive" in desc_lower or "line-drive" in desc_lower:
        spec.scenario = ScenarioType.WATERFLOOD_LINE_DRIVE
    elif (
        "5-spot" in desc_lower or "5 spot" in desc_lower or "five spot" in desc_lower
        or "waterflood" in desc_lower or "water flood" in desc_lower
        or "water injection" in desc_lower
    ):
        # Plain "waterflood"/"water injection" maps to the 5-spot pattern
        # (the only waterflood template in v1) unless line drive was named.
        spec.scenario = ScenarioType.WATERFLOOD_5SPOT
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

    # Parse rates: "produce at 2000 stb/day", "inject 3000 bbl/day"
    target_rate = None
    inject_rate = None
    rate_prod_match = re.search(
        r"produc\w*\s+(?:at\s+|of\s+)?(\d+(?:\.\d+)?)\s*(?:stb|bbl|bopd)", desc_lower)
    if rate_prod_match:
        target_rate = float(rate_prod_match.group(1))
    rate_inj_match = re.search(
        r"inject\w*\s+(?:at\s+|of\s+)?(\d+(?:\.\d+)?)\s*(?:stb|bbl|mscf|bwpd)", desc_lower)
    if rate_inj_match:
        inject_rate = float(rate_inj_match.group(1))

    # Parse wells
    wells = []

    _WORD_COUNTS = {"one": 1, "two": 2, "three": 3, "four": 4,
                    "five": 5, "six": 6, "a": 1, "single": 1}

    def _count(kind_pattern: str) -> int | None:
        """Explicit well count from digits or word forms; None if not stated."""
        digit = re.search(rf"(\d+)\s*{kind_pattern}", desc_lower)
        if digit:
            return int(digit.group(1))
        word = re.search(rf"({'|'.join(_WORD_COUNTS)})\s+{kind_pattern}", desc_lower)
        if word:
            return _WORD_COUNTS[word.group(1)]
        return None

    explicit_producers = _count(r"(?:producers?|production\s+wells?|prod\b)")
    explicit_injectors = _count(r"(?:injectors?|injection\s+wells?|inj\b)")
    num_producers = explicit_producers if explicit_producers is not None else 1
    num_injectors = explicit_injectors if explicit_injectors is not None else 0

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

    # WAG pattern - alternate water and gas injection
    if spec.scenario == ScenarioType.WAG:
        wells = []  # Reset for pattern
        # Injector at (1,1), producer at (nx, ny)
        wells.append(WellSpec(
            name="INJ",
            well_type=WellType.INJ,
            i=1,
            j=1,
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
            j=spec.reservoir.ny,
            k1=1,
            k2=spec.reservoir.nz,
            reference_depth=spec.reservoir.top_depth + sum(spec.reservoir.dz),
        ))

    # Explicit well counts override scenario patterns: "one injector and one
    # producer" waterflood must yield 2 wells, not the 5-spot's 5.
    if explicit_producers is not None:
        producers = [w for w in wells if w.well_type == WellType.PROD]
        others = [w for w in wells if w.well_type != WellType.PROD]
        wells = others + producers[:explicit_producers]
    if explicit_injectors is not None:
        injectors = [w for w in wells if w.well_type == WellType.INJ]
        others = [w for w in wells if w.well_type != WellType.INJ]
        wells = injectors[:explicit_injectors] + others

    # Apply rates parsed from the description to every matching well
    if target_rate is not None:
        for w in wells:
            if w.well_type == WellType.PROD:
                w.target_rate = target_rate
    if inject_rate is not None:
        for w in wells:
            if w.well_type == WellType.INJ:
                w.inject_rate = inject_rate

    spec.wells = wells
    return spec


def extract_parameters_llm(desc: str, client=None) -> ModelSpec | None:
    """
    Extract reservoir model parameters via LLM structured output.

    Renders opm_ai/llm/prompts/extract_model_spec.j2 (embedding the ModelSpec
    JSON schema), asks the client for a JSON object, and validates it with
    Pydantic. Never raises; the caller falls back to
    extract_parameters_offline on None.

    Args:
        desc: Natural language description.
        client: LLMClient (or compatible object with extract_json). A new
            LLMClient is created when omitted.

    Returns:
        Validated ModelSpec, or None on any failure (offline, bad JSON,
        schema violation).
    """
    try:
        if client is None:
            from opm_ai.llm.client import LLMClient
            client = LLMClient()
        if not getattr(client, "available", True):
            return None

        from jinja2 import Template
        prompt_path = (
            Path(__file__).parent.parent / "llm" / "prompts" / "extract_model_spec.j2"
        )
        schema = ModelSpec.model_json_schema()
        system_prompt = Template(prompt_path.read_text(encoding="utf-8")).render(
            schema=json.dumps(schema, indent=2)
        )

        data = client.extract_json(system_prompt, desc, schema=schema)
        if not isinstance(data, dict):
            return None
        return ModelSpec.model_validate(data)
    except Exception:
        return None