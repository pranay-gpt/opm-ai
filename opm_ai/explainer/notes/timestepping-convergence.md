# Timestepping and Convergence in OPM Flow

Reservoir simulation solves a large system of nonlinear equations at each timestep. Understanding how timesteps are chosen and what causes convergence failures is essential for successful simulation.

## The Newton-Raphson Method

OPM Flow (like Eclipse) uses **fully implicit** formulation with Newton-Raphson iteration:

1. **Discretize** mass conservation equations (oil, water, gas) using TPFA (Two-Point Flux Approximation)
2. **Linearize** nonlinear terms (relperm, PVT, well constraints) around current iterate
3. **Solve** linear system: $J \Delta x = -R$ where $J$ = Jacobian, $R$ = residual
4. **Update**: $x^{new} = x^{old} + \Delta x$
5. **Check convergence**: $\|R\| < \epsilon$ or $\|\Delta x\| < \epsilon$
6. **Repeat** until converged or max iterations reached

## Timestep Selection

### Initial Timestep (`TSTEP` keyword)
```
TSTEP
365*10  /  -- 10 years of 1-year steps
```

### Automatic Timestep Control
- **Success**: If converged in < target iterations (default ~4), next step $\times$ 1.5-2.0
- **Chop**: If max iterations exceeded or divergence, cut step $\times$ 0.25-0.5 and retry
- **Limits**: `TSTEP` keyword defines min/max; `TUNING` adjusts chop/growth factors

### Key Tuning Parameters (`TUNING` keyword)
```
TUNING
-- Newton    Linear    Max    Min    Chop   Growth  Target
   iter       iter     iter   iter   factor factor  iters
    20         50       10     1     0.25   1.50    4     /
```

## Common Convergence Issues

| Issue | Symptoms | Fix |
|-------|----------|-----|
| **Timestep chops** | Repeated "TIMESTEP CHOP" messages | Reduce max timestep, increase `TUNING` chop factor |
| **Newton divergence** | Residual increases, iterations max out | Reduce timestep, check PVT/relperm tables |
| **Oscillations** | Solution bounces between states | Add `TUNING` damping, check well constraints |
| **Well control switching** | Producer switches rate ↔ BHP frequently | Relax constraints, add small tolerance |

## Linear Solver (CPR-AMG)

OPM Flow uses **CPR (Constrained Pressure Residual)** with **AMG (Algebraic Multigrid)**:
1. Solve pressure block with AMG (coarse grid correction)
2. Solve full system with ILU or GMRES preconditioned by CPR

**Linear solver failures** (`LINEAR SOLVER FAILED`):
- Ill-conditioned matrix (high contrast permeability, small cells)
- Fix: Increase `TUNING` linear iterations, check grid quality

## Special Cases

### Bubble Point Crossing
- Large nonlinearity as $R_s$ drops, $B_o$ drops, gas appears
- **Fix**: Reduce max timestep near $P_b$, ensure fine PVT table spacing

### Water Breakthrough
- Sharp saturation front → large Jacobian entries
- **Fix**: Use `TSTEP` with smaller steps near expected breakthrough

### Gas Coning
- Strong gravity + high rate → sharp gas-oil contact movement
- **Fix**: Local grid refinement (LGR), smaller timesteps

### Thermal/Compositional
- More components = larger Jacobian = slower convergence
- OPM Flow thermal: `TEMP` keyword, energy equation coupled

## Monitoring Convergence

Key output in `.PRT` / `.DBG` / console:
```
NEWTON ITERATION  1   RESIDUAL = 1.23E+04
NEWTON ITERATION  2   RESIDUAL = 4.56E+02
NEWTON ITERATION  3   RESIDUAL = 1.23E-02   <-- CONVERGED
TIMESTEP =  365.0  DAYS  CUMULATIVE = 3650.0  DAYS
```

**Good**: 3-5 iterations, residual drops 2-3 orders per iteration
**Bad**: >10 iterations, residual stalls or grows

## Best Practices

1. **Start conservative**: Small initial timesteps, generous max chops
2. **Monitor early**: First 10-20 timesteps reveal convergence character
3. **PVT table density**: 20-30 pressure points, denser near $P_b$
4. **Grid quality**: Avoid extreme aspect ratios, check `ACTNUM` for inactive cells
5. **Well constraints**: Always set both rate target AND BHP limit
6. **Output control**: `RPTSCHED` for timestep/convergence summary

**In OPM Flow**: Use `--print-linear-solver-info` and `--print-newton-info` for detailed diagnostics. The `--max-newton-iterations` and `--max-linear-iterations` CLI options override `TUNING`.

**Key takeaway**: Convergence problems usually indicate physical issues (bad PVT, bad relperm, unrealistic rates) or numerical issues (too large timestep, bad grid). Fix the root cause, not just the symptoms.