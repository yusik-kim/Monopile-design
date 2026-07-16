"""
Monopile Foundation Concept Design Engine v0.1

Implements an Arany-et-al.-style ("10-step") initial sizing loop for offshore
wind monopile foundations: iterate ULS -> SLS -> natural-frequency (soft-stiff)
-> FLS using closed-form formulas until a candidate diameter/wall-thickness/
embedded-length converges.

Concept-level screening only. Not certification or FEED design.

Key simplifications (all concept-stage, not detailed/FEED-grade):
- Soil-structure interaction: idealized single homogeneous soil layer (sand or
  clay), closed-form Hetenyi beam-on-elastic-foundation pile-head stiffness
  (not a full nonlinear multi-layer p-y / PISA solve).
- Wave/current load: simplified Morison drag-only quasi-static extreme load
  using linear (Airy) deep-water particle kinematics, not a full DLC time
  -domain simulation.
- Natural frequency: simplified 2-spring (lateral + rocking) cantilever
  flexibility superposition, omitting the K_LM cross-coupling term that
  Arany's full 3-spring model includes.
- Fatigue: single equivalent-stress-range Palmgren-Miner check, not a full
  rainflow-counted multi-bin DLC fatigue simulation.
Each simplification is called out at its function. Treat outputs as a
starting point for detailed design / PISA-based or FE validation, not a
substitute for it -- see Monopile_Initial_Design_Method_Summary.md.
"""
from dataclasses import dataclass, field, asdict
import math

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
G = 9.81
RHO_SEAWATER_KG_M3 = 1025.0
STEEL_DENSITY_T_PER_M3 = 7.85
STEEL_E_MPA = 210_000.0          # Young's modulus (MPa = MN/m^2)
STEEL_YIELD_MPA = 355.0          # S355 offshore structural steel
USD_PER_T_STEEL = 2200.0         # rolled/welded monopile steel, concept-stage

GAMMA_F_ULS = 1.35                # combined wind+wave load factor (DNV normal safety class, simplified single factor)
GAMMA_M_ULS = 1.1                 # material resistance factor (DNV-ST-0126)
MORISON_CD = 0.65                 # drag coefficient, smooth circular cylinder, high Reynolds number

# DNV-RP-C203 style S-N curve (single representative curve for concept screening)
SN_LOG10_A = 12.16
SN_M = 3.0
FATIGUE_DESIGN_FACTOR = 2.0       # DNV DFF for typical (non-critical/inspectable) monopile joints

# Ratio of the fatigue-equivalent stress range to the characteristic (extreme)
# bending stress. Ad-hoc value back-calculated to match the published IEA
# 15MW reference monopile wall thickness (~40-55mm at D=10m) -- see
# docs/methodology.md (2026-07-16). NOT derived from a real DLC/rainflow
# spectrum; recalibrate once the model has real turbine fatigue load data.
FATIGUE_LOAD_FACTOR = 0.17

