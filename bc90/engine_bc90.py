"""
BC90 concept design engine: taut-mooring-supported monopile extension.

Extends engine.py's evaluate_monopile with the mooring effects derived in
docs/BC90_METHODOLOGY_REPORT.md. engine.py / app.py are NOT modified --
this module imports and reuses engine.py's turbine lookup, extreme-load,
soil-stiffness, and ULS/SLS/FLS/buckling formulas unchanged (Sections 2, 3,
4, 5, 6, 8 of the methodology report all say "no equation change"), and adds
only what the report identifies as new:
  - single-line and 3-line mooring stiffness / vertical force (bc90/mooring.py)
  - the redundant-force solve for the net mooring reaction and the resulting
    M_char_net / V_char_net / M_fl (Section 4c)
  - the corrected NFA flexibility term (Section 7)
  - the axial-load addition to local shell buckling (Section 5a)
  - two checks with no baseline equivalent at all: mooring-line ULS and the
    line-slack/minimum-tension check (Section 5, Section 9a)

Explicit scope limits (see docs/BC90_METHODOLOGY_REPORT.md for why each of
these is flagged as an open decision, not defaulted silently):
  - Only evaluate_bc90() is implemented here (the per-candidate check, the
    BC90 analog of engine.py's evaluate_monopile). There is no size_bc90()
    auto-iteration loop yet -- Section 0 proposes pile-geometry and
    mooring-layout loops as NESTED, and Section 9a's mooring initial-guess
    heuristics (sizing K_ml to just clear NFA, T0 from worst-case tension)
    require judgment calls this module does not make on its own.
  - The mooring-line-loss ALS case (Section 5, "mooring as redundant assist"
    vs. "mooring as load-bearing") is NOT implemented. This module computes
    M_char_net/V_char_net assuming all 3 lines are intact and in tension
    (philosophy 2, load-bearing) -- it does not re-check ULS/buckling with
    F_ml=0 or 2 lines. That re-check is required before this is used beyond
    a first internal pass, per the methodology report Section 5.
  - Valid only while every mooring line remains in tension (Section 9a,
    Assumption 2). The slack check below flags a violation; it does not
    correct the linear derivation for it (that would need a nonlinear,
    tension-only line model, out of scope here).
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass, field, asdict

from engine import (
    DesignInputs,
    MonopileGeometry,
    STEEL_DENSITY_T_PER_M3,
    USD_PER_T_STEEL,
    GAMMA_F_ULS,
    turbine_from_capacity,
    most_restrictive_constraint,
    _pile_section_properties,
    _extreme_loads,
    _soil_stiffness,
    _uls_check,
    _sls_check,
    _natural_frequency,
    _fls_check,
    _axial_load_estimate,
    _shell_buckling_check,
)
from bc90.mooring import (
    MooringLayout,
    N_ML,
    line_geometry,
    single_line_horizontal_stiffness,
    net_horizontal_stiffness,
    net_horizontal_stiffness_dynamic,
    vertical_mooring_force,
    pile_flexibility,
    solve_mooring_reaction,
    net_mudline_loads,
    nfa_flexibility_correction,
)

# ---------------------------------------------------------------------------
# New BC90 constants (docs/BC90_METHODOLOGY_REPORT.md Section 1).
# All four are flagged, unsourced placeholders in the methodology report --
# not verified against DNV-OS-E301's actual tables in that research session.
# Treat exactly like the baseline's own documented-provenance placeholders
# (e.g. FATIGUE_LOAD_FACTOR before its calibration sweep); recalibrate before
# using beyond concept screening.
# ---------------------------------------------------------------------------
GAMMA_ML_ULS = 1.75              # partial factor on mooring line tension, DNV-OS-E301-style
T_MIN_FRACTION = 0.05             # minimum allowable tension as a fraction of T0 (slack margin)
USD_PER_M_MOORING_LINE = 500.0    # mooring line unit cost, fallback placeholder used only when
                                   # mooring.mbl_mn is unset -- see polyester_cost_per_m_usd below
                                   # for the sourced, MBL-dependent replacement used otherwise.
USD_PER_ANCHOR = 250_000.0        # anchor unit cost, placeholder (does not model holding-capacity dependence)

# Polyester mooring line cost vs. MBL, sourced 2026-07-24 (docs/
# mooring_line_database.md Section 10a): Striani et al. 2025 (J. Mar. Sci.
# Eng. 13(12), 2341), Eq. (2): C = (0.0138*MBL_kN + 11.281)*L_m [EUR], i.e.
# cost/m depends only on MBL (L_m cancels). Replaces the flat
# USD_PER_M_MOORING_LINE placeholder above -- that constant significantly
# overstated cost at MBL=15 MN ($500/m vs. the sourced ~$236/m). Floating
# -wind shared-mooring cost model, not BC90-specific -- see the doc for the
# full context caveat.
_POLYESTER_COST_EUR_PER_KN_MBL = 0.0138
_POLYESTER_COST_EUR_INTERCEPT = 11.281
EUR_TO_USD_FX = 1.08              # indicative, unsourced -- order-of-magnitude USD conversion only


def polyester_cost_per_m_usd(mbl_mn: float) -> float:
    """Sourced polyester line cost per meter as a function of MBL (see
    Section 10a citation above). MBL here is in MN (this codebase's
    convention); the source's formula takes kN, hence the *1000."""
    cost_eur_per_m = _POLYESTER_COST_EUR_PER_KN_MBL * (mbl_mn * 1000.0) + _POLYESTER_COST_EUR_INTERCEPT
    return cost_eur_per_m * EUR_TO_USD_FX


