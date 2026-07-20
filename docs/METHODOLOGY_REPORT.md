# Monopile Concept Design Engine — Methodology Report

`engine.py` v0.1. This report documents every equation, constant, and assumption
in the code as-implemented, so there is no ambiguity between this document and
the source. Section numbers reference the corresponding function in
`engine.py`. Concept-level screening only — not certification or FEED design.

This report covers current method descriptions only. For the dated history
of how each choice was reached (sensitivity sweeps, bugs found and fixed,
superseded calibrations), see `method_update_log.md`.

---

## 0. Process overview

`size_monopile(inputs)` runs an Arany-et-al.-style ("10-step") iteration:

1. Look up/interpolate turbine properties from `TURBINE_LIBRARY` (§2).
2. Guess an initial geometry from rules of thumb (§9).
3. Evaluate the candidate geometry (`evaluate_monopile`):
   a. Compute mudline extreme moment/shear from wind + wave/current (§3).
   b. Compute closed-form soil stiffness (K_L, K_R) (§4).
   c. Run ULS (§5), SLS (§6), natural-frequency/soft-stiff (§7), FLS (§8),
      and local shell buckling (§5a) checks, each returning a utilization
      ratio (pass if ≤ 1.0).
   d. Compute steel mass/cost and collect validity-range notes.
4. If all five utilizations are ≤ 1.0, stop (converged).
5. Otherwise, adjust diameter or wall thickness per the step-wise rule in §9
   and go back to 3. (Embedded length is *not* an independently-adjusted
   lever here — see the embedment note in §9.)
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

**Local shell buckling (§5a)**
| Symbol | Meaning | Units |
|---|---|---|
| `l_panel` | unsupported panel length (exposed above-mudline shaft, no ring stiffeners assumed) | m |
| `Z_batdorf` | Batdorf shell parameter | – |
| `C_axial_bending`, `C_torsion`, `C_lateral` | DNV-RP-C202 buckling coefficients | – |
| `fea`, `fet`, `feh` | elastic buckling capacities (axial/bending, shear, hoop) | MPa |
| `sigma_axial` | axial compressive stress from self-weight (`axial_load_estimate / A`) | MPa |
| `sigma_hoop` | external hydrostatic hoop stress, `p×r/t` | MPa |
| `lambda_s` | reduced shell slenderness | – |
| `gamma_m` | slenderness-dependent material factor | – |
| `fks`, `fksd` | characteristic / design buckling resistance | MPa |
| `utilization_Buckling` | buckling utilization ratio (pass if ≤ 1.0) | – |

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
| `h` | total cantilever height, mudline to hub, `hub_height_m + water_depth_m` | m |
| `tower_height` | height of the (more flexible) tower segment above the transition piece, `h - pile_above_mudline` | m |
| `cantilever_flexibility` | two-segment tip flexibility of the pile-above-mudline + tower cantilever | m/MN |
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
| `fatigue_load_factor` | assumed ratio converting `sigma_char` to a fatigue-equivalent stress range (`FATIGUE_LOAD_FACTOR` = 0.35) | – |
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
| `STEEL_POISSON_RATIO` | 0.3 | steel Poisson's ratio — used only by the shell buckling check (§5a) |
| `STEEL_YIELD_MPA` | 355 MPa | S355 offshore structural steel |
| `USD_PER_T_STEEL` | 2,200 USD/t | rolled/welded monopile steel, concept-stage placeholder cost |
| `GAMMA_F_ULS` | 1.35 | combined wind+wave load factor — a single blended DNV "normal safety class" factor, not separate per-load-type factors |
| `GAMMA_M_ULS` | 1.1 | DNV-ST-0126 material resistance factor |
| `MORISON_CD` | 0.65 | drag coefficient, smooth circular cylinder, high Reynolds number |
| `SN_LOG10_A` | 12.16 | DNV-RP-C203 basic design S-N curve intercept (in-air, single-slope segment, `m=3`) — one representative curve used for the whole structure, not joint-specific |
| `SN_M` | 3.0 | S-N curve slope (first segment only, per DNV-RP-C203) |
| `FATIGUE_DESIGN_FACTOR` | 2.0 | DNV-ST-0126/DNV-RP-C203 Design Fatigue Factor (DFF), typical accessible/inspectable monopile joint — see DFF table in §8 |
| `FATIGUE_LOAD_FACTOR` | 0.35 | ratio converting characteristic bending stress to a fatigue-equivalent stress range — ad-hoc, chosen empirically (see §8 and `method_update_log.md`) |

---

## 2. Turbine library (`TURBINE_LIBRARY`, `turbine_from_capacity`)

Five reference points (5/10/15/22/25 MW), each with `rotor_diameter_m`,
`hub_height_m`, `mass_t`, `thrust_mn`, `rpm_min`, `rpm_max`,
`transition_piece_height_m`. `turbine_from_capacity(mw)` **linearly
interpolates** between the two bracketing entries (or clamps to the nearest
end point outside 5–25 MW).

