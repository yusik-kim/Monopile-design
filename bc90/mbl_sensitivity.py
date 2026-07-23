"""
MBL sensitivity sweep for BC90, same site as compare_mp_vs_bc90_90m.py: 90 m
water depth, fairlead held at MSL (d_sb_fl_m = water_depth_m), mooring line
angle theta = 40 deg (=> R_a fixed by geometry, independent of MBL), 15 MW
turbine, sand soil, same sea state. Run directly:

    python bc90/mbl_sensitivity.py

MBL swept over [5, 10, 15, 30, 60, 100, 200, 400, 600, 1000] MN. For each
value: EA_quasi_static=13.5xMBL, EA_dynamic=26.5xMBL (same literature-typical
polyester convention as the other bc90 scripts), T0 set by the same rule as
compare_mp_vs_bc90_90m.py (90% of the mooring-ULS ceiling, floored at the
Section 9a load-margin value). Pile geometry is then shrunk from the MP
baseline via shrink_geometry_with_mooring (outer loop only, mooring held
fixed) at each MBL.

No cost columns -- explicitly out of scope for this sweep (cost data is
sparse/unsourced above the ~MBL=15-30 MN range this repo's cost research
actually covered, see docs/mooring_line_database.md Section 10a).

delta_fl,0 (Section 4c) is the UNRESTRAINED fairlead deflection under
thrust+wave loads if there were no mooring line at all -- it depends only on
pile geometry/soil/loads, not on MBL/K_ml, so it varies across the sweep only
through the geometry the shrink loop lands on for each MBL (a stiffer line
allows more pile shrinkage, which changes EI and therefore delta_fl,0
slightly), not because MBL enters that formula directly.
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

THETA_DEG = 40.0
D_SB_FL_M = inputs.water_depth_m  # fairlead at MSL
R_A_M = D_SB_FL_M / math.tan(math.radians(THETA_DEG))

MBL_VALUES_MN = [5, 10, 15, 30, 60, 100, 200, 400, 600, 1000]


def build_mooring_layout(mbl_mn: float, baseline_geometry):
    ea_qs = 13.5 * mbl_mn
    ea_dyn = 26.5 * mbl_mn
    layout_pass1 = layout_from_line_data(
        r_a_m=R_A_M, d_sb_fl_m=D_SB_FL_M, mbl_mn=mbl_mn,
        ea_quasi_static_mn=ea_qs, ea_dynamic_mn=ea_dyn, pretension_fraction=0.15,
    )
    result_pass1 = evaluate_bc90(inputs, baseline_geometry, layout_pass1)
    delta_t_max_mn = result_pass1.mooring_t_max_mn - layout_pass1.t0_mn

    t0_uls_ceiling_mn = mbl_mn / GAMMA_ML_ULS - delta_t_max_mn
    t0_load_margin_mn = 1.35 * delta_t_max_mn
    t0_mn = max(t0_load_margin_mn, 0.90 * t0_uls_ceiling_mn)
    pretension_fraction_final = t0_mn / mbl_mn

    return layout_from_line_data(
        r_a_m=R_A_M, d_sb_fl_m=D_SB_FL_M, mbl_mn=mbl_mn,
        ea_quasi_static_mn=ea_qs, ea_dynamic_mn=ea_dyn, pretension_fraction=pretension_fraction_final,
    )


def main():
    print(f"Site: {inputs.turbine_mw:.0f} MW turbine, {inputs.water_depth_m:.0f} m water depth, "
          f"sand (phi={inputs.soil.friction_angle_deg:.0f} deg), Hs={inputs.hs_m:.1f} m, Tp={inputs.tp_s:.1f} s")
    print(f"Mooring: fairlead at MSL (d_sb_fl={D_SB_FL_M:.1f} m), theta={THETA_DEG:.0f} deg -> R_a={R_A_M:.2f} m\n")

    baseline_geometry = size_monopile(inputs).geometry
    print(f"MP baseline (no mooring): D={baseline_geometry.diameter_m:.2f} m  "
          f"t={baseline_geometry.wall_thickness_m*1000:.1f} mm  L={baseline_geometry.embedded_length_m:.2f} m\n")

    header = (f"{'MBL[MN]':>8} {'D[m]':>6} {'t[mm]':>7} {'L[m]':>7} {'delta_fl0[m]':>13} "
              f"{'ULS':>6} {'SLS':>6} {'NFA':>6} {'FLS':>6} {'Buck':>6} {'MoorULS':>8} {'Slack':>7}  governing")
    print(header)
    print("-" * len(header))

    for mbl_mn in MBL_VALUES_MN:
        mooring = build_mooring_layout(mbl_mn, baseline_geometry)
        try:
            g, r, started_passing = shrink_geometry_with_mooring(inputs, baseline_geometry, mooring)
        except ValueError as exc:
            # Seen at very high MBL (>=400 MN here): the shrink loop drives D
            # down far enough, under the now very stiff mooring reaction, that
            # the net mudline moment used by _fls_check goes non-positive,
            # which math.log10() can't handle. A real edge case of this
            # heuristic at MBL values far outside anything sourced in
            # docs/mooring_line_database.md -- reported, not silently skipped.
            print(f"{mbl_mn:8.0f}   ERROR: shrink loop crashed ({exc}) -- likely drove D below where "
                  f"the net mudline moment stays positive; not a valid result at this MBL.")
            continue
        flag = "" if started_passing else "  [START FAIL]"
        moor_uls = r.mooring_uls_utilization if r.mooring_uls_utilization is not None else float("nan")
        print(f"{mbl_mn:8.0f} {g.diameter_m:6.2f} {g.wall_thickness_m*1000:7.1f} {g.embedded_length_m:7.2f} "
              f"{r.delta_fl0_m:13.4f} {r.uls_utilization:6.3f} {r.sls_utilization:6.3f} {r.nfa_utilization:6.3f} "
              f"{r.fls_utilization:6.3f} {r.buckling_utilization:6.3f} {moor_uls:8.3f} {r.slack_utilization:7.3f}  "
              f"{r.governing_constraint}{flag}")
        if r.notes:
            for n in r.notes:
                print(f"    NOTE: {n}")


if __name__ == "__main__":
    main()
