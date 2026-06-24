# opm_ai/builder/builder.py
"""
Description-to-Deck Builder — two-stage pipeline:

  Stage 1 (LLM):     Parse a plain-English description into a
                     ReservoirDescription dataclass via Groq.
  Stage 2 (Physics): Compute PVT properties from correlations
                     (pvt_builder.build_pvt_props).
  Stage 3 (Jinja2):  Render a valid OPM deck from the populated
                     dataclass using templates/base.j2.

The deck is automatically linted before being returned.
"""
import os
import json
import re
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .models import (
    ReservoirDescription, WellSpec, FluidSystem,
    GridType, BuildResult,
)
from ..linter import lint_deck
from ..preprocess.pvt_builder import build_pvt_props

load_dotenv()

_GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
_LLM_MODEL    = "llama-3.3-70b-versatile"
_TEMPLATES    = Path(__file__).parent / "templates"


# ── Public API ──────────────────────────────────────────────────────────────────

def build_deck(
    description: str,
    use_llm: bool = True,
) -> BuildResult:
    """
    Turn a plain-English reservoir description into a runnable OPM deck.

    Parameters
    ----------
    description : natural-language description from the user
    use_llm     : if True, use Groq to extract parameters; if False,
                  fall back to sensible defaults (useful for testing)

    Returns
    -------
    BuildResult with the rendered deck, lint status, and any warnings.
    """
    logger.info(f"Builder: parsing description ({len(description)} chars)")

    if use_llm and _GROQ_API_KEY:
        res_desc = _llm_extract_parameters(description)
    else:
        if use_llm and not _GROQ_API_KEY:
            logger.warning("Builder LLM stage skipped: GROQ_API_KEY not set")
        res_desc = _default_description(description)

    # Stage 2: compute PVT from physics correlations
    _populate_pvt(res_desc)

    logger.info(
        f"Builder: rendering deck — "
        f"{res_desc.nx}x{res_desc.ny}x{res_desc.nz} grid, "
        f"{len(res_desc.wells)} well(s), "
        f"{res_desc.fluid_system.value}, "
        f"T={res_desc.t_res}°C, P={res_desc.p_init} bar"
    )

    deck_text = _render_template(res_desc)
    lint = lint_deck(deck_text, use_llm=False)

    return BuildResult(
        description=res_desc,
        deck_text=deck_text,
        lint_passed=lint.is_runnable,
        lint_summary=lint.llm_summary,
        warnings=[f"[{d.rule_id}] {d.keyword}: {d.plain_english}" for d in lint.diagnostics],
    )


def build_from_description(
    res_desc: ReservoirDescription,
) -> BuildResult:
    """Build a deck directly from a ReservoirDescription (skip LLM stage)."""
    _populate_pvt(res_desc)
    deck_text = _render_template(res_desc)
    lint = lint_deck(deck_text, use_llm=False)
    return BuildResult(
        description=res_desc,
        deck_text=deck_text,
        lint_passed=lint.is_runnable,
        lint_summary=lint.llm_summary,
        warnings=[f"[{d.rule_id}] {d.keyword}: {d.plain_english}" for d in lint.diagnostics],
    )


# ── PVT population ─────────────────────────────────────────────────────────────

def _populate_pvt(res_desc: ReservoirDescription) -> None:
    """
    Compute PVT properties from physics correlations and write them
    back onto res_desc in-place.  Modifies water_fvf, water_comp,
    water_visc, oil_fvf, oil_visc, gas_fvf, gas_visc, rho_*,
    pvto_rows, pvdg_rows.
    """
    pvt = build_pvt_props(
        p_init_bar   = res_desc.p_init,
        t_c          = res_desc.t_res,
        fluid_system = res_desc.fluid_system.value,
        api          = res_desc.api,
        sg_gas       = res_desc.sg_gas,
        salinity_ppm = res_desc.salinity_ppm,
    )

    # Water (all fluid systems)
    res_desc.water_fvf  = pvt.pvtw_bw
    res_desc.water_comp = pvt.pvtw_cw
    res_desc.water_visc = pvt.pvtw_visc
    res_desc.rho_water  = pvt.rho_water

    # Oil
    if pvt.pvcdo_bo is not None:              # oil_water (dead oil)
        res_desc.oil_fvf  = pvt.pvcdo_bo
        res_desc.oil_visc = pvt.pvcdo_visc
    if pvt.pvto_rows:                          # black_oil (saturated table)
        # Scalar fields from the last (highest-pressure) row for legacy template use
        last_entry = pvt.pvto_rows[-1][1][0]
        res_desc.oil_fvf  = last_entry[1]
        res_desc.oil_visc = last_entry[2]
    if pvt.pvto_rows is not None:
        res_desc.pvto_rows = pvt.pvto_rows
    res_desc.rho_oil = pvt.rho_oil

    # Gas
    if pvt.pvdg_rows:
        last_gas = pvt.pvdg_rows[-1]
        res_desc.gas_fvf  = last_gas[1]
        res_desc.gas_visc = last_gas[2]
    res_desc.pvdg_rows = pvt.pvdg_rows
    res_desc.rho_gas   = pvt.rho_gas


