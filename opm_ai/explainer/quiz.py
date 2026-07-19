"""Quiz generation for the educational explainer.

This module implements generate_quiz() with LLM + offline fallback.
"""

from __future__ import annotations

import json
import re
import random
from typing import Any

from opm_ai.explainer.models import ExplanationLevel, Quiz, QuizQuestion
from opm_ai.explainer.retrieve import retrieve_chunks
from opm_ai.llm.client import LLMClient


# ---- Offline Fallback Question Bank ----

OFFLINE_QUESTIONS = [
    QuizQuestion(
        question="What is the primary mechanism controlling water breakthrough timing in a waterflood?",
        options=(
            "Capillary pressure",
            "Mobility ratio and fractional flow",
            "Rock compressibility",
            "Wellbore storage",
        ),
        correct_index=1,
        explanation="Water breakthrough is governed by Buckley-Leverett fractional flow theory. The shock front velocity depends on the derivative of fractional flow with respect to saturation, which is controlled by the mobility ratio (krw/μw)/(kro/μo). Unfavorable mobility ratio (M > 1) leads to early breakthrough.",
        level="intermediate",
        topic_tags=("waterflood", "watercut", "relative_permeability", "buckley_leverett"),
    ),
    QuizQuestion(
        question="In Buckley-Leverett theory, the shock front saturation Sw* is determined by which condition?",
        options=(
            "dfw/dSw = 0",
            "fw/Sw = maximum",
            "Tangent from Swc to fw curve: dfw/dSw = fw/(Sw - Swc)",
            "fw = 0.5",
        ),
        correct_index=2,
        explanation="The shock front saturation is found by drawing a tangent from the connate water saturation (Swc) to the fractional flow curve. The slope of this tangent equals dfw/dSw at Sw*, and the intercept gives the shock front condition.",
        level="advanced",
        topic_tags=("waterflood", "buckley_leverett", "fractional_flow"),
    ),
    QuizQuestion(
        question="What happens to oil formation volume factor (Bo) when reservoir pressure drops below bubble point?",
        options=(
            "Bo increases as gas comes out of solution",
            "Bo decreases as gas comes out of solution",
            "Bo stays constant",
            "Bo increases then decreases",
        ),
        correct_index=1,
        explanation="Below bubble point, solution gas evolves and leaves the oil phase. The oil shrinks (volume decreases), so Bo = Vres/Vstb decreases. Above bubble point, Bo increases slightly with pressure due to oil compressibility.",
        level="beginner",
        topic_tags=("pvt", "bubble_point", "formation_volume_factor"),
    ),
    QuizQuestion(
        question="Which relative permeability correlation uses power-law exponents (no, nw) to describe curve shape?",
        options=(
            "Corey correlation",
            "Brooks-Corey",
            "van Genuchten",
            "Leverett J-function",
        ),
        correct_index=0,
        explanation="The Corey correlation (1954) uses power-law exponents: kro = kro0 * ((1-Sw-Sor)/(1-Swc-Sor))^no and krw = krw0 * ((Sw-Swc)/(1-Swc-Sor))^nw. This is the most common correlation in reservoir simulation.",
        level="intermediate",
        topic_tags=("relative_permeability", "corey", "correlations"),
    ),
    QuizQuestion(
        question="In a simulation using rate control for a producer, what happens when the well's BHP would drop below the minimum BHP constraint?",
        options=(
            "The well shuts in",
            "The well switches to BHP control at the minimum BHP",
            "The rate constraint is ignored",
            "The timestep is cut and rate is reduced",
        ),
        correct_index=1,
        explanation="Eclipse/OPM Flow well control logic: when a rate-constrained well hits a BHP limit, it automatically switches to BHP control at that limit. The well produces whatever rate results at the minimum BHP. This is standard constraint switching behavior.",
        level="intermediate",
        topic_tags=("well_control", "rate_control", "bhp_constraint", "eclipse"),
    ),
    QuizQuestion(
        question="What is the material balance equation for a depletion-drive reservoir (no water influx, no gas cap)?",
        options=(
            "NpBo = N(Bo - Boi) + N Boi (Rsi - Rs)/Bg",
            "NpBo = N(Bo - Boi) + N Boi (Rsi - Rs)/Bg + N Boi (cwSwi + cf)/(1-Swi) Δp",
            "NpBo = N(Bo - Boi) + N Boi (cwSwi + cf)/(1-Swi) Δp",
            "NpBo = N(Bo - Boi) + We Bw",
        ),
        correct_index=2,
        explanation="For depletion drive (no aquifer, no gas cap), the material balance includes oil expansion, solution gas expansion, and formation/connate water expansion. The water influx term We Bw is zero.",
        level="advanced",
        topic_tags=("material_balance", "depletion_drive", "reservoir_engineering"),
    ),
    QuizQuestion(
        question="Why does a simulation often chop timesteps when pressure crosses the bubble point?",
        options=(
            "Numerical instability from phase appearance",
            "Grid blocks become inactive",
            "Well constraints are violated",
            "Relative permeability tables end",
        ),
        correct_index=0,
        explanation="At bubble point, a new phase (free gas) appears. This introduces a strong nonlinearity in the Jacobian (phase appearance condition Sg ≥ 0, p - Pb(Rs) ≥ 0, Sg·(p - Pb) = 0). The Newton iteration may diverge, triggering timestep chops. OPM Flow uses switching variables and active-set methods to handle this.",
        level="advanced",
        topic_tags=("bubble_point", "phase_appearance", "newton_convergence", "timestep_chop"),
    ),
    QuizQuestion(
        question="What does the CPR-AMG preconditioner do in OPM Flow's linear solver?",
        options=(
            "Solves the full system with algebraic multigrid",
            "Solves pressure block with AMG, then applies ILU to full system",
            "Only solves the saturation equations",
            "Reorders the matrix for better sparsity",
        ),
        correct_index=1,
        explanation="CPR (Constrained Pressure Residual) preconditioning: 1) Solve the pressure block (elliptic part) with AMG (Algebraic Multigrid), 2) Apply ILU(0) to the full system as a smoother. This handles the pressure-saturation coupling efficiently for black-oil systems.",
        level="advanced",
        topic_tags=("cpr_amg", "linear_solver", "preconditioner", "opm_flow"),
    ),
    QuizQuestion(
        question="How is water cut defined in a producing well?",
        options=(
            "Water production rate / Total liquid production rate",
            "Water production rate / Oil production rate",
            "Cumulative water / Cumulative oil",
            "Water saturation at wellbore",
        ),
        correct_index=0,
        explanation="Water cut (WC or WCT) = WWPR / (WOPR + WWPR) at surface conditions. It's a rate-based fraction (0 to 1), not a cumulative ratio or saturation. In simulation, it's computed from well connection fluxes.",
        level="beginner",
        topic_tags=("watercut", "well_performance", "production_engineering"),
    ),
    QuizQuestion(
        question="In a 5-spot waterflood pattern, what primarily controls areal sweep efficiency?",
        options=(
            "Vertical permeability",
            "Mobility ratio and pattern geometry",
            "Wellbore radius",
            "Initial pressure",
        ),
        correct_index=1,
        explanation="Areal sweep efficiency in pattern floods is dominated by mobility ratio (M) and pattern geometry (5-spot, line drive, etc.). Adverse mobility ratio (M > 1) causes fingering and poor areal sweep. Dykstra-Parsons and Craig-Geffen-Morse correlations quantify this.",
        level="intermediate",
        topic_tags=("waterflood", "areal_sweep", "mobility_ratio", "pattern_flood"),
    ),
]