# Reference turbines: mass_t is total turbine mass (RNA + tower); thrust_mn is
# the extreme/ultimate design rotor thrust used directly as the ULS
# characteristic wind load. 5/10/15/22 MW entries are sourced directly from
# published reference-turbine reports (see docs/methodology.md, 2026-07-16);
# 25 MW is a linear extrapolation of the 15->22 MW trend, NOT independently
# verified against a real 25 MW reference document.
#
#   5 MW  -- OC3/NREL 5-MW baseline turbine, monopile (Phase II, flexible
#            foundation): Jonkman & Musial, "Offshore Code Comparison
#            Collaboration (OC3) for IEA Task 23", NREL/TP-500-48191 (2010).
#            Rotor 110 t + Nacelle 240 t = RNA 350 t; Tower 347.5 t.
#            Thrust not tabulated in the source; 0.80 MN is the commonly
#            cited literature value (Jonkman et al. 2009 5-MW definition
#            report), not independently re-derived here.
#   10 MW -- DTU 10-MW reference wind turbine: Bak et al., "Description of
#            the DTU 10 MW Reference Wind Turbine", DTU Wind Energy (2013).
#            Rotor 229 t + Nacelle 446 t = RNA 675 t; Tower 605 t. Thrust
#            (1.50 MN) is a literature estimate -- not in the source excerpt
#            available this session.
#   15 MW -- IEA Wind 15-MW reference turbine: Gaertner et al., NREL/TP-5000
#            -75698 (2020), Table ES-1. RNA 1017 t, Tower 860 t. Thrust
#            (2.50 MN) computed from the report's design-point CT=0.804 at
#            rated wind speed 10.59 m/s -- matches this value to 3 s.f.
#   22 MW -- IEA 22-MW reference turbine: DTU Wind E-0243 report. RNA
#            1215.6 t (stated total), Tower 1574 t. Thrust 2.793 MN and
#            rpm_min/rpm_max taken directly from the report's Table 1/2.
TURBINE_LIBRARY = [
    {"mw": 5.0,  "rotor_diameter_m": 126.0, "hub_height_m": 90.0,  "mass_t": 697.5,  "thrust_mn": 0.80,  "rpm_min": 6.90,  "rpm_max": 12.10},
    {"mw": 10.0, "rotor_diameter_m": 178.3, "hub_height_m": 119.0, "mass_t": 1280.0, "thrust_mn": 1.50,  "rpm_min": 6.00,  "rpm_max": 9.60},
    {"mw": 15.0, "rotor_diameter_m": 240.0, "hub_height_m": 150.0, "mass_t": 1877.0, "thrust_mn": 2.50,  "rpm_min": 5.00,  "rpm_max": 7.56},
    {"mw": 22.0, "rotor_diameter_m": 284.0, "hub_height_m": 170.0, "mass_t": 2789.6, "thrust_mn": 2.793, "rpm_min": 1.807, "rpm_max": 7.061},
    # Extrapolated (NOT a verified reference turbine) -- linear continuation
    # of the 15->22 MW trend for each column. rpm_min in particular drops
    # very steeply between 15 and 22 MW in the real data (5.00 -> 1.807);
    # extrapolating that trend further is the least-certain figure here.
    {"mw": 25.0, "rotor_diameter_m": 303.0, "hub_height_m": 179.0, "mass_t": 3181.0, "thrust_mn": 2.92,  "rpm_min": 0.44,  "rpm_max": 6.85},
]

# API-style nh (constant of horizontal subgrade reaction gradient, MN/m^4)
# vs. submerged friction angle -- approximate, for concept screening only.
_SAND_NH_TABLE = [(28.0, 2.5), (32.0, 7.0), (36.0, 15.0), (40.0, 25.0)]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class SoilProfile:
    soil_type: str                       # "sand" or "clay"
    submerged_unit_weight_kn_m3: float = 9.0
    friction_angle_deg: float = 34.0      # sand only
    undrained_shear_strength_kpa: float = 75.0  # clay only


@dataclass
class DesignInputs:
    turbine_mw: float
    water_depth_m: float
    soil: SoilProfile
    hs_m: float                           # significant wave height, extreme sea state
    tp_s: float                           # peak wave period, extreme sea state
    current_m_s: float = 0.5
    design_life_years: float = 27.0
    duty_factor: float = 0.9              # fraction of time turbine is producing/cycling
    allowable_sls_rotation_deg: float = 0.50
    dt_ratio_min: float = 80.0
    dt_ratio_max: float = 160.0
    l_over_d_min: float = 3.0
    l_over_d_max: float = 8.0
    # Simplified tower geometry, approximated from hub height when not given.
    # Concept-stage placeholder -- refine with actual tower design.
    avg_tower_diameter_m: float | None = None
    avg_tower_wall_thickness_m: float | None = None


@dataclass
class MonopileGeometry:
    diameter_m: float
    wall_thickness_m: float
    embedded_length_m: float


