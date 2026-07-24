"""
Light, dependency-free sanity check for bc90/engine_bc90.py. Run directly:

    python bc90/misc/test_engine_bc90.py

No pytest/GUI required, matching test_engine.py / bc90/misc/test_mooring.py.
These checks are the properties docs/BC90_METHODOLOGY_REPORT.md derives as
UNCONDITIONAL (must hold for any valid geometry/mooring combination, not just
this one) -- they are not regression numbers against a specific reference
design, since no BC90 reference design exists yet (methodology report,
Section 10).
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from engine import DesignInputs, SoilProfile, MonopileGeometry, size_monopile, _natural_frequency, \
    _axial_load_estimate, _shell_buckling_check, turbine_from_capacity, _pile_section_properties, \
    _soil_stiffness
from bc90.engine_bc90 import evaluate_bc90
from bc90.mooring import MooringLayout


def _bc90_inputs_and_geometry():
    """15 MW turbine at 70 m water depth (BC90's 60-90 m target range), sized
    first WITHOUT mooring via the baseline's own size_monopile, then reused
    as the candidate geometry for the BC90 mooring evaluation -- i.e. "how
    much does mooring help/hurt a geometry the baseline alone would pick.\""""
    soil = SoilProfile(soil_type="sand", friction_angle_deg=34.0, submerged_unit_weight_kn_m3=10.0)
    inputs = DesignInputs(turbine_mw=15.0, water_depth_m=70.0, soil=soil, hs_m=5.0, tp_s=9.0, current_m_s=0.4)
    baseline_result = size_monopile(inputs)
    return inputs, baseline_result.geometry


def check_nfa_always_stiffens():
    """Section 7: f_total < f_hh unconditionally (mooring is a restoring
    spring in tension), so BC90's f0 must exceed the baseline's own f0 at
    the SAME geometry, for any valid (in-tension) mooring layout."""
    print("Check: NFA -- mooring must raise f0 relative to no-mooring baseline")
    inputs, geometry = _bc90_inputs_and_geometry()
    turbine = turbine_from_capacity(inputs.turbine_mw)
    _, _, ei_pile = _pile_section_properties(geometry)
    k_lateral, k_rocking, beta, _ = _soil_stiffness(inputs.soil, geometry, ei_pile)
    f0_baseline_hz, _, _, _ = _natural_frequency(inputs, geometry, turbine, k_lateral, k_rocking)

    mooring = MooringLayout(r_a_m=90.0, d_sb_fl_m=30.0, k_ml_mn_per_m=20.0, t0_mn=6.0)
    result = evaluate_bc90(inputs, geometry, mooring)

    assert result.natural_frequency_hz > f0_baseline_hz, (
        f"BC90 f0={result.natural_frequency_hz:.4f} Hz must exceed baseline "
        f"f0={f0_baseline_hz:.4f} Hz -- mooring should always stiffen, never soften"
    )
    print(f"  f0_baseline={f0_baseline_hz:.4f} Hz  f0_bc90={result.natural_frequency_hz:.4f} Hz  PASS\n")


def check_buckling_axial_always_worsens():
    """Section 5a: the vertical mooring force (3*T0*sin(theta)) only adds
    compression, so BC90's axial load (and hence buckling utilization, for
    fixed bending/shear demand) must be >= the baseline's axial-only value."""
    print("Check: buckling -- mooring must add axial compression, not remove it")
    inputs, geometry = _bc90_inputs_and_geometry()
    turbine = turbine_from_capacity(inputs.turbine_mw)
    axial_baseline_mn = _axial_load_estimate(inputs, geometry, turbine)

    mooring = MooringLayout(r_a_m=90.0, d_sb_fl_m=30.0, k_ml_mn_per_m=20.0, t0_mn=6.0)
    result = evaluate_bc90(inputs, geometry, mooring)

    assert result.axial_load_mn > axial_baseline_mn, "mooring vertical component must add to axial load"
    l_panel_m = inputs.water_depth_m + turbine["transition_piece_height_m"]
    # Isolate the axial effect alone: hold M/V fixed at BC90's own (net, reduced)
    # values and swap in the baseline (no mooring vertical force) axial load.
    # This is the unconditional claim -- more axial compression, same M/V,
    # cannot reduce buckling utilization. Comparing against the baseline's own
    # M/V (which also changed) would conflate the axial and M/V effects, which
    # the methodology explicitly says can move in opposite directions.
    buckling_same_mv_baseline_axial = _shell_buckling_check(
        geometry, l_panel_m, result.m_char_net_mnm, result.v_char_net_mn, inputs.water_depth_m, axial_baseline_mn
    )
    assert result.buckling_utilization >= buckling_same_mv_baseline_axial, (
        "for the same M/V demand, adding axial compression must not reduce buckling utilization"
    )
    print(f"  axial_baseline={axial_baseline_mn:.3f} MN  axial_bc90={result.axial_load_mn:.3f} MN")
    print(f"  buckling_util(bc90 M/V, baseline axial)={buckling_same_mv_baseline_axial:.4f}  "
          f"buckling_util(bc90 M/V, bc90 axial)={result.buckling_utilization:.4f}  PASS\n")