# ---- Topic Keywords for Filtering ----

TOPIC_KEYWORDS = {
    "waterflood": ["waterflood", "water flood", "injection", "injector", "5-spot", "pattern"],
    "watercut": ["watercut", "water cut", "breakthrough", "wct", "fractional flow"],
    "pvt": ["pvt", "bubble point", "bubblepoint", "rs ", "gor", "formation volume", "bo ", "bg "],
    "relperm": ["relative permeability", "relperm", "corey", "krw", "kro", "krg"],
    "well_control": ["well control", "rate control", "bhp", "wconprod", "wconinje", "constraint"],
    "material_balance": ["material balance", "mb ", "ooip", "drive mechanism", "depletion"],
    "depletion": ["depletion", "solution gas drive", "gas drive"],
    "timestep": ["timestep", "time step", "chop", "convergence", "newton", "tuning"],
}


def _match_topic_tags(summary: str, topic_focus: list[str] | None) -> list[str]:
    """Match topic tags from summary and focus."""
    tags = []
    summary_lower = summary.lower()

    # Add tags from topic_focus
    if topic_focus:
        tags.extend(topic_focus)

    # Auto-detect from summary
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in summary_lower for kw in keywords):
            tags.append(topic)

    return list(set(tags))  # deduplicate


def _filter_questions_by_topic(questions: list[QuizQuestion], tags: list[str]) -> list[QuizQuestion]:
    """Filter questions matching any of the topic tags."""
    if not tags:
        return questions

    matched = []
    for q in questions:
        if any(tag in q.topic_tags for tag in tags):
            matched.append(q)
    return matched if matched else questions  # fallback to all if no match


