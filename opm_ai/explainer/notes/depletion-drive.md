# Depletion Drive (Solution Gas Drive)

Depletion drive is the primary recovery mechanism when reservoir pressure drops below the bubble point with no significant aquifer or gas cap support. It typically yields the lowest recovery factor of all drive mechanisms.

## Physical Mechanism

1. **Above bubble point** ($P > P_b$):
   - Single-phase oil (undersaturated)
   - Only oil expansion and rock/fluid compressibility drive production
   - Recovery: 2-5% OOIP
   - Pressure declines rapidly

2. **At bubble point** ($P = P_b$):
   - First gas comes out of solution
   - Solution GOR ($R_s$) begins to decrease
   - Free gas saturation builds up

3. **Below bubble point** ($P < P_b$):
   - Two-phase flow: oil + free gas
   - Free gas has high mobility ($\mu_g \ll \mu_o$, $k_{rg} > 0$)
   - Gas flows to producers → GOR increases sharply
   - Oil relative permeability drops as $S_g$ increases
   - Pressure declines more slowly (gas expansion helps)
   - Ultimate recovery: 15-30% OOIP typically

## Key Equations

**Material Balance (simplified, no water influx):**
$$ N_p B_o = N (B_o - B_{oi}) + N B_{oi} \frac{R_{si} - R_s}{B_g} $$

Where:
- $N$ = Original Oil In Place (STB)
- $N_p$ = Cumulative oil production (STB)
- $B_o, B_g$ = Formation volume factors at current pressure
- $R_s$ = Solution GOR at current pressure

**Producing GOR:**
$$ GOR_{prod} = R_s + \frac{k_{rg} \mu_o B_o}{k_{ro} \mu_g B_g} $$

## Characteristics

| Property | Depletion Drive |
|----------|-----------------|
| Pressure decline | Rapid, continuous |
| GOR trend | Constant at $R_{si}$, then sharp increase at $P_b$ |
| Water production | Minimal (connate only) |
| Recovery factor | 15-30% OOIP |
| Economic limit | Often reached early due to high GOR |

## Simulation Considerations

1. **PVT accuracy critical**: $R_s$, $B_o$, $B_g$, $\mu_o$, $\mu_g$ near $P_b$ must be accurate
2. **Relative permeability**: Gas-oil relperm ($k_{rg}$, $k_{ro}$ at low $S_g$) controls GOR
3. **Grid resolution**: Gas saturation fronts can be sharp; fine grid near wells helps
4. **Timestep control**: Crossing $P_b$ causes nonlinearity → Newton iterations, timestep chops
5. **Well constraints**: BHP control often needed as rate drops and GOR increases

## Comparison with Other Drive Mechanisms

| Drive Mechanism | RF Range | Pressure Decline | GOR Behavior |
|-----------------|----------|------------------|--------------|
| Depletion (solution gas) | 15-30% | Rapid | Sharp increase at $P_b$ |
| Gas cap expansion | 30-50% | Moderate | Slow increase |
| Weak water drive | 25-40% | Moderate | Moderate increase |
| Strong water drive | 35-55% | Slow/flat | Stable, then increase |
| Waterflood (secondary) | 45-65% | Managed | Increases after breakthrough |

## In OPM Flow

- Enable with `OIL`, `GAS`, `DISGAS` in RUNSPEC
- `PVTO` table must extend below bubble point
- `SGOF` table needed for gas-oil relperm
- Monitor: `FOPT`, `FGPT`, `FGOR`, `WBHP` in summary output
- Use `TUNING` to adjust Newton tolerances if convergence issues at $P_b$

**Key takeaway**: Depletion drive has poor recovery efficiency. Pressure maintenance (gas injection, waterflood) is almost always economically justified. Simulations of depletion drive serve as base cases for comparing improved recovery methods.