# Reference: WISDEM MonopileSE vs. this engine

Informational only — not a methodology decision (see `methodology.md` for the
decision log). Captured 2026-07-16 after reviewing
[NLRWindSystems/WISDEM](https://github.com/NLRWindSystems/WISDEM)
(`wisdem/fixed_bottomse/monopile.py`, `wisdem/commonse/environment.py`
`TowerSoil`, `wisdem/commonse/utilization_{api,dnvgl,eurocode}.py`,
`wisdem/commonse/utilization_constraints.py`).

## What WISDEM's MonopileSE does

Not a standalone tool — an OpenMDAO component/group inside WISDEM's
whole-turbine systems model, coupled to TowerSE (tower stack), RotorSE/
DrivetrainSE (RNA loads), and cost/BOS models, runnable under gradient-based
MDAO (it declares analytic partials).

- **Structure:** full 3D beam FE model (Frame3DD/pyframe3dd), multi-section
  discretization of monopile + tower with real stiffness/mass matrices —
  not a single-section closed-form beam.
- **Soil:** two options, neither is API-style p-y.
  - Default: **rigid "apparent fixity"** at a user-specified suction-pile
    depth (zero soil flexibility below that point).
  - Optional `soil_springs`: distributed 6-DOF elastic springs from a
    textbook elastic-half-space formula (Arya, O'Neill & Pincus, 1979),
    parameterized by soil shear modulus `G` and Poisson's ratio `ν` — no
    sand friction-angle or clay `su` correlation.
- **Loads:** multiple DLC load cases simultaneously, full Morison
  drag+inertia distributed pressure along the whole structure (vs. a single
  extreme case, drag-only).
- **ULS:** full von Mises stress + shell buckling, selectable code (API RP
  2A, DNVGL-RP-C202, or Eurocode 3), with optional ring/longitudinal
  stiffeners.
- **FLS:** `utilization_constraints.fatigue(M_DEL, N_DEL, ...)` takes
  damage-equivalent loads as *inputs* — it doesn't derive cycles itself;
  that requires an upstream OpenFAST-based DLC fatigue post-processing step.
- **NFA:** real multi-mode FE frequencies + mode shapes (fore-aft/
  side-side/torsion), not a single closed-form f0.

## Comparison

| Aspect | This engine (`engine.py`) | WISDEM MonopileSE |
|---|---|---|
| Structural model | Closed-form Hetenyi beam-on-elastic-foundation, 2-spring (K_L, K_R) head stiffness | Full 3D Frame3DD FEM, multi-section, multi-mode |
| Soil | Closed-form `nh`(friction angle)/`k=0.25×su` — API RP 2GEO-flavored | Rigid apparent-fixity (default) or elastic-half-space springs (G, ν) — not p-y at all |
| Loads | One extreme case, drag-only Morison | Multiple DLC cases, drag+inertia Morison, distributed |
| ULS | Single beam-bending stress vs. yield, γf=1.35 blended | Full von Mises + shell buckling per API/DNVGL/Eurocode |
| FLS | Self-contained: rpm × duty × life → cycles, one S-N curve, placeholder `fatigue_load_factor` | Needs externally-supplied DELs (normally from OpenFAST DLC post-processing) |
| NFA | 2-spring Rayleigh, single f0 vs. soft-stiff band | Multi-mode FE frequencies + mode shapes |
| Iteration | Custom step-wise D/t/L search to 4-check convergence | Embedded in OpenMDAO gradient-based MDAO |
| Scope | Standalone monopile-only screening tool | One coupled module in a full turbine/plant systems model |
| Verification | 3 ad hoc sanity cases, no test suite | Established NREL-lineage project with its own `test/` dir |
| Dependencies | Pure Python, dataclasses only | numpy, scipy, OpenMDAO, compiled pyframe3dd |

## Takeaway

This engine is a genuinely lighter, faster tier than WISDEM — self-contained,
no aeroelastic-sim dependency, suited to first-pass screening. WISDEM trades
that speed for code-compliant (DNVGL/API/Eurocode) buckling checks and
FE-accurate loads/frequencies, but its fatigue check is a stub without an
upstream DLC/OpenFAST fatigue campaign feeding it DELs — which the
`Simulation_database` toolchain already produces and WISDEM's own monopile
module doesn't. Neither tool implements true nonlinear p-y/PISA soil
behavior: WISDEM's more refined soil option is an elastic-half-space model,
not p-y, so that gap is common ground rather than something to fix by
copying WISDEM.
