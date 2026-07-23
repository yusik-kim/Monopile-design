"""
Updated MP (baseline, no mooring) vs. BC90 (taut-mooring-assisted) comparison
at the deep end of BC90's target range. Run directly:

    python bc90/compare_mp_vs_bc90_90m.py

Fixed per this test's brief (vs. compare_mp_vs_bc90.py's more general 75 m
case):
  - Water depth = 90 m.
  - Fairlead held at MSL: d_sb_fl_m = water_depth_m (90 m above seabed).
  - Mooring line angle theta = 40 deg from horizontal -- within the 30-45 deg
    starting range recommended in docs/BC90_METHODOLOGY_REPORT.md Section 9a
    -- which fixes r_a_m = d_sb_fl_m / tan(40 deg).
  - MBL held fixed at 15.0 MN (not re-derived from mbl_required_mn like
    compare_mp_vs_bc90.py does), same fixed-MBL convention as
    optimize_mooring_grid.py. EA_quasi_static=13.5xMBL, EA_dynamic=26.5xMBL
    (same literature-typical polyester figures as the other bc90 scripts).
  - Mooring line cost now uses the sourced MBL-dependent formula (docs/
    mooring_line_database.md Section 10a, Striani et al. 2025 Eq. 2) via
    bc90.engine_bc90.polyester_cost_per_m_usd, wired into evaluate_bc90's
    cost calc as of 2026-07-24 -- replaces the flat $500/m placeholder used
    by the other bc90 comparison scripts before this update.

Turbine (15 MW) and sea state (sand, Hs=5.5 m, Tp=9.5 s, current=0.4 m/s) are
carried over unchanged from compare_mp_vs_bc90.py -- not specified in this
test's brief, kept for consistency/comparability with the earlier comparison.

T0 selection follows the same rule already established in
compare_mp_vs_bc90.py/optimize_mooring_grid.py's build_mooring_layout:
maximize toward 90% of the mooring-ULS ceiling (T0 <= MBL/GAMMA_ML_ULS -
delta_t_max_mn), floored at the Section 9a load-margin value (1.35x the
extreme incremental tension), for maximum slack margin.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import DesignInputs, SoilProfile, size_monopile
from bc90.engine_bc90 import evaluate_bc90, shrink_geometry_with_mooring, GAMMA_ML_ULS
from bc90.mooring import layout_from_line_data


soil = SoilProfile(soil_type="sand", friction_angle_deg=34.0, submerged_unit_weight_kn_m3=10.0)
inputs = DesignInputs(turbine_mw=15.0, water_depth_m=90.0, soil=soil, hs_m=5.5, tp_s=9.5, current_m_s=0.4)

MBL_MN = 15.0
EA_QUASI_STATIC_MN = 13.5 * MBL_MN
EA_DYNAMIC_MN = 26.5 * MBL_MN

THETA_DEG = 40.0
D_SB_FL_M = inputs.water_depth_m  # fairlead at MSL = full water depth above seabed
R_A_M = D_SB_FL_M / math.tan(math.radians(THETA_DEG))


def _print_row(label, d, t_mm, L, mass_t, cost, uls, sls, nfa, fls, buck, governing):
    print(f"{label:<28} D={d:5.2f} m  t={t_mm:6.1f} mm  L={L:5.2f} m  "
          f"mass={mass_t:8.1f} t  cost=${cost:>11,.0f}  "
          f"ULS={uls:.3f} SLS={sls:.3f} NFA={nfa:.3f} FLS={fls:.3f} Buck={buck:.3f}  gov={governing}")


def build_mooring_layout(baseline_geometry):
    """Fixed-MBL version of compare_mp_vs_bc90.py's build_mooring_layout --
    MBL=15.0 MN is a given input here, not re-derived from mbl_required_mn."""
    layout_pass1 = layout_from_line_data(
        r_a_m=R_A_M, d_sb_fl_m=D_SB_FL_M, mbl_mn=MBL_MN,
        ea_quasi_static_mn=EA_QUASI_STATIC_MN, ea_dynamic_mn=EA_DYNAMIC_MN,
        pretension_fraction=0.15,
    )
    result_pass1 = evaluate_bc90(inputs, baseline_geometry, layout_pass1)
    delta_t_max_mn = result_pass1.mooring_t_max_mn - layout_pass1.t0_mn

    t0_uls_ceiling_mn = MBL_MN / GAMMA_ML_ULS - delta_t_max_mn
    t0_load_margin_mn = 1.35 * delta_t_max_mn
    t0_mn = max(t0_load_margin_mn, 0.90 * t0_uls_ceiling_mn)
    pretension_fraction_final = t0_mn / MBL_MN

    print(f"  NOTE: T0 set to {pretension_fraction_final:.1%} of MBL (targeting 90% of the mooring-ULS "
          f"ceiling, {100*t0_uls_ceiling_mn/MBL_MN:.1f}% of MBL) for maximum slack margin.")

    return layout_from_line_data(
        r_a_m=R_A_M, d_sb_fl_m=D_SB_FL_M, mbl_mn=MBL_MN,
        ea_quasi_static_mn=EA_QUASI_STATIC_MN, ea_dynamic_mn=EA_DYNAMIC_MN,
        pretension_fraction=pretension_fraction_final,
    )


def main():
    print(f"Site: {inputs.turbine_mw:.0f} MW turbine, {inputs.water_depth_m:.0f} m water depth, "
          f"sand (phi={inputs.soil.friction_angle_deg:.0f} deg), Hs={inputs.hs_m:.1f} m, Tp={inputs.tp_s:.1f} s")
    print(f"Mooring: fairlead at MSL (d_sb_fl={D_SB_FL_M:.1f} m), theta={THETA_DEG:.0f} deg "
          f"-> R_a={R_A_M:.2f} m, MBL={MBL_MN:.1f} MN\n")

    # --- MP: baseline, no mooring ---
    mp_result = size_monopile(inputs)
    g_mp = mp_result.geometry
    _print_row(
        "MP (no mooring)", g_mp.diameter_m, g_mp.wall_thickness_m * 1000, g_mp.embedded_length_m,
        mp_result.steel_mass_t, mp_result.steel_cost_usd,
        mp_result.uls_utilization, mp_result.sls_utilization, mp_result.nfa_utilization,
        mp_result.fls_utilization, mp_result.buckling_utilization, mp_result.governing_constraint,
    )

    mooring = build_mooring_layout(g_mp)

    # --- BC90 at the SAME geometry as MP ---
    bc90_same_geom = evaluate_bc90(inputs, g_mp, mooring)
    _print_row(
        "BC90 (same geometry as MP)", g_mp.diameter_m, g_mp.wall_thickness_m * 1000, g_mp.embedded_length_m,
        bc90_same_geom.steel_mass_t, bc90_same_geom.total_capex_usd,
        bc90_same_geom.uls_utilization, bc90_same_geom.sls_utilization, bc90_same_geom.nfa_utilization,
        bc90_same_geom.fls_utilization, bc90_same_geom.buckling_utilization, bc90_same_geom.governing_constraint,
    )

    # --- BC90, pile geometry shrunk (outer loop only, mooring held fixed) ---
    g_shrunk, bc90_shrunk, started_passing = shrink_geometry_with_mooring(inputs, g_mp, mooring)
    if not started_passing:
        print("\n  NOTE: starting geometry failed a BC90 check before any shrinking was attempted.")
    _print_row(
        "BC90 (shrunk pile)", g_shrunk.diameter_m, g_shrunk.wall_thickness_m * 1000, g_shrunk.embedded_length_m,
        bc90_shrunk.steel_mass_t, bc90_shrunk.total_capex_usd,
        bc90_shrunk.uls_utilization, bc90_shrunk.sls_utilization, bc90_shrunk.nfa_utilization,
        bc90_shrunk.fls_utilization, bc90_shrunk.buckling_utilization, bc90_shrunk.governing_constraint,
    )

    print(f"\nMooring layout used: N_ml=3  R_a={mooring.r_a_m:.2f} m  d_sb_fl={mooring.d_sb_fl_m:.1f} m  "
          f"theta={bc90_shrunk.theta_deg:.1f} deg  L_ml={bc90_shrunk.l_ml_m:.1f} m")
    print(f"  K_ml(quasi-static)={mooring.k_ml_mn_per_m:.2f} MN/m  K_ml(dynamic)={mooring.k_ml_dynamic_mn_per_m:.2f} MN/m  "
          f"T0={mooring.t0_mn:.2f} MN ({100*mooring.t0_mn/mooring.mbl_mn:.1f}% MBL)  MBL={mooring.mbl_mn:.2f} MN")
    print(f"  T_max={bc90_shrunk.mooring_t_max_mn:.2f} MN  T_min={bc90_shrunk.mooring_t_min_mn:.2f} MN  "
          f"MBL_required={bc90_shrunk.mbl_required_mn:.2f} MN  "
          f"MooringULS utilization={bc90_shrunk.mooring_uls_utilization:.3f}  Slack utilization={bc90_shrunk.slack_utilization:.3f}")
    print(f"  Mooring line cost: ${bc90_shrunk.mooring_line_cost_usd:,.0f}  "
          f"Anchor cost: ${bc90_shrunk.anchor_cost_usd:,.0f}  Steel cost: ${bc90_shrunk.steel_cost_usd:,.0f}")

    print(f"\nSteel mass:  MP={mp_result.steel_mass_t:.1f} t  ->  BC90(shrunk)={bc90_shrunk.steel_mass_t:.1f} t  "
          f"({100*(1 - bc90_shrunk.steel_mass_t/mp_result.steel_mass_t):.1f}% less steel)")
    print(f"Total cost:  MP=${mp_result.steel_cost_usd:,.0f} (steel only)  ->  BC90(shrunk)=${bc90_shrunk.total_capex_usd:,.0f}  "
          f"({100*(1 - bc90_shrunk.total_capex_usd/mp_result.steel_cost_usd):+.1f}% vs. MP steel-only cost)")

    if bc90_shrunk.notes:
        print(f"\nBC90(shrunk) flagged notes ({len(bc90_shrunk.notes)}):")
        for n in bc90_shrunk.notes:
            print(f"  - {n}")


if __name__ == "__main__":
    main()
