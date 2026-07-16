# Monopile Concept Design Engine — Methodology Report

`engine.py` v0.1. This report documents every equation, constant, and assumption
in the code as-implemented, so there is no ambiguity between this document and
the source. Section numbers reference the corresponding function in
`engine.py`. Concept-level screening only — not certification or FEED design.

---

## 0. Process overview

`size_monopile(inputs)` runs an Arany-et-al.-style ("10-step") iteration:

1. Look up/interpolate turbine properties from `TURBINE_LIBRARY` (§2).
2. Guess an initial geometry from rules of thumb (§9).
3. Evaluate the candidate geometry (`evaluate_monopile`):
   a. Compute mudline extreme moment/shear from wind + wave/current (§3).
   b. Compute closed-form soil stiffness (K_L, K_R) (§4).
   c. Run ULS (§5), SLS (§6), natural-frequency/soft-stiff (§7), and FLS (§8)
      checks, each returning a utilization ratio (pass if ≤ 1.0).
   d. Compute steel mass/cost and collect validity-range notes.
4. If all four utilizations are ≤ 1.0, stop (converged).
5. Otherwise, adjust diameter, wall thickness, or embedded length per the
   step-wise rule in §9 and go back to 3.
6. Stop at convergence, at a runaway guard (diameter ≥ 3× the initial guess),
   or after 500 iterations — whichever comes first.

All internal units are SI-with-MN: **length in m, force in MN, moment in
MN·m, stress in MPa (≡ MN/m²), Young's modulus in MPa**. This makes
`EI [MN·m²] = E[MPa] × I[m⁴]` and `stress [MPa] = moment[MN·m] / section
modulus[m³]` unit-consistent without conversion factors, which is why the
code carries no unit-conversion calls inside the physics functions.

---

## Symbol glossary

Every variable used in the equations below, grouped by where it first
appears. Units follow the MN-based convention from §0.

**Geometry & section properties**
| Symbol | Meaning | Units |
|---|---|---|
| `D` | pile outer diameter | m |
| `t` | pile wall thickness | m |
| `L` | pile embedded length | m |
| `D_inner` | pile inner diameter, `D - 2t` | m |
| `I` | pile second moment of area | m⁴ |
| `Z` | pile section modulus, `I / (D/2)` | m³ |
| `A` | pile cross-section area | m² |
| `A_shear` | effective shear area, `0.5 × A` (thin-wall approximation) | m² |
| `EI` | pile flexural rigidity | MN·m² |

**Loads (§3)**
| Symbol | Meaning | Units |
|---|---|---|
| `M_thrust` | mudline moment from extreme wind thrust | MN·m |
| `F_thrust` | mudline shear from extreme wind thrust (= `thrust_mn`) | MN |
| `H_max` | design/extreme individual wave height, `1.9 × Hs` | m |
| `omega` | wave angular frequency, `2π / Tp` | rad/s |
| `k_wave` | wave number (deep-water dispersion relation) | 1/m |
| `u(z)` | horizontal water-particle velocity + current, at depth `z` | m/s |
| `f(z)` | Morison drag force per unit pile length, at depth `z` | MN/m |
| `F_wave` | total wave/current shear at mudline (`∫ f(z) dz`) | MN |
| `M_wave` | total wave/current moment at mudline | MN·m |
| **`M_char`** | **characteristic (unfactored) mudline moment**, `M_thrust + M_wave` — the shared input to ULS, SLS, and FLS | MN·m |
| **`V_char`** | **characteristic (unfactored) mudline shear**, `F_thrust + F_wave` — shared input to ULS and SLS | MN |
| `M_uls`, `V_uls` | ULS design moment/shear, `M_char`/`V_char` × `GAMMA_F_ULS` | MN·m, MN |

**Soil / pile-head stiffness (§4)**
| Symbol | Meaning | Units |
|---|---|---|
| `k_soil` | Winkler modulus of subgrade reaction (idealized homogeneous layer) | MN/m³ |
| `nh` | sand subgrade-reaction gradient, `k_soil(z) = nh × z` | MN/m⁴ |
| `su` | clay undrained shear strength | kPa |
| `z_ref` | characteristic depth used to evaluate sand `k_soil`, `L / 3` | m |
| `k_line` | line-load Winkler modulus, `k_soil × D` | MN/m² |
| `beta` | pile stiffness parameter, `(k_line / 4EI)^0.25` | 1/m |
| `K_L` | pile-head lateral stiffness | MN/m |
| `K_R` | pile-head rocking stiffness | MN·m/rad |
| `K_LM` | pile-head cross-coupling stiffness (derived, **not used** — see §7) | MN |
| `P0`, `M0` | generic applied force/moment at the pile head, used only in the Hetenyi derivation | MN, MN·m |
| `y0` | pile-head lateral deflection | m |
| `theta0` | pile-head rotation | rad (converted to deg where used) |

**ULS (§5)**
| Symbol | Meaning | Units |
|---|---|---|
| `sigma_bending` | mudline bending stress, `M_uls / Z` | MPa |
| `tau_shear` | mudline shear stress, `V_uls / A_shear` | MPa |
| `sigma_vm` | combined (von-Mises-style) stress, `sqrt(sigma_bending² + 3·tau_shear²)` | MPa |
| `utilization_ULS` | ULS utilization ratio (pass if ≤ 1.0) | – |

**SLS (§6)**
| Symbol | Meaning | Units |
|---|---|---|
| `theta0_deg` | mudline rotation, `\|theta0\|` converted to degrees | deg |
| `utilization_SLS` | `theta0_deg / allowable_sls_rotation_deg` | – |