@dataclass
class MonopileResult:
    geometry: MonopileGeometry
    mudline_moment_mnm: float
    mudline_shear_mn: float
    k_lateral_mn_per_m: float
    k_rocking_mnm_per_rad: float
    beta_per_m: float
    uls_utilization: float
    sls_rotation_deg: float
    sls_utilization: float
    natural_frequency_hz: float
    soft_stiff_band_hz: tuple[float, float]
    nfa_utilization: float
    fls_damage: float
    fls_utilization: float
    steel_mass_t: float
    steel_cost_usd: float
    margins: dict[str, float]
    governing_constraint: str
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Turbine lookup
# ---------------------------------------------------------------------------
def turbine_from_capacity(turbine_mw: float) -> dict:
    """Linearly interpolate TURBINE_LIBRARY entries by rated power."""
    library = sorted(TURBINE_LIBRARY, key=lambda t: t["mw"])
    if turbine_mw <= library[0]["mw"]:
        return dict(library[0])
    if turbine_mw >= library[-1]["mw"]:
        return dict(library[-1])
    for lo, hi in zip(library, library[1:]):
        if lo["mw"] <= turbine_mw <= hi["mw"]:
            frac = (turbine_mw - lo["mw"]) / (hi["mw"] - lo["mw"])
            return {
                key: lo[key] + frac * (hi[key] - lo[key])
                for key in lo
            }
    raise ValueError(f"Could not interpolate turbine for {turbine_mw} MW")


# ---------------------------------------------------------------------------
# Loads
# ---------------------------------------------------------------------------
def _pile_section_properties(geometry: MonopileGeometry) -> tuple[float, float, float]:
    """Returns (cross-section area m^2, second moment of area I m^4, EI MN*m^2)."""
    d = geometry.diameter_m
    t = geometry.wall_thickness_m
    d_inner = d - 2 * t
    area = (math.pi / 4) * (d ** 2 - d_inner ** 2)
    i_second_moment = (math.pi / 64) * (d ** 4 - d_inner ** 4)
    ei = STEEL_E_MPA * i_second_moment
    return area, i_second_moment, ei


def _extreme_loads(inputs: DesignInputs, geometry: MonopileGeometry, turbine: dict) -> tuple[float, float]:
    """Simplified extreme wind-thrust + Morison-drag wave/current mudline moment & shear.

    Wind: turbine's extreme design thrust applied at hub height above mudline.
    Wave/current: Morison drag-only (no inertia term), linear deep-water wave
    kinematics at design wave height Hmax = 1.9*Hs, integrated numerically
    over the water column above mudline with a uniform added current.
    Both are combined via simple linear superposition (characteristic loads).
    """
    d = geometry.diameter_m
    water_depth = inputs.water_depth_m

    # Wind thrust moment about mudline.
    lever_arm_m = turbine["hub_height_m"] + water_depth
    thrust_mn = turbine["thrust_mn"]
    m_thrust_mnm = thrust_mn * lever_arm_m
    f_thrust_mn = thrust_mn

    # Wave/current Morison drag, numerically integrated (trapezoidal, N slices).
    h_max = 1.9 * inputs.hs_m
    omega = 2 * math.pi / inputs.tp_s
    k_wave = omega ** 2 / G  # deep-water dispersion relation
    n_slices = 40
    dz = water_depth / n_slices
    f_wave_mn = 0.0
    m_wave_mnm = 0.0
    for i in range(n_slices + 1):
        z = -water_depth + i * dz  # z=0 at MSL, z=-water_depth at mudline
        u = (math.pi * h_max / inputs.tp_s) * math.exp(k_wave * z) + inputs.current_m_s
        f_per_length_mn_m = 0.5 * RHO_SEAWATER_KG_M3 * MORISON_CD * d * u * abs(u) / 1e6
        weight = 0.5 if i in (0, n_slices) else 1.0  # trapezoidal end weights
        moment_arm = z + water_depth  # distance above mudline
        f_wave_mn += weight * f_per_length_mn_m * dz
        m_wave_mnm += weight * f_per_length_mn_m * moment_arm * dz

    m_mudline_mnm = m_thrust_mnm + m_wave_mnm
    v_mudline_mn = f_thrust_mn + f_wave_mn
    return m_mudline_mnm, v_mudline_mn


# ---------------------------------------------------------------------------
# Soil stiffness (closed-form Hetenyi beam-on-elastic-foundation)
# ---------------------------------------------------------------------------
def _sand_nh(friction_angle_deg: float) -> float:
    table = _SAND_NH_TABLE
    if friction_angle_deg <= table[0][0]:
        return table[0][1]
    if friction_angle_deg >= table[-1][0]:
        return table[-1][1]
    for (phi_lo, nh_lo), (phi_hi, nh_hi) in zip(table, table[1:]):
        if phi_lo <= friction_angle_deg <= phi_hi:
            frac = (friction_angle_deg - phi_lo) / (phi_hi - phi_lo)
            return nh_lo + frac * (nh_hi - nh_lo)
    raise ValueError("unreachable")


