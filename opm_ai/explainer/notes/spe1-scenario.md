# SPE1: The Classic Reservoir Simulation Benchmark

SPE1 (SPE Comparative Solution Project 1) is the foundational benchmark problem for 3D black-oil reservoir simulation. Published in 1981 by Odeh (JPT), it has been used to validate every commercial and research simulator since.

## Problem Description

**Geometry**: 3D Cartesian grid, 10 × 10 × 3 = 300 blocks
- X: 10 blocks × 1000 ft = 10,000 ft
- Y: 10 blocks × 1000 ft = 10,000 ft
- Z: 3 layers: 20 ft, 30 ft, 50 ft thick

**Properties**:
- Porosity: 0.3 (uniform)
- Permeability: Layered (500, 50, 200 mD for layers 1, 2, 3)
- Depth: 8325 ft (top of layer 1)
- $k_y = k_x$, $k_z = 0.1 \times k_x$ (via PERMZ keyword)

**Fluids**:
- Oil + Water + Dissolved Gas (DISGAS)
- Bubble point: ~3500 psia
- Initial pressure: 4500 psia (undersaturated)
- $R_{si}$ = 500 SCF/STB
- Oil viscosity: ~1 cp
- Water viscosity: ~0.5 cp

**Wells**:
- Producer: PROD1 at (1,1, all layers) - bottom-hole producer
- Injector: INJ1 at (10,10, all layers) - water injector

**Schedule**:
- Injector: 5000 STB/day water, max BHP 5000 psia
- Producer: 5000 STB/day liquid, min BHP 2000 psia
- Run: 5 years (1825 days)

## Key Results (Odeh Reference)

| Metric | Odeh Reference | Typical OPM Flow |
|--------|----------------|------------------|
| Cumulative oil (5 yr) | ~1.2 MMSTB | ~1.2 MMSTB |
| Water breakthrough | ~Year 3 | ~Year 3 |
| Final water cut | ~90% | ~90% |
| Final GOR | Rising | Rising |

## Why SPE1 Matters

1. **Code verification**: Every new simulator must match SPE1
2. **Grid orientation effects**: 5-spot pattern shows grid orientation sensitivity
3. **Layered system**: Crossflow between layers (high perm vs low perm)
4. **Gravity segregation**: Water injection below oil (dip not modeled, but density difference)
5. **Solution gas drive**: Pressure drops below bubble point during production

## OPM Flow SPE1 Decks

Multiple variants in `tests/fixtures/spe1/`:
- `SPE1CASE1.DATA`: Base case (oil-water-gas)
- `SPE1CASE1_WATER.DATA`: Oil-water only (no gas)
- `SPE1CASE2_*.DATA`: Variations (thermal, compositional, etc.)

## Running SPE1 in OPM Flow

```bash
flow SPE1CASE1.DATA --output-dir results/
```

Key outputs in `results/`:
- `SPE1CASE1.SMSPEC` + `SPE1CASE1.UNSMRY` - Summary data (FOPT, FWPT, FGOR, etc.)
- `SPE1CASE1.UNRST` - Restart/result files for ResInsight

## Expected Summary Vectors

| Vector | Description |
|--------|-------------|
| `FOPT` | Field oil production total (STB) |
| `FOPR` | Field oil production rate (STB/day) |
| `FWPT` | Field water production total (STB) |
| `FWPR` | Field water production rate (STB/day) |
| `FGPT` | Field gas production total (MSCF) |
| `FGOR` | Field gas-oil ratio (SCF/STB) |
| `WWCT:PROD1` | Well water cut (fraction) |
| `WBHP:PROD1` | Well bottom-hole pressure (psia) |
| `WWIR:INJ1` | Well water injection rate (STB/day) |

## Common Issues When Running

| Issue | Symptom | Fix |
|-------|---------|-----|
| Timestep chops | Many "CHOP" messages near year 3 | Reduce max timestep, add TUNING |
| Pressure drops too fast | Producer BHP hits limit early | Check injector rate, aquifer (none in SPE1) |
| Gas evolution wrong | GOR doesn't match reference | Check PVTO table, DISGAS keyword |
| Crossflow wrong | Layer rates don't match | Check PERMZ, TRANZ, grid geometry |

## Teaching Value

SPE1 teaches:
1. **Grid design**: Cartesian vs corner-point, layering
2. **Well placement**: 5-spot pattern, perforation intervals
3. **Fluid properties**: PVTO table construction, bubble point
4. **Well controls**: Rate vs BHP, constraint switching
5. **Timestep control**: TSTEP, TUNING, convergence
6. **History matching**: Compare FOPT, FWPT, FGOR to reference
7. **Post-processing**: ResInsight visualization, summary plots

**Key takeaway**: SPE1 is the "Hello World" of reservoir simulation. If your simulator can't match SPE1, it won't match anything else. OPM Flow matches SPE1 within 1-2% on all key metrics.