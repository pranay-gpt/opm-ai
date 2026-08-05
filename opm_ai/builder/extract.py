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
    ScheduleEvent,
)

# CO2-like injection gas PVDG (FIELD: psia, rb/Mscf, cP). Denser and more
# viscous than the default methane-like table at every pressure; keeps the
# deck in the black-oil subset (no compositional keywords).
CO2_PVDG_ROWS = [
    "14.700\t145.000\t0.014500",
    "264.70\t10.4000\t0.015000",
    "514.70\t5.30000\t0.015800",
    "1014.7\t2.55000\t0.017500",
    "2014.7\t1.10000\t0.026000",
    "2514.7\t0.85000\t0.033000",
    "3014.7\t0.70000\t0.041000",
    "4014.7\t0.55000\t0.052000",
    "5014.7\t0.47000\t0.060000",
    "9014.7\t0.30000\t0.078000",
]


def _wconinje_action(name: str, fluid: str, rate: float, bhp_max: float) -> str:
    """Raw WCONINJE block for a schedule event."""
    return f"WCONINJE\n\t'{name}' {fluid} OPEN RATE {rate:.0f} 1* {bhp_max:.0f} /\n/"


def _wconprod_stop_action(name: str, bhp_limit: float) -> str:
    """Raw WCONPROD block stopping a producer (rate 0, STOP status)."""
    return f"WCONPROD\n\t'{name}' STOP ORAT 0 4* {bhp_limit:.0f} /\n/"


def extract_parameters_offline(desc: str) -> ModelSpec:
    """
    Extract reservoir model parameters from natural language description using regex/heuristics.

    This is the offline (no-LLM) path used by tests and offline mode.

    Args:
        desc: Natural language description like "10x10x5 grid, simple depletion, one producer"

    Returns:
        ModelSpec with parsed parameters
    """
    spec, _provenance = extract_parameters_offline_with_provenance(desc)
    return spec