def _soil_stiffness(soil: SoilProfile, geometry: MonopileGeometry, ei_mnm2: float) -> tuple[float, float, float, list[str]]:
    """Closed-form pile-head lateral (K_L), rocking (K_R) stiffness and beta,
    from a Hetenyi semi-infinite-beam-on-elastic-foundation solution with an
    idealized homogeneous Winkler soil modulus.

    Sand: k(z) = nh * z, evaluated at an equivalent characteristic depth
    z_ref = L/3 (common quick engineering approximation for a linearly
    -varying subgrade modulus) to obtain a single representative constant k.
    Clay: k assumed constant with depth, k = 0.25 * su_kPa (MN/m^3), a rough
    Terzaghi-style correlation.
    Both are concept-stage approximations -- not a substitute for a full
    depth-varying p-y / PISA solve.
    """
    notes: list[str] = []
    d = geometry.diameter_m
    l = geometry.embedded_length_m

    if soil.soil_type == "sand":
        nh = _sand_nh(soil.friction_angle_deg)  # MN/m^4
        z_ref = l / 3.0
        k_soil_mn_m3 = nh * z_ref
    elif soil.soil_type == "clay":
        k_soil_mn_m3 = 0.25 * soil.undrained_shear_strength_kpa / 1000.0
    else:
        raise ValueError(f"Unknown soil_type: {soil.soil_type!r}")

    k_line_mn_m2 = k_soil_mn_m3 * d
    beta_per_m = (k_line_mn_m2 / (4 * ei_mnm2)) ** 0.25

    if beta_per_m * l < 2.5:
        notes.append(
            "beta*L < 2.5: pile is short/stiff relative to soil for the "
            "semi-infinite-beam assumption; treat stiffness as approximate "
            "and validate with a full p-y or PISA solve."
        )

    k_lateral_mn_per_m = k_line_mn_m2 / beta_per_m
    k_rocking_mnm_per_rad = k_line_mn_m2 / (2 * beta_per_m ** 3)
    return k_lateral_mn_per_m, k_rocking_mnm_per_rad, beta_per_m, notes


# ---------------------------------------------------------------------------
# ULS / SLS / NFA / FLS checks
# ---------------------------------------------------------------------------
def _uls_check(geometry: MonopileGeometry, m_char_mnm: float, v_char_mn: float) -> float:
    d = geometry.diameter_m
    t = geometry.wall_thickness_m
    d_inner = d - 2 * t
    i_second_moment = (math.pi / 64) * (d ** 4 - d_inner ** 4)
    section_modulus_m3 = i_second_moment / (d / 2)
    area_m2 = (math.pi / 4) * (d ** 2 - d_inner ** 2)
    shear_area_m2 = 0.5 * area_m2  # thin-wall circular tube approximation

    m_uls_mnm = GAMMA_F_ULS * m_char_mnm
    v_uls_mn = GAMMA_F_ULS * v_char_mn

    sigma_bending_mpa = m_uls_mnm / section_modulus_m3
    tau_shear_mpa = v_uls_mn / shear_area_m2
    sigma_vm_mpa = math.sqrt(sigma_bending_mpa ** 2 + 3 * tau_shear_mpa ** 2)

    allowable_mpa = STEEL_YIELD_MPA / GAMMA_M_ULS
    return sigma_vm_mpa / allowable_mpa


def _sls_check(inputs: DesignInputs, m_char_mnm: float, v_char_mn: float,
               k_line_mn_m2: float, beta_per_m: float) -> tuple[float, float]:
    """Mudline rotation from the same Hetenyi flexibility relations (unfactored,
    characteristic loads, per DNV SLS practice). Returns (rotation_deg, utilization).
    """
    theta0_rad = (2 * beta_per_m ** 2 / k_line_mn_m2) * v_char_mn \
        + (4 * beta_per_m ** 3 / k_line_mn_m2) * m_char_mnm
    theta0_deg = math.degrees(abs(theta0_rad))
    utilization = theta0_deg / inputs.allowable_sls_rotation_deg
    return theta0_deg, utilization


