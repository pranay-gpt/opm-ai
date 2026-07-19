# opm_ai.explainer - Educational Explainer & RAG Engine

## Purpose

This module provides AI-powered educational explanations of reservoir simulation
concepts and results at three pedagogical levels (beginner, intermediate, advanced),
with citations from a curated knowledge base. It also generates quizzes and
session learning reports.

## Key Types (models.py)

- `ExplanationLevel`: Literal["beginner", "intermediate", "advanced"]
- `Citation`: Single source citation (source_id, title, url_or_path, snippet)
- `Explanation`: Structured explanation with text, citations, follow-up questions
- `QuizQuestion`: Multiple-choice question (4 options, correct index, explanation)
- `Quiz`: Set of 3-5 questions on a scenario
- `LearningReport`: End-of-session summary with topics, concepts, quiz scores, markdown

## Knowledge Base

Three source corpora (ingested by `ingest.py`):

1. **Eclipse HTML Reference Manuals** (`tests/eclipse/ecl_rm/`, `tests/eclipse/ecl_td/`)
   - ~2000 HTML files covering keyword syntax and technical descriptions
   - Chunked by HTML sections (<h2>/<h3>), ~512 tokens per chunk

2. **Deck Comment Headers** (`tests/fixtures/**/*.DATA`)
   - Leading `--` comment blocks from OPM test decks
   - Describe scenario, physics, and modeling choices

3. **Teaching Notes** (`opm_ai/explainer/notes/*.md`)
   - 7 original educational markdown files (150-300 words each)
   - Topics: waterflood breakthrough, material balance, relative permeability,
     PVT basics, well controls, depletion drive, timestepping, SPE1 scenario

## Retrieval (retrieve.py)

**Pure-Python BM25** (no chromadb, no sentence-transformers):
- Tokenization: lowercase, alphanumeric split
- BM25 parameters: k1=1.5, b=0.75 (standard defaults)
- Level-aware boosting:
  - beginner: teaching_note ×2.0, ecl_td ×0.5
  - intermediate: balanced
  - advanced: ecl_td ×2.0, teaching_note ×0.8

**Offline KB Build** (`build_knowledge_base()`):
- Run once at Docker image build time
- Persists to `opm_ai/explainer/kb/kb.json`
- Caps ecl_rm at 500 files to keep build < 60s
- Embedding model parameter accepted but ignored (for API compatibility)

**Lazy Loading**: Module-level cache loads KB on first `retrieve_chunks()` call.
Falls back to teaching notes only if KB not built and source dirs missing.

## Explainer (explainer.py)

`explain(topic_or_result, level, context)`:
1. If input is KPI dict → build summary string
2. `retrieve_chunks(summary, k=5, level)`
3. If LLM available: render level-specific prompt + gold examples + citations
4. Offline fallback: template from retrieved snippets + canned level framing
5. Returns `Explanation` with citations (top 3) and follow-up questions

## Quiz (quiz.py)

`generate_quiz(scenario, level, n, topic_focus)`:
1. Retrieve context chunks
2. LLM path: prompt for JSON array of MCQs, parse with substring extraction
3. Offline fallback: 10 hand-written MCQs tagged by topic/level, filter + pad
4. Returns `Quiz` with exactly `n` valid questions

## Report (report.py)

`generate_learning_report(session_id, conversation, kpis_history)`:
1. Extract topics from user messages (keyword matching)
2. Extract quiz scores from "quiz_result" role messages (convention: "topic:score")
3. Retrieve 1 citation per topic
4. LLM writes Session Summary paragraph (optional)
5. Returns `LearningReport` with full markdown

## Deviation Note: BM25 vs Vector DB

The spec originally mentioned `chromadb` + `sentence-transformers` + `llama-index`.
**Deviation**: This implementation uses pure-Python BM25 with no external ML deps.

**Rationale**:
- Keeps Docker image slim (~50MB vs ~500MB+ with transformers)
- CPU-only, no GPU required
- BM25 is strong for keyword-heavy domain queries (Eclipse keywords, SPE terms)
- Interface (`retrieve_chunks`) unchanged - vector backend can replace later

**Trade-offs**:
- No semantic similarity (exact keyword matching only)
- Won't match "water breakthrough" ↔ "waterfront arrival" without shared terms
- Mitigated by teaching notes covering conceptual synonyms

## Testing

Run unit tests (offline, no LLM):
```bash
.venv/bin/pytest tests/unit/test_explainer_retrieve.py tests/unit/test_explainer_offline.py -v
```

Full unit suite:
```bash
.venv/bin/pytest tests/unit -q
```

KB build timing:
```bash
python -c "
from opm_ai.explainer.ingest import build_knowledge_base
from pathlib import Path
import time
t0 = time.time()
build_knowledge_base([
    Path('/home/parallels/opm-ai/tests/eclipse/ecl_rm'),
    Path('/home/parallels/opm-ai/tests/eclipse/ecl_td'),
    Path('/home/parallels/opm-ai/tests/fixtures'),
], Path('/tmp/kb_test'))
print(f'KB build time: {time.time()-t0:.1f}s')
"
```

Retrieve over real corpus:
```bash
python -c "
from opm_ai.explainer.retrieve import retrieve_chunks
cites = retrieve_chunks('WCONPROD', k=3, level='intermediate')
for c in cites:
    print(f'{c.source_id}: {c.snippet[:80]}...')
"
```