def extract_parameters_offline_with_provenance(desc: str) -> tuple[ModelSpec, dict[str, str]]:
    """Same as extract_parameters_offline, but also returns a provenance dict.

    The provenance dict covers the rock-basics fields surfaced in the UI:
    porosity, top_depth, initial_pressure, dz, permx, permy, permz. For each
    field the value is one of:
      - "extracted"  the regex parser picked the value from the description
      - "defaulted"  the description did not name the field; ModelSpec default used

    No field is "required_missing" today - every rock-basics field has a
    safe default and the deck is always buildable. The slot is reserved in
    the schema for future fields that might be required.

    Args:
        desc: Natural language description.

    Returns:
        Tuple of (ModelSpec, provenance dict keyed by field name).
    """
    from opm_ai.api.schemas import PROVENANCE_DEFAULTED, PROVENANCE_EXTRACTED, ROCK_BASICS_FIELDS

    spec = ModelSpec()
    desc_lower = desc.lower()
    provenance: dict[str, str] = {}

    # Parse grid dimensions: "10x10x5" or "10 x 10 x 5"
    grid_match = re.search(r"(\d+)\s*[xX]\s*(\d+)\s*[xX]\s*(\d+)", desc)
    if grid_match:
        spec.reservoir.nx = int(grid_match.group(1))
        spec.reservoir.ny = int(grid_match.group(2))
        spec.reservoir.nz = int(grid_match.group(3))
        # Expand dz to match nz layers (repeat SPE1 pattern: 20, 30, 50)
        default_dz = [20.0, 30.0, 50.0]
        spec.reservoir.dz = [default_dz[i % len(default_dz)] for i in range(spec.reservoir.nz)]
        provenance["dz"] = PROVENANCE_DEFAULTED  # dz always comes from the grid-expansion default; user describing "10x10x5" does not name dz.
        # Expand permx, permy, permz to match nz layers (repeat SPE1 pattern: 500, 50, 200)
        default_permx = [500.0, 50.0, 200.0]
        spec.reservoir.permx = [default_permx[i % len(default_permx)] for i in range(spec.reservoir.nz)]
        spec.reservoir.permy = [default_permx[i % len(default_permx)] for i in range(spec.reservoir.nz)]
        spec.reservoir.permz = [default_permx[i % len(default_permx)] for i in range(spec.reservoir.nz)]
        provenance["permx"] = PROVENANCE_DEFAULTED
        provenance["permy"] = PROVENANCE_DEFAULTED
        provenance["permz"] = PROVENANCE_DEFAULTED
    else:
        provenance["dz"] = PROVENANCE_DEFAULTED
        provenance["permx"] = PROVENANCE_DEFAULTED
        provenance["permy"] = PROVENANCE_DEFAULTED
        provenance["permz"] = PROVENANCE_DEFAULTED

    # --- porosity ----------------------------------------------------------
    # "porosity 0.25", "phi 0.2", "25% porosity", "phi=0.18". Fraction in
    # [0,1] and percent in (0,100] both supported. Keyword may come before
    # OR after the number.
    porosity_match = re.search(
        r"(?:porosity|phi)\s*(?:of|=|is|:)?\s*(\d+(?:\.\d+)?)\s*%?"
        r"|(\d+(?:\.\d+)?)\s*%\s*(?:porosity|phi)",
        desc_lower,
    )
    if porosity_match:
        raw = porosity_match.group(1) or porosity_match.group(2)
        val = float(raw)
        # Heuristic: > 1.0 means percent (e.g. "25% porosity" -> 0.25).
        if val > 1.0 and val <= 100.0:
            val /= 100.0
        if 0.01 <= val <= 0.5:
            spec.reservoir.porosity = val
            provenance["porosity"] = PROVENANCE_EXTRACTED
        else:
            provenance["porosity"] = PROVENANCE_DEFAULTED
    else:
        provenance["porosity"] = PROVENANCE_DEFAULTED

    # --- top depth --------------------------------------------------------
    # "8325 ft", "8500' depth", "8500 ft deep", "depth 9000 ft", "9000 ft
    # deep". Returns ft.
    depth_match = re.search(
        r"(?:top[_\s]*depth|depth|deep)\s*(?:of|=|is|:)?\s*(\d{2,5}(?:\.\d+)?)\s*(?:ft|feet|'|\")?"
        r"|(\d{2,5}(?:\.\d+)?)\s*(?:ft|feet|'|\")?\s*(?:top[_\s]*depth|depth|deep)",
        desc_lower,
    )
    if depth_match:
        raw = depth_match.group(1) or depth_match.group(2)
        val = float(raw)
        if 100.0 <= val <= 30000.0:
            spec.reservoir.top_depth = val
            provenance["top_depth"] = PROVENANCE_EXTRACTED
        else:
            provenance["top_depth"] = PROVENANCE_DEFAULTED
    else:
        provenance["top_depth"] = PROVENANCE_DEFAULTED

    # --- initial pressure --------------------------------------------------
    # "4800 psia", "initial pressure 5000 psi", "p_init 4800 psia",
    # "5000 psi initial pressure".
    pressure_match = re.search(
        r"(?:initial[_\s]*pressure|p_init|pdatum|pressure\s*at\s*datum|reservoir\s*pressure)"
        r"\s*(?:of|=|is|:)?\s*(\d{2,5}(?:\.\d+)?)\s*(?:psia|psi|bar|atm|kpa)?"
        r"|(\d{2,5}(?:\.\d+)?)\s*(?:psia|psi|bar|atm|kpa)\s*(?:initial\s*)?"
        r"(?:initial[_\s]*pressure|pdatum|reservoir\s*pressure)",
        desc_lower,
    )
    if pressure_match:
        raw = pressure_match.group(1) or pressure_match.group(2)
        val = float(raw)
        # Look back at the matched substring for unit hints.
        match_text = pressure_match.group(0).lower()
        if "bar" in match_text:
            val = val / 0.0689476  # bar -> psia
        elif "kpa" in match_text:
            val = val * 0.145038  # kPa -> psia
        elif "atm" in match_text:
            val = val * 14.696  # atm -> psia
        if 14.7 <= val <= 20000.0:
            spec.reservoir.initial_pressure = val
            provenance["initial_pressure"] = PROVENANCE_EXTRACTED
        else:
            provenance["initial_pressure"] = PROVENANCE_DEFAULTED
    else:
        provenance["initial_pressure"] = PROVENANCE_DEFAULTED

    # --- per-layer permeability overrides (when user names perm) -----------
    # "perm 500, 50, 200 mD", "permeability 500 50 200", "kx = 500 mD
    # ky=50 kz=200". Captures a sequence of 1+ numeric values separated
    # by commas, whitespace, or the keyword 'and'.
    perm_match = re.search(
        r"(?:perm(?:eability)?|kx|ky|kz|permx|permy|permz)"
        r"\s*(?:of|=|is|:)?\s*"
        r"(\d+(?:\.\d+)?(?:\s*[,and\s]+\s*\d+(?:\.\d+)?)*)"
        r"\s*(?:mD|md|millidarcy)?\b",
        desc_lower,
    )
    if perm_match:
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", perm_match.group(1))]
        if nums:
            # Replicate across nz if the user named fewer than nz values.
            spec.reservoir.permx = [nums[i % len(nums)] for i in range(spec.reservoir.nz)]
            provenance["permx"] = PROVENANCE_EXTRACTED
            # Plain "perm" with one value treats all three axes as isotropic.
            # Multiple named axes (permx/permy/permz) require more context
            # than the offline parser can reliably extract, so leave y/z as
            # defaulted unless the user gave a single isotropic value.
            if len(nums) >= 1 and "permx" not in desc_lower and "ky" not in desc_lower:
                spec.reservoir.permy = list(spec.reservoir.permx)
                spec.reservoir.permz = list(spec.reservoir.permx)
                provenance["permy"] = PROVENANCE_EXTRACTED
                provenance["permz"] = PROVENANCE_EXTRACTED

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

    # Gas cap: producer in the oil zone, GOC at the top of layer 2 so layer 1
    # is an initial gas cap. Datum sits at the GOC at bubble point pressure
    # (4014.7 psia for the SPE1 PVTO, Rs 1.27) so cap gas and saturated oil
    # coexist at the contact.
    if spec.scenario == ScenarioType.GAS_CAP:
        dz_list = spec.reservoir.dz if isinstance(spec.reservoir.dz, list) \
            else [spec.reservoir.dz] * spec.reservoir.nz
        goc = spec.reservoir.top_depth + dz_list[0]
        bottom = spec.reservoir.top_depth + sum(dz_list)
        spec.equil_datum_depth = goc
        spec.equil_datum_pressure = 4014.7
        spec.equil_goc_depth = goc
        spec.equil_woc_depth = bottom + 25.0
        oil_zone_top = 2 if spec.reservoir.nz >= 2 else 1
        wells = [WellSpec(
            name="PROD",
            well_type=WellType.PROD,
            i=spec.reservoir.nx,
            j=spec.reservoir.ny,
            k1=oil_zone_top,
            k2=spec.reservoir.nz,
            reference_depth=bottom,
        )]

    # CO2 EOR (black-oil approximation): gas injector at (1,1) top layer with
    # a denser, more viscous injection-gas PVDG table; producer at (nx,ny).
    if spec.scenario == ScenarioType.CO2_EOR:
        spec.pvdg_rows = list(CO2_PVDG_ROWS)
        wells = [
            WellSpec(
                name="INJ",
                well_type=WellType.INJ,
                i=1,
                j=1,
                k1=1,
                k2=1,
                reference_depth=spec.reservoir.top_depth + 10.0,
                inject_fluid=InjectFluid.GAS,
                inject_rate=5000.0,
                bhp_max=6000.0,
            ),
            WellSpec(
                name="PROD",
                well_type=WellType.PROD,
                i=spec.reservoir.nx,
                j=spec.reservoir.ny,
                k1=1,
                k2=spec.reservoir.nz,
                reference_depth=spec.reservoir.top_depth + sum(
                    spec.reservoir.dz if isinstance(spec.reservoir.dz, list)
                    else [spec.reservoir.dz] * spec.reservoir.nz
                ),
            ),
        ]

    # Pressure buildup test: single high-rate producer completed in the bottom
    # layer of a uniform low-perm reservoir (measurable drawdown), flowed for
    # 180 days then stopped for a 20-day buildup with short timesteps.
    if spec.scenario == ScenarioType.BUILDUP:
        spec.reservoir.permx = [50.0] * spec.reservoir.nz
        spec.reservoir.permy = [50.0] * spec.reservoir.nz
        spec.reservoir.permz = [50.0] * spec.reservoir.nz
        dz_list = spec.reservoir.dz if isinstance(spec.reservoir.dz, list) \
            else [spec.reservoir.dz] * spec.reservoir.nz
        wells = [WellSpec(
            name="PROD",
            well_type=WellType.PROD,
            i=spec.reservoir.nx,
            j=spec.reservoir.ny,
            k1=spec.reservoir.nz,
            k2=spec.reservoir.nz,
            reference_depth=spec.reservoir.top_depth + sum(dz_list),
            target_rate=4000.0,
            bhp_limit=1000.0,
        )]
        spec.timesteps = [30.0] * 6

    # Multilayer: strong per-layer PERMX/PERMY contrast (500/50/200 md cycled
    # over nz) with restricted vertical communication (kv/kh = 0.1); producer
    # completed across all layers.
    if spec.scenario == ScenarioType.MULTILAYER:
        contrast = [500.0, 50.0, 200.0]
        spec.reservoir.permx = [contrast[i % 3] for i in range(spec.reservoir.nz)]
        spec.reservoir.permy = [contrast[i % 3] for i in range(spec.reservoir.nz)]
        spec.reservoir.permz = [contrast[i % 3] * 0.1 for i in range(spec.reservoir.nz)]
        dz_list = spec.reservoir.dz if isinstance(spec.reservoir.dz, list) \
            else [spec.reservoir.dz] * spec.reservoir.nz
        wells = [WellSpec(
            name="PROD",
            well_type=WellType.PROD,
            i=spec.reservoir.nx,
            j=spec.reservoir.ny,
            k1=1,
            k2=spec.reservoir.nz,
            reference_depth=spec.reservoir.top_depth + sum(dz_list) / 2,
        )]

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

    # WAG schedule: the initial WCONINJE injects water for the first ~90-day
    # half-cycle (spec.timesteps, ending exactly on 1 APR 2015 for the default
    # 1 JAN 2015 start), then 7 more half-cycles alternate gas/water at
    # calendar quarters via DATES events (4 full cycles x ~90 days each).
    if spec.scenario == ScenarioType.WAG:
        injector = next((w for w in wells if w.well_type == WellType.INJ), None)
        if injector is not None:
            spec.timesteps = [30.0, 30.0, 30.0]
            water_rate = injector.inject_rate
            gas_rate = 3000.0  # Mscf/day half-cycle gas slug
            quarter_dates = [
                "1 'JUL' 2015", "1 'OCT' 2015", "1 'JAN' 2016", "1 'APR' 2016",
                "1 'JUL' 2016", "1 'OCT' 2016", "1 'JAN' 2017",
            ]
            events = []
            for half_cycle, date in enumerate(quarter_dates, start=1):
                fluid = "GAS" if half_cycle % 2 == 1 else "WATER"
                rate = gas_rate if fluid == "GAS" else water_rate
                events.append(ScheduleEvent(
                    actions=[_wconinje_action(injector.name, fluid, rate, injector.bhp_max)],
                    date=date,
                ))
            spec.schedule = events

    # Buildup schedule: stop the producer after the drawdown, then take short
    # timesteps (0.25-4 days, 20 days total) to resolve the pressure buildup.
    if spec.scenario == ScenarioType.BUILDUP and wells:
        producer = wells[0]
        spec.schedule = [ScheduleEvent(
            actions=[_wconprod_stop_action(producer.name, producer.bhp_limit)],
            tstep_days=[0.25, 0.25, 0.5, 1.0, 2.0, 4.0, 4.0, 8.0],
        )]

    spec.wells = wells

    # Fill any rock-basics field that the parser did not touch with a
    # "defaulted" provenance tag. Belt-and-braces: every field in
    # ROCK_BASICS_FIELDS must end up in the dict.
    for f in ROCK_BASICS_FIELDS:
        provenance.setdefault(f, PROVENANCE_DEFAULTED)

    return spec, provenance


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