# ── LLM parameter extraction ───────────────────────────────────────────────────

_EXTRACTION_PROMPT = """
You are an expert reservoir simulation engineer. Extract reservoir parameters
from the user's description and return ONLY a JSON object — no explanation,
no markdown, no extra text.

JSON schema (all fields optional — omit any you cannot infer):
{
  "title":          string,
  "nx":             int,
  "ny":             int,
  "nz":             int,
  "dx":             float,   // cell size metres
  "dy":             float,
  "dz":             float,
  "depth_top":      float,   // metres TVD
  "porosity":       float,   // fraction 0-1
  "permeability":   float,   // mD
  "perm_v_h_ratio": float,   // Kv/Kh fraction
  "fluid_system":   "oil_water" | "gas_water" | "black_oil" | "dry_gas",
  "p_init":         float,   // bar
  "t_res":          float,   // reservoir temperature degC
  "api":            float,   // oil API gravity
  "sg_gas":         float,   // gas specific gravity (air=1)
  "salinity_ppm":   float,   // brine NaCl ppm
  "swi":            float,   // initial water saturation fraction
  "sim_years":      float,
  "report_freq":    "monthly" | "quarterly" | "yearly",
  "wells": [
    {
      "name":      string,
      "type":      "PRODUCER" | "INJECTOR",
      "i":         int,
      "j":         int,
      "k1":        int,
      "k2":        int,
      "control":   "BHP" | "ORAT" | "WRAT" | "GRAT" | "LRAT",
      "rate":      float,
      "bhp_limit": float,
      "inj_fluid": "WATER" | "GAS",
      "inj_rate":  float,
      "inj_bhp_max": float
    }
  ]
}

User description:
"""