def check_mooring_uls_and_slack_reporting():
    """Section 5/9a: mooring ULS utilization is None (with a note) when no
    MBL is supplied, and becomes a normal >1.0-fails utilization once one is.
    Slack utilization must always be a finite, sensible number for a
    layout with reasonable pretension margin."""
    print("Check: mooring ULS / slack reporting")
    inputs, geometry = _bc90_inputs_and_geometry()
    mooring_no_mbl = MooringLayout(r_a_m=90.0, d_sb_fl_m=30.0, k_ml_mn_per_m=20.0, t0_mn=6.0)
    result_no_mbl = evaluate_bc90(inputs, geometry, mooring_no_mbl)
    assert result_no_mbl.mooring_uls_utilization is None
    assert "mbl_mn not supplied" in " ".join(result_no_mbl.notes)
    assert "MooringULS" not in result_no_mbl.margins

    required = result_no_mbl.mbl_required_mn
    mooring_generous = MooringLayout(r_a_m=90.0, d_sb_fl_m=30.0, k_ml_mn_per_m=20.0, t0_mn=6.0, mbl_mn=required * 2.0)
    result_generous = evaluate_bc90(inputs, geometry, mooring_generous)
    assert result_generous.mooring_uls_utilization is not None
    assert result_generous.mooring_uls_utilization < 1.0
    assert "MooringULS" in result_generous.margins

    mooring_undersized = MooringLayout(r_a_m=90.0, d_sb_fl_m=30.0, k_ml_mn_per_m=20.0, t0_mn=6.0, mbl_mn=required * 0.5)
    result_undersized = evaluate_bc90(inputs, geometry, mooring_undersized)
    assert result_undersized.mooring_uls_utilization > 1.0

    assert math.isfinite(result_no_mbl.slack_utilization)
    assert result_no_mbl.mooring_t_min_mn < result_no_mbl.mooring.t0_mn

    print(f"  T_max={result_no_mbl.mooring_t_max_mn:.3f} MN  MBL_required={required:.3f} MN")
    print(f"  utilization(MBL=2x required)={result_generous.mooring_uls_utilization:.3f}  "
          f"utilization(MBL=0.5x required)={result_undersized.mooring_uls_utilization:.3f}")
    print(f"  T_min={result_no_mbl.mooring_t_min_mn:.3f} MN  slack_utilization={result_no_mbl.slack_utilization:.3f}  PASS\n")


def check_full_report_is_printable():
    """Not an assertion-heavy check -- just dumps the full BC90Result the way
    Section 0 Step 9 ("Report") describes: diameter/thickness/mooring layout
    and specs/masses/CAPEX, so the numbers can be eyeballed for plausibility."""
    print("Check: full BC90 report output")
    inputs, geometry = _bc90_inputs_and_geometry()
    mooring = MooringLayout(r_a_m=90.0, d_sb_fl_m=30.0, k_ml_mn_per_m=20.0, t0_mn=6.0)
    r = evaluate_bc90(inputs, geometry, mooring)

    print(f"  Pile: D={geometry.diameter_m:.2f} m  t={geometry.wall_thickness_m*1000:.1f} mm  "
          f"L={geometry.embedded_length_m:.2f} m")
    print(f"  Mooring: N_ml=3  R_a={mooring.r_a_m:.1f} m  d_sb_fl={mooring.d_sb_fl_m:.1f} m  "
          f"theta={r.theta_deg:.1f} deg  L_ml={r.l_ml_m:.1f} m  K_ml={mooring.k_ml_mn_per_m:.1f} MN/m  "
          f"T0={mooring.t0_mn:.1f} MN")
    print(f"  Loads: M_char={r.m_char_mnm:.1f} -> M_char_net={r.m_char_net_mnm:.1f} MN.m  "
          f"V_char={r.v_char_mn:.2f} -> V_char_net={r.v_char_net_mn:.2f} MN  M_fl={r.m_fl_mnm:.1f} MN.m  "
          f"F_ml={r.f_ml_mn:.2f} MN")
    print(f"  Utilizations: ULS(mudline/fairlead)={r.uls_mudline_utilization:.3f}/{r.uls_fairlead_utilization:.3f}  "
          f"SLS={r.sls_utilization:.3f}  NFA={r.nfa_utilization:.3f}  FLS={r.fls_utilization:.3f}  "
          f"Buckling={r.buckling_utilization:.3f}  Slack={r.slack_utilization:.3f}")
    print(f"  Governing: {r.governing_constraint}")
    print(f"  Mooring: T_max={r.mooring_t_max_mn:.2f} MN  MBL_required={r.mbl_required_mn:.2f} MN")
    print(f"  Cost: steel=${r.steel_cost_usd:,.0f}  mooring_line=${r.mooring_line_cost_usd:,.0f}  "
          f"anchors=${r.anchor_cost_usd:,.0f}  total_capex=${r.total_capex_usd:,.0f}")
    if r.notes:
        print(f"  Notes: {len(r.notes)} flagged (see result.notes for text)")
    print("  PASS (printed for review, not asserted)\n")


def check_extreme_slack_triggers_flag():
    """Section 9a: a lightly pretensioned, highly flexible-relative-to-load
    mooring should go slack (T_min <= 0) and this must be flagged, not
    silently produce an unvalidated F_ml-based reduction."""
    print("Check: slack condition is flagged when tension margin is inadequate")
    inputs, geometry = _bc90_inputs_and_geometry()
    mooring_low_pretension = MooringLayout(r_a_m=90.0, d_sb_fl_m=30.0, k_ml_mn_per_m=20.0, t0_mn=0.05)
    result = evaluate_bc90(inputs, geometry, mooring_low_pretension)
    assert result.mooring_t_min_mn <= 0.0
    assert result.slack_utilization == float("inf")
    assert any("slack" in n.lower() for n in result.notes)
    print(f"  T_min={result.mooring_t_min_mn:.3f} MN (<=0)  slack flagged in notes  PASS\n")


if __name__ == "__main__":
    check_nfa_always_stiffens()
    check_buckling_axial_always_worsens()
    check_mooring_uls_and_slack_reporting()
    check_full_report_is_printable()
    check_extreme_slack_triggers_flag()
    print("All bc90/engine_bc90.py checks passed.")
