# Monopile Foundation — Industry-Standard Initial (Concept) Design Method

## Governing standards
- **DNV-ST-0126** *Support structures for wind turbines* — primary structural/geotechnical design code used industry-wide; references **DNV-RP-C212** (soil-structure interaction) and **DNV-ST-0437** (loads).
- **IEC 61400-3-1** — design requirements for offshore wind turbines (load cases, safety classes).
- **API RP 2GEO / API RP 2A-WSD** — origin of the classical p-y curve method for laterally loaded piles, adopted (with caveats) by DNV.

## Design philosophy: soft-stiff dynamics
Monopiles are almost always designed to the **soft-stiff** frequency range: the first natural frequency of the tower+monopile+RNA system must sit in the gap between the rotor's rotational frequency (**1P**) and the blade-passing frequency (**3P**), avoiding both wave-frequency excitation and resonance with rotor harmonics. A Campbell diagram (frequency vs. rotor RPM) is used to define this target band; the target natural frequency is the primary driver of monopile diameter and wall thickness, not just static strength.

## Standard design sequence (concept stage)
The widely-cited **"10-step" / Arany et al. (2017)** simplified spreadsheet methodology is the de-facto industry pattern for concept-stage sizing, since detailed metocean and soil data are usually unavailable yet:
1. Estimate environmental & turbine loads (wind thrust, wave/current via Morison equation, RNA mass/inertia).
2. Guess initial pile diameter, wall thickness, and embedded length from rules of thumb.
3. **ULS check** — pile bending/shear capacity vs. extreme load combination (safety-class factored).
4. **SLS check** — mudline rotation and pile-head deflection against allowable limits (typically ≤0.5° rotation at mudline).
5. **Natural frequency assessment (NFA)** — closed-form beam-on-elastic-foundation formula (Arany's simplified 3-spring model) checked against the soft-stiff target band.
6. **FLS check** — accumulated fatigue damage (Miner's rule) from wind+wave cycling over 25–30 yr design life.
Steps 3→6 are iterated until all four are satisfied simultaneously; in practice **FLS most often governs final diameter/wall thickness** (found to control in ~11 of 12 published case studies), not ULS.

## Soil-structure interaction (lateral pile response)
- **Classical method**: Winkler beam-on-nonlinear-spring model using **p-y curves** per API RP 2GEO / DNV-ST-0126, calibrated originally for slender (small-diameter, flexible) oil & gas piles.
- **Known limitation**: API/DNV p-y curves under-predict stiffness and capacity for the large-diameter (6–10 m), rigid, low L/D monopiles now standard in offshore wind, because they ignore pile-base shear and base moment resistance.
- **PISA method** (Pile Soil Analysis JIP, Byrne/Oxford-Cambridge-Imperial, ~2019) is now the emerging industry-preferred approach for large-diameter monopiles: a 1D model with **four calibrated soil-reaction curves** (distributed lateral load, distributed moment, base shear, base moment) fitted to 3D FE analyses, giving more realistic stiffness/capacity than single p-y curves. Increasingly referenced alongside DNV-ST-0126 for detailed/FEED-stage validation.

## Rule-of-thumb initial sizing (concept stage, before iteration)
- **Diameter**: scales with RNA mass, hub height and water depth; typical modern 10–15 MW turbines → monopile diameter roughly **8–10 m**.
- **Embedded length**: commonly **~4–6× diameter** (L/D ≈ 4–6) as a starting point for rigid-pile behavior, later refined by ULS/SLS/PISA checks.
- **Wall thickness**: initial estimate from D/t ≈ 80–140 (API guidance), refined by FLS.

## Practical takeaway for a concept-design tool
A defensible initial sizing module should: (1) size diameter/length/thickness from simple closed-form rules, (2) run the Arany-style ULS→SLS→NFA→FLS spreadsheet loop with API/DNV p-y springs for speed, and (3) flag results for PISA-based or FE validation once diameter exceeds ~7–8 m or L/D drops below ~4, where classical p-y is known to be unreliable.

---
**Sources**
- [Design of monopiles for offshore wind turbines in 10 steps (Arany et al., 2017)](https://www.sciencedirect.com/science/article/abs/pii/S0267726116302937)
- [PISA design model for monopiles for offshore wind turbines: application to a marine sand](https://www.icevirtuallibrary.com/doi/10.1680/jgeot.18.P.277)
- [PISA: new design methods for offshore wind turbine monopiles](https://www.geotechnique-journal.org/articles/geotech/full_html/2019/01/geotech190009s/geotech190009s.html)
- [Generalized P-y curves for monopile design using the PISA methodology (ISSMGE)](https://www.issmge.org/uploads/publications/51/126/468_E_generalized_py_curves_for_monopile_design_using_th.pdf)
- [Structural design of monopile foundation — DNV monopile design checks](https://www.offshoreengineering.com/wind-monopile-design/structural-dimensions-monopile-foundation-design-example/)
- [A review of offshore wind monopiles structural design achievements and challenges](https://www.sciencedirect.com/science/article/abs/pii/S0029801821008192)
- [Geotechnical challenges in monopile foundations and performance assessment of current design methodologies](https://www.sciencedirect.com/science/article/pii/S0029801824018079)
