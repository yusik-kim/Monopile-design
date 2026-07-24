"""
Minimize BC90 total CAPEX over [mooring line angle theta, MBL, fairlead
depth] at the 90 m site (same site as compare_mp_vs_bc90_90m.py /
mbl_sensitivity.py: 15 MW turbine, sand phi=34 deg, Hs=5.5 m, Tp=9.5 s,
current=0.4 m/s). Run directly:

    python bc90/optimize_min_cost.py

Pile geometry (D, t) is co-optimized at every candidate via
shrink_geometry_with_mooring, starting from the MP (no-mooring) baseline --
cost is total CAPEX (steel + mooring line + anchors, BC90Result.total_capex_usd),
using the sourced MBL-dependent polyester line cost (docs/
mooring_line_database.md Section 10a).

Bounds (per 2026-07-24 request):
  - theta (mooring line angle from horizontal): 20-50 deg
  - MBL: 5-150 MN -- matches the cost table's now-tabulated range; higher
    MBL has no sourced/extrapolated cost, so is out of scope for a COST
    objective specifically (see mbl_sensitivity.py for the wider,
    cost-blind MBL=1000 MN sweep).
  - fairlead depth: 0.1x-1.0x water depth (1.0x = fairlead at MSL, the
    stated maximum). r_a_m is derived from (theta, fairlead depth), not
    swept independently.

T0 (pretension) is not a free variable -- same derived rule as the other
bc90 scripts (90% of the mooring-ULS ceiling, floored at the Section 9a
load-margin value).

No scipy in this repo's dependencies (requirements.txt), so this uses a
two-stage search instead of a black-box optimizer:
  1. Coarse grid over the 3 variables to find a good starting region --
     avoids the pattern search below getting stuck in a local optimum, since
     the cost surface is not smooth (governing constraint / feasibility can
     switch discretely as MBL/geometry change, same as mbl_sensitivity.py's
     ERROR/START-FAIL rows at high MBL).
  2. Hooke-Jeeves pattern-search refinement from the best grid point:
     explore +/- a step in each variable, move on any improvement, halve all
     step sizes once a full sweep finds none, stop once steps are below
     tolerance.

Infeasible candidates (shrink loop's started_passing=False, i.e. the MP
baseline itself fails a BC90 check at that mooring layout -- e.g. mooring
ULS or slack violated -- or a numerical domain error at extreme geometries,
same class seen in mbl_sensitivity.py) are treated as cost=+inf and
naturally excluded by both search stages.
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

THETA_BOUNDS_DEG = (20.0, 50.0)
MBL_BOUNDS_MN = (5.0, 150.0)
FAIRLEAD_FRACTION_BOUNDS = (0.1, 1.0)


def build_mooring_layout(theta_deg: float, mbl_mn: float, fairlead_fraction: float, baseline_geometry):
    d_sb_fl_m = fairlead_fraction * inputs.water_depth_m
    r_a_m = d_sb_fl_m / math.tan(math.radians(theta_deg))
    ea_qs = 13.5 * mbl_mn
    ea_dyn = 26.5 * mbl_mn

    layout_pass1 = layout_from_line_data(
        r_a_m=r_a_m, d_sb_fl_m=d_sb_fl_m, mbl_mn=mbl_mn,
        ea_quasi_static_mn=ea_qs, ea_dynamic_mn=ea_dyn, pretension_fraction=0.15,
    )
    result_pass1 = evaluate_bc90(inputs, baseline_geometry, layout_pass1)
    delta_t_max_mn = result_pass1.mooring_t_max_mn - layout_pass1.t0_mn

    t0_uls_ceiling_mn = mbl_mn / GAMMA_ML_ULS - delta_t_max_mn
    t0_load_margin_mn = 1.35 * delta_t_max_mn
    t0_mn = max(t0_load_margin_mn, 0.90 * t0_uls_ceiling_mn)
    pretension_fraction_final = t0_mn / mbl_mn

    return layout_from_line_data(
        r_a_m=r_a_m, d_sb_fl_m=d_sb_fl_m, mbl_mn=mbl_mn,
        ea_quasi_static_mn=ea_qs, ea_dynamic_mn=ea_dyn, pretension_fraction=pretension_fraction_final,
    )


def evaluate_candidate(theta_deg: float, mbl_mn: float, fairlead_fraction: float, baseline_geometry):
    """Returns (cost_usd, detail) -- cost_usd is +inf and detail is None for
    any infeasible or numerically-broken candidate."""
    try:
        mooring = build_mooring_layout(theta_deg, mbl_mn, fairlead_fraction, baseline_geometry)
        g, r, started_passing = shrink_geometry_with_mooring(inputs, baseline_geometry, mooring)
    except (ValueError, ZeroDivisionError):
        return float("inf"), None
    if not started_passing:
        return float("inf"), None
    return r.total_capex_usd, (g, r, mooring)


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def coarse_grid_search(baseline_geometry):
    theta_values = [20, 25, 30, 35, 40, 45, 50]
    mbl_values = [5, 8, 12, 18, 27, 40, 60, 90, 130, 150]
    frac_values = [0.1, 0.25, 0.4, 0.55, 0.7, 0.85, 1.0]

    best = (float("inf"), None, None)
    total = len(theta_values) * len(mbl_values) * len(frac_values)
    done = 0
    for theta_deg in theta_values:
        for mbl_mn in mbl_values:
            for frac in frac_values:
                cost, detail = evaluate_candidate(theta_deg, mbl_mn, frac, baseline_geometry)
                done += 1
                if cost < best[0]:
                    best = (cost, (theta_deg, mbl_mn, frac), detail)
    print(f"Coarse grid: {done} candidates evaluated.")
    return best


def pattern_search_refine(start_point, baseline_geometry, start_cost):
    theta_deg, mbl_mn, frac = start_point
    best_cost = start_cost
    steps = [5.0, 15.0, 0.1]  # theta_deg, mbl_mn, fairlead_fraction
    min_steps = [0.25, 0.5, 0.005]
    bounds = [THETA_BOUNDS_DEG, MBL_BOUNDS_MN, FAIRLEAD_FRACTION_BOUNDS]

    point = [theta_deg, mbl_mn, frac]
    iterations = 0
    while any(s > m for s, m in zip(steps, min_steps)) and iterations < 200:
        iterations += 1
        improved = False
        for i in range(3):
            for sign in (+1, -1):
                trial = list(point)
                trial[i] = _clamp(trial[i] + sign * steps[i], *bounds[i])
                if trial == point:
                    continue
                cost, _ = evaluate_candidate(trial[0], trial[1], trial[2], baseline_geometry)
                if cost < best_cost:
                    best_cost = cost
                    point = trial
                    improved = True
        if not improved:
            steps = [s * 0.5 for s in steps]

    print(f"Pattern search: {iterations} sweeps.")
    return tuple(point), best_cost


def main():
    print(f"Site: {inputs.turbine_mw:.0f} MW turbine, {inputs.water_depth_m:.0f} m water depth, "
          f"sand (phi={inputs.soil.friction_angle_deg:.0f} deg), Hs={inputs.hs_m:.1f} m, Tp={inputs.tp_s:.1f} s")
    print(f"Bounds: theta={THETA_BOUNDS_DEG} deg, MBL={MBL_BOUNDS_MN} MN, "
          f"fairlead={FAIRLEAD_FRACTION_BOUNDS} x water depth\n")

    mp_result = size_monopile(inputs)
    baseline_geometry = mp_result.geometry
    print(f"MP baseline (no mooring): D={baseline_geometry.diameter_m:.2f} m  "
          f"t={baseline_geometry.wall_thickness_m*1000:.1f} mm  L={baseline_geometry.embedded_length_m:.2f} m  "
          f"steel cost=${mp_result.steel_cost_usd:,.0f}\n")

    grid_cost, grid_point, grid_detail = coarse_grid_search(baseline_geometry)
    theta0, mbl0, frac0 = grid_point
    print(f"Best grid point: theta={theta0:.1f} deg  MBL={mbl0:.1f} MN  fairlead_frac={frac0:.2f}  "
          f"cost=${grid_cost:,.0f}\n")

    final_point, final_cost = pattern_search_refine(grid_point, baseline_geometry, grid_cost)
    theta_opt, mbl_opt, frac_opt = final_point
    final_cost_check, final_detail = evaluate_candidate(theta_opt, mbl_opt, frac_opt, baseline_geometry)
    g, r, mooring = final_detail

    print(f"\n=== Optimum ===")
    print(f"theta={theta_opt:.2f} deg  MBL={mbl_opt:.2f} MN  fairlead={frac_opt:.3f} x depth "
          f"({frac_opt*inputs.water_depth_m:.1f} m)  R_a={mooring.r_a_m:.2f} m  L_ml={r.l_ml_m:.2f} m")
    print(f"D={g.diameter_m:.2f} m  t={g.wall_thickness_m*1000:.1f} mm  L={g.embedded_length_m:.2f} m  "
          f"mass={r.steel_mass_t:.1f} t")
    print(f"Cost: steel=${r.steel_cost_usd:,.0f}  mooring_line=${r.mooring_line_cost_usd:,.0f}  "
          f"anchors=${r.anchor_cost_usd:,.0f}  TOTAL=${r.total_capex_usd:,.0f}")
    print(f"Utilizations: ULS={r.uls_utilization:.3f} SLS={r.sls_utilization:.3f} NFA={r.nfa_utilization:.3f} "
          f"FLS={r.fls_utilization:.3f} Buck={r.buckling_utilization:.3f} "
          f"MooringULS={r.mooring_uls_utilization:.3f} Slack={r.slack_utilization:.3f}")
    print(f"Governing: {r.governing_constraint}")
    print(f"\nvs. MP steel-only baseline: ${mp_result.steel_cost_usd:,.0f}  "
          f"({100*(1 - r.total_capex_usd/mp_result.steel_cost_usd):+.1f}%)")

    if r.notes:
        print(f"\nFlagged notes ({len(r.notes)}):")
        for n in r.notes:
            print(f"  - {n}")


if __name__ == "__main__":
    main()
