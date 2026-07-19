# PVT Basics: Solution Gas, Formation Volume Factor, and Bubble Point

PVT (Pressure-Volume-Temperature) properties describe how reservoir fluids change volume and phase with pressure. They are essential for converting between surface (stock tank) and reservoir conditions.

## Key PVT Properties

### 1. Solution Gas-Oil Ratio (Rs)
**Rs = gas dissolved in oil (SCF/STB) at reservoir pressure**

- Increases with pressure (more gas dissolves at higher pressure)
- Constant above bubble point ($P \ge P_b$)
- Decreases below bubble point as gas comes out of solution
- **At bubble point**: $R_{sb}$ = maximum solution GOR

### 2. Oil Formation Volume Factor (Bo)
**Bo = reservoir volume of oil + dissolved gas / surface volume of oil (RB/STB)**

- $B_o \ge 1.0$ always (oil expands with dissolved gas)
- Increases with pressure (more gas dissolves → more expansion)
- Maximum at bubble point: $B_{ob}$
- Decreases below bubble point (gas leaves → oil shrinks)

### 3. Gas Formation Volume Factor (Bg)
**Bg = reservoir volume of free gas / surface volume of gas (RB/SCF)**

- $B_g \propto 1/P$ (ideal gas law approximately)
- Only defined below bubble point (free gas exists)
- Very small at high pressure (gas highly compressed)

### 4. Bubble Point Pressure (Pb)
**Pressure at which first gas bubble comes out of solution**

- Above $P_b$: single-phase oil (undersaturated)
- Below $P_b$: two-phase oil + free gas (saturated)
- Critical for well deliverability (flowing BHP should stay > $P_b$ if possible)

## Typical PVT Table (PVTO keyword in Eclipse)

| Pressure (psia) | Rs (SCF/STB) | Bo (RB/STB) | $\mu_o$ (cp) |
|----------------|--------------|-------------|--------------|
| 5000           | 800          | 1.45        | 0.45         |
| 4000           | 800          | 1.42        | 0.48         |
| 3000           | 800          | 1.38        | 0.52         |
| 2500 (Pb)      | 800          | 1.36        | 0.55         |
| 2000           | 600          | 1.25        | 0.70         |
| 1500           | 400          | 1.15        | 0.95         |
| 1000           | 200          | 1.08        | 1.40         |

## Eclipse Keywords

| Keyword | Fluid | Properties |
|---------|-------|------------|
| `PVTO` | Oil | Rs, Bo, $\mu_o$ vs Pressure |
| `PVTG` | Gas | Bg, $\mu_g$, Rs (gas solubility in gas - rare) vs Pressure |
| `PVTW` | Water | Bw, $\mu_w$, Cw vs Pressure |
| `RSCONST` | - | Constant Rs (for simple cases) |

## Impact on Simulation

1. **Material balance**: $N = \frac{N_p B_o + (R_p - R_s) N_p B_g + W_e B_w}{B_o - B_{oi} + (R_{si} - R_s) B_g}$
2. **Well rates**: Surface rates converted using $B_o$, $R_s$: $q_{res} = q_{surf} B_o$
3. **BHP calculations**: Flowing BHP depends on fluid density (from $B_o$, $R_s$)
4. **Compressibility**: $c_o = -\frac{1}{B_o} \frac{dB_o}{dP}$ affects pressure transient behavior

## In OPM Flow

- Tables read from `PVTO`, `PVTG`, `PVTW` keywords
- Linear interpolation between table entries
- Extrapolation: constant derivative (last two points) - can cause issues if extrapolated far
- `DISGAS` keyword enables dissolved gas (Rs > 0)
- `VDWP` keyword for water vaporization in gas (rare)

**Key takeaway**: Accurate PVT tables are essential. Small errors in $B_o$ or $R_s$ near bubble point cause large errors in production forecasts and well deliverability.