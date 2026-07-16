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
| `h` | cantilever height used in the frequency model, `hub_height_m + water_depth_m` | m |
| `flexibility` | total tip flexibility (tower bending + foundation `K_L` + `K_R`) | m/MN |
| `k_eq` | equivalent lateral stiffness at hub height, `1 / flexibility` | MN/m |
| `m_RNA`, `m_tower` | assumed RNA/tower mass split of `total_turbine_mass_t` | t |
| `m_eff` | effective modal mass, `m_RNA + 0.25 × m_tower` (Rayleigh factor) | kg |
| `f0` | first (fore-aft) natural frequency | Hz |
| `f_1P_max`, `f_1P_min` | rotor (1P) excitation frequency range bounds, from `rpm_max`/`rpm_min` | Hz |
| `f_3P_min` | bottom of the blade-passing (3P) frequency range, `3 × f_1P_min` | Hz |
| `band_low`, `band_high` | soft-stiff target frequency band bounds (with 10% margins) | Hz |
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
| 15 (IEA) | not stated in source | 10.0 | 45 | — |
| 22 (IEA) | 34 | 10.0 (max, bound met) | 45 | 80–160 (optimizer bound; not active at either end in the final design) |

The 22 MW source's D/t design bound (80–160) is why `dt_ratio_max` was
widened from 140 to 160 (2026-07-16) — see §9.

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
independently validated for other turbine sizes. This value has an outsized
effect on the result — see §10 (verification) where an earlier,
under-calibrated version of this formula caused the sizing loop to diverge.

**Simplified 2-spring flexibility superposition:**
Models the tower+RNA as a cantilever of height `h` (hub height above
mudline) with a tip mass, on a foundation with only lateral (`K_L`) and
rocking (`K_R`) springs — **omitting the `K_LM` cross-coupling term** that
Arany's full 3-spring model includes (a documented simplification):
```
I_tower = (pi/64) * (d_avg_tower^4 - (d_avg_tower - 2*t_avg_tower)^4)
EI_tower = STEEL_E_MPA * I_tower

h = hub_height_m + water_depth_m

flexibility = h^3/(3*EI_tower) + 1/K_L + h^2/K_R
k_eq = 1 / flexibility                          [MN/m]

m_RNA   = 0.4 * total_turbine_mass_t            (assumption: 40/60 RNA/tower split)
m_tower = 0.6 * total_turbine_mass_t
m_eff   = (m_RNA + 0.25*m_tower) * 1000          [kg]   (0.25 = standard Rayleigh
                                                          cantilever-with-tip-mass
                                                          effective-mass factor)

f0 = (1/(2*pi)) * sqrt(k_eq_in_N_per_m / m_eff)   [Hz]
```

**Soft-stiff target band:**
```
f_1P_max = rpm_max / 60
f_1P_min = rpm_min / 60
f_3P_min = 3 * f_1P_min

band_low  = 1.1 * f_1P_max      (10% margin above top of 1P range)
band_high = 0.9 * f_3P_min      (10% margin below bottom of 3P range)

utilization_NFA:
  if f0 < band_low:   band_low / f0
  elif f0 > band_high: f0 / band_high
  else: max(band_low/f0, f0/band_high)     (both < 1, i.e. "pass with margin")
```
Pass if `utilization_NFA ≤ 1.0`, i.e. `f0` sits inside `[band_low, band_high]`.

---

## 8. FLS check (`_fls_check`)