def _tower_geometry(inputs: DesignInputs, turbine: dict) -> tuple[float, float]:
    """Approximate average tower diameter/thickness from hub height when not
    supplied. Concept-stage placeholder -- refine with actual tower design.

    Calibrated against the published IEA 15 MW reference tower (base 10.0 m,
    top 6.5 m -> average 8.25 m, at 150 m hub height): d_avg = 0.055*hub_height.
    """
    d_avg = inputs.avg_tower_diameter_m
    if d_avg is None:
        d_avg = 0.055 * turbine["hub_height_m"]
    t_avg = inputs.avg_tower_wall_thickness_m
    if t_avg is None:
        t_avg = d_avg / 170.0
    return d_avg, t_avg


def _natural_frequency(inputs: DesignInputs, geometry: MonopileGeometry, turbine: dict,
                        k_lateral_mn_per_m: float, k_rocking_mnm_per_rad: float) -> tuple[float, tuple[float, float], float]:
    """Simplified 2-spring (K_L, K_R) flexibility-superposition first-mode
    natural frequency: cantilever of height h = hub height above mudline,
    tip mass = RNA + tower participation, on a flexible (translating +
    rotating) foundation. Omits the K_LM cross-coupling term that Arany's
    full 3-spring model includes -- a documented concept-stage simplification.
    """
    d_avg, t_avg = _tower_geometry(inputs, turbine)
    d_inner = d_avg - 2 * t_avg
    i_tower = (math.pi / 64) * (d_avg ** 4 - d_inner ** 4)
    ei_tower_mnm2 = STEEL_E_MPA * i_tower

    h_m = turbine["hub_height_m"] + inputs.water_depth_m

    flexibility_m_per_mn = (h_m ** 3) / (3 * ei_tower_mnm2) + 1.0 / k_lateral_mn_per_m \
        + (h_m ** 2) / k_rocking_mnm_per_rad
    k_eq_mn_per_m = 1.0 / flexibility_m_per_mn
    k_eq_n_per_m = k_eq_mn_per_m * 1e6

    # RNA/tower split of total mass: real reference turbines range from 43.6%
    # (IEA 22MW) to 54.2% (IEA 15MW) RNA fraction (see docs/methodology.md,
    # 2026-07-16); 0.5/0.5 is the average, not a fixed physical ratio.
    total_mass_t = turbine["mass_t"]
    m_rna_t = 0.5 * total_mass_t
    m_tower_t = 0.5 * total_mass_t
    m_eff_kg = (m_rna_t + 0.25 * m_tower_t) * 1000.0

    f0_hz = (1.0 / (2 * math.pi)) * math.sqrt(k_eq_n_per_m / m_eff_kg)

    f_1p_max_hz = turbine["rpm_max"] / 60.0
    f_1p_min_hz = turbine["rpm_min"] / 60.0
    f_3p_min_hz = 3 * f_1p_min_hz

    band_low_hz = f_1p_max_hz * 1.1
    band_high_hz = f_3p_min_hz * 0.9

    if f0_hz < band_low_hz:
        nfa_utilization = band_low_hz / f0_hz
    elif f0_hz > band_high_hz:
        nfa_utilization = f0_hz / band_high_hz
    else:
        nfa_utilization = max(band_low_hz / f0_hz, f0_hz / band_high_hz)

    return f0_hz, (band_low_hz, band_high_hz), nfa_utilization


def _fls_check(inputs: DesignInputs, geometry: MonopileGeometry, turbine: dict,
               m_char_mnm: float) -> tuple[float, float]:
    """Simplified single-equivalent-stress-range Palmgren-Miner fatigue check.

    Delta_sigma_eq is approximated as a fraction of the characteristic
    (unfactored) bending stress -- representative of typical operational
    stress-range-to-extreme-stress ratios -- since deriving a true damage
    -equivalent load requires full DLC time-series/rainflow analysis, which
    is out of scope for concept-stage screening (see research summary).
    """
    d = geometry.diameter_m
    t = geometry.wall_thickness_m
    d_inner = d - 2 * t
    i_second_moment = (math.pi / 64) * (d ** 4 - d_inner ** 4)
    section_modulus_m3 = i_second_moment / (d / 2)
    sigma_char_mpa = m_char_mnm / section_modulus_m3

    delta_sigma_eq_mpa = FATIGUE_LOAD_FACTOR * sigma_char_mpa

    n_allow = 10 ** (SN_LOG10_A - SN_M * math.log10(delta_sigma_eq_mpa))

    rpm_avg = 0.5 * (turbine["rpm_min"] + turbine["rpm_max"])
    seconds_per_year = 365.25 * 24 * 3600
    n_cycles = (rpm_avg / 60.0) * seconds_per_year * inputs.design_life_years * inputs.duty_factor

    damage = n_cycles / n_allow
    utilization = damage * FATIGUE_DESIGN_FACTOR
    return damage, utilization


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def _constraint_margins(uls: float, sls: float, nfa: float, fls: float) -> dict[str, float]:
    return {"ULS": 1.0 - uls, "SLS": 1.0 - sls, "NFA": 1.0 - nfa, "FLS": 1.0 - fls}


