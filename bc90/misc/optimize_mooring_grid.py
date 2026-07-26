"""
Grid sweep over mooring layout (R_a, d_sb_fl), MBL held fixed at 15.0 MN.
Run directly:

    python bc90/misc/optimize_mooring_grid.py

Site: 15 MW turbine, 75 m water depth, same environmental inputs as
bc90/misc/compare_mp_vs_bc90.py (sand soil, Hs=5.5 m, Tp=9.5 s, current=0.4 m/s) --
per "Optimization test.md", only turbine/depth were restated there.

Grid: R_a in [0.5, 1.5] x water_depth (10 points), d_sb_fl in [0.3, 1.0] x
water_depth (10 points) -- 100 combinations.

Mooring line held fixed across the whole grid at MBL=15.0 MN with
EA_quasi_static=13.5xMBL, EA_dynamic=26.5xMBL, and the current
USD_PER_M_MOORING_LINE cost placeholder -- per "Optimization test.md"'s
"use the initial setup, MBL=15.0 MN, and corresponding cost and static and
dynamic stiffness." Only R_a and d_sb_fl vary.

T0 (pretension) is NOT held fixed, though: it's recomputed per grid point
using the same rule already committed in compare_mp_vs_bc90.py's
build_mooring_layout (T0 = max(1.35x the extreme incremental tension,
90% of the mooring-ULS ceiling MBL/GAMMA_ML_ULS - delta_t_max_mn)), since
that rule was added specifically for slack margin and the user confirmed it
should carry over here. This is safe to do per-grid-point without the
earlier K_ml-contamination problem (see compare_mp_vs_bc90.py's
build_mooring_layout docstring) because MBL itself is fixed here, not
re-derived from T0's pass-1 guess -- so K_ml (via EA=13.5x/26.5xMBL) never
changes across the sweep, only T0 does.

For each grid point, runs shrink_geometry_with_mooring to find the smallest
pile geometry (D, t) that still passes all checks, matching the actual
"optimization" framing of the test (not just evaluating a fixed baseline
geometry).
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from engine import DesignInputs, SoilProfile, size_monopile
from bc90.engine_bc90 import evaluate_bc90, shrink_geometry_with_mooring, GAMMA_ML_ULS
from bc90.mooring import layout_from_line_data


soil = SoilProfile(soil_type="sand", friction_angle_deg=34.0, submerged_unit_weight_kn_m3=10.0)
inputs = DesignInputs(turbine_mw=15.0, water_depth_m=75.0, soil=soil, hs_m=5.5, tp_s=9.5, current_m_s=0.4)

MBL_MN = 15.0
EA_QUASI_STATIC_MN = 13.5 * MBL_MN
EA_DYNAMIC_MN = 26.5 * MBL_MN

GRID_N = 10
R_A_RANGE = (0.5 * inputs.water_depth_m, 1.5 * inputs.water_depth_m)
D_SB_FL_RANGE = (0.3 * inputs.water_depth_m, 1.0 * inputs.water_depth_m)


def _linspace(lo: float, hi: float, n: int) -> list[float]:
    if n == 1:
        return [lo]
    step = (hi - lo) / (n - 1)
    return [lo + i * step for i in range(n)]


def build_layout_fixed_mbl(r_a_m: float, d_sb_fl_m: float, baseline_geometry):
    """Same T0-selection rule as compare_mp_vs_bc90.py's build_mooring_layout,
    but MBL/EA are fixed inputs here rather than re-derived from pass-1
    demand -- see module docstring."""
    layout_pass1 = layout_from_line_data(
        r_a_m=r_a_m, d_sb_fl_m=d_sb_fl_m, mbl_mn=MBL_MN,
        ea_quasi_static_mn=EA_QUASI_STATIC_MN, ea_dynamic_mn=EA_DYNAMIC_MN,
        pretension_fraction=0.15,
    )
    result_pass1 = evaluate_bc90(inputs, baseline_geometry, layout_pass1)
    delta_t_max_mn = result_pass1.mooring_t_max_mn - layout_pass1.t0_mn

    t0_uls_ceiling_mn = MBL_MN / GAMMA_ML_ULS - delta_t_max_mn
    t0_load_margin_mn = 1.35 * delta_t_max_mn
    t0_mn = max(t0_load_margin_mn, 0.90 * t0_uls_ceiling_mn)

    return layout_from_line_data(
        r_a_m=r_a_m, d_sb_fl_m=d_sb_fl_m, mbl_mn=MBL_MN,
        ea_quasi_static_mn=EA_QUASI_STATIC_MN, ea_dynamic_mn=EA_DYNAMIC_MN,
        pretension_fraction=t0_mn / MBL_MN,
    )


def main():
    baseline_geometry = size_monopile(inputs).geometry
    r_a_values = _linspace(*R_A_RANGE, GRID_N)
    d_sb_fl_values = _linspace(*D_SB_FL_RANGE, GRID_N)

    rows = []
    total = len(r_a_values) * len(d_sb_fl_values)
    done = 0
    for r_a_m in r_a_values:
        for d_sb_fl_m in d_sb_fl_values:
            mooring = build_layout_fixed_mbl(r_a_m, d_sb_fl_m, baseline_geometry)
            g, r, started_passing = shrink_geometry_with_mooring(inputs, baseline_geometry, mooring)
            rows.append({
                "R_a_m": r_a_m, "d_sb_fl_m": d_sb_fl_m,
                "theta_deg": r.theta_deg, "L_ml_m": r.l_ml_m,
                "T0_mn": mooring.t0_mn, "K_ml_mn_per_m": mooring.k_ml_mn_per_m,
                "diameter_m": g.diameter_m, "wall_thickness_mm": g.wall_thickness_m * 1000,
                "embedded_length_m": g.embedded_length_m,
                "started_passing": started_passing,
                "uls_mudline_utilization": r.uls_mudline_utilization,
                "uls_fairlead_utilization": r.uls_fairlead_utilization,
                "sls_utilization": r.sls_utilization,
                "nfa_utilization": r.nfa_utilization,
                "fls_utilization": r.fls_utilization,
                "buckling_utilization": r.buckling_utilization,
                "mooring_uls_utilization": r.mooring_uls_utilization,
                "slack_utilization": r.slack_utilization,
                "governing_constraint": r.governing_constraint,
                "steel_mass_t": r.steel_mass_t,
                "total_capex_usd": r.total_capex_usd,
            })
            done += 1
            print(f"  [{done}/{total}] R_a={r_a_m:6.2f} d_sb_fl={d_sb_fl_m:6.2f}  "
                  f"D={g.diameter_m:.2f} t={g.wall_thickness_m*1000:.1f}mm  gov={r.governing_constraint}")

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mooring_grid_results.csv")
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