**Natural frequency / NFA (§7)**
| Symbol | Meaning | Units |
|---|---|---|
| `d_avg_tower`, `t_avg_tower` | approximated average tower diameter/thickness | m |
| `I_tower`, `EI_tower` | tower second moment of area / flexural rigidity | m⁴, MN·m² |
| `EI_pile` | pile flexural rigidity (same as `EI` elsewhere), used for the pile-above-mudline cantilever segment | MN·m² |
| `transition_piece_height_m` | height of the tower base (monopile/tower interface) above MSL; a turbine-library field | m |
| `pile_above_mudline` | height of the (stiff) pile segment from mudline to the transition piece, `water_depth_m + transition_piece_height_m` | m |
| `h` | total cantilever height, mudline to hub, `hub_height_m + water_depth_m` (unchanged) | m |
| `tower_height` | height of the (more flexible) tower segment above the transition piece, `h - pile_above_mudline` | m |
| `cantilever_flexibility` | two-segment tip flexibility of the pile-above-mudline + tower cantilever (see §7) | m/MN |
| `flexibility` | total tip flexibility (`cantilever_flexibility` + foundation `K_L` + `K_R`) | m/MN |
| `k_eq` | equivalent lateral stiffness at hub height, `1 / flexibility` | MN/m |
| `m_RNA`, `m_tower` | assumed RNA/tower mass split of `total_turbine_mass_t` | t |
| `m_eff` | effective modal mass, `m_RNA + 0.25 × m_tower` (Rayleigh factor) | kg |
| `f0` | first (fore-aft) natural frequency | Hz |
| `f_1P_max`, `f_1P_min` | rotor (1P) excitation frequency range bounds, from `rpm_max`/`rpm_min` | Hz |
| `f_3P_min` | bottom of the blade-passing (3P) frequency range, `3 × f_1P_min` | Hz |
| `f_3P_max` | top of the 3P range (3P at rated), `3 × f_1P_max` — used as the degenerate-gap fallback ceiling | Hz |
| `band_low`, `band_high` | soft-stiff target frequency band bounds (with 10% margins); `band_high` falls back to `0.9×f_3P_max` when the classical gap is degenerate | Hz |
| `utilization_NFA` | NFA utilization ratio (pass if `f0` inside `[band_low, band_high]`) | – |

**FLS (§8)**
| Symbol | Meaning | Units |
|---|---|---|
| `sigma_char` | characteristic (unfactored) bending stress used for fatigue, `M_char / Z` | MPa |
| `fatigue_load_factor` | assumed ratio converting `sigma_char` to a fatigue-equivalent stress range (`FATIGUE_LOAD_FACTOR` = 0.17) | – |
| **`delta_sigma_eq`** | **equivalent constant-amplitude stress range** for the Palmgren-Miner check, `fatigue_load_factor × sigma_char` | MPa |
| `N_allow` | allowable cycles to failure at `delta_sigma_eq`, from the S-N curve | – |
| `rpm_avg` | average rotor speed used for cycle counting, `0.5 × (rpm_min + rpm_max)` | rpm |
| `n_cycles` | total stress cycles accumulated over `design_life_years` | – |
| `damage` | Palmgren-Miner cumulative damage ratio, `n_cycles / N_allow` | – |
| `utilization_FLS` | `damage × FATIGUE_DESIGN_FACTOR` | – |

**Initial guess & iteration (§9)**
| Symbol | Meaning | Units |
|---|---|---|
| `D0`, `L0`, `t0` | initial geometry guess (diameter, embedded length, wall thickness) | m |
| `d_step`, `t_step` | per-iteration step sizes for diameter/thickness | m |
| `dt_ratio` | `D / t` | – |
| `l_over_d` | `L / D` | – |

---

## 1. Constants (module-level)

| Constant | Value | Meaning / source |
|---|---|---|
| `G` | 9.81 m/s² | gravity |
| `RHO_SEAWATER_KG_M3` | 1025 kg/m³ | seawater density |
| `STEEL_DENSITY_T_PER_M3` | 7.85 t/m³ | structural steel |
| `STEEL_E_MPA` | 210,000 MPa | steel Young's modulus |
| `STEEL_YIELD_MPA` | 355 MPa | S355 offshore structural steel |
| `USD_PER_T_STEEL` | 2,200 USD/t | rolled/welded monopile steel, concept-stage placeholder cost |
| `GAMMA_F_ULS` | 1.35 | combined wind+wave load factor — **assumption**: a single blended DNV "normal safety class" factor, not separate per-load-type factors |
| `GAMMA_M_ULS` | 1.1 | DNV-ST-0126 material resistance factor |
| `MORISON_CD` | 0.65 | drag coefficient, smooth circular cylinder, high Reynolds number |
| `SN_LOG10_A` | 12.16 | DNV-RP-C203 basic design S-N curve intercept (in-air, single-slope segment, `m=3`) — **assumption**: one representative curve used for the whole structure, not joint-specific; the real curve's bilinear knee at ~10⁷ cycles is not modeled (see §8) |
| `SN_M` | 3.0 | S-N curve slope (first segment only, per DNV-RP-C203) |
| `FATIGUE_DESIGN_FACTOR` | 2.0 | DNV-ST-0126/DNV-RP-C203 Design Fatigue Factor (DFF), typical accessible/inspectable monopile joint — see DFF table in §8 |

---

## 2. Turbine library (§ `TURBINE_LIBRARY`, `turbine_from_capacity`)

Five reference points (5/10/15/22/25 MW), each with `rotor_diameter_m`,
`hub_height_m`, `mass_t`, `thrust_mn`, `rpm_min`, `rpm_max`. `turbine_from_capacity(mw)`
**linearly interpolates** between the two bracketing entries (or clamps to the
nearest end point outside 5–25 MW). Updated 2026-07-16 to replace the
original six hand-estimated points (8/10/12/15/18/20 MW) with sourced values
from four published reference-turbine reports, plus one extrapolated point.

**Sourced anchors (verified 2026-07-16):**

| MW | Source | Rotor D (m) | Hub height (m) | RNA (t) | Tower (t) | Total mass (t) | Thrust (MN) | rpm min/max |
|---|---|---|---|---|---|---|---|---|
| 5 | OC3/NREL 5-MW, Phase II monopile (NREL/TP-500-48191) | 126.0 | 90.0 | 350.0 (Rotor 110 + Nacelle 240) | 347.5 | 697.5 | 0.80* | 6.90 / 12.10 |
| 10 | DTU 10-MW RWT (Bak et al. 2013) | 178.3 | 119.0 | 675.0 (Rotor 229 + Nacelle 446) | 605.0 | 1280.0 | 1.50* | 6.00 / 9.60 |
| 15 | IEA Wind 15-MW RWT (NREL/TP-5000-75698), Table ES-1 | 240.0 | 150.0 | 1017.0 | 860.0 | 1877.0 | 2.50 | 5.00 / 7.56 |
| 22 | IEA 22-MW RWT (DTU Wind E-0243), Table 1/2 | 284.0 | 170.0 | 1215.6 | 1574.0 | 2789.6 | 2.793 | 1.807 / 7.061 |
| 25 | **extrapolated**, not a real reference turbine | 303.0 | 179.0 | — | — | 3181.0 | 2.92 | 0.44 / 6.85 |

