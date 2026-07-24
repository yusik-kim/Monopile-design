"""
Monopile Foundation Concept Design Engine v0.1

Implements an Arany-et-al.-style ("10-step") initial sizing loop for offshore
wind monopile foundations: iterate ULS -> SLS -> natural-frequency (soft-stiff)
-> FLS -> local shell buckling using closed-form formulas until a candidate
diameter/wall-thickness/embedded-length converges.

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
- Local shell buckling (added 2026-07-18): DNV-RP-C202 unstiffened-cylinder
  check, using a single panel length equal to the exposed (above-mudline)
  shaft length -- i.e. assuming no ring stiffeners anywhere on the pile. See
  _shell_buckling_check for why, and for what this replaced.
Each simplification is called out at its function. Treat outputs as a
starting point for detailed design / PISA-based or FE validation, not a
substitute for it -- see docs/Monopile_Initial_Design_Method_Summary.md and
docs/METHODOLOGY_REPORT.md for the full equations/constants/assumptions, and
docs/method_update_log.md for the dated history of how they were chosen.
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
STEEL_POISSON_RATIO = 0.3        # used only by the shell buckling check
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
# bending stress. Revised again 2026-07-18: with the local shell buckling
# check below now active in size_monopile, a sensitivity sweep of FLF from
# 0.25 to 0.60 (step 0.05) against 5/15/22 MW showed the FLS-vs-Buckling
# crossover point itself scales with turbine size (~0.30 for 5MW, ~0.35 for
# 15MW, ~0.55 for 22MW) -- there is no single FLF that makes FLS govern
# uniformly across all three. 0.35 was chosen empirically as the value where:
# (a) FLS governs both 5MW and 15MW (t=64.5mm, 106.9mm), matching the
#     industry expectation that fatigue drives monopile sizing below ~15MW;
# (b) 22MW remains buckling-governed (t=110.4mm) -- treated as consistent
#     with (a) rather than contradicting it, since large turbines are
#     expected to behave differently;
# (c) resulting thicknesses land close to the real reference designs once
#     buckling is included: 64.5mm vs. the real OC3 5MW's 60mm, and 110.4mm
#     vs. the real IEA 22MW's 100mm -- both within ~10%.
# Still ad-hoc and not derived from a real DLC/rainflow spectrum; recalibrate
# once the model has real turbine fatigue load data. See docs/method_update_log.md
# (2026-07-18) for the full sensitivity sweep table.
FATIGUE_LOAD_FACTOR = 0.35

# Reference turbines: mass_t is total turbine mass (RNA + tower); thrust_mn is
# the extreme/ultimate design rotor thrust used directly as the ULS
# characteristic wind load. 5/10/15/22 MW entries are sourced directly from
# published reference-turbine reports (see docs/method_update_log.md, 2026-07-16);
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
#   transition_piece_height_m: height of the tower base (monopile/tower
#   interface) above MSL. Sourced for 5/15/22 MW (OC3: 10m; IEA 15/22MW: 15m
#   each, stated directly in their reports); 10MW is assumed (not stated in
#   the DTU 10MW turbine-only report, which doesn't cover the support
#   structure) equal to the more common 15m value; 25MW extrapolated/assumed.
TURBINE_LIBRARY = [
    {"mw": 5.0,  "rotor_diameter_m": 126.0, "hub_height_m": 90.0,  "mass_t": 697.5,  "thrust_mn": 0.80,  "rpm_min": 6.90,  "rpm_max": 12.10, "transition_piece_height_m": 10.0},
    {"mw": 10.0, "rotor_diameter_m": 178.3, "hub_height_m": 119.0, "mass_t": 1280.0, "thrust_mn": 1.50,  "rpm_min": 6.00,  "rpm_max": 9.60,  "transition_piece_height_m": 15.0},
    {"mw": 15.0, "rotor_diameter_m": 240.0, "hub_height_m": 150.0, "mass_t": 1877.0, "thrust_mn": 2.50,  "rpm_min": 5.00,  "rpm_max": 7.56,  "transition_piece_height_m": 15.0},
    {"mw": 22.0, "rotor_diameter_m": 284.0, "hub_height_m": 170.0, "mass_t": 2789.6, "thrust_mn": 2.793, "rpm_min": 1.807, "rpm_max": 7.061, "transition_piece_height_m": 15.0},
    # Extrapolated (NOT a verified reference turbine) -- linear continuation
    # of the 15->22 MW trend for each column. rpm_min in particular drops
    # very steeply between 15 and 22 MW in the real data (5.00 -> 1.807);
    # extrapolating that trend further is the least-certain figure here.
    {"mw": 25.0, "rotor_diameter_m": 303.0, "hub_height_m": 179.0, "mass_t": 3181.0, "thrust_mn": 2.92,  "rpm_min": 0.44,  "rpm_max": 6.85,  "transition_piece_height_m": 15.0},
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
    l_over_d_max: float = 12.0
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
    buckling_utilization: float
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

    NOTE on embedded length L: K_L/K_R below are pile-HEAD STIFFNESS terms
    only, from the classical semi-infinite-beam solution -- by construction
    they have no L dependence for clay (k_soil is constant with depth, so
    k_line/beta/K_L/K_R never see L at all) and only a weak one for sand (via
    z_ref = L/3). This is mathematically correct for that closed-form
    solution once beta*L clears the validity threshold checked below, but it
    means this function alone can never be the reason embedment length grows
    with moment/water depth -- that would require a separate ULTIMATE
    lateral/moment soil CAPACITY check (e.g. Broms' method, or integrating
    ultimate p-y resistance over depth), which does not exist yet in this
    engine. FUTURE WORK: add such a capacity check and use it to drive L in
    size_monopile, instead of L only ever moving as a side effect of the
    L/D clamp on D (see docs/METHODOLOGY_REPORT.md Section 11 item 21 and
    docs/method_update_log.md).
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
                        k_lateral_mn_per_m: float, k_rocking_mnm_per_rad: float) -> tuple[float, tuple[float, float], float, list[str]]:
    """Simplified 2-spring (K_L, K_R) flexibility-superposition first-mode
    natural frequency: a two-segment cantilever (stiff pile-above-mudline
    segment + more flexible tower segment above the transition piece), tip
    mass = RNA + tower participation, on a flexible (translating + rotating)
    foundation. Omits the K_LM cross-coupling term that Arany's full
    3-spring model includes -- a documented concept-stage simplification.

    The cantilever is split at the transition piece rather than treated as
    one uniform "average tower" section over the whole mudline-to-hub span:
    lumping the much stiffer pile-above-mudline length in with the tower's
    average EI was found (2026-07-16) to systematically underpredict f0 --
    see docs/method_update_log.md.
    """
    d_avg, t_avg = _tower_geometry(inputs, turbine)
    d_inner = d_avg - 2 * t_avg
    i_tower = (math.pi / 64) * (d_avg ** 4 - d_inner ** 4)
    ei_tower_mnm2 = STEEL_E_MPA * i_tower

    _, _, ei_pile_mnm2 = _pile_section_properties(geometry)

    h_m = turbine["hub_height_m"] + inputs.water_depth_m
    pile_above_mudline_m = inputs.water_depth_m + turbine["transition_piece_height_m"]
    tower_height_m = h_m - pile_above_mudline_m

    # Two-segment cantilever tip flexibility (virtual work), stiff pile
    # segment (0 to pile_above_mudline_m) + tower segment (to h_m):
    #   flexibility = (h^3 - tower_height^3)/(3*EI_pile) + tower_height^3/(3*EI_tower)
    cantilever_flexibility_m_per_mn = (h_m ** 3 - tower_height_m ** 3) / (3 * ei_pile_mnm2) \
        + (tower_height_m ** 3) / (3 * ei_tower_mnm2)

    flexibility_m_per_mn = cantilever_flexibility_m_per_mn + 1.0 / k_lateral_mn_per_m \
        + (h_m ** 2) / k_rocking_mnm_per_rad
    k_eq_mn_per_m = 1.0 / flexibility_m_per_mn
    k_eq_n_per_m = k_eq_mn_per_m * 1e6

    # RNA/tower split of total mass: real reference turbines range from 43.6%
    # (IEA 22MW) to 54.2% (IEA 15MW) RNA fraction (see docs/method_update_log.md,
    # 2026-07-16); 0.5/0.5 is the average, not a fixed physical ratio.
    total_mass_t = turbine["mass_t"]
    m_rna_t = 0.5 * total_mass_t
    m_tower_t = 0.5 * total_mass_t
    m_eff_kg = (m_rna_t + 0.25 * m_tower_t) * 1000.0

    f0_hz = (1.0 / (2 * math.pi)) * math.sqrt(k_eq_n_per_m / m_eff_kg)

    f_1p_max_hz = turbine["rpm_max"] / 60.0
    f_1p_min_hz = turbine["rpm_min"] / 60.0
    f_3p_min_hz = 3 * f_1p_min_hz
    f_3p_max_hz = 3 * f_1p_max_hz

    notes: list[str] = []
    band_low_hz = f_1p_max_hz * 1.1
    band_high_hz = f_3p_min_hz * 0.9
    if band_high_hz <= band_low_hz:
        # Classical soft-stiff gap (between the top of the 1P band and the
        # bottom of the 3P band) doesn't exist when the rotor-speed range is
        # wide enough that 3*rpm_min < 1.1*rpm_max -- a real trend for very
        # large turbines (see docs/method_update_log.md, 2026-07-16). Fall back to
        # a lower-bound-only criterion (clear 1P at rated), matching e.g. the
        # IEA 22MW reference design's single-sided 0.15 Hz minimum-frequency
        # target; use 3P-at-rated as a loose upper ceiling instead of 3P-at
        # -cut-in, since that no longer meaningfully constrains the design.
        band_high_hz = f_3p_max_hz * 0.9
        notes.append(
            "soft-stiff 1P/3P gap does not exist for this turbine's rotor "
            "-speed range (3*rpm_min < 1.1*rpm_max); falling back to a "
            "lower-bound-only frequency criterion (clear 1P at rated), "
            "matching real large-turbine practice (e.g. IEA 22MW)."
        )

    if f0_hz < band_low_hz:
        nfa_utilization = band_low_hz / f0_hz
    elif f0_hz > band_high_hz:
        nfa_utilization = f0_hz / band_high_hz
    else:
        nfa_utilization = max(band_low_hz / f0_hz, f0_hz / band_high_hz)

    return f0_hz, (band_low_hz, band_high_hz), nfa_utilization, notes


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
# Local shell buckling (DNV-RP-C202, unstiffened cylinder)
# ---------------------------------------------------------------------------
def _axial_load_estimate(inputs: DesignInputs, geometry: MonopileGeometry, turbine: dict) -> float:
    """Rough self-weight estimate (RNA + tower mass, from TURBINE_LIBRARY,
    plus the pile's own steel weight above mudline), used only by the shell
    buckling check below. ULS/SLS/FLS don't need this -- they only combine
    the extreme lateral load's bending and shear, per their own docstrings.
    """
    d = geometry.diameter_m
    t = geometry.wall_thickness_m
    d_inner = d - 2 * t
    area_m2 = (math.pi / 4) * (d ** 2 - d_inner ** 2)
    pile_self_weight_t = area_m2 * inputs.water_depth_m * STEEL_DENSITY_T_PER_M3
    total_weight_t = turbine["mass_t"] + pile_self_weight_t
    return total_weight_t * G / 1000.0  # MN


def _shell_buckling_coefficients(z_batdorf: float, r_m: float, t_m: float) -> tuple[float, float, float]:
    """C coefficients (psi, xi, rho -> C) for an unstiffened cylindrical
    shell under axial/bending, torsion/shear, and lateral (hoop, external
    pressure) buckling -- DNV-RP-C202 Section 3.4, Table 3-2. Cross-checked
    against WISDEM's open-source DNV-RP-C202 implementation
    (wisdem/commonse/utilization_dnvgl.py, CylinderBuckling class).
    """
    def _c(psi: float, xi: float, rho: float) -> float:
        return psi * math.sqrt(1 + (rho * xi / psi) ** 2)

    c_axial_bending = _c(1.0, 0.702 * z_batdorf, 0.5 * (1 + r_m / (150 * t_m)) ** -0.5)
    c_torsion = _c(5.34, 0.856 * z_batdorf ** 0.75, 0.6)
    c_lateral = _c(4.0, 1.04 * math.sqrt(z_batdorf), 0.6)
    return c_axial_bending, c_torsion, c_lateral


def _shell_buckling_check(geometry: MonopileGeometry, l_panel_m: float, m_char_mnm: float,
                           v_char_mn: float, water_depth_m: float, axial_load_mn: float) -> float:
    """DNV-RP-C202 local shell buckling check for an unstiffened cylindrical
    shell -- the thin wall itself rippling under compressive stress, well
    before the material yields (a different failure mode from ULS's yield
    check). Combines axial+bending, hoop (external hydrostatic pressure),
    and shear stress against their own elastic buckling capacities, then
    reduces by a slenderness-dependent material factor.

    l_panel_m ("the panel length"): the spacing between ring stiffeners --
    NOT can-to-can fabrication weld seams, which don't provide the same
    restraint against the buckling mode a dedicated stiffening ring does.
    This model assumes NO ring stiffeners anywhere on the pile (consistent
    with how large modern monopiles are typically detailed -- thickness is
    varied can-by-can instead), so l_panel_m is the full unsupported
    above-mudline shaft length (water depth + freeboard to the transition
    piece); the embedded portion is excluded since soil continuously
    restrains it. See docs/METHODOLOGY_REPORT.md Section 5 for the
    sensitivity analysis behind this choice, and Section 11 item 18 for
    where this replaced "not implemented."

    Before this check existed (through 2026-07-17), size_monopile's 15 MW
    case converged to t~=50mm without ever evaluating buckling -- ULS, SLS,
    NFA, and FLS all had comfortable margin at that thickness, so nothing
    caught that an unstiffened wall this thin, at this pile's proportions,
    fails shell buckling by roughly 2x. Adding this check raises the
    converged wall thickness substantially across every turbine size.
    """
    d = geometry.diameter_m
    t = geometry.wall_thickness_m
    r = d / 2
    d_inner = d - 2 * t
    area_m2 = (math.pi / 4) * (d ** 2 - d_inner ** 2)
    i_second_moment = (math.pi / 64) * (d ** 4 - d_inner ** 4)
    section_modulus_m3 = i_second_moment / r

    m_uls_mnm = GAMMA_F_ULS * m_char_mnm
    v_uls_mn = GAMMA_F_ULS * v_char_mn
    sigma_bending_mpa = m_uls_mnm / section_modulus_m3
    sigma_axial_mpa = axial_load_mn / area_m2
    tau_shear_mpa = v_uls_mn / (0.5 * area_m2)

    p_mpa = (RHO_SEAWATER_KG_M3 * G * water_depth_m) / 1e6
    sigma_hoop_mpa = p_mpa * r / t

    nu = STEEL_POISSON_RATIO
    z_batdorf = (l_panel_m ** 2 / (r * t)) * math.sqrt(1 - nu ** 2)
    c_axial_bending, c_torsion, c_lateral = _shell_buckling_coefficients(z_batdorf, r, t)

    def _f_elastic(c: float) -> float:
        return (c * math.pi ** 2 * STEEL_E_MPA) / (12 * (1 - nu ** 2)) * (t / l_panel_m) ** 2

    fea = _f_elastic(c_axial_bending)   # axial/bending elastic buckling capacity
    fet = _f_elastic(c_torsion)         # shear elastic buckling capacity
    feh = _f_elastic(c_lateral)         # hoop elastic buckling capacity

    # DNV convention: only the compressive part of each stress counts.
    axial_compressive_mpa = abs(min(-(sigma_axial_mpa + sigma_bending_mpa), 0.0))
    hoop_compressive_mpa = abs(min(-sigma_hoop_mpa, 0.0))
    shear_mpa = abs(tau_shear_mpa)

    sigma_vm_mpa = math.sqrt(
        ((axial_compressive_mpa + hoop_compressive_mpa) / 2) ** 2
        + 3 * (((axial_compressive_mpa - hoop_compressive_mpa) / 2) ** 2 + shear_mpa ** 2)
    )

    lambda_s = math.sqrt(
        (STEEL_YIELD_MPA / sigma_vm_mpa)
        * (axial_compressive_mpa / fea + shear_mpa / fet + hoop_compressive_mpa / feh)
    )
    if lambda_s < 0.5:
        gamma_m = 1.15
    elif lambda_s >= 1.0:
        gamma_m = 1.45
    else:
        gamma_m = 0.85 + 0.6 * lambda_s

    fks_mpa = STEEL_YIELD_MPA / math.sqrt(1 + lambda_s ** 4)
    fksd_mpa = fks_mpa / gamma_m
    return sigma_vm_mpa / fksd_mpa


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def _constraint_margins(uls: float, sls: float, nfa: float, fls: float, buckling: float) -> dict[str, float]:
    return {"ULS": 1.0 - uls, "SLS": 1.0 - sls, "NFA": 1.0 - nfa, "FLS": 1.0 - fls, "Buckling": 1.0 - buckling}


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
    f0_hz, band, nfa_utilization, nfa_notes = _natural_frequency(inputs, geometry, turbine, k_lateral, k_rocking)
    fls_damage, fls_utilization = _fls_check(inputs, geometry, turbine, m_mudline_mnm)

    l_panel_m = inputs.water_depth_m + turbine["transition_piece_height_m"]
    axial_load_mn = _axial_load_estimate(inputs, geometry, turbine)
    buckling_utilization = _shell_buckling_check(
        geometry, l_panel_m, m_mudline_mnm, v_mudline_mn, inputs.water_depth_m, axial_load_mn
    )

    margins = _constraint_margins(uls_utilization, sls_utilization, nfa_utilization, fls_utilization, buckling_utilization)
    governing, _ = most_restrictive_constraint(margins)

    d = geometry.diameter_m
    t = geometry.wall_thickness_m
    d_inner = d - 2 * t
    area_m2 = (math.pi / 4) * (d ** 2 - d_inner ** 2)
    steel_mass_t = area_m2 * geometry.embedded_length_m * STEEL_DENSITY_T_PER_M3

    notes = list(soil_notes) + list(nfa_notes)
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
        buckling_utilization=buckling_utilization,
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
    Diameter regressed against two real reference-monopile anchor points
    (6.0 m at 5 MW -- OC3/NREL; 10.0 m at 15 MW -- IEA, see TURBINE_LIBRARY
    sources); embedded length at a fixed L/D=5 rule-of-thumb ratio (not tied
    to l_over_d_min/max); wall thickness at mid-range D/t=110.

    Fixed 2026-07-17: this previously anchored to 7 m at 8 MW / 11 m at 20 MW,
    leftover from the original six-turbine hand-estimated library (8-20 MW)
    that TURBINE_LIBRARY replaced on 2026-07-16 with sourced 5/10/15/22/25 MW
    anchors -- the formula was never updated to match, so it extrapolated
    off turbine data that no longer existed in the code.
    """
    d_initial_m = 6.0 + (10.0 - 6.0) * (turbine["mw"] - 5.0) / (15.0 - 5.0)
    l_initial_m = 5.0 * d_initial_m
    t_initial_m = d_initial_m / 110.0
    return MonopileGeometry(diameter_m=d_initial_m, wall_thickness_m=t_initial_m, embedded_length_m=l_initial_m)


def size_monopile(inputs: DesignInputs, max_iterations: int = 500) -> MonopileResult:
    """Arany-style step-wise iteration, adjusting whichever dimension is most
    effective for the worst-failing check, until all five utilizations are
    <= 1.0 (or max_iterations is reached):

    - NFA failing low (too soft): increase diameter first -- D is the
      dominant lever for both foundation stiffness and frequency (it raises
      EI ~D^4 and K_L/K_R), more effective than embedded length.
    - ULS/FLS/Buckling failing: increase wall thickness. Buckling behaves
      like ULS/FLS here -- more wall thickness directly increases its
      elastic buckling capacity (see _shell_buckling_check).
    - SLS failing: increase diameter (stiffens the foundation, reduces
      mudline rotation).
    - NFA failing high (too stiff, uncommon for monopiles): reduce diameter,
      but not past the point where the smaller diameter would itself violate
      ULS/FLS/Buckling capacity at the current wall thickness -- see the
      guard in the NFA-too-stiff branch below.

    NOTE: embedded length L is never an independently-adjusted lever above --
    none of the five branches touch it directly. L starts at L0=5*D0 (see
    _initial_geometry) and afterward only changes as a passive side effect
    of the L/D clamp reacting to D. This means e.g. a larger mudline moment
    from deeper water never directly grows embedment, only diameter/
    thickness. That's consistent with the current model: there is no
    ultimate lateral/moment soil CAPACITY check (e.g. Broms' method) that
    would give L a load-driven reason to grow -- see the NOTE in
    _soil_stiffness for why the existing stiffness-based checks (SLS/NFA)
    can't substitute for one, especially for clay. FUTURE WORK: implement
    such a capacity check and wire a "capacity failing -> increase L" branch
    into the loop below (see docs/METHODOLOGY_REPORT.md Section 11 item 21
    and docs/method_update_log.md).

    dt_ratio_min/max are advisory, not a hard search bound (see docs/
    method_update_log.md): wall thickness is free to grow or shrink past
    them if that's what the physics checks demand, and the final geometry
    is flagged with a manufacturability warning note if it ends up outside
    that range -- rather than the search silently clamping thickness back
    to the boundary, which was found to distort results (converged geometries
    landing exactly at dt_ratio_max regardless of what the checks needed).
    L/D bounds are still a hard clamp.
    """
    turbine = turbine_from_capacity(inputs.turbine_mw)
    geometry = _initial_geometry(inputs, turbine)

    d_step_m = 0.15
    t_step_m = 0.002
    t_floor_m = 0.001  # absolute sanity floor, not tied to dt_ratio_max

    def _clamped(geom: MonopileGeometry) -> MonopileGeometry:
        d, t, l = geom.diameter_m, geom.wall_thickness_m, geom.embedded_length_m
        l_over_d = l / d
        if l_over_d < inputs.l_over_d_min:
            l = inputs.l_over_d_min * d
        elif l_over_d > inputs.l_over_d_max:
            l = inputs.l_over_d_max * d
        return MonopileGeometry(d, t, l)

    def _note_nfa_stiff_accepted(res: MonopileResult) -> None:
        # Stiff-side NFA (f0 above the band's upper edge, i.e. above 3P
        # minimum) is not normally safety-critical for monopiles -- unlike
        # the too-soft case, it mainly risks resonance with a rarely-hit
        # high-rpm operating point rather than a persistent one. Accept this
        # geometry as final rather than spiraling D/t into an unrealistic
        # ratio just to chase NFA <= 1.0.
        res.notes.append(
            f"NFA utilization {res.nfa_utilization:.3f} > 1.0: natural frequency "
            f"f0={res.natural_frequency_hz:.4f} Hz is above the soft-stiff band's "
            f"upper edge ({res.soft_stiff_band_hz[1]:.4f} Hz, 3P minimum). "
            "Stiff-side exceedance is usually not safety-critical for monopiles, "
            "so this geometry is accepted as the final design despite NFA > 1.0."
        )

    d_runaway_cap_m = 3.0 * geometry.diameter_m  # if this is exceeded, D is not resolving the failing check(s)

    result = evaluate_monopile(inputs, geometry)
    converged = False
    for _ in range(max_iterations):
        checks = {
            "ULS": result.uls_utilization,
            "SLS": result.sls_utilization,
            "NFA": result.nfa_utilization,
            "FLS": result.fls_utilization,
            "Buckling": result.buckling_utilization,
        }
        if all(u <= 1.0 for u in checks.values()):
            converged = True
            break

        if geometry.diameter_m >= d_runaway_cap_m:
            break

        nfa_too_soft = checks["NFA"] > 1.0 and result.natural_frequency_hz < result.soft_stiff_band_hz[0]

        if nfa_too_soft:
            geometry = MonopileGeometry(geometry.diameter_m + d_step_m, geometry.wall_thickness_m, geometry.embedded_length_m)
        elif checks["ULS"] > 1.0 or checks["FLS"] > 1.0 or checks["Buckling"] > 1.0:
            geometry = MonopileGeometry(geometry.diameter_m, geometry.wall_thickness_m + t_step_m, geometry.embedded_length_m)
        elif checks["SLS"] > 1.0:
            geometry = MonopileGeometry(geometry.diameter_m + d_step_m, geometry.wall_thickness_m, geometry.embedded_length_m)
        elif checks["NFA"] > 1.0:
            nfa_too_stiff = result.natural_frequency_hz > result.soft_stiff_band_hz[1]
            trial = _clamped(MonopileGeometry(
                max(geometry.diameter_m - d_step_m, 0.1), geometry.wall_thickness_m, geometry.embedded_length_m
            ))
            if trial.diameter_m == geometry.diameter_m:
                # Already at the diameter floor, nothing left to try.
                if nfa_too_stiff:
                    _note_nfa_stiff_accepted(result)
                    converged = True
                break
            trial_result = evaluate_monopile(inputs, trial)
            if (trial_result.uls_utilization > 1.0 or trial_result.fls_utilization > 1.0
                    or trial_result.buckling_utilization > 1.0):
                # Shrinking D further to relieve an NFA-too-stiff reading would
                # itself break ULS/FLS/Buckling capacity at the current wall
                # thickness. This heuristic has no other lever for NFA-too-
                # stiff (see docstring), so stop here rather than spiral into
                # a shrink-D/grow-t tug-of-war that lands on an unrealistic
                # D/t ratio. If it's specifically the stiff-side case, that's
                # usually not safety-critical, so accept the geometry instead
                # of flagging non-convergence.
                if nfa_too_stiff:
                    _note_nfa_stiff_accepted(result)
                    converged = True
                break
            geometry, result = trial, trial_result
            continue

        geometry = _clamped(geometry)
        result = evaluate_monopile(inputs, geometry)

    if converged:
        # Shrink diameter step-wise (holding wall thickness fixed) while every
        # check stays <= 1.0. The growth loop above only ever adds diameter
        # (never shrinks it) and stops at the first passing geometry, so it
        # can converge with real diameter headroom left on the table -- the
        # same class of gap the thickness-shrink step below already existed
        # to close for wall thickness. bc90/engine_bc90.py's
        # shrink_geometry_with_mooring already established this exact pattern
        # (shrink D holding t, then shrink t holding D) for the BC90
        # extension; this applies it to the baseline too.
        #
        # Caveat carried over from the historical reason this was skipped:
        # NFA's f0 prediction is not yet independently verified (see docs/
        # method_update_log.md, "NFA is not yet verified"). Shrinking D
        # relies on whichever check governs at the smaller diameter; if that
        # turns out to be NFA, the result leans on an unverified formula more
        # than a ULS/FLS/Buckling/SLS-governed one would. Flagged in notes
        # below when it applies, rather than silently accepted.
        #
        # This is a FIXED-ORDER greedy search (D fully, then t fully), not a
        # joint optimum -- verified 2026-07-24 (docs/method_update_log.md):
        # for most cases tried, reversing the order or searching jointly
        # lands on the identical geometry (t never has a legal move at any
        # point along the path), but at least one counter-example (22 MW/
        # 34 m) found the reverse order ~2% lighter. Good enough for concept
        # screening; not provably the smallest passing geometry.
        while True:
            smaller_geometry = _clamped(MonopileGeometry(
                max(geometry.diameter_m - d_step_m, 0.1), geometry.wall_thickness_m, geometry.embedded_length_m
            ))
            if smaller_geometry.diameter_m == geometry.diameter_m:
                break
            smaller_result = evaluate_monopile(inputs, smaller_geometry)
            smaller_checks = (
                smaller_result.uls_utilization,
                smaller_result.sls_utilization,
                smaller_result.nfa_utilization,
                smaller_result.fls_utilization,
                smaller_result.buckling_utilization,
            )
            if all(u <= 1.0 for u in smaller_checks):
                geometry, result = smaller_geometry, smaller_result
            else:
                break

        if result.governing_constraint == "NFA":
            result.notes.append(
                "Diameter shrink stopped with NFA as the governing constraint, "
                "which is not yet independently verified (see docs/"
                "method_update_log.md) -- treat this diameter with more "
                "caution than one stopped by ULS/FLS/Buckling/SLS."
            )

        # The growth loop above only ever adds material and stops at the
        # first passing geometry -- if the initial guess (t0 = D/110)
        # already satisfies every check, it never runs at all, leaving
        # wall thickness at that guess regardless of how much margin FLS/ULS
        # actually have. Shrink thickness step-wise while every check stays
        # <= 1.0, so the result reflects the true minimum-material thickness
        # rather than just "the first geometry checked that happened to
        # pass," at the now diameter-minimized geometry above.
        while True:
            t_thinner_m = max(geometry.wall_thickness_m - t_step_m, t_floor_m)
            if t_thinner_m >= geometry.wall_thickness_m:
                break
            thinner_geometry = MonopileGeometry(geometry.diameter_m, t_thinner_m, geometry.embedded_length_m)
            thinner_result = evaluate_monopile(inputs, thinner_geometry)
            thinner_checks = (
                thinner_result.uls_utilization,
                thinner_result.sls_utilization,
                thinner_result.nfa_utilization,
                thinner_result.fls_utilization,
                thinner_result.buckling_utilization,
            )
            if all(u <= 1.0 for u in thinner_checks):
                geometry, result = thinner_geometry, thinner_result
            else:
                break

    dt_ratio_final = geometry.diameter_m / geometry.wall_thickness_m
    if dt_ratio_final < inputs.dt_ratio_min or dt_ratio_final > inputs.dt_ratio_max:
        result.notes.append(
            f"D/t = {dt_ratio_final:.0f} is beyond general manufacturability "
            f"requirements ({inputs.dt_ratio_min:.0f} < D/t < {inputs.dt_ratio_max:.0f})."
        )

    if not converged:
        result.notes.append(
            "size_monopile did not converge: increasing diameter/thickness/length "
            "did not clear all five checks within max_iterations. This usually "
            "means a check is dominated by an input outside the pile geometry "
            "(e.g. tower stiffness for NFA) -- review DesignInputs."
        )
    return result


def result_as_dict(result: MonopileResult) -> dict:
    return asdict(result)
