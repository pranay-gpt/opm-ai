# Waterflood Breakthrough and Watercut Behavior

Waterflooding is the most common secondary recovery method in petroleum engineering. When water is injected into a reservoir to displace oil, a waterfront advances through the pore space. The physics of this displacement is governed by the fractional flow equation derived from the Buckley-Leverett theory.

The key concept is the **fractional flow of water** ($f_w$), which depends on water saturation ($S_w$) through relative permeability curves:

$$f_w = \frac{1}{1 + \frac{k_{ro}}{k_{rw}} \frac{\mu_w}{\mu_o}}$$

where $k_{ro}$ and $k_{rw}$ are relative permeabilities to oil and water, and $\mu_o$ and $\mu_w$ are viscosities.

**Water breakthrough** occurs when the waterfront reaches a production well. At this point, the water cut (fraction of water in produced fluids) jumps sharply from near-zero to a significant value. The timing depends on:
- Injection rate (higher rate = earlier breakthrough)
- Mobility ratio $M = \frac{k_{rw}/\mu_w}{k_{ro}/\mu_o}$ (unfavorable if M > 1)
- Reservoir heterogeneity and well spacing

After breakthrough, watercut typically follows an S-shaped curve approaching 100% at late time. The shape depends on the fractional flow curve's derivative $df_w/dS_w$.

**Key takeaway**: Early water breakthrough with unfavorable mobility ratio leads to poor sweep efficiency. Understanding the Buckley-Leverett front velocity helps predict breakthrough timing and design better injection strategies.