\* Thrust not tabulated in the 5 MW/10 MW source excerpts available this
session; these are commonly cited literature values (Jonkman et al. 2009 for
the 5 MW turbine; Bak et al. 2013 for the 10 MW turbine), not independently
re-derived here the way the 15 MW value was (see below). The 15 MW thrust
(2.50 MN) was cross-checked by computing `0.5 × ρ_air × A × U_rated² × C_T`
using the report's stated design-point `C_T = 0.804` at rated wind speed
10.59 m/s — matches the library value to 3 significant figures.

**25 MW row is a linear extrapolation** of the 15→22 MW trend for each
column, **not** verified against any real 25 MW reference document. The
`rpm_min` trend in particular is steep in the real data (5.00 → 1.807 rpm
from 15 to 22 MW) — extrapolating it further to 0.44 rpm is the single
least-certain number in the table.

**Assumptions baked into the library data:**
- `mass_t` is **total turbine mass (RNA + tower combined)**, not RNA alone.
- `thrust_mn` is used directly as the **extreme/ultimate ULS design thrust**
  (not the rated/operational thrust) — no additional extreme-load multiplier
  is applied elsewhere in the code.
- RNA/tower mass split (used only in §7's natural-frequency check) is now
  **50/50** (updated 2026-07-16, was a flat 40/60 guess) — the real RNA
  fraction observed across the four sourced turbines ranges from 43.6% (22
  MW) to 54.2% (15 MW), so 50/50 is an average, not a fixed physical ratio.

**Cross-checked monopile foundation data (not used by the code directly, but
useful for validating `size_monopile` outputs against real designs):**

| MW | Water depth (m) | Monopile base D (m) | Embedment (m) | D/t design bounds |
|---|---|---|---|---|
| 5 (OC3 Phase II) | 20 | 6.0 (constant) | 36 | t=60mm constant (D/t=100) |
| 15 (IEA) | not stated in source | 10.0 | 45 | mudline wall thickness ≈50mm, tapering to ≈20-25mm near the tower top — read off Fig. 4-2 of the source report (diameter/thickness-vs-height plot), **image-derived estimate, not a table value** (2026-07-17) |
| 22 (IEA) | 34 | 10.0 (max, bound met) | 45 | 80–160 (optimizer bound; not active at either end in the final design) |

The 22 MW source's D/t design bound (80–160) is why `dt_ratio_max` was
widened from 140 to 160 (2026-07-16) — see §9.

**Natural frequency comparison note (IEA 22 MW, resolved 2026-07-17):** the
source report's Table 13 gives *two* fore-aft first frequencies: 0.22 Hz
"clamped at tower base" (tower alone, treated as rigidly fixed at the
transition piece — excludes monopile+soil flexibility) vs. **0.16 Hz
"clamped at monopile base"** (full system: tower+monopile+soil). This
model's `_natural_frequency` computes the full-system equivalent, so **0.16
Hz is the correct comparison** — confirming the §10 validation (`f0=0.1600
Hz` at the real 22 MW geometry) was already correct.

---

## 3. Extreme mudline loads (`_extreme_loads`)

**Wind (thrust):**
```
lever_arm_m = hub_height_m + water_depth_m
M_thrust = thrust_mn × lever_arm_m
F_thrust = thrust_mn
```
**Assumption:** the extreme thrust load is applied as a single point force at
hub height; no separate blade/nacelle wind drag term.

**Wave + current (Morison drag only, no inertia term):**
```
H_max = 1.9 × Hs                              (design/extreme individual wave height)
omega = 2*pi / Tp
k_wave = omega^2 / g                          (deep-water dispersion relation)
u(z) = (pi * H_max / Tp) * exp(k_wave * z) + current_m_s      for z in [-water_depth, 0]
f(z) = 0.5 * rho_seawater * Cd * D * u(z) * |u(z)|            (Morison drag per unit length)
```
`F_wave = ∫ f(z) dz`, `M_wave = ∫ f(z) × (z + water_depth) dz`, both evaluated
by the **trapezoidal rule with 40 slices** from mudline (`z = -water_depth`)
to still water level (`z = 0`).

**Assumptions:**
- **Drag-only Morison** — the inertia term (`Cm × (π D²/4) × du/dt`) is
  omitted entirely. This is only conservative if drag genuinely dominates at
  the load case considered; for some pile/wave combinations this can
  under-predict the true extreme wave load.
- **Deep-water (Airy) linear wave theory**, evaluated up to still water
  level only — wave crest elevation above MSL is not included in the
  integration (a known non-conservative simplification).
- **Current is depth-uniform** and added linearly to the wave particle
  velocity (no blockage/shielding factor).
- Wind and wave/current mudline moments/shears are combined by **simple
  linear superposition** of characteristic (unfactored) loads; the combined
  `GAMMA_F_ULS = 1.35` factor is applied afterward, only inside `_uls_check`.

---

## 4. Soil stiffness — closed-form Hetenyi solution (`_soil_stiffness`)

Model: a semi-infinite beam on a **homogeneous (constant-with-depth) Winkler
foundation**, loaded at the free end (mudline) by force `P0` and moment `M0`.
Governing ODE `EI·y'''' + k_line·y = 0` has the decaying solution
`y(x) = e^(-βx)(C1 cos βx + C2 sin βx)`. Applying free-end boundary
conditions gives the (self-derived, dimensionally verified) flexibility
relation:
```
y0    = (2*beta/k_line)*P0     + (2*beta^2/k_line)*M0
theta0 = (2*beta^2/k_line)*P0  + (4*beta^3/k_line)*M0
```
Inverting this 2×2 flexibility matrix gives the pile-head stiffness terms
used elsewhere in the code:
```
beta = (k_line / (4*EI))^0.25
K_L  = k_line / beta                  (lateral stiffness, MN/m)
K_R  = k_line / (2*beta^3)            (rocking stiffness, MN*m/rad)
```
(A third term, `K_LM = -k_line/(2*beta^2)`, exists in the same derivation but
is **not used** anywhere in the code — see the natural-frequency
simplification in §7.)

**Idealized homogeneous soil modulus `k_line = k_soil × D`:**
- **Sand**: `k(z) = nh × z` (linear with depth). The code evaluates a single
  representative depth `z_ref = L / 3` (embedded length ÷ 3) — an
  **engineering rule-of-thumb**, not a rigorous equivalent-depth derivation —
  giving `k_soil = nh × (L/3)`.
  `nh` (MN/m⁴) is read off `_SAND_NH_TABLE`, an **approximate API-style
  correlation** vs. submerged friction angle, linearly interpolated:
  | φ (deg) | nh (MN/m⁴) |
  |---|---|
  | 28 | 2.5 |
  | 32 | 7.0 |
  | 36 | 15.0 |
  | 40 | 25.0 |
  (clamped to the table's end values outside 28–40°).
- **Clay**: `k_soil = 0.25 × su_kPa / 1000` (MN/m³) — a **rough
  Terzaghi-style correlation**, constant with depth, not adjusted for strain
  level (ε50) as detailed API/DNV clay p-y curves would be.

**Validity flag:** if `beta × L < 2.5`, the pile is too short/rigid relative
to the soil for the semi-infinite-beam assumption to hold; the code appends
a note to that effect rather than silently returning an unreliable value.

---

## 5. ULS check (`_uls_check`)

```
I        = (pi/64) * (D^4 - (D - 2t)^4)
Z        = I / (D/2)                       (section modulus)
A        = (pi/4) * (D^2 - (D - 2t)^2)
A_shear  = 0.5 * A                          (thin-wall circular tube approximation)

M_uls = GAMMA_F_ULS * M_char
V_uls = GAMMA_F_ULS * V_char

sigma_bending = M_uls / Z
tau_shear     = V_uls / A_shear
sigma_vm      = sqrt(sigma_bending^2 + 3*tau_shear^2)     (von Mises-style combination)

utilization_ULS = sigma_vm / (STEEL_YIELD_MPA / GAMMA_M_ULS)
```
Pass if `utilization_ULS ≤ 1.0`.

**`GAMMA_F_ULS = 1.35` reference:** styled after **DNV-ST-0126 / DNV-OS-J101**
partial load-factor tables for offshore wind support structures, "normal
safety class," ULS combinations. Those standards give *separate* γf values
for permanent/functional loads (~1.1–1.2) vs. environmental (wind+wave) loads
(~1.35) within a load combination; this code collapses that to **one blended
factor applied to the whole combined characteristic load**, rather than
factoring wind and wave (or permanent vs. environmental) contributions
separately. It is not a number any code mandates directly for a "combined
wind+wave" load — it is the engine's own simplification. IEC 61400-3-1's
DLC-dependent partial-factor approach is not followed at all; one blended
factor is applied regardless of which physical load case it represents.

**`sigma_vm` equation reference:** the general **von Mises (Huber–von
Mises–Hencky) yield criterion**, degenerated to a stress state with one
normal component (bending, σ) and one shear component (transverse shear, τ),
with the other in-plane normal stress set to zero:
```
sigma_vM = sqrt(sigma_x^2 - sigma_x*sigma_y + sigma_y^2 + 3*tau_xy^2)   with sigma_y = 0
         = sqrt(sigma_x^2 + 3*tau_xy^2)
```
This is textbook solid mechanics, not specific to one offshore code — API RP
2A-WSD, DNV-RP-C203, and Eurocode 3 all use the same reduction for tubular
member interaction checks. **What this omits:** there is no axial stress
term (self-weight, any pretension) and no hoop/radial stress term (external
hydrostatic pressure on the shell) — both are `sigma_y` contributions a full
check would include. For a large-diameter thin shell at depth, hydrostatic
hoop stress is not necessarily negligible; it is not evaluated anywhere in
this code.

**Buckling is not checked anywhere in this model.** `_uls_check` is a pure
yield check only (`sigma_vm` vs. `STEEL_YIELD_MPA / GAMMA_M_ULS`) — there is
no local shell buckling check (axial/bending-induced, or external
-pressure-induced) and no global (Euler) buckling check. This matters
because the sizing loop (§9) pushes wall thickness toward `dt_ratio_max`
(thinnest allowed wall) whenever ULS/FLS aren't binding, and D/t ratios in
the 80–160 range are squarely in territory where real monopile ULS design is
very often **buckling-governed rather than yield-governed** (the kind of
check DNV-RP-C202 / API RP 2A shell-buckling provisions cover — e.g. WISDEM's
`commonse/utilization_dnvgl.py` `CylinderBuckling` class implements exactly
this). A geometry that passes this engine's yield-only ULS check could still
fail shell buckling in reality; there is no constraint in `size_monopile`
preventing that.

**Investigated 2026-07-17, decided not to implement (concept stage):**
- **Global (Euler) buckling** is rarely the design driver for a monopile —
  the axial load (self-weight of RNA/tower/pile) is tiny relative to the
  elastic critical buckling load of a large-diameter shell, so this check is
  very unlikely to govern over ULS/FLS/NFA/local buckling in practice.
- **Local shell buckling** was checked by hand (DNV-RP-C202 method,
  cross-checked against WISDEM's `utilization_dnvgl.CylinderBuckling`) at
  the 15 MW reference case's converged geometry. Using a single unstiffened
  panel spanning the full 35 m exposed water column gives utilization ≈2.2
  (fails badly), but that panel-length assumption is unrealistic — WISDEM
  itself runs this check per discretized section (a few meters to ~10s of
  meters), not over the whole exposed shaft. At a **10 m** section length
  (a reasonable stand-in for real fabrication/can lengths), utilization
  comes out to **≈1.07** — close to governing, but not by a wide margin.
- **Decision:** do not implement a buckling check in `engine.py` for now.
  At concept stage, wall thickness is a single constant value along the
  whole pile; a real design tapers thickness with depth (thicker at the
  mudline, thinner toward the interface — see the FLS discussion above).
  Since buckling utilization is this sensitive to exactly the parameters
  (thickness distribution, actual section/can length) that concept stage
  hasn't fixed yet, refining a buckling check now would be precision spent
  on a shape that later design stages will change anyway. Revisit once
  the model supports a thickness taper and real section lengths are known.

---

## 6. SLS check (`_sls_check`)

Uses the **same Hetenyi flexibility relation** as §4, evaluated with
**unfactored (characteristic) loads**, per DNV SLS practice:
```
theta0 = (2*beta^2/k_line)*V_char + (4*beta^3/k_line)*M_char     [rad]
theta0_deg = |theta0| in degrees

utilization_SLS = theta0_deg / allowable_sls_rotation_deg   (default 0.50 deg)
```
Pile-head lateral deflection (`y0`) is not computed as a separate SLS
criterion — mudline rotation is treated as the sole governing SLS check, per
the research summary's finding that rotation (not deflection) is the
recognized industry criterion.

---

## 7. Natural frequency / soft-stiff check (`_tower_geometry`, `_natural_frequency`)

**Tower geometry (placeholder, used only for this check):**
```
d_avg_tower = 0.055 * hub_height_m     (if not supplied in DesignInputs)
t_avg_tower = d_avg_tower / 170
```
**Assumption/calibration:** this regression is calibrated to match the
published IEA 15 MW reference tower (base 10.0 m / top 6.5 m → average
8.25 m at 150 m hub height) as the **only** anchor point; it is not
independently validated for other turbine sizes.

**Two-segment cantilever flexibility (fixed 2026-07-16):** the cantilever
from mudline to hub is **not** a single uniform "average tower" section —
it is split at the transition piece into (1) the pile-above-mudline segment,
which uses the **actual pile's own EI** (much stiffer than the tower, since
it's the same large-diameter section as below mudline), and (2) the tower
segment above the transition piece, using the average-tower EI above. The
original single-segment version (`h^3/(3*EI_tower)` over the *whole*
mudline-to-hub span) was found to systematically underpredict `f0` — see §10.
```
pile_above_mudline = water_depth_m + transition_piece_height_m   (transition_piece_height_m
                                                                    is a turbine-library field,
                                                                    see SS2)
h = hub_height_m + water_depth_m                        (unchanged: total mudline-to-hub height)
tower_height = h - pile_above_mudline

I_tower = (pi/64) * (d_avg_tower^4 - (d_avg_tower - 2*t_avg_tower)^4)
EI_tower = STEEL_E_MPA * I_tower
EI_pile  = STEEL_E_MPA * I                              (I = pile second moment of area, SS0/SS5)

# Two-segment cantilever tip flexibility (virtual work, stiff pile segment
# 0..pile_above_mudline, more flexible tower segment pile_above_mudline..h):
cantilever_flexibility = (h^3 - tower_height^3) / (3*EI_pile) + tower_height^3 / (3*EI_tower)

flexibility = cantilever_flexibility + 1/K_L + h^2/K_R
k_eq = 1 / flexibility                          [MN/m]

m_RNA   = 0.5 * total_turbine_mass_t            (assumption: 50/50 RNA/tower split, see SS2)
m_tower = 0.5 * total_turbine_mass_t
m_eff   = (m_RNA + 0.25*m_tower) * 1000          [kg]   (0.25 = standard Rayleigh
                                                          cantilever-with-tip-mass
                                                          effective-mass factor)

f0 = (1/(2*pi)) * sqrt(k_eq_in_N_per_m / m_eff)   [Hz]
```
Still omits the `K_LM` cross-coupling term that Arany's full 3-spring model
includes (a documented simplification, unchanged).

**Soft-stiff target band, with a degenerate-gap fallback (fixed 2026-07-16):**
```
f_1P_max = rpm_max / 60
f_1P_min = rpm_min / 60
f_3P_min = 3 * f_1P_min
f_3P_max = 3 * f_1P_max

band_low  = 1.1 * f_1P_max      (10% margin above top of 1P range)
band_high = 0.9 * f_3P_min      (10% margin below bottom of 3P range)

if band_high <= band_low:
    # Classical soft-stiff gap doesn't exist (wide rotor-speed range: real
    # trend for very large turbines, e.g. IEA 22MW rpm_min/rpm_max = 0.256).
    # Fall back to a lower-bound-only criterion, matching how the IEA 22MW
    # reference design itself is framed (single-sided 0.15 Hz minimum-
    # frequency target, checked only against 1P at rated): use 3P-at-rated
    # as a loose upper ceiling instead of 3P-at-cut-in.
    band_high = 0.9 * f_3P_max
    # -> a note is added to the result explaining the fallback was used.

utilization_NFA:
  if f0 < band_low:   band_low / f0
  elif f0 > band_high: f0 / band_high
  else: max(band_low/f0, f0/band_high)     (both < 1, i.e. "pass with margin")
```
Pass if `utilization_NFA ≤ 1.0`, i.e. `f0` sits inside `[band_low, band_high]`.

**Why the fallback is principled, not arbitrary:** the classical two-sided
"avoid both 1P and 3P across the whole operating rpm range" criterion
requires `3*rpm_min > rpm_max` (with margin) to have any valid solution at
all. This holds for smaller turbines (5–15 MW, `rpm_max/rpm_min` ≈ 1.5–1.8)
but breaks down once that ratio exceeds ~3 (22 MW: ratio 3.9). At that point
the 3P energy at cut-in-region rpm is already *below* the 1P-at-rated
target, so it stops being a meaningful constraint — which is exactly why the
IEA 22 MW report doesn't mention 3P avoidance at all, only a single 0.15 Hz
minimum tied to 1P at rated (§2).

---

## 8. FLS check (`_fls_check`)

**Single equivalent-stress-range Palmgren-Miner check** — explicitly not a
rainflow-counted multi-bin fatigue simulation:
```
sigma_char = M_char / Z                         (characteristic bending stress, same Z as ULS,
                                                  M_char = M_thrust + M_wave from §3)
delta_sigma_eq = FATIGUE_LOAD_FACTOR * sigma_char     (FATIGUE_LOAD_FACTOR = 0.24, ad-hoc)

N_allow = 10 ^ (SN_LOG10_A - SN_M * log10(delta_sigma_eq))

n_cycles = (rpm_avg/60) * seconds_per_year * design_life_years * duty_factor
  where rpm_avg = 0.5*(rpm_min + rpm_max), seconds_per_year = 365.25*24*3600

damage = n_cycles / N_allow
utilization_FLS = damage * FATIGUE_DESIGN_FACTOR     (DFF = 2.0)
```

**`M_char` provenance:** not computed here — it is the same characteristic
(unfactored) mudline moment derived once in `_extreme_loads` (§3) from extreme
wind thrust (point load at hub height) plus Morison drag-only wave/current
load, and passed into ULS, SLS, and FLS alike. FLS reuses the *extreme*
characteristic moment as the base stress from which a fatigue-equivalent
range is estimated — it does not run a separate operational/fatigue load
case.

**Where `N_allow`'s formula comes from vs. where `delta_sigma_eq`'s doesn't:**
- `N_allow = 10^(log10(a) − m·log10(Δσ))` is the standard single-slope S-N
  (Wöhler) curve form from **DNV-RP-C203, "Fatigue design of offshore steel
  structures."** `SN_LOG10_A = 12.16`, `SN_M = 3.0` match a representative
  DNV-RP-C203 basic design S-N curve (in-air, first-segment slope `m=3`,
  valid below the ~10⁷-cycle knee). **Simplification:** only this single
  slope is implemented — the real DNV-RP-C203 curves are bilinear (slope
  changes to `m=5` above ~10⁷ cycles), and one curve is applied structure
  -wide rather than per joint/detail classification.
- `delta_sigma_eq = fatigue_load_factor × sigma_char` has **no standard
  source** — `FATIGUE_LOAD_FACTOR` has been revised twice, neither time from
  first principles:
  - Originally **0.35**: made FLS demand ~2x too much wall thickness (FLS
    utilization of 8.85 at the real IEA 15 MW reference geometry, ~50 mm
    wall at D=10 m).
  - Revised to **0.17** (2026-07-16): back-solved to make FLS utilization
    ≈ 1.0 at that same real reference geometry. This fixed the overshoot but
    introduced a different problem: at this model's own converged 15 MW
    geometry, FLS utilization dropped to 0.324, well *below* ULS (0.352) and
    NFA (0.818) — i.e. **FLS no longer governed**, contradicting both
    industry experience and this project's own research summary, which
    expect FLS to typically be the governing check for monopiles.
  - Revised to **0.24** (2026-07-16): chosen via a sensitivity sweep
    (`FATIGUE_LOAD_FACTOR` = 0.17→0.35, step 0.02, refined to 0.005 near the
    transition) at the 15 MW/35 m/sand reference case. Below ~0.235, the
    geometry doesn't move (NFA governs, wall thickness stays at the
    iteration's 84.8 mm) and FLS utilization scales cleanly as `factor³`
    (consistent with the S-N slope `m=3`). 0.24 is the first value where FLS
    becomes the governing check (utilization 0.911, vs. NFA's 0.818) —
    without requiring any wall-thickness increase from the 0.17 case's own
    geometry. Verified against the 8 MW/clay case (still converges, still
    flags the `beta·L<2.5` soil-validity caveat) and the turbine-library/NFA
    benchmark cases (unaffected, since they don't depend on this constant).

  None of these three values are derived from a specific DLC spectrum,
  wind/rotor-speed distribution, or rainflow-counted time series — **treat
  0.24 as temporary, to be recalibrated once real turbine fatigue load data
  is available**. This remains **the single most influential unvalidated
  number in the fatigue check** — since FLS is frequently the governing
  constraint (see §10), this one placeholder effectively sets the final pile
  sizing in those cases.

Cycle counting assumes one stress cycle per rotor revolution at the average
of `rpm_min`/`rpm_max`, scaled by a `duty_factor` (default 0.9) — real
turbines see a distribution of wind speeds/rotor speeds, not one average
rate.

**`FATIGUE_DESIGN_FACTOR = 2.0` reference:** this is DNV's **Design Fatigue
Factor (DFF)**, per DNV-ST-0126 / DNV-RP-C203, tabulated by structural
element classification (accessibility for inspection/repair × failure
consequence):

| DFF | Typical classification |
|---|---|
| 1 | Accessible, redundant, non-critical |
| **2** | **Accessible for inspection, "normal" component — this code's assumption** |
| 3 | Not accessible/non-inspectable, but not safety-critical |
| 5–10 | Critical, non-redundant, non-accessible (e.g. below-mudline welds) |

The code assumes an above-mudline, inspectable shell joint. A below-mudline
or non-inspectable joint would warrant DFF 5–10 per the DNV table, which
would push `utilization_FLS` well past 1.0 for the same geometry — worth
revisiting given FLS is already often governing.

**Worked example** (15 MW, 35 m depth, sand φ=35°, `size_monopile` converged
geometry with `FATIGUE_LOAD_FACTOR = 0.24`: D=9.33 m, t=84.8 mm, L=46.67 m —
same geometry as the §10 verification run; only the fatigue factor changed,
so ULS/SLS/NFA are unchanged and FLS now governs):

| Quantity | Value |
|---|---|
| `M_char` | 474.7 MN·m |
| `Z` | 5.649 m³ |
| `sigma_char` | 84.05 MPa |
| `delta_sigma_eq` (×0.24) | 20.17 MPa |
| `N_allow` (S-N curve) | 1.76×10⁸ cycles |
| `n_cycles` (27 yr life, rpm_avg=6.28, duty=0.9) | 8.03×10⁷ cycles |
| `damage` | 0.456 |
| `utilization_FLS` (×DFF=2.0) | 0.911 |

---

## 9. Initial guess and iteration loop (`_initial_geometry`, `size_monopile`)

**Initial geometry (rule of thumb, then refined by iteration):**
```
D0 = 7.0 + (11.0 - 7.0) * (turbine_mw - 8.0) / (20.0 - 8.0)   [m]   (linear
     regression between two anchor points: ~7 m at 8 MW, ~11 m at 20 MW —
     not independently validated, chosen to be "close enough" as a starting
     point for iteration)
L0 = 5.0 * D0            (mid of the allowed L/D range, default 3-8)
t0 = D0 / 110.0           (mid of the allowed D/t range, default 80-160)
```

**Step-wise iteration** (step sizes: `d_step = 0.15 m`, `t_step = 0.002 m`),
each iteration re-evaluates all four checks and adjusts **one** dimension
per the following priority:
1. **NFA failing low** (`f0` below the band) → increase `D` (dominant lever
   for both stiffness and frequency, since `EI ∝ D⁴` and `K_L, K_R` both
   grow strongly with `D`).
2. **ULS or FLS failing**, and wall thickness is *not* already at the
   `dt_ratio_min` bound → increase `t`.
3. **ULS, FLS, or SLS failing**, wall thickness *is* capped → increase `D`
   (fallback lever once `t` can't grow further).
4. **NFA failing high** (`f0` above the band, uncommon for monopiles) →
   decrease `D`.

After each adjustment, geometry is clamped to `dt_ratio ∈ [80, 160]` and
`L/D ∈ [3, 8]` (both configurable in `DesignInputs`). `dt_ratio_max` was
widened from 140 to 160 on 2026-07-16 to match the real D/t optimization
bound used in the IEA 22 MW reference monopile design (§2).

**Stopping conditions:** all four utilizations ≤ 1.0 (converged), OR
diameter reaches **3× the initial guess** (runaway guard — appends a
non-convergence note explaining that a check is likely dominated by an
input outside pile geometry, e.g. tower stiffness), OR 500 iterations.

**Post-convergence thickness shrink (added 2026-07-16):** the growth loop
above is **one-directional** — it only ever adds material and stops at the
first geometry that passes, starting from `t0 = D0/110`. If that initial
guess already satisfies every check (common whenever ULS/FLS have
comfortable margin at the D/t midpoint), the loop runs **zero** iterations
and reports `t0` as "the" answer, regardless of how much thinner a wall
could also pass. Once the growth loop converges, `size_monopile` now steps
wall thickness back **down** by `t_step` — re-evaluating all four checks
each step — until either a step would fail a check (keep the last passing
thickness) or the `dt_ratio_max` floor is reached. This finds the true
minimum-material wall thickness rather than just the first one the growth
loop happened to land on. **Diameter is deliberately not shrunk** by this
step — it also feeds the extreme-load calculation and NFA, and NFA is still
pending its own verification (see `docs/methodology.md`), so widening the
shrink logic to diameter is left for later. This changed the converged wall
thickness for **every** verification case in §10, not just the ones where
FLS governs — see the updated table there.

---

## 10. Verification performed

Cases were run against `size_monopile` and `evaluate_monopile` as sanity
checks (not a unit test suite). Numbers below reflect the current model:
`FATIGUE_LOAD_FACTOR = 0.176` (§8), the post-convergence thickness-shrink
step (§9), and the two-segment cantilever + degenerate-gap NFA fallback
(§7) — all updated 2026-07-16, see `docs/methodology.md`. `test_engine.py`
at the repo root reproduces all of these as runnable checks.

| Case | Result | Governing check | Notes |
|---|---|---|---|
| 15 MW, 35 m depth, sand (φ=35°) | D=9.33 m, t=60.8 mm, L=46.67 m (L/D≈5.0) | **FLS** (margin 0.048) | Wall thickness now close to the real IEA 15 MW reference (~55 mm) rather than the pre-shrink 84.8 mm; FLS governing matches industry expectation and this project's research summary |
| 20 MW, 45 m depth, sand (φ=38°) | D=11.0 m, t=68.8 mm, L=55 m (L/D=5.0) | **NFA** (margin 0.166) | Thickness dropped from a pre-shrink 100.0 mm to the true minimum once ULS/FLS/SLS all had margin to spare |
| 5 MW, 20 m depth, sand (φ=36°) | D=6.00 m, t=37.5 mm, L=30.0 m (L/D=5.0) | **NFA** (margin 0.043) | Diameter still matches the real OC3 monopile (6 m); thickness now well below the real 60 mm — NFA is the binding constraint, not FLS/ULS, at this size |
| 22 MW, 34 m depth, sand (φ=36°) | D=11.67 m, t=72.9 mm, L=58.3 m (L/D=5.0) | **NFA** (margin 0.216) | Real IEA 22MW design caps diameter at 10 m (an explicit optimizer bound not replicated here); thickness dropped from a pre-shrink 106.1 mm |
| 8 MW, 25 m depth, clay (su=80 kPa) | D=8.20 m, t=61.6 mm, L=35.0 m (L/D≈4.3) | **NFA** (margin 0.002) | Also flags `beta*L < 2.5` — the closed-form soil assumption is genuinely at the edge of its valid range for this combination; correctly flagged rather than silently ignored. NFA margin is now razor-thin (0.002) — see the open-questions note on NFA below |

**The thickness-shrink step (§9) changed every case above**, not just the
one where FLS governs — every case was previously stuck at an
over-conservative initial-guess thickness that the grow-only loop never
questioned. A consequence worth flagging: with thinner walls now the norm,
**NFA sits close to its 1.0 limit in four of the five cases** (margins
0.166, 0.043, 0.216, and especially 0.002 for the 8 MW/clay case) — where
before, thicker walls gave NFA more incidental headroom. Since NFA is
explicitly not yet verified (open question below), the model's overall
reliability is now more exposed to whatever that verification finds than it
was before this change.

Two bugs were found and fixed during verification, both while testing the
newly-sourced 5 MW/OC3 and 22 MW/IEA turbines (§2) against their *real*
reference monopile geometries — neither was visible when the model had only
ever been checked against 15/20 MW:

1. **Tower-geometry miscalibration** (found earlier, already noted above):
   the original `_tower_geometry` regression (`4.0 + 0.01×hub_height`)
   under-estimated tower stiffness so severely that tower flexibility
   dominated >95% of total system flexibility — the iteration loop grew the
   pile diameter to 84 m chasing an unreachable frequency target. Fixed by
   recalibrating against the published IEA 15 MW tower geometry.
2. **Two-segment cantilever + degenerate-gap fallback** (found and fixed
   2026-07-16): evaluating `evaluate_monopile` at the *real* 5 MW/OC3
   geometry (D=6 m, t=60 mm, L=36 m) gave `f0 = 0.191 Hz`, below its own
   target band `[0.222, 0.31] Hz`; at the *real* 22 MW/IEA geometry (D=10 m,
   t=100 mm, L=45 m) the target band itself came out **inverted**
   (`band_low = 0.1295 > band_high = 0.0813`). Root cause for both: the
   single-segment cantilever formula lumped the much stiffer pile-above
   -mudline length in with the tower's (much more flexible) average EI over
   the *whole* mudline-to-hub span, underpredicting stiffness/frequency; and
   the classical 1P/3P gap formula doesn't handle turbines whose rotor
   -speed range is wide enough that `3×rpm_min < 1.1×rpm_max` (real for very
   large turbines — the IEA 22 MW report itself only targets a single-sided
   minimum frequency, not a two-sided gap, for exactly this reason). Fixed
   by splitting the cantilever into a pile-above-mudline segment (real pile
   EI) plus a tower segment (average-tower EI) per §7, and adding a fallback
   band definition when the classical gap is degenerate. **Result:** the 22
   MW case now predicts `f0 = 0.1600 Hz`, matching the report's own stated
   achieved value (~0.16 Hz) to 3 significant figures; the 5 MW case now
   falls inside its band; and the previously-non-converging 8 MW/clay case
   now converges too, as a side effect of the same fix.

Both bugs were caught because `size_monopile` failed to converge and
flagged it rather than silently returning a plausible-looking wrong answer
— see the non-convergence note in §9. The NFA formula itself (§7) has been
checked against real f0 values at four real turbine sizes (5/15/20/22 MW),
but **the NFA check as a whole is explicitly not yet considered verified**
by the user (2026-07-16) pending further review — separate from whether its
frequency prediction matches published values, open questions remain about
whether it's the right check to be governing designs at all. This matters
more now than before the thickness-shrink step (§9): NFA margins are razor
-thin in several cases in the table above (as low as 0.002), so any
correction to NFA found during that later verification could materially
change several of these converged designs. The 25 MW extrapolated turbine
entry (§2) remains unverified for a separate reason, since it isn't a real
reference turbine.

---

## 11. Full list of unvalidated / placeholder assumptions

For quick scanning — every number below is a concept-stage judgment call,
not a value taken from a specific project-specific input or validated
source, and is a candidate for review before results are used beyond
early screening:

1. `GAMMA_F_ULS = 1.35` as a single blended wind+wave load factor.
2. `thrust_mn` in `TURBINE_LIBRARY` used directly as extreme ULS thrust (no separate extreme-event multiplier); the 5/10 MW entries' thrust values are literature estimates, not from the sourced reports directly (§2).
3. The 25 MW `TURBINE_LIBRARY` entry is a linear extrapolation of the 15→22 MW trend, not a verified reference turbine (§2).
4. Morison **drag-only** wave load (no inertia term); integration capped at still-water level (no crest elevation).
5. Current assumed depth-uniform, linearly superposed on wave velocity.
6. Sand `nh` vs. friction-angle correlation table (4 points, linearly interpolated).
7. Sand equivalent depth `z_ref = L/3` for a linearly-varying subgrade modulus.
8. Clay `k_soil = 0.25 × su` correlation (no ε50/strain-level adjustment).
9. SLS governed by rotation only (no deflection limit checked).
10. Tower average diameter/thickness regressed from hub height alone, calibrated to one data point (IEA 15 MW) — now used only for the tower segment above the transition piece (§7), which reduced its impact on the overall result, but the regression itself is still single-point-calibrated.
11. RNA/tower mass split assumed 50/50 of total turbine mass (updated 2026-07-16 from a 40/60 guess) — real observed range is 43.6%–54.2% across the four sourced turbines.
12. Rayleigh effective-mass factor of 0.25 for the tower's tip-mass contribution.
13. Natural-frequency model omits the `K_LM` foundation cross-coupling term. The band-inversion bug for wide-rotor-speed-range turbines (e.g. 22 MW) was found and fixed 2026-07-16 with a documented fallback (§7) — validated against 5/15/20/22 MW; the 25 MW extrapolated entry is unverified.
14. Fatigue `FATIGUE_LOAD_FACTOR = 0.176` (ratio of fatigue-driving stress range to extreme characteristic stress) — revised 2026-07-16, chosen via a sensitivity sweep (excluding NFA from the target) to put the 15 MW reference case's true-minimum wall thickness at ≈60 mm, close to the real IEA 15 MW reference (~55 mm); still an ad-hoc placeholder pending recalibration against real turbine fatigue load data, and the single most influential unvalidated FLS number.
15. Fatigue cycle count uses one cycle per rotor revolution at the min/max rpm average, not a wind-speed distribution.
16. Single DNV-RP-C203-style S-N curve (`log10(a)=12.16`, `m=3`) applied structure-wide, not joint-specific.
17. `USD_PER_T_STEEL = 2200` — a placeholder, not sourced from a specific quote.
18. **No buckling check anywhere** — `_uls_check` is yield-only (von Mises vs. `STEEL_YIELD_MPA/GAMMA_M_ULS`); no local shell buckling or global Euler buckling is evaluated. Investigated 2026-07-17 (see §5): global buckling is very unlikely to govern (axial load tiny vs. elastic critical load); local shell buckling utilization is ≈1.07 at a realistic 10 m section length, close to governing but not decisively — deliberately not implemented at concept stage, since wall thickness here is a single constant value and a real design would taper it, making detailed buckling optimization now premature.
19. `sigma_vm` in `_uls_check` omits axial stress (self-weight/pretension) and hoop/radial stress (external hydrostatic pressure) — only bending + shear are combined (§5).
20. The post-convergence thickness-shrink step (§9, added 2026-07-16) only shrinks wall thickness, not diameter — a design could still be carrying more diameter than strictly necessary if diameter, not thickness, is what's over-conservative for a given case. NFA is explicitly excluded from driving any shrink, pending its own verification (see §10).

Items 6–13 (soil and natural-frequency modeling) are the ones most likely to
materially shift results if refined with real project data — see §4/§7 and
the bugs described in §10. **Item 18 (no buckling check) is a structural gap,
not just an unvalidated number** — it means a converged design could be
unsafe in a way none of the four implemented checks would catch. **NFA's own
verification status (§10) is now higher-stakes than before item 14's fix**,
since several converged designs sit within a hair of their NFA limit.
