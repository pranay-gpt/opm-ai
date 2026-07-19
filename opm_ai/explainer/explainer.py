"""Core explain() function for the educational explainer.

This module implements the main explain() entry point with LLM + offline fallback.
"""

from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger

from opm_ai.explainer.models import Citation, Explanation, ExplanationLevel
from opm_ai.explainer.retrieve import retrieve_chunks
from opm_ai.llm.client import LLMClient


# ---- Offline Fallback Templates ----

OFFLINE_TEMPLATES = {
    "watercut": {
        "beginner": (
            "Based on the knowledge base, water cut increases when injected water "
            "breaks through to the production well. This is called **water breakthrough**. "
            "Before breakthrough, the well produces mostly oil. After breakthrough, "
            "water cut rises sharply as the water front passes through the reservoir "
            "rock toward the producer. The timing depends on injection rate, well "
            "spacing, and how easily water moves relative to oil (mobility ratio)."
        ),
        "intermediate": (
            "Water cut behavior follows **Buckley-Leverett fractional flow theory**. "
            "The water fractional flow $f_w$ depends on water saturation $S_w$ through "
            "relative permeability:\n"
            "$$f_w = \\frac{1}{1 + \\frac{k_{ro}}{k_{rw}} \\frac{\\mu_w}{\\mu_o}}$$"
            "where $k_{ro}, k_{rw}$ are relative permeabilities and $\\mu_o, \\mu_w$ "
            "are viscosities. Water breakthrough occurs when the shock front reaches "
            "the producer. The shock front saturation $S_{w}^*$ satisfies the tangent "
            "line condition: $df_w/dS_w = f_w/(S_w - S_{wc})$. After breakthrough, "
            "water cut follows the fractional flow curve. An unfavorable mobility ratio "
            "$M = (k_{rw}/\\mu_w)/(k_{ro}/\\mu_o) > 1$ leads to early breakthrough "
            "and poor sweep efficiency."
        ),
        "advanced": (
            "Water breakthrough timing in numerical simulation is controlled by the "
            "discretized fractional flow equation. Using TPFA (Two-Point Flux "
            "Approximation) on a structured grid, the water saturation equation is:\n"
            "$$\\phi \\frac{\\partial S_w}{\\partial t} + \\nabla \\cdot (f_w \\mathbf{v}_t) = q_w$$\n"
            "where $\\mathbf{v}_t = -\\lambda_t \\mathbf{K} \\nabla p$ is total velocity. "
            "The shock front is captured numerically but subject to **numerical "
            "dispersion** (grid block size $\\Delta x$ smears the front). OPM Flow "
            "uses upstream weighting for mobility terms. Convergence issues near "
            "breakthrough often manifest as timestep chops due to the sharp saturation "
            "gradient. The **CPR-AMG** linear solver handles the pressure block; "
            "saturation updates use Newton iteration. For grid convergence, refine "
            "until breakthrough time changes < 5%."
        ),
    },
    "recovery": {
        "beginner": (
            "Oil recovery factor tells you what fraction of the original oil in place "
            "has been produced. In a waterflood, recovery depends on how well the "
            "injected water sweeps the reservoir. **Sweep efficiency** has two parts: "
            "(1) *Areal sweep* - does water contact all parts of the reservoir? "
            "(2) *Vertical sweep* - does water contact all layers? Poor sweep leaves "
            "oil behind. Good waterflood design uses pattern flooding (like 5-spot) "
            "and mobility control (polymer) to improve sweep."
        ),
        "intermediate": (
            "Recovery factor $RF = N_p / N$ where $N_p$ is cumulative oil production "
            "and $N$ is original oil in place (OOIP). For waterflood, "
            "$$RF = E_A \\times E_V \\times E_D \\times (1 - S_{or})$$\n"
            "where $E_A$ = areal sweep efficiency, $E_V$ = vertical sweep efficiency, "
            "$E_D$ = displacement efficiency, $S_{or}$ = residual oil saturation. "
            "Displacement efficiency depends on mobility ratio and capillary number. "
            "**Buckley-Leverett theory** gives 1D displacement efficiency; pattern "
            "models (Dykstra-Parsons, Craig-Geffen-Morse) extend to 2D/3D areal "
            "and vertical sweep. **Stiles method** accounts for layering: "
            "$E_V = 1 - \\frac{\\sum h_i k_i (1 - E_{D,i})}{\\sum h_i k_i}$."
        ),
        "advanced": (
            "In simulation, recovery factor is computed from cumulative production: "
            "$N_p = \\sum FOPT$. The material balance equation provides a check: "
            "$N = \\frac{N_p B_o + W_p B_w + G_p B_g + (W_e - W_p) B_w}{B_o - B_{oi} + "
            "(R_{si} - R_s) B_g + B_{oi}(c_w S_{wi} + c_f) \\Delta p / (1 - S_{wi})}$. "
            "Numerical dispersion in the saturation equation overpredicts sweep "
            "efficiency on coarse grids. **Grid convergence study** required: refine "
            "until $RF$ changes < 2%. **Adaptive mesh refinement (AMR)** near the "
            "waterfront improves accuracy. OPM Flow's **CPR-AMG** solver with "
            "ILU(0) preconditioning on the saturation block handles the coupled "
            "pressure-saturation system. For highly heterogeneous models, "
            "**multi-scale methods** (MSFV, MsFEM) provide coarse-scale accuracy "
            "with fine-scale detail."
        ),
    },
    "pressure": {
        "beginner": (
            "Reservoir pressure drops as fluids are produced. The rate of pressure "
            "decline depends on the drive mechanism: depletion drive (fast decline), "
            "gas cap expansion (moderate), water drive (slow). Pressure maintenance "
            "via water or gas injection keeps pressure high, improving oil recovery "
            "and well productivity. **Bubble point pressure** is critical - below it, "
            "gas comes out of solution, changing fluid properties and well performance."
        ),
        "intermediate": (
            "Pressure behavior is governed by the **diffusivity equation**: "
            "$$\\frac{\\partial p}{\\partial t} = \\frac{k}{\\phi \\mu c_t} \\nabla^2 p$$\n"
            "where $c_t = c_o S_o + c_w S_w + c_g S_g + c_f$ is total compressibility. "
            "For radial flow to a well: $p(r,t) = p_i - \\frac{q \\mu}{4 \\pi k h} "
            "\\left[ \\ln\\left(\\frac{4 k t}{\\phi \\mu c_t r_w^2}\\right) - \\gamma "
            "\\right]$ (line-source solution). **Material balance** provides average "
            "reservoir pressure: $N_p B_o = N (B_o - B_{oi}) + N B_{oi} \\frac{R_{si} - "
            "R_s}{B_g} + ...$. Below bubble point, two-phase flow and gas evolution "
            "increase total mobility, accelerating pressure decline."
        ),
        "advanced": (
            "In fully implicit simulation, pressure is solved simultaneously with "
            "saturations via Newton-Raphson. The Jacobian matrix couples pressure "
            "and saturation blocks. **CPR (Constrained Pressure Residual)** "
            "preconditioning solves the pressure block with AMG, then applies "
            "ILU to the full system. **Timestep selection** uses truncation error "
            "estimation: $\\Delta t_{new} = \\Delta t_{old} \\left(\\frac{\\epsilon_{target}}{\\epsilon_{est}}\\right)^{1/2}$. "
            "Near bubble point, the Jacobian becomes ill-conditioned due to phase "
            "appearance; OPM Flow uses **phase appearance/disappearance logic** with "
            "switching variables to maintain quadratic convergence. **Constraint "
            "switching** (rate <-> BHP) adds complementarity conditions solved via "
            "active-set method."
        ),
    },
    "bubble_point": {
        "beginner": (
            "The **bubble point** is the pressure at which gas first comes out of "
            "solution in the oil. Above bubble point, oil is undersaturated (single "
            "phase). Below it, gas evolves (two-phase: oil + free gas). This changes "
            "everything: oil shrinks (Bo drops), gas flows (high mobility), viscosity "
            "increases, and well GOR rises. In simulation, crossing the bubble point "
            "often causes timestep chops because the physics changes abruptly."
        ),
        "intermediate": (
            "At bubble point $P_b$, $R_s = R_{si}$ and $B_o = B_{ob}$. Below $P_b$:\n"
            "- $R_s$ decreases with pressure (gas leaves solution)\n"
            "- $B_o$ decreases (oil shrinks as gas leaves)\n"
            "- Free gas saturation $S_g > 0$, gas relative permeability $k_{rg} > 0$\n"
            "- Solution gas-oil ratio follows correlation (e.g., Standing, Vazquez-Beggs)\n"
            "In PVT tables (`PVTO` keyword), $R_s$, $B_o$, $\\mu_o$ are tabulated vs "
            "pressure. Interpolation method matters near $P_b$: linear is standard but "
            "spline can overshoot. **Phase appearance** in simulation: when $S_g$ "
            "exceeds critical gas saturation $S_{gc}$, gas becomes mobile."
        ),
        "advanced": (
            "Bubble point crossing introduces **strong nonlinearity** in the "
            "Jacobian. The oil phase molar density $n_o = (1 - R_s/R_{si})/B_o $ "
            "changes slope at $P_b$. Newton iteration may diverge if timestep is too "
            "large. OPM Flow handles phase transitions via **switching variables** "
            "(e.g., use $P$ and $S_g$ as primary variables when gas present, $P$ and "
            "$R_s$ when not). The complementarity condition $S_g \\ge 0, \\quad "
            "p - p_b(R_s) \\ge 0, \\quad S_g (p - p_b) = 0$ is solved via active-set. "
            "For compositional simulation, **negative flash** algorithms handle phase "
            "appearance robustly. **Adaptive timestepping** with error control "
            "(\\texttt{TUNING} keyword) is essential near $P_b$."
        ),
    },
    "generic": {
        "beginner": (
            "Based on the knowledge base, here's what you need to know. The simulation "
            "shows key reservoir behaviors that are explained by fundamental petroleum "
            "engineering principles. The results match expected patterns for this "
            "type of reservoir and drive mechanism."
        ),
        "intermediate": (
            "The simulation results can be understood through standard reservoir "
            "engineering concepts: material balance, fractional flow theory, and "
            "well deliverability equations. The knowledge base contains relevant "
            "sections from the Eclipse reference manual and OPM technical description "
            "that support this interpretation."
        ),
        "advanced": (
            "Numerical simulation results reflect the coupled solution of mass "
            "conservation equations discretized via TPFA on a structured grid, "
            "solved fully implicitly with Newton-Raphson and CPR-AMG linear solver. "
            "Key numerical parameters (timestep control, convergence tolerances, "
            "grid resolution) affect the quantitative results. Refer to OPM Flow "
            "technical description for solver details."
        ),
    },
}