@dataclass
class BC90Result:
    geometry: MonopileGeometry
    mooring: MooringLayout

    # Mooring geometry, derived (Section 4a)
    theta_deg: float
    l_ml_m: float
    k_ml_net_mn_per_m: float             # quasi-static, used for Section 4c/ULS/mooring-ULS/slack
    k_ml_net_dynamic_mn_per_m: float      # dynamic/storm, used for NFA only (Section 7)

    # Net mudline / fairlead loads after the mooring reaction (Section 4c)
    m_char_mnm: float          # pre-mooring characteristic mudline moment (Section 3, unchanged)
    v_char_mn: float           # pre-mooring characteristic mudline shear (Section 3, unchanged)
    delta_fl0_m: float          # unrestrained (no-mooring) fairlead deflection under thrust+wave, Section 4c
    f_ml_mn: float             # net mooring reaction at the fairlead
    m_char_net_mnm: float
    v_char_net_mn: float
    m_fl_mnm: float

    # Six checks (five baseline + mooring ULS), utilization > 1.0 = fail
    uls_mudline_utilization: float
    uls_fairlead_utilization: float
    uls_utilization: float     # governing = worse of the two sections above
    sls_rotation_deg: float
    sls_utilization: float
    natural_frequency_hz: float
    soft_stiff_band_hz: tuple[float, float]
    nfa_utilization: float
    fls_damage: float
    fls_utilization: float
    axial_load_mn: float        # baseline self-weight axial + mooring vertical component
    buckling_utilization: float
    mooring_t_max_mn: float
    mbl_required_mn: float
    mooring_uls_utilization: float | None   # None if mooring.mbl_mn not supplied
    mooring_t_min_mn: float
    slack_utilization: float

    steel_mass_t: float
    steel_cost_usd: float
    mooring_line_cost_usd: float
    anchor_cost_usd: float
    total_capex_usd: float

    margins: dict[str, float]
    governing_constraint: str
    notes: list[str] = field(default_factory=list)