**Sourced anchors:**

| MW | Source | Rotor D (m) | Hub height (m) | RNA (t) | Tower (t) | Total mass (t) | Thrust (MN) | rpm min/max | Transition height (m) |
|---|---|---|---|---|---|---|---|---|---|
| 5 | OC3/NREL 5-MW, Phase II monopile (NREL/TP-500-48191) | 126.0 | 90.0 | 350.0 (Rotor 110 + Nacelle 240) | 347.5 | 697.5 | 0.80* | 6.90 / 12.10 | 10.0 |
| 10 | DTU 10-MW RWT (Bak et al. 2013) | 178.3 | 119.0 | 675.0 (Rotor 229 + Nacelle 446) | 605.0 | 1280.0 | 1.50* | 6.00 / 9.60 | 15.0† |
| 15 | IEA Wind 15-MW RWT (NREL/TP-5000-75698), Table ES-1 | 240.0 | 150.0 | 1017.0 | 860.0 | 1877.0 | 2.50 | 5.00 / 7.56 | 15.0 |
| 22 | IEA 22-MW RWT (DTU Wind E-0243), Table 1/2 | 284.0 | 170.0 | 1215.6 | 1574.0 | 2789.6 | 2.793 | 1.807 / 7.061 | 15.0 |
| 25 | **extrapolated**, not a real reference turbine | 303.0 | 179.0 | — | — | 3181.0 | 2.92 | 0.44 / 6.85 | 15.0† |

\* Thrust not tabulated in the 5/10 MW source documents; these are commonly
cited literature values (Jonkman et al. 2009 for 5 MW; Bak et al. 2013 for
10 MW), not independently re-derived the way the 15 MW value was. The 15 MW
thrust (2.50 MN) was cross-checked by computing
`0.5 × ρ_air × A × U_rated² × C_T` using the report's stated design-point
`C_T = 0.804` at rated wind speed 10.59 m/s — matches the library value to 3
significant figures.

† Assumed (not stated in the source document), equal to the more common 15m
value from the sourced entries.

**25 MW row is a linear extrapolation** of the 15→22 MW trend for each
column, **not** verified against any real 25 MW reference document. The
`rpm_min` trend is steep in the real data (5.00 → 1.807 rpm from 15 to
22 MW) — extrapolating it further to 0.44 rpm is the single least-certain
number in the table.

**Assumptions baked into the library data:**
- `mass_t` is **total turbine mass (RNA + tower combined)**, not RNA alone.
- `thrust_mn` is used directly as the **extreme/ultimate ULS design thrust**
  (not the rated/operational thrust) — no additional extreme-load multiplier
  is applied elsewhere in the code.
