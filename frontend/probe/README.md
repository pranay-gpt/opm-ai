# 3D viewer render harness

Mounts the real `Grid3DViewer` on its own page so the WebGL output can be driven
headlessly. Not part of the app build; nothing in `src/` imports it.

It exists because `tsc -b`, eslint and the backend suite all passed while the
viewer rendered nothing at all: the engine effect read `containerRef.current`
with `[]` deps, but the component early-returns a "Loading grid…" tree until
`/grid/info` lands, so the container did not exist on first mount and the effect
never re-ran. Every `engine?.setX()` call then no-opped through its optional
chain. Only an actual render catches that class of bug.

## Running it

Serve the API with a couple of fixture jobs registered as completed, then the
harness page against it:

```python
# serve.py
import uvicorn
from opm_ai.api.job_store import create_job, set_job_completed, set_job_running
from opm_ai.api.schemas import SimulationResultDTO
from opm_ai.api.server import create_app
from tests.conftest import FIXTURES_DIR

app = create_app()
for jid, d in {
    "probe-spe1": FIXTURES_DIR / "spe1",
    "probe-norne": FIXTURES_DIR / "norne" / "opm-simulation-reference" / "flow_legacy",
}.items():
    create_job(jid)
    set_job_running(jid)
    set_job_completed(jid, SimulationResultDTO(
        success=True, output_dir=str(d), returncode=0, duration_s=1.0))
uvicorn.run(app, host="127.0.0.1", port=8011)
```

```sh
PYTHONPATH=. python serve.py &
cd frontend && npx vite --config vite.probe.config.ts   # http://127.0.0.1:5199
```

`window.__setJob('probe-norne' | 'probe-spe1' | null)` switches case or unmounts,
which is how engine reuse and context release get tested. `window.__probe`
carries `{ errors, contexts }`; `contexts` counts `getContext('webgl2')` calls so
a leak across mounts shows up as a rising number. Browsers cap live contexts at
around 16 and then blank the canvas, so that counter matters.

## Headless WebGL

No GPU needed. Playwright's bundled chromium renders through SwiftShader:

```python
browser = p.chromium.launch(args=[
    "--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--no-sandbox",
])
```

Judge the result from `page.screenshot()`, not from `gl.readPixels` on the
default framebuffer: after the frame is presented that buffer reads back cleared,
so readPixels reports a single colour on a canvas that is visibly drawn.
