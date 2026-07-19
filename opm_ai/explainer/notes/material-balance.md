# Material Balance Equation

The material balance equation (MBE) is a fundamental tool for reservoir engineering that expresses conservation of mass in a reservoir. It relates original hydrocarbons in place to cumulative production and remaining fluids.

For a black-oil system, the general material balance equation is:

$$N_p B_o + W_p B_w + G_p B_g = N (B_o - B_{oi}) + N B_{oi} \left(\frac{R_{si} - R_s}{B_g}\right) + N B_{oi} \frac{c_w S_{wi} + c_f}{1 - S_{wi}} \Delta p + (W_e - W_p) B_w$$

Where:
- $N$ = original oil in place (STB)
- $N_p, W_p, G_p$ = cumulative oil, water, gas production
- $B_o, B_w, B_g$ = formation volume factors
- $R_s$ = solution gas-oil ratio
- $c_w, c_f$ = water and formation compressibility
- $S_{wi}$ = initial water saturation
- $W_e$ = water influx (aquifer)
- $\Delta p$ = pressure drop

**Simplified for depletion drive (no water influx, no gas cap):**
$$N_p B_o = N (B_o - B_{oi}) + N B_{oi} \frac{R_{si} - R_s}{B_g} + N B_{oi} \frac{c_w S_{wi} + c_f}{1 - S_{wi}} \Delta p$$

**Key applications:**
1. **Determine OOIP (N)**: Plot $F$ vs $E_o + E_g$ where $F$ = cumulative withdrawal, $E$ = expansion terms
2. **Identify drive mechanism**: Slope of $F/E$ plot indicates aquifer support
3. **History matching**: Match production and pressure data by adjusting $N$, aquifer model

**Limitations**: Assumes uniform pressure (tank model), ignores spatial effects, requires good PVT and pressure data.