def most_restrictive_constraint(margins: dict[str, float]) -> tuple[str, float]:
    name = min(margins, key=lambda k: margins[k])
    return name, margins[name]


def evaluate_monopile(inputs: DesignInputs, geometry: MonopileGeometry) -> MonopileResult:
    turbine = turbine_from_capacity(inputs.turbine_mw)
    _, _, ei_mnm2 = _pile_section_properties(geometry)

    m_mudline_mnm, v_mudline_mn = _extreme_loads(inputs, geometry, turbine)

    k_lateral, k_rocking, beta, soil_notes = _soil_stiffness(inputs.soil, geometry, ei_mnm2)
    k_line_mn_m2 = k_lateral * beta  # back out k_line = K_L * beta (see _soil_stiffness derivation)

    uls_utilization = _uls_check(geometry, m_mudline_mnm, v_mudline_mn)
    sls_rotation_deg, sls_utilization = _sls_check(inputs, m_mudline_mnm, v_mudline_mn, k_line_mn_m2, beta)
    f0_hz, band, nfa_utilization = _natural_frequency(inputs, geometry, turbine, k_lateral, k_rocking)
    fls_damage, fls_utilization = _fls_check(inputs, geometry, turbine, m_mudline_mnm)

    margins = _constraint_margins(uls_utilization, sls_utilization, nfa_utilization, fls_utilization)
    governing, _ = most_restrictive_constraint(margins)

    d = geometry.diameter_m
    t = geometry.wall_thickness_m
    d_inner = d - 2 * t
    area_m2 = (math.pi / 4) * (d ** 2 - d_inner ** 2)
    steel_mass_t = area_m2 * geometry.embedded_length_m * STEEL_DENSITY_T_PER_M3

    notes = list(soil_notes)
    if d > 7.5 or (geometry.embedded_length_m / d) < 4.0:
        notes.append(
            "Diameter > ~7.5 m or L/D < 4: classical p-y / Hetenyi closed-form "
            "stiffness is known to under-predict capacity for large-diameter, "
            "low-L/D monopiles. Validate with the PISA method or FE before "
            "committing to this geometry."
        )

    return MonopileResult(
        geometry=geometry,
        mudline_moment_mnm=m_mudline_mnm,
        mudline_shear_mn=v_mudline_mn,
        k_lateral_mn_per_m=k_lateral,
        k_rocking_mnm_per_rad=k_rocking,
        beta_per_m=beta,
        uls_utilization=uls_utilization,
        sls_rotation_deg=sls_rotation_deg,
        sls_utilization=sls_utilization,
        natural_frequency_hz=f0_hz,
        soft_stiff_band_hz=band,
        nfa_utilization=nfa_utilization,
        fls_damage=fls_damage,
        fls_utilization=fls_utilization,
        steel_mass_t=steel_mass_t,
        steel_cost_usd=steel_mass_t * USD_PER_T_STEEL,
        margins=margins,
        governing_constraint=governing,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Initial sizing loop (Arany-style iteration)
# ---------------------------------------------------------------------------
def _initial_geometry(inputs: DesignInputs, turbine: dict) -> MonopileGeometry:
    """Rule-of-thumb starting guess, refined by the iteration loop below.
    Diameter regressed against two published anchor points (~7 m at 8 MW,
    ~11 m at 20 MW); embedded length at mid-range L/D=5; wall thickness at
    mid-range D/t=110.
    """
    d_initial_m = 7.0 + (11.0 - 7.0) * (turbine["mw"] - 8.0) / (20.0 - 8.0)
    l_initial_m = 5.0 * d_initial_m
    t_initial_m = d_initial_m / 110.0
    return MonopileGeometry(diameter_m=d_initial_m, wall_thickness_m=t_initial_m, embedded_length_m=l_initial_m)


def size_monopile(inputs: DesignInputs, max_iterations: int = 500) -> MonopileResult:
    """Arany-style step-wise iteration, adjusting whichever dimension is most
    effective for the worst-failing check, until all four utilizations are
    <= 1.0 (or max_iterations is reached):

    - NFA failing low (too soft): increase diameter first -- D is the
      dominant lever for both foundation stiffness and frequency (it raises
      EI ~D^4 and K_L/K_R), more effective than embedded length.
    - ULS/FLS failing: increase wall thickness, unless thickness is already
      capped at dt_ratio_min (thickest allowed wall), in which case fall
      back to increasing diameter.
    - SLS failing: increase diameter (stiffens the foundation, reduces
      mudline rotation).
    - NFA failing high (too stiff, uncommon for monopiles): reduce diameter.
    """
    turbine = turbine_from_capacity(inputs.turbine_mw)
    geometry = _initial_geometry(inputs, turbine)

    d_step_m = 0.15
    t_step_m = 0.002

    def _clamped(geom: MonopileGeometry) -> MonopileGeometry:
        d, t, l = geom.diameter_m, geom.wall_thickness_m, geom.embedded_length_m
        dt_ratio = d / t
        if dt_ratio < inputs.dt_ratio_min:
            t = d / inputs.dt_ratio_min
        elif dt_ratio > inputs.dt_ratio_max:
            t = d / inputs.dt_ratio_max
        l_over_d = l / d
        if l_over_d < inputs.l_over_d_min:
            l = inputs.l_over_d_min * d
        elif l_over_d > inputs.l_over_d_max:
            l = inputs.l_over_d_max * d
        return MonopileGeometry(d, t, l)

    d_runaway_cap_m = 3.0 * geometry.diameter_m  # if this is exceeded, D is not resolving the failing check(s)

    result = evaluate_monopile(inputs, geometry)
    converged = False
    for _ in range(max_iterations):
        checks = {
            "ULS": result.uls_utilization,
            "SLS": result.sls_utilization,
            "NFA": result.nfa_utilization,
            "FLS": result.fls_utilization,
        }
        if all(u <= 1.0 for u in checks.values()):
            converged = True
            break

        if geometry.diameter_m >= d_runaway_cap_m:
            break

        dt_ratio = geometry.diameter_m / geometry.wall_thickness_m
        t_capped = dt_ratio <= inputs.dt_ratio_min + 1e-9
        nfa_too_soft = checks["NFA"] > 1.0 and result.natural_frequency_hz < result.soft_stiff_band_hz[0]

        if nfa_too_soft:
            geometry = MonopileGeometry(geometry.diameter_m + d_step_m, geometry.wall_thickness_m, geometry.embedded_length_m)
        elif (checks["ULS"] > 1.0 or checks["FLS"] > 1.0) and not t_capped:
            geometry = MonopileGeometry(geometry.diameter_m, geometry.wall_thickness_m + t_step_m, geometry.embedded_length_m)
        elif checks["ULS"] > 1.0 or checks["FLS"] > 1.0 or checks["SLS"] > 1.0:
            geometry = MonopileGeometry(geometry.diameter_m + d_step_m, geometry.wall_thickness_m, geometry.embedded_length_m)
        elif checks["NFA"] > 1.0:
            geometry = MonopileGeometry(max(geometry.diameter_m - d_step_m, 0.1), geometry.wall_thickness_m, geometry.embedded_length_m)

        geometry = _clamped(geometry)
        result = evaluate_monopile(inputs, geometry)

    if not converged:
        result.notes.append(
            "size_monopile did not converge: increasing diameter/thickness/length "
            "within the configured bounds did not clear all four checks. This "
            "usually means a check is dominated by an input outside the pile "
            "geometry (e.g. tower stiffness for NFA) -- review DesignInputs "
            "rather than relaxing the D/t or L/D bounds."
        )
    return result


def result_as_dict(result: MonopileResult) -> dict:
    return asdict(result)