FOLLOW_UP_MAP = {
    "watercut": [
        "How does mobility ratio affect water breakthrough timing?",
        "What is the Buckley-Leverett shock front and how is it captured numerically?",
        "How can polymer injection improve sweep efficiency after breakthrough?",
    ],
    "recovery": [
        "How do you calculate sweep efficiency from simulation results?",
        "What is the difference between displacement efficiency and volumetric sweep?",
        "How does reservoir heterogeneity affect waterflood recovery?",
    ],
    "pressure": [
        "How does material balance verify simulation pressure predictions?",
        "What is the diffusivity equation and how does it apply to pressure transient analysis?",
        "How do well constraints affect reservoir pressure distribution?",
    ],
    "bubble_point": [
        "How does crossing bubble point affect well deliverability?",
        "What PVT properties change at bubble point and how are they modeled?",
        "Why does simulation often chop timesteps near bubble point?",
    ],
    "generic": [
        "What are the key KPIs to monitor for this type of simulation?",
        "How would you history match this simulation to field data?",
        "What sensitivities should be run to understand uncertainty?",
    ],
}


def _detect_topic(text: str) -> str:
    """Detect topic from text for template selection."""
    text_lower = text.lower()
    if any(kw in text_lower for kw in ["watercut", "water cut", "breakthrough", "wct"]):
        return "watercut"
    if any(kw in text_lower for kw in ["recovery", "rf ", "factor", "sweep", "ooip", "n_p"]):
        return "recovery"
    if any(kw in text_lower for kw in ["pressure", "bhp", "drawdown", "buildup", "diffusivity"]):
        return "pressure"
    if any(kw in text_lower for kw in ["bubble point", "bubblepoint", "rs ", "gas-oil ratio", "gor", "solution gas"]):
        return "bubble_point"
    return "generic"