def evaluate_bc90(inputs: DesignInputs, geometry: MonopileGeometry, mooring: MooringLayout,
                   cos_phi_worst: float = 1.0) -> BC90Result:
    """BC90 analog of engine.py's evaluate_monopile: one candidate pile
    geometry + mooring layout, all six utilizations.

    cos_phi_worst: worst-heading single-line tension factor (Section 4b),
    ranges 0.5-1.0 depending on load heading relative to the fixed line
    azimuths. Defaults to the conservative 1.0 recommended for concept
    screening (Section 5) unless the mooring layout is deliberately oriented
    relative to a known dominant load heading.
    """
    notes: list[str] = []
    turbine = turbine_from_capacity(inputs.turbine_mw)
    _, _, ei_pile_mnm2 = _pile_section_properties(geometry)

    k_lateral, k_rocking, beta, soil_notes = _soil_stiffness(inputs.soil, geometry, ei_pile_mnm2)
    k_line_mn_m2 = k_lateral * beta
    notes.extend(soil_notes)

    # --- Section 3: pre-mooring extreme mudline loads, unchanged equations ---
    m_char_mnm, v_char_mn = _extreme_loads(inputs, geometry, turbine)

    # Thrust/wave load-height breakdown, needed for the Section 4c flexibility
    # integral (delta_fl,0). Derived algebraically from the combined
    # _extreme_loads() output rather than re-integrating the Morison load --
    # avoids duplicating that numerical integration a second time.
    hub_height_above_mudline_m = turbine["hub_height_m"] + inputs.water_depth_m
    f_thrust_mn = turbine["thrust_mn"]
    m_thrust_mnm = f_thrust_mn * hub_height_above_mudline_m
    f_wave_mn = v_char_mn - f_thrust_mn
    m_wave_mnm = m_char_mnm - m_thrust_mnm
    z_wave_eq_m = m_wave_mnm / f_wave_mn if f_wave_mn else 0.0

    # --- Section 4a/4b: mooring geometry and net (isotropic) group stiffness ---
    theta_rad, l_ml_m = line_geometry(mooring)
    k_ml_net = net_horizontal_stiffness(mooring)

    pile_above_mudline_m = inputs.water_depth_m + turbine["transition_piece_height_m"]
    if mooring.d_sb_fl_m > pile_above_mudline_m:
        notes.append(
            "d_sb_fl exceeds pile-above-mudline height: fairlead is modeled as "
            "sitting on the tower, not the monopile shaft. The single-EI "
            "flexibility formulas below (Section 4c) assume the fairlead is "
            "within the pile's own EI and are not valid in this regime."
        )
    if mooring.d_sb_fl_m > z_wave_eq_m:
        notes.append(
            "d_sb_fl > z_wave_eq: the fairlead-section moment M_fl approximation "
            "(loads-above-fairlead only, Section 4c) assumes the wave-load "
            "resultant acts above the fairlead. Re-derive M_fl directly from the "
            "load distribution before trusting this value."
        )

    # --- Section 4c: redundant-force solve for the net mooring reaction ---
    f_aa = pile_flexibility(mooring.d_sb_fl_m, mooring.d_sb_fl_m, k_lateral, k_rocking, ei_pile_mnm2)
    f_a_thrust = pile_flexibility(mooring.d_sb_fl_m, hub_height_above_mudline_m, k_lateral, k_rocking, ei_pile_mnm2)
    f_a_wave = pile_flexibility(mooring.d_sb_fl_m, z_wave_eq_m, k_lateral, k_rocking, ei_pile_mnm2)
    delta_fl0_m = f_thrust_mn * f_a_thrust + f_wave_mn * f_a_wave

    f_ml_mn = solve_mooring_reaction(delta_fl0_m, f_aa, k_ml_net)
    m_char_net_mnm, v_char_net_mn, m_fl_mnm = net_mudline_loads(m_char_mnm, v_char_mn, f_ml_mn, mooring.d_sb_fl_m)
    if abs(m_char_net_mnm) >= abs(m_char_mnm):
        notes.append(
            "M_char_net did not reduce relative to M_char: the naive "
            "M_char - F_ml*d_sb_fl subtraction is not guaranteed to be a "
            "benign reduction (Section 4c) -- verify sign/magnitude for this "
            "geometry/mooring combination before using it."
        )

    # --- Section 5: ULS at both mudline (net loads) and fairlead (M_fl) ---
    uls_mudline = _uls_check(geometry, m_char_net_mnm, v_char_net_mn)
    # V at the fairlead cut is V_char (unfactored-original), not V_char_net --
    # the mooring reaction acts at the fairlead itself, so a cut immediately
    # above it has not yet "seen" the reaction (Section 5).
    uls_fairlead = _uls_check(geometry, m_fl_mnm, v_char_mn)
    uls_utilization = max(uls_mudline, uls_fairlead)

    # --- Section 6: SLS, net loads, unchanged Hetenyi rotation formula ---
    sls_rotation_deg, sls_utilization = _sls_check(inputs, m_char_net_mnm, v_char_net_mn, k_line_mn_m2, beta)

    # --- Section 7: NFA, corrected flexibility ---
    # engine.py's _natural_frequency doesn't expose EI_pile/m_eff/tower-split
    # internals needed for the flexibility correction, so f_hh and m_eff are
    # recovered/recomputed here rather than modifying engine.py. m_eff_kg
    # duplicates engine.py's own (undocumented-as-a-constant) 0.5/0.5 RNA
    # -tower split formula verbatim -- if that formula changes in engine.py,
    # this must be updated to match (drift risk of extending via wrapper
    # instead of modifying the source, accepted per this phase's scope to
    # keep engine.py untouched).
    f0_baseline_hz, band_hz, _nfa_util_baseline, nfa_notes = _natural_frequency(
        inputs, geometry, turbine, k_lateral, k_rocking
    )
    notes.extend(nfa_notes)
    total_mass_t = turbine["mass_t"]
    m_eff_kg = (0.5 * total_mass_t + 0.25 * (0.5 * total_mass_t)) * 1000.0
    k_eq_baseline_n_per_m = (2 * math.pi * f0_baseline_hz) ** 2 * m_eff_kg
    f_hh = 1.0 / (k_eq_baseline_n_per_m / 1e6)   # N/m -> MN/m

    # NFA uses the DYNAMIC line stiffness (falls back to k_ml_net if no
    # separate dynamic value was given) -- Section 7 flags this distinction
    # explicitly: NFA is a cyclic/dynamic phenomenon, so it should not reuse
    # the same quasi-static K_ml the static Section 4c reaction/ULS/slack
    # checks use.
    f_ha = pile_flexibility(mooring.d_sb_fl_m, hub_height_above_mudline_m, k_lateral, k_rocking, ei_pile_mnm2)
    k_ml_net_dynamic = net_horizontal_stiffness_dynamic(mooring)
    f_total = nfa_flexibility_correction(f_hh, f_ha, f_aa, k_ml_net_dynamic)
    k_eq_bc90_n_per_m = (1.0 / f_total) * 1e6
    f0_hz = (1.0 / (2 * math.pi)) * math.sqrt(k_eq_bc90_n_per_m / m_eff_kg)

    band_low_hz, band_high_hz = band_hz
    if f0_hz < band_low_hz:
        nfa_utilization = band_low_hz / f0_hz
    elif f0_hz > band_high_hz:
        nfa_utilization = f0_hz / band_high_hz
    else:
        nfa_utilization = max(band_low_hz / f0_hz, f0_hz / band_high_hz)

    # --- Section 8: FLS, net loads, unchanged Palmgren-Miner formula ---
    fls_damage, fls_utilization = _fls_check(inputs, geometry, turbine, m_char_net_mnm)

    # --- Section 5a: buckling, with the vertical mooring force added to axial load ---
    axial_load_baseline_mn = _axial_load_estimate(inputs, geometry, turbine)
    f_z_vertical_mn = vertical_mooring_force(mooring)
    axial_load_mn = axial_load_baseline_mn + f_z_vertical_mn
    l_panel_m = inputs.water_depth_m + turbine["transition_piece_height_m"]
    buckling_utilization = _shell_buckling_check(
        geometry, l_panel_m, m_char_net_mnm, v_char_net_mn, inputs.water_depth_m, axial_load_mn
    )

    # --- Section 5/9a: mooring-line ULS and slack check (no baseline equivalent) ---
    disp_fl_char_m = delta_fl0_m - f_aa * f_ml_mn
    disp_fl_uls_m = GAMMA_F_ULS * disp_fl_char_m
    k_single = single_line_horizontal_stiffness(mooring)  # not used directly; kept for reference/reuse
    delta_t_max_mn = mooring.k_ml_mn_per_m * math.cos(theta_rad) * abs(disp_fl_uls_m) * cos_phi_worst
    mooring_t_max_mn = mooring.t0_mn + delta_t_max_mn
    mbl_required_mn = GAMMA_ML_ULS * mooring_t_max_mn

    if mooring.mbl_mn is not None:
        mooring_uls_utilization = GAMMA_ML_ULS * mooring_t_max_mn / mooring.mbl_mn
    else:
        mooring_uls_utilization = None
        notes.append(
            "mooring.mbl_mn not supplied: mooring-line ULS utilization not "
            "computed. Required MBL is reported (mbl_required_mn) -- select a "
            "real line/chain with MBL >= mbl_required_mn and re-run with it set."
        )

    mooring_t_min_mn = mooring.t0_mn - delta_t_max_mn
    slack_threshold_mn = T_MIN_FRACTION * mooring.t0_mn
    if mooring_t_min_mn > 0:
        slack_utilization = slack_threshold_mn / mooring_t_min_mn
    else:
        slack_utilization = float("inf")
        notes.append(
            "Line goes slack (T_min <= 0) under factored/extreme loads: the "
            "entire linear isotropic-group-stiffness derivation (Sections 4b, "
            "4c, 7) stops applying once this happens. F_ml/M_char_net/f0 above "
            "are not valid for this geometry/mooring combination."
        )

    # --- Costs (steel cost reused unchanged; mooring costs are new, unsourced
    # placeholders -- see docs/BC90_METHODOLOGY_REPORT.md Note section for
    # the installation/inspection/OPEX cost categories NOT included here) ---
    d = geometry.diameter_m
    t = geometry.wall_thickness_m
    d_inner = d - 2 * t
    area_m2 = (math.pi / 4) * (d ** 2 - d_inner ** 2)
    steel_mass_t = area_m2 * geometry.embedded_length_m * STEEL_DENSITY_T_PER_M3
    steel_cost_usd = steel_mass_t * USD_PER_T_STEEL

    cost_per_m_usd = polyester_cost_per_m_usd(mooring.mbl_mn) if mooring.mbl_mn is not None else USD_PER_M_MOORING_LINE
    mooring_line_cost_usd = N_ML * l_ml_m * cost_per_m_usd
    anchor_cost_usd = N_ML * USD_PER_ANCHOR
    total_capex_usd = steel_cost_usd + mooring_line_cost_usd + anchor_cost_usd

    margins = {
        "ULS": 1.0 - uls_utilization,
        "SLS": 1.0 - sls_utilization,
        "NFA": 1.0 - nfa_utilization,
        "FLS": 1.0 - fls_utilization,
        "Buckling": 1.0 - buckling_utilization,
        "Slack": 1.0 - slack_utilization,
    }
    if mooring_uls_utilization is not None:
        margins["MooringULS"] = 1.0 - mooring_uls_utilization
    governing, _ = most_restrictive_constraint(margins)

    return BC90Result(
        geometry=geometry,
        mooring=mooring,
        theta_deg=math.degrees(theta_rad),
        l_ml_m=l_ml_m,
        k_ml_net_mn_per_m=k_ml_net,
        k_ml_net_dynamic_mn_per_m=k_ml_net_dynamic,
        m_char_mnm=m_char_mnm,
        v_char_mn=v_char_mn,
        delta_fl0_m=delta_fl0_m,
        f_ml_mn=f_ml_mn,
        m_char_net_mnm=m_char_net_mnm,
        v_char_net_mn=v_char_net_mn,
        m_fl_mnm=m_fl_mnm,
        uls_mudline_utilization=uls_mudline,
        uls_fairlead_utilization=uls_fairlead,
        uls_utilization=uls_utilization,
        sls_rotation_deg=sls_rotation_deg,
        sls_utilization=sls_utilization,
        natural_frequency_hz=f0_hz,
        soft_stiff_band_hz=band_hz,
        nfa_utilization=nfa_utilization,
        fls_damage=fls_damage,
        fls_utilization=fls_utilization,
        axial_load_mn=axial_load_mn,
        buckling_utilization=buckling_utilization,
        mooring_t_max_mn=mooring_t_max_mn,
        mbl_required_mn=mbl_required_mn,
        mooring_uls_utilization=mooring_uls_utilization,
        mooring_t_min_mn=mooring_t_min_mn,
        slack_utilization=slack_utilization,
        steel_mass_t=steel_mass_t,
        steel_cost_usd=steel_cost_usd,
        mooring_line_cost_usd=mooring_line_cost_usd,
        anchor_cost_usd=anchor_cost_usd,
        total_capex_usd=total_capex_usd,
        margins=margins,
        governing_constraint=governing,
        notes=notes,
    )


