"""
MP vs BC90 (cost-optimized) sweep over water depth = 20:10:150 m, 15 MW
turbine, sand phi=34 deg, Hs=5.5 m, Tp=9.5 s, current=0.4 m/s -- same site
convention used throughout this session's BC90 work.

At each water depth:
  - MP: size_monopile baseline (no mooring) -- steel mass, steel cost.
  - BC90: full optimize_min_cost.optimize() re-run at that depth (mooring
    angle/MBL/fairlead re-optimized independently per depth, not held fixed
    at the single 90m optimum found earlier) -- steel mass, total CAPEX
    (steel + mooring line + anchors).

Run directly:  python bc90/sweep_water_depth_cost.py
Writes bc90/water_depth_sweep_results.csv.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import DesignInputs, SoilProfile, size_monopile
from bc90.optimize_min_cost import optimize

WATER_DEPTHS_M = list(range(20, 151, 10))  # 20, 30, ..., 150


def main():
    soil = SoilProfile(soil_type="sand", friction_angle_deg=34.0, submerged_unit_weight_kn_m3=10.0)
    rows = []

    header = (f"{'depth[m]':>9} {'MP_D[m]':>8} {'MP_mass[t]':>11} {'MP_cost':>13}  "
              f"{'BC90_D[m]':>10} {'BC90_mass[t]':>13} {'BC90_cost':>13}  {'wt_save%':>9} {'cost_save%':>10}  theta/MBL/frac")
    print(header)
    print("-" * len(header))

    for depth in WATER_DEPTHS_M:
        inputs = DesignInputs(turbine_mw=15.0, water_depth_m=float(depth), soil=soil, hs_m=5.5, tp_s=9.5, current_m_s=0.4)

        mp_result = size_monopile(inputs)
        mp_mass = mp_result.steel_mass_t
        mp_cost = mp_result.steel_cost_usd

        theta_opt, mbl_opt, frac_opt, g, r, mooring = optimize(inputs, mp_result.geometry)
        bc90_mass = r.steel_mass_t
        bc90_cost = r.total_capex_usd

        wt_save_pct = 100 * (1 - bc90_mass / mp_mass)
        cost_save_pct = 100 * (1 - bc90_cost / mp_cost)

        rows.append({
            "water_depth_m": depth,
            "mp_diameter_m": mp_result.geometry.diameter_m,
            "mp_mass_t": mp_mass,
            "mp_cost_usd": mp_cost,
            "bc90_diameter_m": g.diameter_m,
            "bc90_mass_t": bc90_mass,
            "bc90_cost_usd": bc90_cost,
            "weight_saved_pct": wt_save_pct,
            "cost_saved_pct": cost_save_pct,
            "theta_deg": theta_opt,
            "mbl_mn": mbl_opt,
            "fairlead_fraction": frac_opt,
            "bc90_governing": r.governing_constraint,
        })

        print(f"{depth:9d} {mp_result.geometry.diameter_m:8.2f} {mp_mass:11.1f} ${mp_cost:11,.0f}  "
              f"{g.diameter_m:10.2f} {bc90_mass:13.1f} ${bc90_cost:11,.0f}  "
              f"{wt_save_pct:8.1f}% {cost_save_pct:9.1f}%  {theta_opt:.0f}deg/{mbl_opt:.0f}MN/{frac_opt:.2f}")

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "water_depth_sweep_results.csv")
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
