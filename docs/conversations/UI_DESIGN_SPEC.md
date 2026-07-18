# UI Design Specification

Reference: `docs/Reference_UI.png` - 4-panel visual guide for the OPM-AI frontend.

This document extracts the concrete design decisions from the reference UI to guide React component implementation. Cross-reference with `06-chat-and-api.md` (functional spec) and the "design_sense" prompt (Dark Void theme).

---

## Panel 1: Home/Dashboard (Top-Left)

**Purpose:** Landing view - workflow overview + capability highlights

**Layout:**
- Dark navy background (#0A1628 or similar)
- Left sidebar: vertical icon nav (Home, Deck Builder, Data Linter, Reservoir Engineering, Simulator, ResInsight Results, AI Explainer)
- Main area: hero section + cards

**Hero Section:**
- Large 3D isometric illustration (geomodel with wells/layers)
- Title: "End-to-end/geoworkflow"
- Subtitle: descriptive tagline
- Visual style: gradient mesh, glowing connection points, data flow lines

**Cards (2x3 grid below hero):**
- "Overview cards" - workflow status metrics
- "Overview" - capability description with "Operational" badge (cyan)
- "Workflow status" table (Braion Status, Workflow Status, Capability progress bar)
- "Workflow capability" - bullet list (Static Model Intake, Geomodel Validation, Deck Generation, Simulation Setup, Result Interpretation)

**Capability Highlights (bottom):**
- 5 feature cards in a row: Static Model Intake, Geomodel Validation, Deck Generation, Simulation Setup, Result Interpretation
- Each card: title + 2-line description + "Learn More >" link (cyan)
- Cards have subtle border, dark background

**Color Palette (observed):**
- Background: very dark blue (#0A1628)
- Cards: slightly lighter dark blue (#0F2642)
- Primary accent: cyan (#00D9FF) for links, badges, progress bars
- Text: white headings, gray (#A0AEC0) body
- Illustrations: multi-color gradient (blue/cyan/yellow/orange nodes)

---

## Panel 2: Deck Editor (Top-Right)

**Purpose:** Syntax-aware OPM deck editor with real-time validation

**Layout:**
- Top nav: same 7 functions (Home, Deck Builder highlighted, Data Linter, etc.)
- Left sidebar: section tree (RUNSPEC, GRID, PROPS, SOLUTION, SCHEDULE, etc.)
- Center: Monaco-style code editor with line numbers
- Right sidebar: workflow panels (Template selection, Dataset upload, Diagnostics, Validation summary)

**Editor Features:**
- Line numbers (left gutter)
- Syntax highlighting:
  - Keywords: bright cyan (`SIMULATION`, `MORNING`, `RESOURCES`)
  - Comments: green (`-- all sections 0`)
  - Numbers: orange (`0.053355`)
  - Strings: yellow highlight for attention items (`_timestepper`, `_burning`)
- Current line highlight (line 11 has yellow warning icon in gutter)
- Section folding indicators

**Section Tree (left):**
- Expandable/collapsible sections (RUNSPEC, GRID, PROPS, SOLUTION, SCHEDULE, etc.)
- Active section highlighted
- Icon prefix (file/folder icons)

**Right Sidebar Panels:**
- "Template selection" dropdown at top
- "Dataset upload" with "Upload" button (download icon)
- "Diagnostics" collapsible section (70% progress bars for Section progress, Prepopulate, Validate progress)
- "Validation summary" at bottom:
  - Green checkmarks: "Validation", "Syntax", "Validation semmentry" (typo in ref image)
  - Yellow warning: "Validate summary" (attention needed)

**Top-Right Actions:**
- "Flexible status" dropdown
- User avatar/settings icon

---

## Panel 3: Deck Builder Workflow (Bottom-Left)

**Purpose:** Guided workflow for building decks via forms/templates

**Layout:**
- Top nav: "Deck Builder" tab active
- Left sidebar: collapsible section list (RUNSPEC, GRID, PROPS, SOLUTION, SCHEDULE, etc.)
- Main area: 3-column workflow cards + data tables

**Workflow Areas (top row, 3 cards):**
1. "PVT field modelling" - line chart (pressure vs depth)
2. "SCAL relative permeability" - dual-axis chart (saturation curves)
3. "Capillary pressure curve" - line chart

Each card has:
- Title + "OG Banges" badge (top-right, cyan)
- Interactive chart (dark background, cyan/white lines)
- "Dimensione sciensae" dropdown above chart group (Italian text in ref, likely placeholder)

**Data Tables (middle row):**
- "Rock-fluid properties table" - 5x8 grid with Property/Depth/Sat/Perm columns
- "Initialization" - parameter selector (Equilibrium selector: Z00, Fluid compress: AnaloticHaar)
- "Fluid contacts" - settings dropdowns (Pressure selector: WH 18000, etc.)
- All tables have "OG Banges" badges and dark styling

**Bottom Sections:**
- "Wall controls" - dropdowns for parameter visualization
- "History matching", "Development scenarios" sections with "OG banges"/"OC Banges" badges
- "Block-oil" computational setup options

**Visual Style:**
- Very dark blue background (#0A1628)
- Cards slightly lighter (#0F2642)
- Cyan badges (#00D9FF)
- Charts: white/cyan lines on dark grid
- Dropdowns: dark with subtle border

---

## Panel 4: ResInsight Results (Bottom-Right)

**Purpose:** 3D visualization + post-processing analytics

**Layout:**
- Top nav: "ResInsight Results" tab active
- Left sidebar: collapsible "Perverver grid" tree + timestep/case controls
- Center: large 3D property view (pressure/saturation on grid)
- Right sidebar: filters + linked result plots

**3D View (center, dominant):**
- Perspective geomodel grid (10x10x5 visible)
- Property mapped as heatmap (red/yellow/green/blue for pressure)
- Color scale legend (right side, 0.00 - 1.00 bar range with gradient)
- Interactive (implied): rotate/zoom controls, axes (X/Y/Z with RGB arrows bottom-right)
- Grid lines visible, transparent where low property value

**Left Controls:**
- "Perverver grid" tree selector (dropdown)
- "Timestep" slider (0 to max, scrub through time)
- "Ensemble size" slider (-18, 38, 3000 range shown)
- "Case comparison" toggles (Targeted, Case1, etc.)

**Right Sidebar:**
- "Wall filters" panel (top):
  - Toggles: Property (1.60), Case comparison (0%), Well structural (0%), Show result
- "Summary vector plots" - time-series line chart (5000 timesteps, multiple colored traces)
- "Linked result" - "infocalendrid GBM" badge with "OG Banges"
- "Cross-plots" - scatter plot with regression line (R2 fit, 0-250 range)
- "Flow diagnostics" - another scatter/line plot (cyan points, white trendline)
- All charts: dark background, white/cyan elements, minimal gridlines

**Top-Right Actions:**
- "Reservoir grid" dropdown
- "Vienoil Grid" button (likely "View Grid")
- "Viewed results" / "Unlish results" buttons (typos, likely "View"/"Unlink")
- User avatar

**Color Legend (3D view):**
- Continuous gradient bar: blue (low 0.00) -> cyan -> green -> yellow -> red (high 1.00)
- Positioned vertically on right edge of 3D viewport
- Label: "Property 1.60" at top

---

## Cross-Cutting Design Patterns

### Typography
- Headings: likely sans-serif, medium weight, white
- Body: smaller sans, gray (#A0AEC0)
- Monospace: code editor (Monaco or Fira Code)

### Navigation
- Horizontal top nav: 7 fixed tabs (Home, Deck Builder, Data Linter, Reservoir Engineering, Simulator, ResInsight Results, AI Explainer)
- Active tab: cyan underline or background highlight
- Vertical left sidebar: collapsible section tree or icon nav
- Breadcrumbs/badges: cyan "OG Banges" labels (operational/status indicator)

### Cards
- Dark background (#0F2642 on #0A1628 base)
- Subtle border (1px #1A3A5A or similar)
- Rounded corners (4-8px)
- Inner padding: 16-24px
- Hover: slight glow or border color shift

### Interactive Elements
- Buttons: cyan primary (#00D9FF), dark secondary
- Dropdowns: dark background, white text, chevron icon
- Sliders: cyan track/thumb
- Toggles: cyan when active
- Links: cyan, no underline, ">" chevron suffix for "Learn More"

### Data Visualization
- Charts: Plotly or similar (dark theme)
- Lines: white/cyan
- Grid: subtle gray (#1A3A5A)
- Axes: white labels, gray ticks
- Legends: compact, right-aligned or overlay

### Status Indicators
- Progress bars: cyan fill on dark gray track
- Badges: cyan background, white text, rounded pill
- Icons: line-style (not filled), cyan or white
- Checkmarks: green (#00C853)
- Warnings: yellow (#FFB020) with exclamation icon

### Spacing
- Section gaps: 24-32px vertical
- Card grids: 16px gap
- Inner padding: 16-24px
- Line height: 1.5-1.6 for body text

---

## Implementation Notes

1. **3D View:** Use Three.js or deck.gl for the geomodel grid. Plotly 3D surface may suffice for simpler cases. ResInsight gRPC can generate snapshots server-side.

2. **Code Editor:** Monaco Editor (VS Code) or CodeMirror 6 with custom OPM keyword syntax highlighting.

3. **Charts:** Plotly.js with dark template. Backend serializes `fig.to_json()` per `BUILD_GUIDE.md` section 4.

4. **Section Tree:** Collapsible/expandable component (react-checkbox-tree or custom). Sync with editor scroll position.

5. **Real-time Validation:** WebSocket from backend sends lint updates as user types (debounced 500ms). Show inline squiggles + right-sidebar summary.

6. **Responsive:** All 4 panels are desktop-first (1280px+ width). Mobile deferred to Phase 3.

7. **Theme:** The reference is darker than the "Dark Void" theme in design_sense (which uses warm cream/charcoal). Decision needed: match the reference's pure dark blue, or adapt to the warmer Dark Void palette. Recommend **matching the reference** since it's domain-appropriate (technical/scientific tools trend dark/cool, not warm/editorial).

---

## Design Sense Reconciliation

The `design_sense` prompt specifies warm/earthy tones (cream #F7F4EF, terracotta #C4612F), editorial serif headings, and a single-column centered layout. The reference UI is the opposite: dark blue/cyan, technical sans-serif, multi-column dashboard.

**Resolution:** The reference UI is the authoritative design for OPM-AI (it's domain-appropriate for a simulation workbench). The `design_sense` palette applies only when the user provides NO design direction. Here, the user provided explicit visual guidance via `Reference_UI.png`, so we follow the reference.

**Palette to Use (extracted from reference):**
- Base: `#0A1628` (very dark blue)
- Surface: `#0F2642` (card background)
- Border: `#1A3A5A` (subtle)
- Primary: `#00D9FF` (cyan - links, badges, active states)
- Text: `#FFFFFF` (headings), `#A0AEC0` (body)
- Success: `#00C853` (green checkmarks)
- Warning: `#FFB020` (yellow icons)
- Chart lines: `#FFFFFF`, `#00D9FF`, gradient for heatmaps

---

## Next Steps

1. Add this spec to the 06-chat-and-api.md references section.
2. Update `frontend/src/theme.ts` with the extracted palette.
3. Scaffold the 4 main views as separate routes: `/` (home), `/deck-builder`, `/deck-editor`, `/results`.
4. Implement the horizontal nav + sidebar layout shell first.
5. Build the Deck Editor (Panel 2) as the first vertical slice - it's the most complex and demonstrates Monaco + real-time validation + section tree.
