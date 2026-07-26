"""
MP (baseline, no mooring) vs. BC90 (taut-mooring-assisted) comparison, same
environmental inputs. Run directly:

    python bc90/misc/compare_mp_vs_bc90.py

Site: a general (not extreme) representative BC90-range case -- 15 MW
turbine, 75 m water depth (mid of the 60-90 m target range), sand soil,
moderate extreme sea state. Not tied to any specific real site.

Mooring line data used here is derived from literature-typical polyester
rope properties (see the module docstring's References note below) via
bc90.mooring.layout_from_line_data -- not a specific manufacturer's product,
and NOT independently verified against a real test certificate. Treat as a
first-pass estimate, same caveat as engine.py's own unsourced cost/factor
placeholders.

References used for the mooring line data below:
- R4 studless chain MBL-vs-diameter: Dawson Group product data (DNV/ABS
  certified test loads), used only to sanity-check that the required MBL
  falls in a normal commercial size range, not to select chain instead of
  rope (see the printed recommendation for why rope was chosen over chain
  /wire for this application).
- Polyester rope EA/MBL: quasi-static ~12-15, dynamic/storm ~25-28 (ResearchGate
  "Non-linear Polyester Axial Stiffness" and "Factors Affecting the Measurement
  of Axial Stiffness of Polyester Deepwater Mooring Rope" -- dynamic values of
  25.8 (25% MBL) and 27.5 (40% MBL) reported there; quasi-static range from
  general mooring-engineering literature (e.g. Del Vecchio-type test data
  cited across multiple sources), not independently re-derived here.
- Pretension: 15-20% MBL is the commonly-cited industry range for taut
  floating-wind mooring, but is NOT used here. This script instead
  deliberately maximizes T0 (for slack margin) up to 90% of the ceiling set
  by the mooring line's own ULS check (T0 <= mbl_mn/GAMMA_ML_ULS -
  delta_t_max_mn), floored at the Section 9a load-margin value
  (1.35x the extreme incremental tension) so it never goes below that
  minimum. This trades slack margin against mooring-line ULS utilization and
  pile buckling utilization (higher T0 -> more axial load via
  Fz=N_ml*T0*sin(theta), Section 5a) -- see build_mooring_layout's docstring.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from engine import DesignInputs, SoilProfile, size_monopile
from bc90.engine_bc90 import evaluate_bc90, shrink_geometry_with_mooring, GAMMA_ML_ULS
from bc90.mooring import MooringLayout, layout_from_line_data


# ---------------------------------------------------------------------------
# General environmental inputs (same for MP and BC90)
# ---------------------------------------------------------------------------
soil = SoilProfile(soil_type="sand", friction_angle_deg=34.0, submerged_unit_weight_kn_m3=10.0)
inputs = DesignInputs(turbine_mw=15.0, water_depth_m=75.0, soil=soil, hs_m=5.5, tp_s=9.5, current_m_s=0.4)


def _print_row(label, d, t_mm, L, mass_t, cost, uls, sls, nfa, fls, buck, governing):
    print(f"{label:<28} D={d:5.2f} m  t={t_mm:6.1f} mm  L={L:5.2f} m  "
          f"mass={mass_t:8.1f} t  cost=${cost:>11,.0f}  "
          f"ULS={uls:.3f} SLS={sls:.3f} NFA={nfa:.3f} FLS={fls:.3f} Buck={buck:.3f}  gov={governing}")


def build_mooring_layout(r_a_m: float, d_sb_fl_m: float) -> MooringLayout:
    """First-pass mooring layout from literature-typical polyester rope
    data, then one refinement pass on T0 using BC90's own slack criterion
    (Section 9a: T0 ~ 1.2-1.5x the extreme incremental tension), rather than
    trusting the 15%-MBL floating-vessel convention on its own.

    Pass-1's pretension_fraction is a placeholder guess (0.15): T0 is
    ultimately an outcome of the loads (via delta_fl0/F_ml, Section 4c),
    which are themselves a function of MP sizing, so no a-priori fraction
    guessed here can be more than a placeholder. It CANNOT simply be pushed
    to an extreme (e.g. 1.0) to "play it safe", though: K_ml is derived from
    MBL via EA = 13.5x_MBL (mooring.py's layout_from_line_data), so a bigger
    pass-1 T0 -> bigger pass-1 T_max -> bigger mbl_required_mn -> bigger
    final MBL -> proportionally STIFFER final K_ml. That is a real physics
    change, not a free conservative margin -- tried here with
    pretension_fraction=1.0 and it roughly doubled K_ml (3.24 -> 7.16 MN/m
    in the default case), which pushed the "same geometry as MP" case into
    slack failure (T_min < 0) that doesn't occur at 0.15. Keep this modest.
    """
    guess_mbl_mn = 15.0
    layout_pass1 = layout_from_line_data(
        r_a_m=r_a_m, d_sb_fl_m=d_sb_fl_m, mbl_mn=guess_mbl_mn,
        ea_quasi_static_mn=13.5 * guess_mbl_mn, ea_dynamic_mn=26.5 * guess_mbl_mn,
        pretension_fraction=0.15,
    )
    baseline_geometry = size_monopile(inputs).geometry
    result_pass1 = evaluate_bc90(inputs, baseline_geometry, layout_pass1)
    delta_t_max_mn = result_pass1.mooring_t_max_mn - layout_pass1.t0_mn

    mbl_required_mn = result_pass1.mbl_required_mn
    mbl_mn = max(guess_mbl_mn, 1.25 * mbl_required_mn)  # round up with 25% margin over the computed requirement

    # T0 is capped by the SAME line's own mooring-ULS check, independent of slack:
    #   mooring_uls_utilization = gamma_ML_ULS * (T0 + delta_t_max_mn) / mbl_mn  <= 1
    #   =>  T0 <= mbl_mn / GAMMA_ML_ULS - delta_t_max_mn
    # Maximizing T0 for slack margin means approaching this ceiling, not pushing
    # pretension_fraction toward 1.0 (which corrupts K_ml via the EA=13.5xMBL
    # convention, and which independently fails mooring ULS outright: T0=MBL
    # alone already gives utilization=GAMMA_ML_ULS=1.75 > 1, before any load
    # swing is even added). Take 90% of that ceiling as the target, floored at
    # the Section 9a load-margin value so T0 never drops below the original
    # slack-only criterion.
    t0_uls_ceiling_mn = mbl_mn / GAMMA_ML_ULS - delta_t_max_mn
    t0_load_margin_mn = 1.35 * delta_t_max_mn  # Section 9a: 1.2-1.5x margin over the extreme incremental tension
    t0_mn = max(t0_load_margin_mn, 0.90 * t0_uls_ceiling_mn)

    pretension_fraction_final = t0_mn / mbl_mn
    print(f"  NOTE: T0 set to {pretension_fraction_final:.1%} of MBL (targeting 90% of the mooring-ULS "
          f"ceiling, {100*t0_uls_ceiling_mn/mbl_mn:.1f}% of MBL) for maximum slack margin -- check the "
          f"printed Buck utilization below, since higher T0 also raises axial load via Fz=N_ml*T0*sin(theta) (Sec 5a).")

    return layout_from_line_data(
        r_a_m=r_a_m, d_sb_fl_m=d_sb_fl_m, mbl_mn=mbl_mn,
        ea_quasi_static_mn=13.5 * mbl_mn, ea_dynamic_mn=26.5 * mbl_mn,
        pretension_fraction=pretension_fraction_final,
    )


def main():
    print(f"Site: {inputs.turbine_mw:.0f} MW turbine, {inputs.water_depth_m:.0f} m water depth, "
          f"sand (phi={inputs.soil.friction_angle_deg:.0f} deg), Hs={inputs.hs_m:.1f} m, Tp={inputs.tp_s:.1f} s\n")

    # --- MP: baseline, no mooring ---
    mp_result = size_monopile(inputs)
    g_mp = mp_result.geometry
    _print_row(
        "MP (no mooring)", g_mp.diameter_m, g_mp.wall_thickness_m * 1000, g_mp.embedded_length_m,
        mp_result.steel_mass_t, mp_result.steel_cost_usd,
        mp_result.uls_utilization, mp_result.sls_utilization, mp_result.nfa_utilization,
        mp_result.fls_utilization, mp_result.buckling_utilization, mp_result.governing_constraint,
    )

    # --- Mooring layout: R_a/d_sb_fl chosen for theta in the 30-45 deg range
    # recommended as a starting point (Section 9a) ---
    r_a_m, d_sb_fl_m = 48.0, 40.0
    mooring = build_mooring_layout(r_a_m, d_sb_fl_m)

    # --- BC90 at the SAME geometry as MP: isolates "what does mooring do to
    # an already-sized pile" without claiming any downsizing benefit yet ---
    bc90_same_geom = evaluate_bc90(inputs, g_mp, mooring)
    _print_row(
        "BC90 (same geometry as MP)", g_mp.diameter_m, g_mp.wall_thickness_m * 1000, g_mp.embedded_length_m,
        bc90_same_geom.steel_mass_t, bc90_same_geom.total_capex_usd,
        bc90_same_geom.uls_utilization, bc90_same_geom.sls_utilization, bc90_same_geom.nfa_utilization,
        bc90_same_geom.fls_utilization, bc90_same_geom.buckling_utilization, bc90_same_geom.governing_constraint,
    )

    # --- BC90, pile geometry shrunk (outer loop only, mooring held fixed):
    # the actual value-proposition comparison -- how much smaller can the
    # pile go once the mooring line is carrying some of the load ---
    g_shrunk, bc90_shrunk, started_passing = shrink_geometry_with_mooring(inputs, g_mp, mooring)
    if not started_passing:
        print("\n  NOTE: starting geometry failed a BC90 check before any shrinking was attempted.")
    _print_row(
        "BC90 (shrunk pile)", g_shrunk.diameter_m, g_shrunk.wall_thickness_m * 1000, g_shrunk.embedded_length_m,
        bc90_shrunk.steel_mass_t, bc90_shrunk.total_capex_usd,
        bc90_shrunk.uls_utilization, bc90_shrunk.sls_utilization, bc90_shrunk.nfa_utilization,
        bc90_shrunk.fls_utilization, bc90_shrunk.buckling_utilization, bc90_shrunk.governing_constraint,
    )

    print(f"\nMooring layout used: N_ml=3  R_a={mooring.r_a_m:.1f} m  d_sb_fl={mooring.d_sb_fl_m:.1f} m  "
          f"theta={bc90_shrunk.theta_deg:.1f} deg  L_ml={bc90_shrunk.l_ml_m:.1f} m")
    print(f"  K_ml(quasi-static)={mooring.k_ml_mn_per_m:.2f} MN/m  K_ml(dynamic)={mooring.k_ml_dynamic_mn_per_m:.2f} MN/m  "
          f"T0={mooring.t0_mn:.2f} MN ({100*mooring.t0_mn/mooring.mbl_mn:.1f}% MBL)  MBL={mooring.mbl_mn:.2f} MN")
    print(f"  T_max={bc90_shrunk.mooring_t_max_mn:.2f} MN  T_min={bc90_shrunk.mooring_t_min_mn:.2f} MN  "
          f"MooringULS utilization={bc90_shrunk.mooring_uls_utilization:.3f}  Slack utilization={bc90_shrunk.slack_utilization:.3f}")

    print(f"\nSteel mass:  MP={mp_result.steel_mass_t:.1f} t  ->  BC90(shrunk)={bc90_shrunk.steel_mass_t:.1f} t  "
          f"({100*(1 - bc90_shrunk.steel_mass_t/mp_result.steel_mass_t):.1f}% less steel)")
    print(f"Total CAPEX: MP=${mp_result.steel_cost_usd:,.0f}  ->  BC90(shrunk)=${bc90_shrunk.total_capex_usd:,.0f}  "
          f"({100*(1 - bc90_shrunk.total_capex_usd/mp_result.steel_cost_usd):+.1f}% vs. MP steel-only cost)")

    if bc90_shrunk.notes:
        print(f"\nBC90(shrunk) flagged notes ({len(bc90_shrunk.notes)}):")
        for n in bc90_shrunk.notes:
            print(f"  - {n}")


if __name__ == "__main__":
    main()
