# Relative Permeability and the Corey Model

Relative permeability describes how the presence of multiple fluid phases reduces the effective permeability to each phase. It is a function of saturation and is central to multiphase flow modeling.

## Definition

For a two-phase (oil-water) system:
$$ k_{ro}(S_w) = \frac{k_{o}(S_w)}{k} \quad \text{(oil relative permeability)} $$
$$ k_{rw}(S_w) = \frac{k_{w}(S_w)}{k} \quad \text{(water relative permeability)} $$

where $k$ is absolute permeability, $k_o$ and $k_w$ are effective permeabilities.

**Key properties**:
- $k_{ro}(S_{wc}) = 1.0$ at connate water saturation
- $k_{ro}(1 - S_{or}) = 0$ at residual oil saturation
- $k_{rw}(S_{wc}) = 0$ at connate water saturation
- $k_{rw}(1 - S_{or}) = k_{rw}^{max} \le 1.0$ at irreducible oil saturation

## Corey Model (Power-Law)

The most common empirical model for relative permeability:

$$ k_{rw}(S_w) = k_{rw}^{max} \left( \frac{S_w - S_{wc}}{1 - S_{wc} - S_{or}} \right)^{n_w} $$
$$ k_{ro}(S_w) = k_{ro}^{max} \left( \frac{1 - S_w - S_{or}}{1 - S_{wc} - S_{or}} \right)^{n_o} $$

**Parameters**:
- $S_{wc}$: connate water saturation (irreducible)
- $S_{or}$: residual oil saturation (to waterflood)
- $n_w, n_o$: Corey exponents (typically 2-4)
- $k_{rw}^{max}$: endpoint water relperm at $S_o = S_{or}$ (often < 1)
- $k_{ro}^{max}$: endpoint oil relperm at $S_w = S_{wc}$ (usually = 1)

**Normalized saturation**:
$$ S_{wn} = \frac{S_w - S_{wc}}{1 - S_{wc} - S_{or}} \in [0, 1] $$

Then:
$$ k_{rw} = k_{rw}^{max} S_{wn}^{n_w} $$
$$ k_{ro} = k_{ro}^{max} (1 - S_{wn})^{n_o} $$

## Three-Phase Relative Permeability

For oil-water-gas systems, OPM Flow uses **Stone's Model** (Stone I or II):

**Stone I** (zero gas-oil interfacial tension):
$$ k_{rog} = k_{ro}^o \left[ \left( \frac{k_{rw} + k_{rog}}{k_{rw}^{max}} \right) \left( \frac{k_{rg} + k_{rog}}{k_{rg}^{max}} \right) - \frac{k_{rw} k_{rg}}{k_{rw}^{max} k_{rg}^{max}} \right] $$

**Stone II** (more general):
$$ k_{rog} = k_{ro}^o \left[ \left( \frac{k_{rw} + k_{rog}}{k_{rw}^{max}} \right) \left( \frac{k_{rg} + k_{rog}}{k_{rg}^{max}} \right) - \frac{k_{rw}}{k_{rw}^{max}} - \frac{k_{rg}}{k_{rg}^{max}} \right] $$

Where $k_{ro}^o$ is two-phase oil relperm at $S_w$ (ignoring gas).

## Eclipse Keywords

| Keyword | Purpose |
|---------|---------|
| `SWOF` | Water-oil relperm table (Sw, krw, kro, Pc) |
| `SGOF` | Gas-oil relperm table (Sg, krg, kro) |
| `SLGOF` | Three-phase: gas-liquid relperm |
| `KRW`, `KRO`, `KRG` | Endpoint scaling keywords |
| `SWCR`, `SOWCR`, `SGCR` | Critical saturations |
| `SORW`, `SORG` | Residual oil saturations |

## Impact on Waterflood

- **High $n_w$**: Water relperm rises slowly -> delayed breakthrough, lower watercut
- **High $n_o$**: Oil relperm drops fast -> early oil rate decline
- **Low $S_{or}$**: More oil recovered -> higher recovery factor
- **Endpoint $k_{rw}^{max}$**: Controls injectivity and watercut after breakthrough

**Typical values** (sandstone):
- $S_{wc} = 0.15-0.25$, $S_{or} = 0.15-0.30$
- $n_w = 2-3$, $n_o = 2-4$
- $k_{rw}^{max} = 0.3-0.6$

## In OPM Flow

- Tables read via `SWOF`, `SGOF`, `SGWF` keywords
- Linear interpolation between table entries
- Endpoint scaling via `KRW`, `KRO`, `KRG` modifies table endpoints
- Hysteresis: `HYSTER` keyword enables Killough model for drainage/imbibition