**Single equivalent-stress-range Palmgren-Miner check** — explicitly not a
rainflow-counted multi-bin fatigue simulation:
```
sigma_char = M_char / Z                         (characteristic bending stress, same Z as ULS,
                                                  M_char = M_thrust + M_wave from §3)
delta_sigma_eq = FATIGUE_LOAD_FACTOR * sigma_char     (FATIGUE_LOAD_FACTOR = 0.17, ad-hoc)

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
  source** — `FATIGUE_LOAD_FACTOR = 0.17` (updated 2026-07-16, was 0.35) is a
  project-internal, **ad-hoc** value, back-calculated to make the model's
  FLS check pass at the published IEA 15 MW reference monopile's real wall
  thickness (~40-55 mm at D=10 m) rather than derived from first principles.
  The original 0.35 guess made FLS demand ~2x too much wall thickness (FLS
  utilization of 8.85 at the real 50 mm reference geometry); 0.17 was solved
  for as the value that makes FLS utilization ≈ 1.0 there instead (see
  `docs/methodology.md`, 2026-07-16). It is still not derived from any
  specific DLC spectrum, wind/rotor-speed distribution, or rainflow-counted
  time series — **recalibrate again once real turbine fatigue load data is
  available**, per the user's explicit instruction to treat this as
  temporary. This remains **the single most influential unvalidated number
  in the fatigue check** — since FLS is frequently the governing constraint
  (see §10), this one placeholder effectively sets the final pile sizing in
  those cases.

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
geometry with `FATIGUE_LOAD_FACTOR = 0.17`: D=9.33 m, t=84.8 mm, L=46.67 m —
matches the §10 verification run):

| Quantity | Value |
|---|---|
| `M_char` | 474.7 MN·m |
| `Z` | 5.649 m³ |
| `sigma_char` | 84.05 MPa |
| `delta_sigma_eq` (×0.17) | 14.29 MPa |
| `N_allow` (S-N curve) | 4.96×10⁸ cycles |
| `n_cycles` (27 yr life, rpm_avg=6.28, duty=0.9) | 8.03×10⁷ cycles |
| `damage` | 0.162 |
| `utilization_FLS` (×DFF=2.0) | 0.324 |

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

---

## 10. Verification performed

Three cases were run against `size_monopile` as a sanity check (not a unit
test suite). Numbers below are with `FATIGUE_LOAD_FACTOR = 0.17` (updated
2026-07-16 — see §8 and `docs/methodology.md`); `test_engine.py` at the repo
root reproduces the 15 MW case as a runnable check.

| Case | Result | Governing check | Notes |
|---|---|---|---|
| 15 MW, 35 m depth, sand (φ=35°) | D=9.33 m, t=84.8 mm, L=46.67 m (L/D≈5.0) | **NFA** (margin 0.036) | Diameter and embedded length match the published IEA 15 MW reference-monopile range; wall thickness (~85 mm) is thicker than the reference's ~40-55 mm but no longer pinned at the `dt_ratio_min` floor the way it was under the old fatigue factor — see §8 worked example |
| 20 MW, 45 m depth, sand (φ=38°) | D=11.0 m, t=100.0 mm, L=55 m (L/D=5.0) | **NFA** (margin 0.097) | Scales sensibly with turbine size |
| 8 MW, 25 m depth, clay (su=80 kPa) | Does **not** converge (runaway guard at D=21.1 m) | NFA | Also flags `beta*L < 2.5` — the closed-form soil assumption itself breaks down for this combination; correctly reported rather than silently returning a bad answer |

Note that FLS no longer governs the 15/20 MW cases now that
`FATIGUE_LOAD_FACTOR` is calibrated down to 0.17 (FLS utilization dropped
from ~0.97 to ~0.32-0.33) — **NFA** is the tightest check instead. This is a
direct, expected consequence of the recalibration in §8, not a new issue.

**Bug found and fixed during verification:** the original `_tower_geometry`
regression (`4.0 + 0.01×hub_height`) under-estimated tower stiffness so
severely that tower flexibility dominated >95% of total system flexibility
at all realistic pile sizes — the iteration loop grew the pile diameter to
84 m chasing a frequency target that pile geometry could not move. Fixed by
recalibrating against the published IEA 15 MW tower geometry (§7) and adding
the runaway guard described in §9 so any future similar mismatch fails
loudly instead of silently.

**Two new NFA generalization issues found 2026-07-16, NOT yet fixed**,
discovered by evaluating `evaluate_monopile` directly at the *real* reference
geometries for the newly-sourced 5 MW and 22 MW turbines (§2):

1. **5 MW/OC3** (real geometry D=6 m, t=60 mm, L=36 m, 20 m water depth):
   the model computes `f0 = 0.191 Hz`, below its own target band
   `[0.222, 0.31] Hz`. This is a different failure from the 15 MW tower
   -calibration bug above (already fixed) — it suggests the simplified
   2-spring frequency model (§7) may be biased low in general, not only at
   the one point (15 MW) it was calibrated against. Not independently
   confirmed against the OC3 report's own eigenanalysis figure (Figure 20),
   which is image-only in the source PDF and wasn't extractable as text
   this session.
2. **22 MW/IEA** (real geometry D=10 m, t=100 mm, L=45 m, 34 m water depth):
   the target band itself comes out **inverted** —
   `band_low = 0.1295 Hz > band_high = 0.0813 Hz`. Cause: at very wide rotor
   -speed ranges (`rpm_min=1.807` vs `rpm_max=7.061`, a real trend for very
   large turbines — see §2), `3 × f_1P_min` falls below `1.1 × f_1P_max`, so
   no valid gap exists between the 1P and 3P bands under the `band_low`/
   `band_high` formula in §7. This is a **logic gap**, not a calibration
   issue — it mirrors a real industry challenge (the soft-stiff gap shrinks
   or vanishes for very large turbines with wide operating rpm ranges), but
   the code doesn't currently detect or handle the degenerate case; it just
   produces a confusing `nfa_utilization` and the iteration loop chases an
   impossible target, hitting the non-convergence guard (§9).

Both cases were caught precisely because `size_monopile` failed to converge
and flagged it rather than silently returning a plausible-looking wrong
answer — see the non-convergence note added in §9. Neither has been fixed
yet; treat the NFA check as **not validated outside the 15/20 MW range**
until this is addressed.

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
10. Tower average diameter/thickness regressed from hub height alone, calibrated to one data point (IEA 15 MW) — and, per §10, still under- or over-predicts frequency at other verified turbine sizes (5 MW, 22 MW).
11. RNA/tower mass split assumed 50/50 of total turbine mass (updated 2026-07-16 from a 40/60 guess) — real observed range is 43.6%–54.2% across the four sourced turbines.
12. Rayleigh effective-mass factor of 0.25 for the tower's tip-mass contribution.
13. Natural-frequency model omits the `K_LM` foundation cross-coupling term, and (per §10, found 2026-07-16) its soft-stiff band formula can become inverted/degenerate for turbines with very wide rotor-speed ranges (e.g. 22 MW) — **not validated outside 15/20 MW**.
14. Fatigue `FATIGUE_LOAD_FACTOR = 0.17` (ratio of fatigue-driving stress range to extreme characteristic stress) — updated 2026-07-16, back-calculated to match the IEA 15 MW reference wall thickness; still an ad-hoc placeholder pending recalibration against real turbine fatigue load data, and the single most influential unvalidated FLS number.
15. Fatigue cycle count uses one cycle per rotor revolution at the min/max rpm average, not a wind-speed distribution.
16. Single DNV-RP-C203-style S-N curve (`log10(a)=12.16`, `m=3`) applied structure-wide, not joint-specific.
17. `USD_PER_T_STEEL = 2200` — a placeholder, not sourced from a specific quote.

Items 6–13 (soil and natural-frequency modeling) are the ones most likely to
materially shift results if refined with real project data — see §4/§7 and
the bugs described in §10. Item 13 in particular is now a **known-broken**
area outside the 15/20 MW range, not just an approximation.
