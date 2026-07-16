# Monopile Foundation Concept Design Engine — Methodology Log

## Decisions
- 2026-07-16 — Adopted Arany et al. (2017) "10-step" ULS→SLS→NFA→FLS iterative sizing loop — matches published industry concept-stage practice.
- 2026-07-16 — Soil-structure interaction: closed-form Hetenyi beam-on-elastic-foundation (idealized homogeneous sand/clay), not full p-y/PISA — user confirmed speed over accuracy for concept stage.
- 2026-07-16 — ULS: single blended load factor γf=1.35 (DNV normal safety class) instead of separate wind/wave partial factors — no detailed load-case combinations at concept stage.
- 2026-07-16 — FLS: single DNV-RP-C203-style S-N curve (log10(a)=12.16, m=3) with DFF=2.0, not joint-specific curves — no detailed joint design exists yet.
- 2026-07-16 — SLS governed by mudline rotation only (0.5° default), no separate deflection limit — matches the industry-recognized governing SLS criterion.
- 2026-07-16 — Natural frequency: 2-spring (K_L, K_R) model, omitting K_LM cross-coupling — kept the derivation self-verifiable in closed form rather than risk misquoting Arany's published 3-spring coefficients.
- 2026-07-16 — Tower stiffness regression calibrated to the published IEA 15MW tower geometry (base 10m/top 6.5m), sole anchor point — an earlier uncalibrated version caused a sizing-loop divergence bug (see METHODOLOGY_REPORT.md §10).
- 2026-07-16 — FATIGUE_LOAD_FACTOR changed 0.35→0.17 (ad-hoc) — 0.35 made FLS demand ~2x too much wall thickness vs. the published IEA 15MW reference (55mm); 0.17 back-solved to match it. User: recalibrate properly once the model is more mature.
- 2026-07-16 — Replaced 6 hand-estimated TURBINE_LIBRARY entries (8-20MW) with 5 entries sourced from real reference-turbine reports (5/10/15/22 MW verified + 25MW extrapolated) — see METHODOLOGY_REPORT.md §2 for sources (OC3/NREL 5MW, DTU 10MW, IEA 15MW, IEA 22MW).
- 2026-07-16 — dt_ratio_max widened 140→160 — matches the real D/t optimization bound used in the IEA 22MW reference monopile design.
- 2026-07-16 — RNA/tower mass split (natural-frequency check only) changed 40/60→50/50 — real observed range across 4 sourced turbines is 43.6%-54.2% RNA fraction; 50/50 is the average, not a fixed ratio.
- 2026-07-16 — NFA cantilever changed from one uniform "average tower" section over the whole mudline-to-hub span to a two-segment model (real pile EI below the transition piece, average-tower EI above it) — the uniform version lumped the much-stiffer pile-above-mudline length in with the flexible tower EI, systematically underpredicting f0 (found via the 5MW/OC3 real-geometry check). Added `transition_piece_height_m` to TURBINE_LIBRARY (sourced: OC3=10m, IEA15/22MW=15m each; DTU10MW assumed=15m, not stated in its turbine-only report).
- 2026-07-16 — Soft-stiff band formula: added a fallback for when `3×rpm_min < 1.1×rpm_max` (band would invert) — falls back to a lower-bound-only criterion using `3×rpm_max` as a loose ceiling, matching how the IEA 22MW report itself frames its frequency target (single-sided 0.15Hz minimum, no explicit 3P-avoidance). Fixes the 22MW band inversion; result now matches the report's stated ~0.16Hz achieved frequency to 3 s.f.

## Open questions
- FATIGUE_LOAD_FACTOR=0.17 is still ad-hoc (back-solved to one reference point, not a DLC spectrum) — recalibrate later.
- Sand nh-vs-friction-angle table and clay k=0.25×su correlation are rough approximations, not validated against site-specific geotechnical data.
- NFA is now validated against 4 real turbine sizes (5/15/20/22MW, see METHODOLOGY_REPORT.md §10) but still omits the K_LM cross-coupling term and uses a single-point-calibrated tower regression for the tower segment above the transition piece.

## Standards / references in use
- DNV-ST-0126 — support structures for wind turbines
- IEC 61400-3-1 — design requirements, load cases
- API RP 2GEO — origin of the p-y method; basis for the sand nh / clay k correlations
- DNV-RP-C203-style S-N curve — fatigue
- Arany et al. (2017), "Design of monopiles for offshore wind turbines in 10 steps"
- Jonkman & Musial, "Offshore Code Comparison Collaboration (OC3) for IEA Task 23", NREL/TP-500-48191 (2010) — OC3/NREL 5MW turbine + monopile
- Bak et al., "Description of the DTU 10 MW Reference Wind Turbine", DTU Wind Energy (2013)
- Gaertner et al., "Definition of the IEA 15-Megawatt Offshore Reference Wind Turbine", NREL/TP-5000-75698 (2020)
- IEA 22MW Reference Wind Turbine report, DTU Wind E-0243