def _kpi_summary(kpis: dict[str, Any]) -> str:
    """Build a narrative summary from KPI dictionary."""
    parts = []
    if kpis.get("days"):
        parts.append(f"Simulation ran for {kpis['days']:.0f} days.")
    if kpis.get("field_oil_recovery"):
        parts.append(f"Cumulative oil production: {kpis['field_oil_recovery']:,.0f} STB.")
    if kpis.get("water_breakthrough_day"):
        parts.append(f"Water breakthrough at day {kpis['water_breakthrough_day']:.0f}.")
    if kpis.get("max_watercut") is not None:
        parts.append(f"Maximum water cut: {kpis['max_watercut']*100:.1f}%.")
    if kpis.get("producer_count"):
        parts.append(f"Number of producers: {kpis['producer_count']}.")
    if kpis.get("avg_gor"):
        parts.append(f"Average GOR: {kpis['avg_gor']:.0f} SCF/STB.")
    return " ".join(parts) if parts else "Simulation completed with standard KPIs."


def _build_prompt(topic: str, level: ExplanationLevel, citations: list[Citation]) -> list[dict]:
    """Build messages for LLM call."""
    level_instructions = {
        "beginner": (
            "Explain in plain English for a student new to reservoir simulation. "
            "Use analogies. No equations. Define all technical terms. 3-4 paragraphs."
        ),
        "intermediate": (
            "Explain for a graduate student or engineer. Include key governing "
            "equations (Darcy, material balance, fractional flow). Define symbols. "
            "3-4 paragraphs with equations in LaTeX."
        ),
        "advanced": (
            "Explain for a reservoir simulation expert. Include numerical methods "
            "(TPFA, Newton-Raphson, CPR-AMG, timestep control), discretization "
            "details, and convergence considerations. Use technical terminology. "
            "3-4 paragraphs with equations."
        ),
    }

    citation_text = "\n\n".join([
        f"[Citation {i+1}] {c.title} (source: {c.source_id})\n{c.snippet}"
        for i, c in enumerate(citations)
    ])

    system_prompt = (
        "You are an expert reservoir engineering educator. Provide a clear, "
        "accurate explanation at the requested level. Use the provided citations "
        "to support your statements. End with exactly 2-3 follow-up questions, "
        "each on a new line prefixed with 'FOLLOW-UP:'."
    )

    user_prompt = (
        f"Topic: {topic}\n\n"
        f"Level: {level}\n\n"
        f"Instructions: {level_instructions[level]}\n\n"
        f"Citations:\n{citation_text}\n\n"
        f"Write the explanation in Markdown. Then add 2-3 follow-up questions "
        f"prefixed with 'FOLLOW-UP:'."
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _parse_llm_response(response: str) -> tuple[str, list[str]]:
    """Parse LLM response into explanation text and follow-up questions."""
    # Find FOLLOW-UP lines
    follow_ups = re.findall(r"^FOLLOW-UP:\s*(.+)$", response, re.MULTILINE)
    # Remove follow-up lines from main text
    text = re.sub(r"^FOLLOW-UP:.*$", "", response, flags=re.MULTILINE).strip()
    return text, follow_ups[:3]


def explain(
    topic_or_result: str | dict,
    level: ExplanationLevel = "intermediate",
    context: dict | None = None,
) -> Explanation:
    """
    Main entry point for generating explanations.

    Args:
        topic_or_result: Free-text question or KPI dict from extract_kpis()
        level: Explanation level (beginner/intermediate/advanced)
        context: Optional dict with deck_path, simulation_result, kpis, plots

    Returns:
        Explanation with markdown text, citations, and follow-up questions.
    """
    # Build topic summary
    if isinstance(topic_or_result, dict):
        topic = _kpi_summary(topic_or_result)
    else:
        topic = topic_or_result

    # Retrieve relevant chunks
    citations = retrieve_chunks(topic, k=5, level=level)
    # Use top 3 for LLM context
    llm_citations = citations[:3]

    # Try LLM
    llm = LLMClient()
    explanation_text = ""
    follow_ups: list[str] = []

    if llm.available:
        try:
            messages = _build_prompt(topic, level, llm_citations)
            response = llm.chat(messages)
            if response:
                explanation_text, follow_ups = _parse_llm_response(response)
                logger.debug("LLM explanation generated successfully")
        except Exception as e:
            logger.warning(f"LLM call failed: {e}, falling back to offline template")

    # Offline fallback
    if not explanation_text:
        topic_key = _detect_topic(topic)
        template = OFFLINE_TEMPLATES.get(topic_key, OFFLINE_TEMPLATES["generic"])
        explanation_text = template[level]

        # Add citation references
        if citations:
            explanation_text += "\n\n**Sources:**\n"
            for i, c in enumerate(citations[:3]):
                explanation_text += f"{i+1}. {c.title} ({c.source_id})\n"

        follow_ups = FOLLOW_UP_MAP.get(topic_key, FOLLOW_UP_MAP["generic"])

    return Explanation(
        topic=topic,
        level=level,
        text=explanation_text,
        citations=tuple(citations),
        follow_up_questions=tuple(follow_ups[:3]),
    )