# Part 7: Educational Explainer & RAG Engine  (module: `opm_ai.explainer`)

> Given any simulation result or concept, explain it at three pedagogical levels with citations; generate quizzes, teaching moments, and session learning reports.

---

## 1. Role in the AIM

The AIM explicitly calls for "an AI layer ... that will help academic students, researchers and faculty to **understand and teach reservoir simulation** in the most efficient and fun way using simple chats." The explainer is the teaching layer:

- **For students**: "Why did water cut spike at year 3?" -> Dake-cited explanation at their chosen level.
- **For faculty**: "Give me three quiz questions on this waterflood" + "teaching moment" slide notes.
- **For researchers**: "Explain the IMPES vs. fully-implicit trade-off for my SPE9 run" with solver-level detail and citations.
- **For all**: a session "learning report" summarising every concept covered, with citations, ready for a lab notebook.

The explainer **does not run simulations**. It consumes:
- KPI dictionaries from Part 5 (`opm_ai.postprocess.kpi.extract_kpis` -> `dict`).
- Deck text and linter annotations from Part 2/3.
- User questions in plain English.

It produces **explanations with citations**, **quiz questions**, and **session summaries**.

---

## 2. Position in build order

| Aspect | Detail |
|--------|--------|
| **Phase** | Phase 3 (v1.2) - deferred until after Phase 2 (API + Frontend + Postprocess) ships |
| **Depends on** | Part 5 Postprocess (KPI dict + Plotly figures), Part 6 API (`/api/chat` route to expose explainer), Part 8 Deployment (pre-built vector DB in Docker image) |
| **Depended on by** | Nothing in v1.1; becomes the primary value driver for academic adoption in v1.2 |
| **New deps added here** | `chromadb`, `llama-index` (or `langchain`), `sentence-transformers` (embedding model) - **only at this phase** per `00-overview-and-architecture.md` D3 |

Cross-links: see `00-overview-and-architecture.md` section 4 D3, `05-postprocess.md` section 3 (KPI dict shape), `06-chat-and-api.md` section 4 (chat route wiring), `08-deployment.md` section 5 (pre-built vector DB in image).

---

## 3. Hard API contract (proposed - no test exists yet)

No test file asserts this module yet. The following signatures are the **proposed contract** that the Phase 3 integration test will eventually assert.

```python
# opm_ai/explainer/__init__.py
from dataclasses import dataclass
from typing import Literal, Optional
from pathlib import Path

ExplanationLevel = Literal["beginner", "intermediate", "advanced"]

@dataclass(frozen=True)
class Citation:
    """A single retrievable source citation."""
    source_id: str          # e.g., "dake_ch9", "eclipse_kw_COMPDAT", "spe1_deck_comment_42"
    title: str              # Human-readable title
    url_or_path: str        # File path or URL
    snippet: str            # Relevant excerpt (<= 200 chars)

@dataclass(frozen=True)
class Explanation:
    """Structured explanation returned by explain()."""
    topic: str              # Echo of the input topic/result summary
    level: ExplanationLevel
    text: str               # Markdown-formatted explanation
    citations: tuple[Citation, ...]  # 1-5 citations supporting claims
    follow_up_questions: tuple[str, ...]  # 2-3 suggested follow-ups

@dataclass(frozen=True)
class QuizQuestion:
    """Single multiple-choice question."""
    question: str
    options: tuple[str, str, str, str]  # exactly 4 options A-D
    correct_index: int                  # 0-3
    explanation: str                    # Why the answer is correct (with citation)
    level: ExplanationLevel
    topic_tags: tuple[str, ...]         # e.g., ("waterflood", "watercut", "relative_permeability")

@dataclass(frozen=True)
class Quiz:
    """A set of 3-5 questions on a scenario."""
    scenario_summary: str
    questions: tuple[QuizQuestion, ...]

@dataclass(frozen=True)
class LearningReport:
    """End-of-session summary for student or professor."""
    session_id: str
    topics_covered: tuple[str, ...]
    explanations_generated: int
    questions_asked: int
    quiz_scores: dict[str, float] | None  # if quizzes were taken
    key_concepts: tuple[str, ...]
    citations_used: tuple[Citation, ...]
    markdown: str  # Full report rendered as markdown

# --- Public API ---

def explain(
    topic_or_result: str | dict,
    level: ExplanationLevel = "intermediate",
    context: dict | None = None
) -> Explanation:
    """
    Main entry point.
    
    - topic_or_result: either a free-text question ("why did watercut spike?"),
      or a KPI dict from extract_kpis() (will produce "what happened" narration).
    - level: beginner (plain English, no equations), intermediate (concepts + key equations),
      advanced (numerical methods, solver internals, timestep control).
    - context: optional dict with deck_path, simulation_result, kpis, plots for richer answers.
    
    Returns Explanation with citations from the RAG knowledge base.
    """

def generate_quiz(
    scenario_summary: str,
    level: ExplanationLevel = "intermediate",
    n_questions: int = 3,
    topic_focus: list[str] | None = None
) -> Quiz:
    """
    Generate a multiple-choice quiz from a scenario description or KPI dict.
    Uses the same RAG retrieval + few-shot prompt as explain().
    """

def generate_learning_report(
    session_id: str,
    conversation_history: list[dict],
    kpis_history: list[dict] | None = None
) -> LearningReport:
    """
    Summarise a chat session into a structured learning report.
    conversation_history: list of {"role": "user|assistant", "content": "..."}.
    """

# --- RAG internals (not public API but documented for implementers) ---

def build_knowledge_base(
    source_dirs: list[Path],
    persist_dir: Path,
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
) -> None:
    """
    One-time offline build: chunk, embed, and persist to chromadb.
    Run at Docker image build time (see 08-deployment.md).
    """

def retrieve_chunks(query: str, k: int = 5, level: ExplanationLevel = "intermediate") -> list[Citation]:
    """
    Semantic search over the knowledge base. Level-aware: beginner prefers textbook
    excerpts; advanced prefers OPM technical docs and SPE papers.
    """
```

