# Contributing to opm-ai

## Development Setup (Ubuntu 22.04 / 24.04)

Ubuntu 24.04 uses **PEP 668** — system-wide `pip install` is blocked by design.
Always use a virtual environment. Follow these steps exactly:

### 1. Install OPM Flow (system package — requires sudo)

```bash
sudo add-apt-repository -y ppa:opm/ppa
sudo apt-get update
sudo apt-get install -y \
  mpi-default-bin \
  libopm-simulators-bin \
  python3-opm-common \
  python3-opm-simulators \
  resinsight \
  python3-venv \
  python3-full
```

Verify:
```bash
flow --version
```

### 2. Clone the repo with submodules

```bash
git clone --recurse-submodules https://github.com/pranay-gpt/opm-ai.git
cd opm-ai
```

If you already cloned without `--recurse-submodules`:
```bash
git submodule update --init --recursive
```

### 3. Create and activate the virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

You should see `(.venv)` in your prompt. **Always activate the venv before any work.**

### 4. Install the project + dev dependencies

```bash
pip install -e ".[dev]"
```

This installs all dependencies from `pyproject.toml` (including `loguru`,
`python-dotenv`, `pytest`, etc.) into the venv.

### 5. Set up your environment variables

```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY (free at https://console.groq.com)
```

### 6. Run tests

```bash
# Always use python -m pytest (not bare pytest)
# This ensures the venv Python is used, not /usr/bin/pytest
python -m pytest tests/ -v
```

Expected output on a fresh Ubuntu 24.04 install:
- `test_smoke.py` — 4 passed
- `test_runner.py` — 3 passed (SPE1 integration test requires Flow + submodule)

---

## Why `python -m pytest` and not `pytest`?

On Ubuntu, `/usr/bin/pytest` uses system Python. Even after activating `.venv`,
typing `pytest` may resolve to the system binary, which cannot see venv packages.
`python -m pytest` always uses the active Python interpreter — guaranteed correct.

## Why no `--threads` flag in OPM Flow?

The `--threads` runtime argument is not supported on all OPM Flow builds
(notably the ARM64 Ubuntu 24.04 PPA build). Parallelism via MPI (`mpirun -np 4 flow ...`)
is a separate concern and not part of the runner's default path.

## Module Structure

```
opm_ai/
├── runner/      Part 1 — OPM Flow executor
├── linter/      Part 2 — Deck linter (in progress)
├── builder/     Part 3 — NL → deck generator
├── preprocess/  Part 4 — PVT & rel-perm builder
├── postprocess/ Part 5 — ResInsight bridge
├── chat/        Part 6 — Streamlit chat UI
└── explainer/   Part 7 — RAG educational explainer
```

## Coding Standards

- Python 3.10+ type hints on all functions
- `loguru` for all logging (no `print()`)
- Every module function must have a docstring
- No function should raise to the caller — return structured error objects
- Tests live in `tests/` and follow the `test_<module>.py` naming convention
