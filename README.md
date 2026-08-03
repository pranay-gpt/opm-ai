# OPM-AI

<p align="center">
  <strong>An AI-assisted workbench for reservoir simulation, built on the open-source OPM Flow simulator.</strong>
</p>

<p align="center">
  Describe a reservoir in plain English and it builds the deck, lints it, runs the simulation, and explains the results.
</p>

<p align="center">
  Made for students, researchers, and faculty who want to learn and teach reservoir engineering without fighting the tooling.
</p>

<p align="center">
  <a href="#why-this-exists">Why</a> ·
  <a href="#features">Features</a> ·
  <a href="#screenshots">Screenshots</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#roadmap">Roadmap</a> ·
  <a href="#credits">Credits</a>
</p>

## Why this exists

Reservoir simulation has a tooling problem, not a physics problem. The physics is
open: [OPM Flow](https://opm-project.org/) is a production-grade, fully implicit
three-phase black-oil simulator, free to anyone, and it will happily solve a
field model on a laptop. What stops people is everything around it. The input
deck is an unforgiving fixed-format language where a missing slash 400 lines
down produces an error message about something else entirely. Reading the
results means another tool. Understanding them means someone senior with time to
spare.

So the simulator is free and the knowledge is not. Students learn the theory
from a textbook and meet a real deck for the first time in industry.

OPM-AI is an attempt to close that gap. Describe a reservoir in plain English
and it writes the deck, checks it before you burn an hour on a run that was
never going to converge, executes it on OPM Flow, draws the grid in 3D, and
explains what came back. Every layer is inspectable: the generated deck is a
normal `.DATA` file you can read, edit, and run by hand with `flow`. Nothing is
hidden behind a binary format or a licence server.

It runs fully offline by default. No API key, no account, no telemetry, and no
network call unless you opt in to the LLM features.

One caveat worth stating up front: the binary grid fixtures (`.EGRID`, `.UNRST`,
`.INIT`) are gitignored to keep the clone small, so the tests that read them are
skipped on a fresh checkout until you run a simulation of your own. Everything
else works immediately.

## Features

- **Build decks from plain English** — describe a model and get a valid OPM Flow deck, with an offline generator and optional LLM extraction
- **Lint decks offline** — a rule engine catches errors and inconsistencies before you run, no simulator needed
- **Run OPM Flow** — launch simulations and get structured results, with readable crash reports when a run fails
- **See the results** — field and per-well KPIs, interactive Plotly charts, and a live 3D grid viewer
- **Chat with tools** — one conversation that builds, lints, runs, plots, and explains
- **Learn as you go** — concept explanations and auto-generated quizzes for reservoir topics
- **Dark, light, and auto themes** — sharp panels, rounded controls, follows your system setting

## Screenshots

### Home — dark theme (default)

<p align="center">
  <img src="docs/screenshots/home-dark.png" alt="Home dark theme" width="800">
</p>

### Deck Builder

<p align="center">
  <img src="docs/screenshots/builder-deck.png" alt="Deck Builder" width="800">
</p>

### Linter

<p align="center">
  <img src="docs/screenshots/linter.png" alt="Linter" width="800">
</p>

### Simulator

<p align="center">
  <img src="docs/screenshots/simulator-page.png" alt="Simulator" width="800">
</p>

### Results — KPIs and tables

<p align="center">
  <img src="docs/screenshots/results.png" alt="Results" width="800">
</p>

### Results — Interactive Plotly charts

<p align="center">
  <img src="docs/screenshots/results-plot.png" alt="Results Plot" width="800">
</p>

### Results — 3D

<p align="center">
  <img src="docs/screenshots/results-3D.png" alt="Results 3D" width="800">
</p>

### Learn & Chat

| Learn | Chat |
|---|---|
| ![Learn](docs/screenshots/learn.png) | ![Chat](docs/screenshots/chat.png) |

### Light theme

<p align="center">
  <img src="docs/screenshots/home-light.png" alt="Home light theme" width="800">
</p>

## Quick start

```bash
git clone https://github.com/pranay-gpt/opm-ai.git
cd opm-ai
docker compose up -d --build
# open http://localhost:8000
```

That's it. The frontend is built inside the image, so you don't need Node locally.
The app runs fully offline by default; to enable the LLM chat and extraction features,
copy `.env.example` to `.env` and add an API key (e.g. `GROQ_API_KEY` with `LLM_PROVIDER=groq`).

### Running without Docker

Needs OPM Flow on `PATH`, a virtualenv with `pip install -e .`, and Node for the
frontend build.

```bash
./scripts/run.sh build    # build the frontend bundle, then serve
./scripts/run.sh          # serve  -> http://localhost:8000
./scripts/run.sh dev      # serve + Vite hot reload -> http://localhost:5173
```

Ctrl-C stops everything. `build` is only needed the first time and after
frontend changes; `dev` skips it and serves from Vite instead.

Browsing decks: the Simulator's **Browse** button lists `.DATA` files on the
server rather than uploading them, so a deck keeps its `include/` folder and its
INCLUDE keywords resolve. It lists `tests/fixtures` and the system temp dir by
default; point it at your own deck library with `OPM_DECKS_ROOT=/path/to/decks`
in `.env`.

### One server, every screen

The server runs on Ubuntu, where OPM Flow lives. Everything else is a browser
tab. Run it on the lab workstation or a spare box, and the same session is
reachable from a laptop, a tablet, or a phone on the same network - nothing to
install on the device you happen to be holding.

That is the part worth caring about for teaching. Reservoir simulation normally
means a licensed desktop package on a machine you have to physically sit at.
Here a student can start a run in the lab, then read the KPIs, ask the chat why
the GOR climbed, and work through a quiz on the bus home. The heavy solve stays
on the server; the phone only ever renders a web page.

Phone support today is honest but partial: the app **loads and is usable** on a
phone, and the 3D grid genuinely renders and responds to touch orbit and pinch
zoom. Chat, Learn, and the KPI cards read well at that width. The Simulator form
and the 3D control panel are still laid out for a desktop and are cramped on a
small screen. Proper mobile layouts are on the roadmap below.

## Architecture

```text
opm-ai/
├── frontend/                React 18 + Vite + TypeScript SPA
│   └── src/components/viewer3d/   Native WebGL grid viewer (three.js)
├── opm_ai/                  Python package
│   ├── api/                 FastAPI app, routes, WebSocket chat
│   ├── builder/             Deck generation from a description
│   ├── linter/              Offline rule engine over deck sections
│   ├── runner/              OPM Flow subprocess + crash parsing
│   ├── postprocess/         Summary vectors, KPIs, plots, 3D grid
│   ├── explainer/           Retrieval-backed explanations and quizzes
│   ├── preprocess/          PVT and relative permeability table builders
│   ├── llm/                 Provider client (optional, offline by default)
│   └── cli.py               Click CLI entry point
├── tests/                   334 tests (pytest)
├── docker/                  Dockerfile, compose
├── docs/                    Screenshots, design records, viewer contract
└── scripts/                 run.sh, smoke.sh
```

The frontend is React 18, TypeScript, Tailwind CSS, Zustand, Monaco, Plotly.js,
and three.js. The backend is FastAPI over OPM Flow, with an optional LLM
provider (Groq, OpenAI, or any OpenAI-compatible endpoint such as NVIDIA NIM).
Communication is REST plus a WebSocket for chat.

**The 3D viewer is live geometry, not a screenshot.** It reads EGRID/INIT/UNRST
server-side with `resfo`, culls to the visible skin, and ships little-endian
binary buffers straight into WebGL. Binary rather than JSON because the Norne
field packs to 6.2 MB of Float32, where the same numbers as decimal text
would run to tens of megabytes. It carries the ResInsight colour palettes, ternary saturation, cell
filters, faults, wells, and time-step playback.

There is no ResInsight process behind it. The packaged ResInsight build ships
without gRPC and its batch mode needs a live X display, so an in-process bridge
was never possible and the viewer was written from the file formats up.

## Development

| Command | Purpose |
|---------|---------|
| `docker compose up -d --build` | Full stack in containers |
| `./scripts/run.sh dev` | Backend plus Vite hot reload |
| `pip install -e .[dev]` | Local Python dev environment (installs pytest) |
| `pytest` | Run the test suite (334 tests) |
| `cd frontend && npm run build` | Production bundle |
| `cd frontend && npm test` | Frontend self-check (binary mesh parsers, colour maps) |
| `cd frontend && npm run lint` | Lint the frontend |

## Roadmap

- Mobile-first layouts for the Simulator form and the 3D control panel
- Remaining ResInsight 3D features: intersections and section planes, contour
  maps, streamlines, multi-view linking, LGRs
- Scenario-specific deck templates (WAG, gas-cap EQUIL, CO2 streams)
- Inline linter diagnostics in the deck editor

## Credits

**This project would not exist without the [Open Porous Media initiative](https://github.com/OPM).**

[OPM Flow](https://opm-project.org/) is the simulator. Every result this
workbench shows was computed by their solver, in their file formats, following
the deck language their team implemented and documented. The 3D viewer here
reads EGRID, INIT and UNRST files written by Flow, and it was built by studying
[ResInsight](https://resinsight.org/), OPM's own post-processor, for the colour
palettes, the face-culling rules, and the conventions a reservoir engineer
expects. The `resfo` library that parses those files is theirs too.

The OPM team spent years building and giving away a production-quality reservoir
simulator, with the test decks, the reference cases, and the documentation that
make it genuinely usable. That is an enormous amount of careful engineering
released for nothing. OPM-AI is a thin, opinionated layer on top of their work,
and the hard part was already done before this repository existed.

If you find this useful, the credit belongs upstream. Go
[star OPM](https://github.com/OPM) and read their documentation.

This project is independent and is **not** affiliated with, endorsed by, or
supported by the OPM initiative.

### Also built on

[FastAPI](https://fastapi.tiangolo.com/), [React](https://react.dev/),
[three.js](https://threejs.org/), [Plotly](https://plotly.com/),
[Monaco](https://microsoft.github.io/monaco-editor/), and
[Tailwind CSS](https://tailwindcss.com/) - all open source, all free to use.

## License

Released under the [MIT License](LICENSE). Use it, fork it, teach with it.

**Author:** Pranay Gupta — [GitHub](https://github.com/pranay-gpt) · [LinkedIn](https://www.linkedin.com/in/pranay-ism/)
