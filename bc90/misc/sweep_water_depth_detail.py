"""
Extended version of bc90/sweep_water_depth_cost.py: same sweep (15 MW, sand
phi=34 deg, Hs=5.5 m, Tp=9.5 s, current=0.4 m/s, water depth 20:10:150 m),
but also captures full utilization vectors (MP and BC90) and the BC90 cost
breakdown (steel / mooring line / anchor), for the engineering report's
governing-utilization and cost-breakdown sections.

Run directly:  python bc90/misc/sweep_water_depth_detail.py
Writes bc90/misc/water_depth_sweep_detail.csv.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from engine import DesignInputs, SoilProfile, size_monopile
from bc90.misc.optimize_min_cost import optimize

WATER_DEPTHS_M = list(range(20, 151, 10))


def main():
    soil = SoilProfile(soil_type="sand", friction_angle_deg=34.0, submerged_unit_weight_kn_m3=10.0)
    rows = []

    for depth in WATER_DEPTHS_M:
        inputs = DesignInputs(turbine_mw=15.0, water_depth_m=float(depth), soil=soil, hs_m=5.5, tp_s=9.5, current_m_s=0.4)

        mp = size_monopile(inputs)
        theta_opt, mbl_opt, frac_opt, g, r, mooring = optimize(inputs, mp.geometry)

        mooring_line_cost_per_m_usd = r.mooring_line_cost_usd / (3.0 * r.l_ml_m) if r.l_ml_m else 0.0
        anchor_cost_per_anchor_usd = r.anchor_cost_usd / 3.0

        rows.append({
            "water_depth_m": depth,
            "mp_uls": mp.uls_utilization,
            "mp_sls": mp.sls_utilization,
            "mp_nfa": mp.nfa_utilization,
            "mp_fls": mp.fls_utilization,
            "mp_buckling": mp.buckling_utilization,
            "mp_governing": mp.governing_constraint,
            "bc90_uls": r.uls_utilization,
            "bc90_sls": r.sls_utilization,
            "bc90_nfa": r.nfa_utilization,
            "bc90_fls": r.fls_utilization,
            "bc90_buckling": r.buckling_utilization,
            "bc90_mooring_uls": r.mooring_uls_utilization if r.mooring_uls_utilization is not None else "",
            "bc90_slack": r.slack_utilization,
            "bc90_governing": r.governing_constraint,
            "steel_cost_usd": r.steel_cost_usd,
            "mooring_line_cost_usd": r.mooring_line_cost_usd,
            "anchor_cost_usd": r.anchor_cost_usd,
            "total_capex_usd": r.total_capex_usd,
            "l_ml_m_per_line": r.l_ml_m,
            "mooring_line_cost_per_m_usd": mooring_line_cost_per_m_usd,
            "anchor_cost_per_anchor_usd": anchor_cost_per_anchor_usd,
            "mbl_mn": mbl_opt,
        })
        print(f"depth={depth:>4}m  MP gov={mp.governing_constraint:>9}  "
              f"BC90 gov={r.governing_constraint:>11}  "
              f"BC90 utils: ULS={r.uls_utilization:.2f} SLS={r.sls_utilization:.2f} "
              f"NFA={r.nfa_utilization:.2f} FLS={r.fls_utilization:.2f} Buck={r.buckling_utilization:.2f} "
              f"MooringULS={r.mooring_uls_utilization:.2f} Slack={r.slack_utilization:.2f}  |  "
              f"steel=${r.steel_cost_usd:,.0f} line=${r.mooring_line_cost_usd:,.0f} "
              f"({mooring_line_cost_per_m_usd:.0f}$/m) anchor=${r.anchor_cost_usd:,.0f} "
              f"({anchor_cost_per_anchor_usd:,.0f}$/ea)")

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "water_depth_sweep_detail.csv")
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