---

## 4. Key design decisions

| # | Decision | Rationale | Alternatives considered | Consequences |
|---|----------|-----------|------------------------|--------------|
| **D1** | **RAG stack: `chromadb` + `llama-index` (not LangChain)** | LlamaIndex is purpose-built for RAG (indexing, retrieval, query engines) with a cleaner abstraction for "retrieve -> synthesize" pipelines. Chroma is a lightweight local vector store with no external service. LangChain adds unnecessary abstraction layers for this use case. | LangChain + Chroma; LangChain + FAISS; LlamaIndex + FAISS | Keeps dependency count low. LlamaIndex's `VectorStoreIndex` + `RetrieverQueryEngine` maps 1:1 to our `retrieve_chunks` -> `explain` flow. |
| **D2** | **Knowledge base seeds (shipped pre-built in Docker)** | 1. Eclipse keyword reference HTML in `tests/eclipse/ecl_rm/` + `tests/eclipse/ecl_td/` (keyword syntax, section rules, examples).<br>2. Eclipse file format reference in `tests/eclipse_fileformat/`.<br>3. `opm-flow-editor-support` keyword reference Markdown export (from VS Code extension scripts).<br>4. `opm-tests` deck comments (`tests/fixtures/*/`) - each deck has header comments explaining the scenario.<br>5. Public-domain textbook excerpts: *Craft & Hawkins* Ch. 1-3 (basic concepts), *Dake* Ch. 9-10 (waterflood, material balance) - only sections confirmed public domain or fair-use for education. | Add SPE papers (copyright), full textbooks (license), OPM manual (OK but verbose) | Pre-building the vector DB in the Docker image (see `08-deployment.md`) means first `docker compose up` is fast - no embedding wait for users. Corpus size ~200k chunks is manageable for Chroma on CPU. |
| **D3** | **Chunking strategy** | - HTML files: split by `<h2>`/`<h3>` sections (keyword pages are naturally sectioned).<br>- Markdown: split by `##` headings.<br>- Deck comments: split by blank-line paragraphs.<br>- Textbook PDFs (if added): split by chapter/section using `pymupdf` TOC.<br>Chunk size: 512 tokens, overlap 50 tokens. Embedding: `all-MiniLM-L6-v2` (384 dim, fast CPU, good general retrieval). | Fixed-size sliding window; semantic chunking via LLM | Section-aware chunking preserves keyword/equation context. `all-MiniLM-L6-v2` is small (22 MB), runs on CPU, and is well-tested in LlamaIndex. |
| **D4** | **Three explanation levels mapped to prompt + retrieval bias** | | Beginner: retrieve textbook chunks, prompt "explain in plain English, no equations, use analogies".<br>Intermediate: retrieve keyword ref + textbook, prompt "include governing equations (Darcy, material balance), define symbols".<br>Advanced: retrieve OPM technical description + SPE papers, prompt "include discretisation (TPFA), linearisation (Newton), solver (CPR-AMG), timestep selection". | Single level with adaptive depth | Explicit level selector gives user control and makes evaluation deterministic (gold-set calibration per level). |
| **D5** | **Five gold-standard few-shot examples (human-written calibration set)** | One per canonical scenario type: (1) Single-well depletion, (2) 5-spot waterflood, (3) Line-drive injector-producer, (4) Gas-cap expansion / WAG, (5) Pressure buildup test. Each example = (input: KPI dict + deck summary, level, output: Explanation with citations). Stored in `opm_ai/explainer/gold_examples/`. Used as few-shot prefix in every `explain()` call. | Let LLM generate freely; evaluate with LLM-judge | Fixed calibration set ensures consistent quality across model versions. Human writes these **once** (highest-leverage contribution per GUIDE 3 Part 7). |
| **D6** | **KPI dict -> "what happened" narration** | Input: `{"days": 1825, "FOPT": 1.2e6, "WCT_breakthrough_day": 1100, "peak_WOPR_day": 200, ...}` (from `extract_kpis`). Prompt: "Narrate the production history in 3 paragraphs: (1) early depletion, (2) water breakthrough, (3) late decline. Cite Dake Ch. 9 for breakthrough theory, cite deck's WCONINJE for injection rate." Output: Explanation with 2-3 citations. | Feed raw summary vectors to LLM | Structured KPI dict is smaller, deterministic, and maps directly to engineering concepts. |
| **D7** | **Quiz generation uses the same retrieval + few-shot pipeline** | `generate_quiz()` retrieves top-k chunks for the scenario, then prompts: "Write 3 multiple-choice questions at {level} testing understanding of {topic_focus}. Each question: stem, 4 options (1 correct), explanation with citation." Same gold examples calibrate quality. | Separate quiz model | Consistency; explanations in quiz answers double as teaching moments. |
| **D8** | **Session learning report aggregates across conversation** | `generate_learning_report()` clusters conversation topics (embedding-based), deduplicates citations, renders markdown with sections: "Concepts Covered", "Key Equations", "Quiz Performance", "Suggested Reading". | Simple transcript dump | Produces a study artifact - the "lab notebook" the AIM promises. |