def result_as_dict(result: BC90Result) -> dict:
    return asdict(result)


def _passes_all_checks(result: BC90Result) -> bool:
    checks = [
        result.uls_utilization, result.sls_utilization, result.nfa_utilization,
        result.fls_utilization, result.buckling_utilization, result.slack_utilization,
    ]
    if result.mooring_uls_utilization is not None:
        checks.append(result.mooring_uls_utilization)
    return all(u <= 1.0 for u in checks)


def shrink_geometry_with_mooring(inputs: DesignInputs, geometry: MonopileGeometry, mooring: MooringLayout,
                                  d_step_m: float = 0.1, t_step_m: float = 0.002,
                                  min_diameter_m: float = 0.5, min_thickness_m: float = 0.001
                                  ) -> tuple[MonopileGeometry, BC90Result, bool]:
    """Greedily shrink diameter, then wall thickness, holding the mooring
    layout fixed, while every BC90 check stays <= 1.0. This is the OUTER
    pile-geometry loop only (Section 0) -- mooring parameters (K_ml, T0,
    R_a, d_sb_fl) are NOT co-optimized here, consistent with this phase's
    nested-loop simplification (mooring sizing per Section 9a is a separate,
    not-yet-automated exercise).

    Diameter is shrunk first because a smaller diameter is exactly what
    mooring is meant to enable (methodology report Section 4, Section 9);
    thickness second, mirroring engine.py's size_monopile's own
    thickness-shrink pass for the same reason (material minimization once
    the checks already pass).

    Not a general optimizer: greedy, single-direction, stops at the first
    geometry that fails a check -- does not backtrack to try, e.g., a larger
    diameter with thinner wall. Returns (geometry, result, started_passing):
    started_passing is False if the INPUT geometry itself already fails a
    BC90 check (nothing was shrunk in that case).
    """
    current = geometry
    current_result = evaluate_bc90(inputs, current, mooring)
    if not _passes_all_checks(current_result):
        return current, current_result, False

    while True:
        smaller = MonopileGeometry(
            max(current.diameter_m - d_step_m, min_diameter_m), current.wall_thickness_m, current.embedded_length_m
        )
        if smaller.diameter_m == current.diameter_m:
            break
        result = evaluate_bc90(inputs, smaller, mooring)
        if _passes_all_checks(result):
            current, current_result = smaller, result
        else:
            break

    while True:
        thinner = MonopileGeometry(
            current.diameter_m, max(current.wall_thickness_m - t_step_m, min_thickness_m), current.embedded_length_m
        )
        if thinner.wall_thickness_m == current.wall_thickness_m:
            break
        result = evaluate_bc90(inputs, thinner, mooring)
        if _passes_all_checks(result):
            current, current_result = thinner, result
        else:
            break

    return current, current_result, True