- RNA/tower mass split (used only in §7's natural-frequency check) is
  **50/50** — the real RNA fraction observed across the four sourced
  turbines ranges from 43.6% (22 MW) to 54.2% (15 MW), so 50/50 is an
  average, not a fixed physical ratio.

**Cross-checked monopile foundation data** (not used by the code directly,
but useful for validating `size_monopile` outputs against real designs):

| MW | Water depth (m) | Monopile base D (m) | Embedment (m) | D/t |
|---|---|---|---|---|
| 5 (OC3 Phase II) | 20 | 6.0 (constant) | 36 | t=60mm constant (D/t=100) |
| 15 (IEA) | not stated in source | 10.0 | 45 | mudline thickness not table-sourced; an earlier image-derived estimate from the report's diameter/thickness chart (~50mm, D/t≈200) is doubted — this engine's own converged design at D/t≈93-99 matches the pattern of the two sourced references (below) much more closely |
| 22 (IEA) | 34 | 10.0 (max, bound met) | 45 | 80–160 (optimizer bound; not active at either end in the real design) |

The 22 MW source's D/t design bound (80–160) is why `dt_ratio_max` in
`DesignInputs` defaults to 160.

**Natural frequency comparison (IEA 22 MW):** the source report's Table 13
gives *two* fore-aft first frequencies: 0.22 Hz "clamped at tower base"
(tower alone, rigidly fixed at the transition piece — excludes
monopile+soil flexibility) vs. **0.16 Hz "clamped at monopile base"** (full
system: tower+monopile+soil). `_natural_frequency` computes the full-system
equivalent, so **0.16 Hz is the correct comparison** (§10).

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

**`H_max = 1.9 × Hs` basis:** the commonly-used rule of thumb for the most
probable maximum individual wave height in a several-hour storm sea state,
from Rayleigh wave-height statistics: `H_max/Hs ≈ sqrt(0.5 × ln(N))` for `N`
waves in the storm duration (`N≈1000-1100` for a 3-hour storm at a typical
~10s mean period gives ≈1.86-1.9). This type of relation is standard content
in **DNV-RP-C205** ("Environmental Conditions and Environmental Loads"),
though the exact value has not been independently verified against that
document in this project — treat the 1.9 factor itself as unverified, and
note it doesn't adapt to the site's actual storm duration/mean period (`N`
is implicitly fixed, not derived from `Tp`).

**Other assumptions:**
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
  `GAMMA_F_ULS = 1.35` factor is applied afterward, only inside `_uls_check`
  (and `_shell_buckling_check`, §5a).

---

## 4. Soil stiffness — closed-form Hetenyi solution (`_soil_stiffness`)

Model: a semi-infinite beam on a **homogeneous (constant-with-depth) Winkler
foundation**, loaded at the free end (mudline) by force `P0` and moment `M0`.
Governing ODE `EI·y'''' + k_line·y = 0` has the decaying solution
`y(x) = e^(-βx)(C1 cos βx + C2 sin βx)`. Applying free-end boundary
conditions gives the flexibility relation:
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
  engineering rule-of-thumb, not a rigorous equivalent-depth derivation —
  giving `k_soil = nh × (L/3)`.
  `nh` (MN/m⁴) is read off `_SAND_NH_TABLE`, an approximate API-style
  correlation vs. submerged friction angle, linearly interpolated:
  | φ (deg) | nh (MN/m⁴) |
  |---|---|
  | 28 | 2.5 |
  | 32 | 7.0 |
  | 36 | 15.0 |
  | 40 | 25.0 |
  (clamped to the table's end values outside 28–40°).
- **Clay**: `k_soil = 0.25 × su_kPa / 1000` (MN/m³) — a rough Terzaghi-style
  correlation, constant with depth, not adjusted for strain level (ε50) as
  detailed API/DNV clay p-y curves would be. `su_kPa` is
  `SoilProfile.undrained_shear_strength_kpa`, **default 75 kPa** — a plain
  user input from site investigation (triaxial/vane shear tests), not
  derived by the code.

**Validity flag:** if `beta × L < 2.5`, the pile is too short/rigid relative
to the soil for the semi-infinite-beam assumption to hold; the code appends
a note to that effect rather than silently returning an unreliable value.
`2.5` is a commonly-used rule-of-thumb in beam-on-elastic-foundation
literature (Hetenyi's original 1946 text, and texts such as Poulos & Davis,
discuss "long/flexible" pile behavior once `beta×L` exceeds some threshold),
but different sources use different cutoffs in roughly the 2–4 range (e.g.
`π≈3.14` is also commonly cited) — treat as indicative, not a precise
code-mandated limit.

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

**`GAMMA_F_ULS = 1.35`:** styled after **DNV-ST-0126 / DNV-OS-J101**
partial load-factor tables for offshore wind support structures, "normal
safety class," ULS combinations. Those standards give *separate* γf values
for permanent/functional loads (~1.1–1.2) vs. environmental (wind+wave) loads
(~1.35) within a load combination; this code collapses that to **one blended
factor applied to the whole combined characteristic load**, rather than
factoring wind and wave (or permanent vs. environmental) contributions
separately. IEC 61400-3-1's DLC-dependent partial-factor approach is not
followed at all; one blended factor is applied regardless of which physical
load case it represents.

**`sigma_vm` equation:** the general **von Mises (Huber–von Mises–Hencky)
yield criterion**, degenerated to a stress state with one normal component
(bending, σ) and one shear component (transverse shear, τ), with the other
in-plane normal stress set to zero:
```
sigma_vM = sqrt(sigma_x^2 - sigma_x*sigma_y + sigma_y^2 + 3*tau_xy^2)   with sigma_y = 0
         = sqrt(sigma_x^2 + 3*tau_xy^2)
```
This is textbook solid mechanics, not specific to one offshore code — API RP
2A-WSD, DNV-RP-C203, and Eurocode 3 all use the same reduction for tubular
member interaction checks. **What this omits:** there is no axial stress
term (self-weight, any pretension) and no hoop/radial stress term (external
hydrostatic pressure on the shell) — both are `sigma_y` contributions a full
check would include.

`_uls_check` is a **pure yield check only**. Shell buckling (axial/bending
-induced, or external-pressure-induced) is evaluated separately, in §5a.
Global (Euler) column buckling is not evaluated at all (see §5a).

---

## 5a. Local shell buckling check (`_shell_buckling_check`)

**Method — DNV-RP-C202, unstiffened cylinder:**
```
Z_batdorf = (l_panel^2 / (r*t)) * sqrt(1 - nu^2)          (nu = 0.3, steel)

C_axial_bending = psi*sqrt(1+(rho*xi/psi)^2)   psi=1,    xi=0.702*Z_batdorf,      rho=0.5*(1+r/(150t))^-0.5
C_torsion       = psi*sqrt(1+(rho*xi/psi)^2)   psi=5.34, xi=0.856*Z_batdorf^0.75, rho=0.6
C_lateral       = psi*sqrt(1+(rho*xi/psi)^2)   psi=4,    xi=1.04*sqrt(Z_batdorf), rho=0.6

fE(C) = (C * pi^2 * E) / (12*(1-nu^2)) * (t/l_panel)^2
fea = fE(C_axial_bending)   fet = fE(C_torsion)   feh = fE(C_lateral)

sigma_bending = M_uls/Z_sec            (M_uls = GAMMA_F_ULS * M_char, same as ULS)
sigma_axial   = axial_load_estimate/A  (RNA+tower weight + pile self-weight -- see below)
tau_shear     = V_uls/(0.5*A)
sigma_hoop    = (rho_seawater*g*water_depth)*r/t   (external hydrostatic pressure)

# DNV convention: only the compressive part of each stress counts.
axial = |min(-(sigma_axial+sigma_bending), 0)|
hoop  = |min(-sigma_hoop, 0)|
shear = |tau_shear|
sigma_vM = sqrt(((axial+hoop)/2)^2 + 3*(((axial-hoop)/2)^2 + shear^2))

lambda_s = sqrt((fy/sigma_vM) * (axial/fea + shear/fet + hoop/feh))
gamma_m  = 1.15 if lambda_s<0.5; 1.45 if lambda_s>=1.0; else 0.85+0.6*lambda_s
fks      = fy / sqrt(1+lambda_s^4)
fksd     = fks/gamma_m

utilization_Buckling = sigma_vM / fksd
```
Cross-checked against WISDEM's open-source DNV-RP-C202 implementation
(`wisdem/commonse/utilization_dnvgl.py`, `CylinderBuckling` class) for the
same coefficient formulas. See `docs/misc/local_shell_buckling_method.md`
for the full derivation.

**`l_panel` = the exposed above-mudline shaft length**
(`water_depth_m + transition_piece_height_m`), **not** can length. This is a
deliberate modeling choice: `l_panel` in DNV-RP-C202 means the spacing
between **ring stiffeners** specifically — dedicated structural elements
that resist the ovalization/buckling mode — not the spacing between
fabrication can-to-can weld seams, which don't provide the same restraint.
This model assumes no ring stiffeners exist anywhere on the pile, so the
unsupported length is the full exposed shaft; the embedded portion is
excluded because soil continuously restrains it there.

**`axial_load_estimate` (`_axial_load_estimate`):** a rough self-weight
figure — RNA+tower mass from `TURBINE_LIBRARY` plus the pile's own steel
weight above mudline, times gravity. Used only by this check; ULS/SLS/FLS
don't need it, since they only combine bending and shear from the extreme
lateral load.

**Global (Euler) column buckling is not implemented** — axial load is small
relative to the elastic critical buckling load of a large-diameter shell,
making it unlikely to govern for this structure type.

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
criterion — mudline rotation is treated as the sole governing SLS check,
matching the recognized industry criterion for monopiles.

---

## 7. Natural frequency / soft-stiff check (`_tower_geometry`, `_natural_frequency`)

**Tower geometry (placeholder, used only for this check):**
```
d_avg_tower = 0.055 * hub_height_m     (if not supplied in DesignInputs)
t_avg_tower = d_avg_tower / 170
```
Calibrated against the published IEA 15 MW reference tower (base 10.0 m /
top 6.5 m → average 8.25 m, at 150 m hub height) as the only anchor point;
not independently validated for other turbine sizes.

**Two-segment cantilever flexibility:** the cantilever from mudline to hub
is split at the transition piece into (1) the pile-above-mudline segment,
using the **actual pile's own EI** (much stiffer than the tower, since it's
the same large-diameter section as below mudline), and (2) the tower
segment above the transition piece, using the average-tower EI:
```
pile_above_mudline = water_depth_m + transition_piece_height_m   (transition_piece_height_m
                                                                    is a turbine-library field,
                                                                    see §2)
h = hub_height_m + water_depth_m                        (total mudline-to-hub height)
tower_height = h - pile_above_mudline

I_tower = (pi/64) * (d_avg_tower^4 - (d_avg_tower - 2*t_avg_tower)^4)
EI_tower = STEEL_E_MPA * I_tower
EI_pile  = STEEL_E_MPA * I                              (I = pile second moment of area, §0/§5)

# Two-segment cantilever tip flexibility (virtual work, stiff pile segment
# 0..pile_above_mudline, more flexible tower segment pile_above_mudline..h):
cantilever_flexibility = (h^3 - tower_height^3) / (3*EI_pile) + tower_height^3 / (3*EI_tower)

flexibility = cantilever_flexibility + 1/K_L + h^2/K_R
k_eq = 1 / flexibility                          [MN/m]

m_RNA   = 0.5 * total_turbine_mass_t            (assumption: 50/50 RNA/tower split, see §2)
m_tower = 0.5 * total_turbine_mass_t
m_eff   = (m_RNA + 0.25*m_tower) * 1000          [kg]   (0.25 = standard Rayleigh
                                                          cantilever-with-tip-mass
                                                          effective-mass factor)

f0 = (1/(2*pi)) * sqrt(k_eq_in_N_per_m / m_eff)   [Hz]
```

**Reference and derivation.** This flexibility-superposition approach —
including the two-segment split, but not the omitted `K_LM` term — is the
standard simplified natural-frequency method from **Arany et al. (2017)**,
the same "10-step" paper cited as this engine's primary methodology
reference (this check *is* step 7 of that method). Related earlier work by
Arany, Bhattacharya, Adhikari & Hogan on OWT natural frequency via
foundation flexibility uses the same approach.

`flexibility` is deflection-per-unit-force (the reciprocal of stiffness). It
adds across elements connected **in series along the same load path** — the
same principle as electrical resistances in series, or springs stacked
end-to-end (`1/k_total = 1/k1 + 1/k2`).

**`h^3/(3*EI)`:** the classical Euler-Bernoulli cantilever tip-deflection
formula for a uniform beam fixed at one end, free at the other, under a
point force at the tip (`delta = F*h^3/(3EI)`) — standard textbook
structural mechanics (Timoshenko, Hibbeler, or *Roark's Formulas for Stress
and Strain*), not offshore-wind-specific.

**Why the two-segment `cantilever_flexibility` splits additively (exact, not
approximate):** for a cantilever of total height `h` under a tip force `F`,
the bending moment at any section a distance `z` from the base is
`M(z) = F*(h-z)` — identical form whether `z` is in the pile segment or the
tower segment, since it only depends on distance to the tip. The unit-load
(virtual work / Castigliano) method gives:
```
flexibility = integral from 0 to h of (h-z)^2 / EI(z) dz
```
Splitting this integral at the segment boundary (`z = pile_above_mudline`,
where `tower_height = h - pile_above_mudline`) and evaluating each piece:
```
integral from 0 to pile_above_mudline of (h-z)^2/EI_pile dz   =  (h^3 - tower_height^3) / (3*EI_pile)
integral from pile_above_mudline to h of (h-z)^2/EI_tower dz  =  tower_height^3 / (3*EI_tower)
```
Adding them gives exactly the `cantilever_flexibility` line above — the
additive form is a genuine closed-form result of linear beam theory for a
stepped-EI cantilever under a tip load, not a simplifying assumption.

**Why `1/K_L` and `h^2/K_R` extend the same series-flexibility principle:**
- `1/K_L`: pure lateral translation of the pile head. `K_L` is *defined* as
  force/displacement, so its reciprocal is displacement-per-force directly.
- `h^2/K_R`: base **rotation** propagated up to the tip. A lateral force `F`
  at height `h` creates an overturning moment `M = F*h` at the base, causing
  a base rotation `theta = M/K_R = F*h/K_R`. Propagated rigidly up through
  height `h` (small-angle assumption), that rotation adds an *extra* tip
  deflection `y = theta*h = F*h^2/K_R`. Dividing by `F` gives the flexibility
  contribution `h^2/K_R`.

All three terms represent the same tip force flowing through three things in
series — cantilever bending, foundation translation, foundation rocking —
so by the superposition principle (valid for any linear elastic system)
their flexibilities simply add.

Still omits the `K_LM` cross-coupling term that Arany's full 3-spring model
includes (a documented simplification).

**Soft-stiff target band, with a degenerate-gap fallback:**
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
delta_sigma_eq = FATIGUE_LOAD_FACTOR * sigma_char     (FATIGUE_LOAD_FACTOR = 0.35, ad-hoc)

N_allow = 10 ^ (SN_LOG10_A - SN_M * log10(delta_sigma_eq))

n_cycles = (rpm_avg/60) * seconds_per_year * design_life_years * duty_factor
  where rpm_avg = 0.5*(rpm_min + rpm_max), seconds_per_year = 365.25*24*3600

damage = n_cycles / N_allow
utilization_FLS = damage * FATIGUE_DESIGN_FACTOR     (DFF = 2.0)
```

**`M_char` provenance:** the same characteristic (unfactored) mudline moment
derived once in `_extreme_loads` (§3), passed into ULS, SLS, and FLS alike.
FLS reuses the *extreme* characteristic moment as the base stress from which
a fatigue-equivalent range is estimated — it does not run a separate
operational/fatigue load case.

**`N_allow`:** the standard single-slope S-N (Wöhler) curve form from
**DNV-RP-C203, "Fatigue design of offshore steel structures."**
`SN_LOG10_A = 12.16`, `SN_M = 3.0` match a representative DNV-RP-C203 basic
design S-N curve (in-air, first-segment slope `m=3`, valid below the
~10⁷-cycle knee). Only this single slope is implemented — the real
DNV-RP-C203 curves are bilinear (slope changes to `m=5` above ~10⁷ cycles),
and one curve is applied structure-wide rather than per joint/detail
classification.

**`delta_sigma_eq = fatigue_load_factor × sigma_char` has no standard
source.** `FATIGUE_LOAD_FACTOR = 0.35` is an ad-hoc value, chosen
empirically via a sensitivity sweep (not derived from a DLC spectrum,
wind/rotor-speed distribution, or rainflow-counted time series) — see
`method_update_log.md` for the calibration history. **Treat it as temporary,
to be recalibrated once real turbine fatigue load data is available.** This
remains the single most influential unvalidated number in the fatigue check
whenever FLS governs (currently 5/15 MW; 22 MW is buckling-governed — §10).

Cycle counting assumes one stress cycle per rotor revolution at the average
of `rpm_min`/`rpm_max`, scaled by a `duty_factor` (default 0.9) — real
turbines see a distribution of wind speeds/rotor speeds, not one average
rate.

**`FATIGUE_DESIGN_FACTOR = 2.0`:** this is DNV's **Design Fatigue Factor
(DFF)**, per DNV-ST-0126 / DNV-RP-C203, tabulated by structural element
classification (accessibility for inspection/repair × failure consequence):

| DFF | Typical classification |
|---|---|
| 1 | Accessible, redundant, non-critical |
| **2** | **Accessible for inspection, "normal" component — this code's assumption** |
| 3 | Not accessible/non-inspectable, but not safety-critical |
| 5–10 | Critical, non-redundant, non-accessible (e.g. below-mudline welds) |

The code assumes an above-mudline, inspectable shell joint. A below-mudline
or non-inspectable joint would warrant DFF 5–10 per the DNV table, which
would push `utilization_FLS` well past 1.0 for the same geometry.

**Worked example** (15 MW, 35 m depth, sand φ=35°, `size_monopile` converged
geometry: D=10.00 m, t=106.91 mm, L=50.00 m — see §10; FLS governs here):

| Quantity | Value |
|---|---|
| `M_char` | 475.6 MN·m |
| `Z` | 8.131 m³ |
| `sigma_char` | 58.49 MPa |
| `delta_sigma_eq` (×0.35) | 20.47 MPa |
| `N_allow` (S-N curve) | 1.68×10⁸ cycles |
| `n_cycles` (27 yr life, rpm_avg=6.28, duty=0.9) | 8.03×10⁷ cycles |
| `damage` | 0.477 |
| `utilization_FLS` (×DFF=2.0) | 0.953 |

---

## 9. Initial guess and iteration loop (`_initial_geometry`, `size_monopile`)

**Initial geometry (rule of thumb, then refined by iteration):**
```
D0 = 6.0 + (10.0 - 6.0) * (turbine_mw - 5.0) / (15.0 - 5.0)   [m]   (linear
     regression between two real reference-monopile diameters:
     6.0m at 5MW/OC3, 10.0m at 15MW/IEA -- see TURBINE_LIBRARY sources, §2)
L0 = 5.0 * D0            (fixed rule-of-thumb ratio, not tied to l_over_d_min/max)
t0 = D0 / 110.0           (mid of the allowed D/t range, default 80-160)
```
An unclamped linear extrapolation for turbine sizes away from the two
anchor points (e.g. 22 MW extrapolates to D0=12.8m, past the real-but
-externally-capped 10m reference).

**Step-wise iteration** (step sizes: `d_step = 0.15 m`, `t_step = 0.002 m`),
each iteration re-evaluates all five checks and adjusts **one** dimension
per the following priority:
1. **NFA failing low** (`f0` below the band) → increase `D` (dominant lever
   for both stiffness and frequency, since `EI ∝ D⁴` and `K_L, K_R` both
   grow strongly with `D`).
2. **ULS, FLS, or Buckling failing** → increase `t`. More thickness directly
   raises elastic buckling capacity too (§5a), so it behaves like ULS/FLS
   here.
3. **SLS failing** → increase `D` (stiffens the foundation, reduces mudline
   rotation).
4. **NFA failing high** (`f0` above the band, uncommon for monopiles) →
   decrease `D`.

After each adjustment, `L/D` is clamped to `[3, 12]` (configurable in
`DesignInputs`). **`D/t` is *not* clamped** — wall thickness is free to grow
or shrink past `[dt_ratio_min, dt_ratio_max]` (default `[80, 160]`, matching
the real D/t bound used in the IEA 22 MW reference monopile design, §2) if
that's what the checks demand; the final geometry is flagged with a
manufacturability warning note if it ends up outside that range instead of
being silently clamped back to it.

**Embedded length `L` has no independent design driver.** None of the five
check-failure branches above ever adjust `L` directly — only `D` and `t` do.
`L` starts at `L0 = 5.0 × D0` (a fixed rule-of-thumb ratio, itself only a
function of `D0`) and afterward only changes as a passive side effect of the
`L/D ∈ [3, 12]` clamp reacting to `D` changes made for other reasons. There is
no check anywhere in this model for what actually governs embedment in real
design practice — ultimate lateral/moment soil capacity (e.g. Broms' method,
or a p-y-based capacity check ensuring the pile doesn't rotate out of the
soil under the design moment). The `beta×L < 2.5` validity flag (§4) is only
a warning that the *stiffness* formula is out of its valid range — it never
triggers the loop to lengthen the pile. In short: `L` is a derived ratio, not
a solved-for design variable, in this model.

**Stopping conditions:** all five utilizations ≤ 1.0 (converged), OR
diameter reaches **3× the initial guess** (runaway guard — appends a
non-convergence note explaining that a check is likely dominated by an
input outside pile geometry, e.g. tower stiffness), OR 500 iterations.

**Post-convergence thickness shrink:** the growth loop above is
**one-directional** — it only ever adds material and stops at the first
geometry that passes, starting from `t0 = D0/110`. If that initial guess
already satisfies every check, the loop runs **zero** iterations and reports
`t0` as "the" answer, regardless of how much thinner a wall could also pass.
Once the growth loop converges, `size_monopile` steps wall thickness back
**down** by `t_step` — re-evaluating all five checks each step — until
either a step would fail a check (keep the last passing thickness) or a
1mm absolute floor is reached. This finds the true minimum-material wall
thickness rather than just the first one the growth loop happened to land
on. **Diameter is deliberately not shrunk** by this step — it also feeds the
extreme-load calculation and NFA, and NFA is still pending its own
verification (see `method_update_log.md`).

**For most turbine sizes, the growth loop for diameter also runs zero
iterations** — `_initial_geometry`'s starting guess for `D` already
satisfies every check for most turbine sizes tested, so `D` (and therefore
`L`, via the fixed `L/D=5` ratio) never moves from the initial guess either.
A converged result can therefore be almost entirely the raw starting guess
rather than something the checks actually drove — worth keeping in mind
when reading any single result from this tool in isolation (see also §11
item 22).

---

## 10. Verification

Cases were run against `size_monopile` and `evaluate_monopile` as sanity
checks (not a unit test suite); `test_engine.py` at the repo root reproduces
these as runnable checks. Verification is limited to the three turbine sizes
with a **real reference monopile design** to compare against (5/15/22 MW).

| Case | Result | Governing check | Notes |
|---|---|---|---|
| 5 MW, 20 m depth, sand (φ=36°) | D=6.00 m, t=64.5 mm, L=30.0 m (L/D=5.0, D/t=93.0) | **FLS** (margin 0.063) | Diameter matches the real OC3 monopile (6 m) exactly; thickness within ~8% of the real 60 mm |
| 15 MW, 35 m depth, sand (φ=35°) | D=10.00 m, t=106.9 mm, L=50.0 m (L/D=5.0, D/t=93.5) | **FLS** (margin 0.047) | Diameter matches the real IEA 15 MW reference (10 m) exactly; D/t≈93 sits close to the 5/22 MW pattern (§2) |
| 22 MW, 34 m depth, sand (φ=36°) | D=12.80 m, t=110.4 mm, L=64.0 m (L/D=5.0, D/t=116.0) | **Buckling** (margin 0.016) | Real IEA 22 MW design caps diameter at 10 m (an explicit optimizer bound not replicated here); thickness within ~10% of the real 100 mm. At the *real* reference geometry (D=10m, t=100mm), buckling utilization independently comes out to 1.012 — within 2% of governing exactly |

**FLS governs 5/15 MW; 22 MW is buckling-governed** — matching the industry
pattern that fatigue typically drives monopile sizing for turbines below
~15MW, while larger turbines are governed by other checks.

Both prior real bugs in this model (an under-calibrated tower-stiffness
regression, and a natural-frequency band-inversion for wide-rotor-speed
-range turbines) were caught because `size_monopile` failed to converge and
flagged it, rather than silently returning a plausible-looking wrong answer
— see `method_update_log.md` for the details.

**NFA status:** the frequency formula (§7) has been checked against real f0
values at the two turbine sizes with a sourced reference geometry (5/22 MW)
— see §2's natural-frequency comparison. **The NFA check as a whole is not
yet considered fully verified**: separate from whether its frequency
prediction matches published values, open questions remain about whether
it's the right check to be governing designs at all (see `method_update_log.md`).
NFA currently has comfortable margin in all three verified cases (buckling
and FLS carry more of the governing load), which reduces — but doesn't
eliminate — how much a future NFA correction could move these results. The
25 MW extrapolated turbine entry (§2) is unverified for a separate reason,
since it isn't a real reference turbine.

---

## 11. Major assumptions

Every item below is a concept-stage judgment call, not a value taken from a
specific project-specific input or fully validated source — candidates for
review before results are used beyond early screening:

1. `GAMMA_F_ULS = 1.35` as a single blended wind+wave load factor, not DNV's separate permanent/environmental partial factors.
2. `thrust_mn` in `TURBINE_LIBRARY` used directly as extreme ULS thrust (no separate extreme-event multiplier); the 5/10 MW entries' thrust values are literature estimates, not from the sourced reports directly (§2).
3. The 25 MW `TURBINE_LIBRARY` entry is a linear extrapolation of the 15→22 MW trend, not a verified reference turbine (§2).
4. Morison **drag-only** wave load (no inertia term); integration capped at still-water level (no crest elevation); `H_max=1.9×Hs` is an unverified rule of thumb (§3).
5. Current assumed depth-uniform, linearly superposed on wave velocity.
6. Sand `nh` vs. friction-angle correlation table (4 points, linearly interpolated).
7. Sand equivalent depth `z_ref = L/3` for a linearly-varying subgrade modulus.
8. Clay `k_soil = 0.25 × su` correlation (no ε50/strain-level adjustment).
9. SLS governed by rotation only (no deflection limit checked).
10. Tower average diameter/thickness regressed from hub height alone, calibrated to one data point (IEA 15 MW) — used only for the tower segment above the transition piece (§7).
11. RNA/tower mass split assumed 50/50 of total turbine mass — real observed range is 43.6%–54.2% across the four sourced turbines.
12. Rayleigh effective-mass factor of 0.25 for the tower's tip-mass contribution.
13. Natural-frequency model omits the `K_LM` foundation cross-coupling term. Checked against real f0 values at 5/22 MW (sourced reference geometries); the 15 MW comparison is informational only; the 25 MW extrapolated entry is unverified.
14. Fatigue `FATIGUE_LOAD_FACTOR = 0.35` (ratio of fatigue-driving stress range to extreme characteristic stress) — chosen empirically via a sensitivity sweep against 5/15/22 MW real-reference matching, not derived from a DLC spectrum. Ad-hoc; the single most influential unvalidated FLS number.
15. Fatigue cycle count uses one cycle per rotor revolution at the min/max rpm average, not a wind-speed distribution.
16. Single DNV-RP-C203-style S-N curve (`log10(a)=12.16`, `m=3`) applied structure-wide, not joint-specific.
17. `USD_PER_T_STEEL = 2200` — a placeholder, not sourced from a specific quote.
18. Local shell buckling (`_shell_buckling_check`, §5a) — DNV-RP-C202 unstiffened cylinder, panel length assumed equal to the full exposed above-mudline shaft (no ring stiffeners). Often the governing check (5/15/22 MW all converge buckling-governed or near it). **Global (Euler) column buckling is not implemented** — axial load is small relative to elastic critical load, judged unlikely to govern for this structure type.
19. `sigma_vm` in `_uls_check` omits axial stress (self-weight/pretension) and hoop/radial stress (external hydrostatic pressure) — only bending + shear are combined (§5).
20. The post-convergence thickness-shrink step (§9) only shrinks wall thickness, not diameter — a design could still be carrying more diameter than strictly necessary. NFA is explicitly excluded from driving any shrink, pending its own verification (§10).
21. **Embedded length `L` has no independent design driver** — it's a fixed `L/D=5` rule-of-thumb ratio at the initial guess, only ever changing as a passive side effect of the `L/D∈[3,8]` clamp when `D` changes for other reasons. No check evaluates ultimate lateral/moment soil capacity (e.g. Broms' method) to actually size embedment against load; `beta×L<2.5` (§4) is only a stiffness-formula validity warning, not a corrective design action (§9).
22. **For most turbine sizes, the growth loop runs zero iterations** — `_initial_geometry`'s starting guess already satisfies ULS/SLS/NFA/FLS/Buckling, so `D` (and therefore `L`, via the fixed `L/D=5` ratio) never moves from the initial guess at all. A result can look like a converged, optimized design while actually being almost entirely the raw starting guess (§9).
23. `D/t` bounds (default `[80, 160]`) are advisory, not a hard search limit (§9) — the converged geometry can fall outside them, flagged with a manufacturability warning note rather than being blocked from getting there.
24. The 15 MW mudline wall-thickness reference figure (§2) is not table-sourced; an earlier image-derived chart estimate is doubted based on this engine's own converged D/t pattern (§2, §10).

Items 6–13 (soil and natural-frequency modeling) are the ones most likely to
materially shift results if refined with real project data. NFA's own
verification status (§10) still matters, though buckling and FLS now carry
more of the governing load across the three verified cases than NFA does.
