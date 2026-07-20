# Monopile Concept Design

Concept-stage sizing tool for offshore wind monopile foundations: an
Arany-et-al.-style ("10-step") iteration of ULS/SLS/natural-frequency
(soft-stiff)/FLS/local-shell-buckling checks that converges on a diameter,
wall thickness, and embedded length.

Concept-level screening only -- not certification or FEED design.

## Try it

**[monopile-concept-design.streamlit.app](https://monopile-concept-design.streamlit.app/)**
-- no install, no command line, just open the link.

## Design process

`size_monopile(inputs)` runs an iterative loop:

1. Look up/interpolate turbine properties (rotor diameter, hub height, mass,
   thrust, rotor speed range) from `TURBINE_LIBRARY` by rated power.
2. Guess an initial diameter/wall-thickness/embedded-length from rules of
   thumb anchored to real reference-monopile dimensions.
3. Evaluate the candidate geometry against five checks, each producing a
   utilization ratio (pass if <= 1.0):
   - **ULS** -- mudline yield check (von Mises bending + shear vs. steel yield).
   - **SLS** -- mudline rotation vs. an allowable limit (default 0.5 deg).
   - **NFA** -- first natural frequency vs. the "soft-stiff" target band
     between the 1P (rotor) and 3P (blade-passing) excitation frequencies.
   - **FLS** -- simplified Palmgren-Miner fatigue damage over the design life.
   - **Buckling** -- local shell (DNV-RP-C202 unstiffened cylinder) buckling
     under combined axial, bending, shear, and hydrostatic hoop stress.
4. If all five checks pass, stop (converged). Otherwise adjust diameter or
   wall thickness -- whichever is more effective for the worst-failing
   check -- and re-evaluate.
5. Once converged, step wall thickness back down while every check still
   passes, so the result reflects the true minimum-material thickness rather
   than just the first passing geometry found.
6. Stop at convergence, a runaway guard, or a maximum iteration count --
   whichever comes first.

Loads (extreme wind thrust + Morison wave/current drag) and soil-pile
stiffness (closed-form Hetenyi beam-on-elastic-foundation, sand or clay) are
computed once per candidate geometry and shared across all five checks. See
`docs/METHODOLOGY_REPORT.md` for every equation, constant, symbol
definition, and reference used -- this section is a summary, that document
is the source of truth.

## Major assumptions

This is a concept-stage screening tool, not a certified design method. The
most consequential simplifications:

- **Soil-structure interaction** is a closed-form, idealized single
  homogeneous layer (sand or clay) -- not a full nonlinear multi-layer p-y
  or PISA solve.
- **Wave loading** is a single extreme case, Morison drag-only (no inertia
  term) -- not a multi-DLC time-domain simulation.
- **Natural frequency** uses a simplified 2-spring (lateral + rocking)
  closed-form model, omitting the foundation cross-coupling term Arany's
  full 3-spring method includes. This check is not yet considered fully
  verified.
- **Fatigue** is a single equivalent-stress-range Palmgren-Miner check with
  an empirically-calibrated (not first-principles) load factor -- not a
  rainflow-counted multi-bin DLC fatigue simulation.
- **Local shell buckling** assumes no ring stiffeners anywhere on the pile
  (a single unsupported panel spanning the full exposed above-mudline
  shaft); global (Euler) column buckling is not evaluated.
- **Embedded length has no independent design driver** -- it's a fixed L/D
  ratio at the initial guess, not solved against ultimate soil capacity.
- **D/t manufacturability bounds are advisory**, not a hard limit -- a
  converged geometry outside the configured range is flagged with a warning
  rather than blocked.
- **Turbine data** for 5/15/22 MW is sourced from published reference-turbine
  reports; 10 MW is sourced separately; 25 MW is an unverified extrapolation.

The full, current list (24 items) is in `docs/METHODOLOGY_REPORT.md` section
11. For the dated history of how each assumption was chosen or changed
(sensitivity sweeps, bugs found and fixed), see `docs/method_update_log.md`.

## Run locally

```bash
pip install -r requirements.txt
py -m streamlit run app.py
```

## Turbine library

`engine.py`'s `TURBINE_LIBRARY` spans 5-25 MW. The 5/15/22 MW entries are
sourced from published reference-turbine reports (OC3/NREL 5MW, IEA 15MW,
IEA 22MW); 10 MW is from the DTU 10MW report; 25 MW is an extrapolation, not
an independently verified turbine.