---

## 5. Toolchain grounding

| Item | Path / version / spec | Source | Status |
|------|----------------------|--------|--------|
| **Vector store** | `chromadb>=0.5` (local, persistent) | Phase 3 dep only | UNVERIFIED - add to `pyproject.toml` at Phase 3 start |
| **RAG framework** | `llama-index>=0.10` (core, vector-stores-chroma) | Phase 3 dep only | UNVERIFIED - add at Phase 3 |
| **Embedding model** | `sentence-transformers/all-MiniLM-L6-v2` (384 dim, CPU) | HuggingFace, bundled in LlamaIndex | UNVERIFIED - verify download size (~90 MB) acceptable in Docker |
| **Eclipse keyword HTML** | `tests/eclipse/ecl_rm/*.html`, `tests/eclipse/ecl_td/*.html` | OPM reference clone | VERIFIED - 1,000+ files, section-structured |
| **Eclipse file format HTML** | `tests/eclipse_fileformat/fileformats/*.html` | OPM reference clone | VERIFIED |
| **opm-flow-editor-support Markdown** | External repo; keyword reference export | GUIDE 3 Part 2 seed | UNVERIFIED - clone or vendor at Phase 3 start |
| **Deck comments (opm-tests)** | `tests/fixtures/*/` deck headers | BUILD_GUIDE.md section 6 | VERIFIED - 110 decks with scenario descriptions |
| **Craft & Hawkins excerpts** | Public domain chapters (Ch. 1-3) | GUIDE 3 Part 7 | UNVERIFIED - confirm public domain status; else replace with MIT-licensed notes |
| **Dake excerpts** | Ch. 9-10 (waterflood, material balance) | GUIDE 3 Part 7 | UNVERIFIED - verify copyright; may need to write original summaries instead |
| **OPM technical description** | `tests/eclipse/ecl_td/EclipseTechnicalDescription_*.html` | OPM docs | VERIFIED - has discretisation, linearisation, solver sections |
| **LLM providers** | Groq (Llama-3.3-70B), OpenAI-compatible (NVIDIA NIM) | 00-overview-and-architecture.md D4 | VERIFIED - reuse `opm_ai.llm.client.LLMClient` |

