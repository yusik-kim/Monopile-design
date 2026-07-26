"""
Spot check (2026-07-26): re-run optimize_min_cost.optimize() at water depth
60 m and 70 m after extending MBL_BOUNDS_MN from (5, 150) to (5, 300) MN --
see docs/misc/mooring_line_database.md Section 10a and this module's updated
docstring. Both depths previously optimized to exactly MBL=150 MN (the old
upper bound, i.e. the search was pinned against its own ceiling, not a
converged interior optimum) per bc90/water_depth_sweep_results.csv. This
checks whether MBL=150 was in fact just an artifact of that ceiling, or
whether these two depths still land near it once the ceiling is pushed out.

Run directly:  python bc90/misc/mbl300_spotcheck_60_70m.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from engine import DesignInputs, SoilProfile, size_monopile
from bc90.misc.optimize_min_cost import optimize, MBL_BOUNDS_MN

DEPTHS_M = [60.0, 70.0]

OLD_MBL_150_RESULT = {
    60.0: dict(bc90_cost=4_258_317.99, cost_save_pct=-20.3, mbl_mn=150.0, theta_deg=40.6, frac=1.0, governing="FLS"),
    70.0: dict(bc90_cost=3_625_759.71, cost_save_pct=5.1, mbl_mn=150.0, theta_deg=40.0, frac=1.0, governing="NFA"),
}


def main():
    soil = SoilProfile(soil_type="sand", friction_angle_deg=34.0, submerged_unit_weight_kn_m3=10.0)
    print(f"MBL_BOUNDS_MN now = {MBL_BOUNDS_MN}\n")

    for depth in DEPTHS_M:
        inputs = DesignInputs(turbine_mw=15.0, water_depth_m=depth, soil=soil, hs_m=5.5, tp_s=9.5, current_m_s=0.4)
        mp_result = size_monopile(inputs)
        mp_cost = mp_result.steel_cost_usd

        theta_opt, mbl_opt, frac_opt, g, r, mooring = optimize(inputs, mp_result.geometry, verbose=False)
        cost_save_pct = 100 * (1 - r.total_capex_usd / mp_cost)

        old = OLD_MBL_150_RESULT[depth]
        print(f"=== Depth = {depth:.0f} m ===")
        print(f"  MP steel cost: ${mp_cost:,.0f}")
        print(f"  New optimum: theta={theta_opt:.1f} deg  MBL={mbl_opt:.1f} MN  fairlead_frac={frac_opt:.3f}  "
              f"D={g.diameter_m:.2f} m  mass={r.steel_mass_t:.1f} t")
        print(f"  New cost: steel=${r.steel_cost_usd:,.0f}  mooring_line=${r.mooring_line_cost_usd:,.0f}  "
              f"anchors=${r.anchor_cost_usd:,.0f}  TOTAL=${r.total_capex_usd:,.0f}  "
              f"({cost_save_pct:+.1f}% vs MP)")
        print(f"  New utilizations: ULS={r.uls_utilization:.3f} SLS={r.sls_utilization:.3f} "
              f"NFA={r.nfa_utilization:.3f} FLS={r.fls_utilization:.3f} Buck={r.buckling_utilization:.3f} "
              f"MooringULS={r.mooring_uls_utilization:.3f} Slack={r.slack_utilization:.3f}")
        print(f"  New governing: {r.governing_constraint}")
        print(f"  --- vs. old MBL<=150 result: MBL={old['mbl_mn']:.0f} MN  theta={old['theta_deg']:.1f} deg  "
              f"frac={old['frac']:.2f}  cost=${old['bc90_cost']:,.0f} ({old['cost_save_pct']:+.1f}%)  "
              f"governing={old['governing']}")
        mbl_moved = abs(mbl_opt - 150.0) > 1.0
        cost_delta_pct = cost_save_pct - old["cost_save_pct"]
        print(f"  --- MBL moved off old 150 MN ceiling: {mbl_moved}   "
              f"cost-saved-% delta vs old: {cost_delta_pct:+.2f} pts\n")


if __name__ == "__main__":
    main()