# ---- LLM-based Quiz Generation ----

QUIZ_SYSTEM_PROMPT = """You are an expert reservoir engineering educator creating multiple-choice quiz questions.

Generate exactly {n_questions} questions at {level} level. Each question must have:
- A clear stem
- Exactly 4 options (A, B, C, D)
- One correct answer (index 0-3)
- An explanation with citation reference
- Topic tags

Output as VALID JSON array only, no extra text. Format:
[
  {
    "question": "...",
    "options": ["A", "B", "C", "D"],
    "correct_index": 0,
    "explanation": "...",
    "level": "{level}",
    "topic_tags": ["tag1", "tag2"]
  }
]"""

QUIZ_USER_PROMPT = """Scenario: {scenario_summary}

Topic focus: {topic_focus}

Retrieved context:
{context}

Generate {n_questions} MCQs."""


def _build_quiz_prompt(scenario: str, level: ExplanationLevel, n: int, topic_focus: list[str] | None) -> list[dict]:
    """Build prompt for LLM quiz generation."""
    # Retrieve relevant chunks for context
    citations = retrieve_chunks(scenario, k=5, level=level)
    context = "\n\n".join([f"[{c.source_id}] {c.title}: {c.snippet}" for c in citations])

    return [
        {"role": "system", "content": QUIZ_SYSTEM_PROMPT.format(n_questions=n, level=level)},
        {"role": "user", "content": QUIZ_USER_PROMPT.format(
            scenario_summary=scenario,
            topic_focus=", ".join(topic_focus) if topic_focus else "general",
            context=context,
            n_questions=n,
        )},
    ]


def _parse_llm_quiz(response: str, level: ExplanationLevel) -> list[QuizQuestion] | None:
    """Parse LLM response into QuizQuestion objects."""
    try:
        # Extract JSON array from response
        start = response.find("[")
        end = response.rfind("]") + 1
        if start == -1 or end == 0:
            return None
        json_str = response[start:end]
        data = json.loads(json_str)

        questions = []
        for item in data:
            if not all(k in item for k in ("question", "options", "correct_index", "explanation")):
                return None
            opts = tuple(item["options"])
            if len(opts) != 4:
                return None
            if not isinstance(item["correct_index"], int) or not 0 <= item["correct_index"] <= 3:
                return None

            questions.append(QuizQuestion(
                question=item["question"],
                options=opts,
                correct_index=item["correct_index"],
                explanation=item["explanation"],
                level=level,
                topic_tags=tuple(item.get("topic_tags", [])),
            ))
        return questions
    except Exception:
        return None


# ---- Public API ----

def generate_quiz(
    scenario_summary: str,
    level: ExplanationLevel = "intermediate",
    n_questions: int = 3,
    topic_focus: list[str] | None = None,
) -> Quiz:
    """
    Generate a multiple-choice quiz from a scenario description.

    Args:
        scenario_summary: Description of the simulation scenario or KPI summary
        level: Difficulty level
        n_questions: Number of questions (3-5)
        topic_focus: Optional list of topic tags to focus on

    Returns:
        Quiz object with scenario summary and questions
    """
    n_questions = max(1, min(10, n_questions))

    # Try LLM first
    llm = LLMClient()
    questions: list[QuizQuestion] = []

    if llm.available:
        try:
            messages = _build_quiz_prompt(scenario_summary, level, n_questions, topic_focus)
            response = llm.chat(messages)
            if response:
                parsed = _parse_llm_quiz(response, level)
                if parsed and len(parsed) >= n_questions:
                    questions = parsed[:n_questions]
        except Exception:
            pass  # Fall through to offline

    # Offline fallback
    if not questions:
        # Filter offline bank by topic and level
        tags = _match_topic_tags(scenario_summary, topic_focus)
        filtered = _filter_questions_by_topic(OFFLINE_QUESTIONS, tags)
        # Further filter by level
        filtered = [q for q in filtered if q.level == level]
        if not filtered:
            filtered = [q for q in OFFLINE_QUESTIONS if q.level == level]

        # Shuffle and pick
        random.shuffle(filtered)
        questions = filtered[:n_questions]

        # Pad with generic if needed
        while len(questions) < n_questions:
            remaining = [q for q in OFFLINE_QUESTIONS if q.level == level and q not in questions]
            if not remaining:
                # Fall back to any level
                remaining = [q for q in OFFLINE_QUESTIONS if q not in questions]
            if not remaining:
                break
            questions.append(random.choice(remaining))

    # Ensure exactly n_questions
    questions = questions[:n_questions]

    return Quiz(
        scenario_summary=scenario_summary,
        questions=tuple(questions),
    )