**What to check at implementation time**:
1. `llama-index` + `chromadb` import and version compatibility (pin both).
2. Chroma persistence directory permissions in Docker (UID/GID mapping).
3. Embedding model download at build time (not runtime) - use `sentence-transformers` CLI or LlamaIndex's `download_loader`.
4. HTML parsing: `beautifulsoup4` or `llama-index-readers-web` for the keyword refs.
5. Token counting for prompt assembly (LlamaIndex handles, but verify context window for Llama-3.3-70B ~8k tokens).

---

## 6. Implementation approach (concrete, ordered steps)

### Step 1 - Module skeleton and data models
**Files**: `opm_ai/explainer/__init__.py`, `opm_ai/explainer/models.py`, `opm_ai/explainer/context.md`
- Define `ExplanationLevel`, `Citation`, `Explanation`, `QuizQuestion`, `Quiz`, `LearningReport` (as in section 3).
- `context.md`: one-paragraph purpose + key types.

### Step 2 - Knowledge base builder (offline, run once at Docker build)
**Files**: `opm_ai/explainer/ingest.py`, `opm_ai/explainer/build_kb.py`
- `ingest.py`: readers for each source type:
  - `read_eclipse_html(dir)` -> list of (section_title, text, source_id, path)
  - `read_deck_comments(fixtures_dir)` -> list of (deck_name, comment_text, source_id, path)
  - `read_textbook_md(file)` -> list of (chapter, section, text, source_id)
- `build_kb.py`: 
  - Chunk with `SentenceSplitter(chunk_size=512, chunk_overlap=50)`.
  - Embed with `HuggingFaceEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")`.
  - Persist to `chromadb.PersistentClient(path=persist_dir)`.
  - CLI entry: `python -m opm_ai.explainer.build_kb --sources-dir ... --persist-dir ...`
- **Docker integration** (see `08-deployment.md`): run this at image build time; copy `persist_dir` into image.

### Step 3 - Retrieval engine
**File**: `opm_ai/explainer/retrieve.py`
- `retrieve_chunks(query, k=5, level="intermediate") -> list[Citation]`:
  - Load index from persisted Chroma.
  - Level-aware filter: beginner -> boost textbook chunks; advanced -> boost OPM technical + SPE chunks (metadata tag `source_type`).
  - Return top-k as `Citation` objects with snippet extraction.

### Step 4 - Prompt templates and gold examples
**Files**: `opm_ai/explainer/prompts/`, `opm_ai/explainer/gold_examples/`
- `prompts/explain.j2`: Jinja2 template with slots for `level`, `topic`, `retrieved_chunks`, `gold_examples`.
- `prompts/quiz.j2`: similar, outputs structured JSON for `Quiz`.
- `prompts/report.j2`: aggregates conversation history.
- `gold_examples/`: 5 JSON files, one per scenario:
  ```json
  {
    "scenario": "depletion",
    "level": "intermediate",
    "input_kpis": {"days": 1825, "FOPT": 1.2e6, "cum_WOPR": ...},
    "expected_explanation": "The reservoir undergoes natural depletion...",
    "expected_citations": ["dake_ch9_sec3", "eclipse_kw_PVTO"]
  }
  ```
  Human writes these once; they become the few-shot prefix for every LLM call.