def _llm_extract_parameters(description: str) -> ReservoirDescription:
    """Call Groq to parse the description into a ReservoirDescription."""
    try:
        from groq import Groq
    except ImportError:
        logger.warning("groq not installed — using defaults")
        return _default_description(description)

    client = Groq(api_key=_GROQ_API_KEY)
    try:
        response = client.chat.completions.create(
            model=_LLM_MODEL,
            messages=[{
                "role": "user",
                "content": _EXTRACTION_PROMPT + description,
            }],
            temperature=0.1,
            max_tokens=1024,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        params = json.loads(raw)
        return _params_to_description(params, description)

    except Exception as exc:  # noqa: BLE001
        logger.warning(f"LLM extraction failed: {exc} — using defaults")
        return _default_description(description)


def _params_to_description(
    params: dict,
    original: str,
) -> ReservoirDescription:
    """Map LLM-extracted JSON dict to a ReservoirDescription."""
    wells = []
    for w in params.get("wells", []):
        wells.append(WellSpec(
            name        = w.get("name", "W1"),
            type        = w.get("type", "PRODUCER"),
            i           = int(w.get("i", 5)),
            j           = int(w.get("j", 5)),
            k1          = int(w.get("k1", 1)),
            k2          = int(w.get("k2", 1)),
            group       = w.get("group", "FIELD"),
            control     = w.get("control", "BHP"),
            rate        = float(w.get("rate", 0.0)),
            bhp_limit   = float(w.get("bhp_limit", 100.0)),
            inj_fluid   = w.get("inj_fluid", "WATER"),
            inj_rate    = float(w.get("inj_rate", 0.0)),
            inj_bhp_max = float(w.get("inj_bhp_max", 400.0)),
        ))

    fluid_map = {
        "oil_water": FluidSystem.OIL_WATER,
        "gas_water": FluidSystem.GAS_WATER,
        "black_oil": FluidSystem.BLACK_OIL,
        "dry_gas":   FluidSystem.DRY_GAS,
    }

    if not wells:
        nx = int(params.get("nx", 10))
        ny = int(params.get("ny", 10))
        nz = int(params.get("nz", 3))
        wells = _auto_place_wells(original, nx, ny, nz)

    return ReservoirDescription(
        title          = params.get("title", "opm-ai Generated Reservoir"),
        nx             = int(params.get("nx", 10)),
        ny             = int(params.get("ny", 10)),
        nz             = int(params.get("nz", 3)),
        dx             = float(params.get("dx", 100.0)),
        dy             = float(params.get("dy", 100.0)),
        dz             = float(params.get("dz", 10.0)),
        depth_top      = float(params.get("depth_top", 2000.0)),
        porosity       = float(params.get("porosity", 0.20)),
        permeability   = float(params.get("permeability", 100.0)),
        perm_v_h_ratio = float(params.get("perm_v_h_ratio", 0.1)),
        fluid_system   = fluid_map.get(
            params.get("fluid_system", "oil_water"),
            FluidSystem.OIL_WATER,
        ),
        p_init         = float(params.get("p_init", 350.0)),
        t_res          = float(params.get("t_res", 80.0)),
        api            = float(params.get("api", 35.0)),
        sg_gas         = float(params.get("sg_gas", 0.65)),
        salinity_ppm   = float(params.get("salinity_ppm", 50_000.0)),
        swi            = float(params.get("swi", 0.20)),
        sim_years      = float(params.get("sim_years", 5.0)),
        report_freq    = params.get("report_freq", "monthly"),
        wells          = wells,
    )


def _auto_place_wells(
    description: str,
    nx: int,
    ny: int,
    nz: int,
) -> list[WellSpec]:
    """Auto-place wells when LLM gave count but no positions."""
    desc_lower = description.lower()
    n_prod = 1
    n_inj  = 0

    if "injector" in desc_lower or "injection" in desc_lower:
        n_inj = 1
    if "two producer" in desc_lower or "2 producer" in desc_lower:
        n_prod = 2

    wells = [
        WellSpec(name="PROD1", type="PRODUCER",
                 i=nx // 2, j=ny // 2, k1=1, k2=nz,
                 control="BHP", bhp_limit=100.0)
    ]
    if n_prod > 1:
        wells.append(WellSpec(name="PROD2", type="PRODUCER",
                              i=nx // 2 + 2, j=ny // 2, k1=1, k2=nz,
                              control="BHP", bhp_limit=100.0))
    if n_inj > 0:
        wells.append(WellSpec(name="INJ1", type="INJECTOR",
                              i=1, j=1, k1=1, k2=nz,
                              inj_fluid="WATER", inj_rate=200.0, inj_bhp_max=400.0))
    return wells


# ── Jinja2 renderer ────────────────────────────────────────────────────────────────────

def _render_template(desc: ReservoirDescription) -> str:
    """Render base.j2 with the given ReservoirDescription."""
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["FluidSystem"] = FluidSystem
    env.globals["GridType"]    = GridType
    template = env.get_template("base.j2")
    return template.render(desc=desc)


# ── Default fallback ───────────────────────────────────────────────────────────────────────

def _default_description(description: str) -> ReservoirDescription:
    """Minimal sensible defaults when LLM is unavailable."""
    return ReservoirDescription(
        title=description[:60].strip() or "opm-ai Default Reservoir",
        wells=[
            WellSpec(name="PROD1", type="PRODUCER",
                     i=5, j=5, k1=1, k2=3,
                     control="BHP", bhp_limit=100.0),
            WellSpec(name="INJ1", type="INJECTOR",
                     i=1, j=1, k1=1, k2=3,
                     inj_fluid="WATER", inj_rate=200.0, inj_bhp_max=400.0),
        ]
    )