### Step 5 - Core `explain()` implementation
**File**: `opm_ai/explainer/explainer.py`
- `explain(topic_or_result, level, context)`:
  1. If input is `dict` (KPI dict), build a summary string: "Simulation ran 1825 days. Cumulative oil 1.2 MMSTB. Water breakthrough day 1100."
  2. Retrieve chunks: `retrieve_chunks(summary, k=5, level=level)`.
  3. Load gold examples for the detected scenario (heuristic: keywords in summary -> example file).
  4. Render prompt with Jinja2: level-specific instructions + retrieved chunks + gold examples.
  5. Call `LLMClient().chat(messages)` (reuse `opm_ai.llm.client`).
  6. Parse response into `Explanation` (citations from retrieved chunks).
  7. Return `Explanation`.

### Step 6 - `generate_quiz()` and `generate_learning_report()`
**File**: `opm_ai/explainer/quiz.py`, `opm_ai/explainer/report.py`
- `generate_quiz()`: similar flow to `explain()`, but prompt asks for 3-5 MCQs in JSON schema.
- `generate_learning_report()`: embed all user messages, cluster with `sklearn.cluster.KMeans` (or simple keyword extraction), deduplicate citations, render markdown via `prompts/report.j2`.

### Step 7 - API route wiring (cross-ref `06-chat-and-api.md`)
**File**: `opm_ai/api/routes/explainer.py` (new)
- `POST /api/explain` -> `Explanation`
- `POST /api/quiz` -> `Quiz`
- `POST /api/learning-report` -> `LearningReport`
- All streaming-capable for long explanations.

### Step 8 - Verification and snapshot tests
**Files**: `tests/unit/test_explainer_retrieve.py`, `tests/unit/test_explainer_snapshots.py`
- Retrieval smoke test: query "watercut breakthrough" returns chunks from Dake Ch. 9 and Eclipse WCONINJE.
- Snapshot test: `explain(kpi_dict, level="intermediate")` output matches gold example (allowing LLM variance via `pytest-snapshot` with fuzzy matching on citations).

---

## 7. Risks and open questions

| Risk / question | Impact | Mitigation / who decides |
|-----------------|--------|--------------------------|
| **Copyright on textbook excerpts** | Cannot ship Dake/Craft & Hawkins in public repo | Legal review before Phase 3. Fallback: write original educational summaries citing the textbook (fair use for teaching) or use only OPM docs + SPE papers with open access. |
| **Embedding model quality for petroleum domain** | `all-MiniLM-L6-v2` is general-purpose; may miss domain terms (e.g., "CPR-AMG", "ENDSCALE") | Evaluate against a small benchmark (20 queries from OPM docs). If recall < 0.7, consider `sentence-transformers/all-mpnet-base-v2` (larger) or domain-adaptive fine-tuning (Phase 4). |
| **Gold example maintenance** | If LLM provider changes (Groq deprecates Llama-3.3), explanations drift | Version gold examples with model ID. Re-calibrate (re-write gold) when model changes. |
| **Chroma persistence in Docker** | Volume mount vs. baked-in image | Bake pre-built DB in image for fast cold start; mount volume for user-added docs (Phase 3+). |
| **Level "advanced" needs solver internals** | OPM technical description has discretisation/linearisation details but not all decks expose solver logs | Advanced level may need `flow --print-linear-solver-info` output; defer until Runner captures that (future extension). |
| **Quiz answer parsing fragility** | LLM may not emit valid JSON for MCQ | Use `llama-index` `PydanticOutputParser` or `Guardrails` to enforce schema; fallback to regex parse. |
| **Session state for learning report** | Chat history must be passed from frontend | Frontend (Part 6) sends conversation array with each request; backend is stateless. |
| **Latency** | Retrieve (50 ms) + LLM (500-2000 ms) per explanation | Stream response token-by-token; cache retrieval for repeated queries in session. |

---

## 8. Verification and done-criteria

**No existing test gates this part.** The following will be the acceptance criteria when the module lands in Phase 3:

| Criterion | How verified |
|-----------|--------------|
| `opm_ai.explainer` imports cleanly with Phase 3 deps only | `python -c "import opm_ai.explainer; print('ok')"` in Docker image |
| Knowledge base builds without error | `python -m opm_ai.explainer.build_kb --sources-dir tests/ --persist-dir /tmp/kb` exits 0, produces `chroma.sqlite3` |
| Retrieval smoke test passes | `pytest tests/unit/test_explainer_retrieve.py -v` (query "watercut breakthrough" -> citations include Dake Ch. 9) |
| `explain()` returns `Explanation` with >=1 citation at all 3 levels | `pytest tests/unit/test_explainer_snapshots.py -v` (snapshot against gold examples) |
| `generate_quiz()` returns `Quiz` with 3 valid MCQs | `pytest tests/unit/test_explainer_quiz.py -v` |
| `generate_learning_report()` produces markdown with sections | `pytest tests/unit/test_explainer_report.py -v` |
| API routes return 200 with correct schemas | `pytest tests/integration/test_api_explainer.py -v` (FastAPI TestClient) |
| Pre-built vector DB loads in < 2 s at container start | Manual: `time docker run --rm opm-ai python -c "from opm_ai.explainer import retrieve_chunks; retrieve_chunks('test')"` |

**Manual smoke test** (after Step 7):
```bash
cd /home/parallels/opm-ai
python -c "
from opm_ai.explainer import explain, generate_quiz
from opm_ai.postprocess.kpi import extract_kpis
import pandas as pd

# Mock KPI dict like extract_kpis would return
kpis = {'days': 1825, 'FOPT': 1.2e6, 'WCT_breakthrough_day': 1100,
        'peak_WOPR_day': 200, 'final_WOPR': 50}
exp = explain(kpis, level='intermediate')
print(exp.text[:500])
print('--- Citations ---')
for c in exp.citations:
    print(f'  {c.source_id}: {c.title}')
print()
quiz = generate_quiz('5-year waterflood with breakthrough at year 3', level='intermediate')
for q in quiz.questions:
    print(f'Q: {q.question}')
    for i, opt in enumerate(q.options):
        print(f'  {chr(65+i)}. {opt}')
    print(f'  Answer: {chr(65+q.correct_index)}')
"
```
Expected: prints a coherent 3-paragraph narration with 2-3 citations, then 3 well-formed MCQs.

---

## 9. Future extensions (Phase 4+)

1. **Multi-modal explanations**: embed ResInsight snapshot PNGs (from Part 5) into explanations via vision-LLM (GPT-4o, Llama-3.2-Vision) - "here is the saturation front at breakthrough".
2. **Interactive tutoring mode**: Socratic dialogue where the explainer asks guiding questions instead of giving the answer, tracks student misconceptions.
3. **Homework variation generator**: from one SPE1 deck, generate 5 variants (change perm, relperm, schedule) with worked solutions - for problem sets.
4. **Multi-lingual support**: translate explanations to Spanish, Portuguese, Arabic using the same RAG + translation prompt.
5. **Citation linking to live docs**: in the React UI, make citations clickable to open the source HTML/Markdown in a side pane.
6. **Professor dashboard**: aggregate learning reports across a class, identify common misconceptions, auto-generate exam questions.

---

## Appendix A. Sibling document index (for cross-referencing)

| Doc | Part | Module(s) | One-line summary |
|-----|------|-----------|------------------|
| 00-overview-and-architecture.md | 0 | `opm_ai`, `settings` | AIM, architecture, stack decisions, Stage 0 foundation |
| 01-runner.md | 1 | `opm_ai.runner` | Wrap `/usr/bin/flow` as subprocess; structured `SimulationResult`, never raises |
| 02-linter.md | 2 | `opm_ai.linter` | Offline `Deck` parser + rule engine; `lint_deck` returns `LintResult` |
| 03-builder.md | 3 | `opm_ai.builder`, `llm`, `cli` | NL -> ModelSpec -> Jinja2 deck; auto-lint; LLM client; click CLI |
| 04-preprocess.md | 4 | `opm_ai.preprocess` | PVT/relperm correlations to PROPS blocks; AI advisor; validators |
| 05-postprocess.md | 5 | `opm_ai.postprocess` | `resfo` summary -> KPIs -> Plotly; optional `rips` ResInsight 3D |
| 06-chat-and-api.md | 6 | `opm_ai.api`, `frontend/` | FastAPI backend exposing modules as `/api/*`; React+Vite SPA |
| **07-explainer.md** | **7** | **`opm_ai.explainer`** | **Deferred RAG explainer (chromadb/llama-index); Phase 3** |
| 08-deployment.md | 8 | `docker/`, `README.md`, CI | `docker compose up`; Dockerfile with Flow/ResInsight; GitHub Actions |

---

*End of 07-explainer.md*