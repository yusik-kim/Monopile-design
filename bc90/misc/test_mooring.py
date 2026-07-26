"""
Light, dependency-free sanity check for bc90/mooring.py. Run directly:

    python bc90/misc/test_mooring.py

No pytest/GUI required -- prints each check and raises AssertionError on
failure, matching the convention of the baseline's own test_engine.py.
Checks reproduce the exact-limit derivations in
docs/BC90_METHODOLOGY_REPORT.md Sections 4b, 4c, and 7 -- these are not
arbitrary regression numbers, they are the closed-form identities the
methodology report itself derives and relies on.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from bc90.mooring import (
    MooringLayout,
    line_geometry,
    net_horizontal_stiffness,
    net_mudline_loads,
    nfa_flexibility_correction,
    pile_flexibility,
    single_line_horizontal_stiffness,
    solve_mooring_reaction,
    vertical_mooring_force,
)


def check_three_line_isotropy():
    """Section 4b: sum_i cos^2(phi_i - phi_load) == 1.5 for 3 equally-spaced
    lines, for ANY load heading -- verified here by brute-force summation
    over several headings, then checked against net_horizontal_stiffness's
    closed form (1.5 * single-line stiffness)."""
    print("Check: 3-line isotropic net stiffness")
    layout = MooringLayout(r_a_m=80.0, d_sb_fl_m=50.0, k_ml_mn_per_m=12.0, t0_mn=3.0)
    phi_lines_deg = [0.0, 120.0, 240.0]
    k_single = single_line_horizontal_stiffness(layout)

    for phi_load_deg in [0.0, 37.0, 90.0, 200.0, 359.0]:
        phi_load = math.radians(phi_load_deg)
        brute_force_sum = sum(
            math.cos(math.radians(phi_i) - phi_load) ** 2 for phi_i in phi_lines_deg
        )
        assert abs(brute_force_sum - 1.5) < 1e-12, (
            f"expected sum cos^2 == 1.5 at heading {phi_load_deg} deg, got {brute_force_sum}"
        )

    k_net = net_horizontal_stiffness(layout)
    assert abs(k_net - 1.5 * k_single) < 1e-12
    print(f"  k_single={k_single:.4f} MN/m  K_ml,net={k_net:.4f} MN/m (= 1.5x, isotropic)  PASS\n")


def check_geometry_consistency():
    print("Check: line geometry (theta, L_ml)")
    layout = MooringLayout(r_a_m=80.0, d_sb_fl_m=60.0, k_ml_mn_per_m=10.0, t0_mn=2.0)
    theta_rad, l_ml_m = line_geometry(layout)
    assert abs(l_ml_m - math.hypot(80.0, 60.0)) < 1e-9
    assert abs(math.tan(theta_rad) - 60.0 / 80.0) < 1e-9
    print(f"  theta={math.degrees(theta_rad):.2f} deg  L_ml={l_ml_m:.2f} m  PASS\n")


def check_pile_flexibility_symmetry_and_baseline_reduction():
    """f(a,b) must be symmetric (Maxwell-Betti) and reduce exactly to the
    baseline's cantilever_flexibility + 1/K_L + h^2/K_R when a=b=h."""
    print("Check: pile_flexibility symmetry and a=b=h reduction to baseline form")
    k_lat, k_rock, ei = 25.0, 4.0e4, 6.0e5  # representative MN/m, MN.m/rad, MN.m^2

    f_ab = pile_flexibility(30.0, 90.0, k_lat, k_rock, ei)
    f_ba = pile_flexibility(90.0, 30.0, k_lat, k_rock, ei)
    assert abs(f_ab - f_ba) < 1e-12, "flexibility kernel must be symmetric in (a,b)"

    h = 90.0
    f_hh = pile_flexibility(h, h, k_lat, k_rock, ei)
    baseline_form = 1.0 / k_lat + h ** 2 / k_rock + h ** 3 / (3 * ei)
    assert abs(f_hh - baseline_form) < 1e-9, "a=b=h must reduce to baseline cantilever formula"
    print(f"  f(30,90)={f_ab:.6e} == f(90,30)={f_ba:.6e}")
    print(f"  f(h,h)={f_hh:.6e} == baseline form {baseline_form:.6e}  PASS\n")


def check_mooring_reaction_limits():
    """Section 4c Step 2: F_ml must vanish for zero stiffness, and approach
    the rigid-prop reaction delta_fl0/f_aa as K_ml,net -> infinity."""
    print("Check: solve_mooring_reaction limits")
    delta_fl0_m = 0.35
    f_aa = 2.0e-4

    f_ml_zero = solve_mooring_reaction(delta_fl0_m, f_aa, k_ml_net_mn_per_m=0.0)
    assert abs(f_ml_zero) < 1e-12

    f_ml_huge = solve_mooring_reaction(delta_fl0_m, f_aa, k_ml_net_mn_per_m=1e12)
    rigid_prop_reaction = delta_fl0_m / f_aa
    assert abs(f_ml_huge - rigid_prop_reaction) / rigid_prop_reaction < 1e-6
    print(f"  F_ml(k=0)={f_ml_zero:.6f}  F_ml(k->inf)={f_ml_huge:.4f} ~= delta/f_aa={rigid_prop_reaction:.4f}  PASS\n")


def check_net_mudline_loads_statics():
    print("Check: net_mudline_loads statics")
    m_char, v_char, f_ml, d_sb_fl = 500.0, 8.0, 3.0, 60.0
    m_net, v_net, m_fl = net_mudline_loads(m_char, v_char, f_ml, d_sb_fl)
    assert abs(m_net - (m_char - f_ml * d_sb_fl)) < 1e-12
    assert abs(v_net - (v_char - f_ml)) < 1e-12
    assert abs(m_fl - (m_char - d_sb_fl * v_char)) < 1e-12
    print(f"  M_char_net={m_net:.2f}  V_char_net={v_net:.2f}  M_fl={m_fl:.2f}  PASS\n")


def check_vertical_force_direction_and_magnitude():
    print("Check: vertical_mooring_force magnitude (3*T0*sin(theta))")
    layout = MooringLayout(r_a_m=60.0, d_sb_fl_m=60.0, k_ml_mn_per_m=10.0, t0_mn=4.0)
    theta_rad, _ = line_geometry(layout)
    f_z = vertical_mooring_force(layout)
    expected = 3 * 4.0 * math.sin(theta_rad)
    assert abs(f_z - expected) < 1e-12
    assert f_z > 0.0, "vertical mooring force must be a positive (downward) axial addition"
    print(f"  Fz={f_z:.4f} MN (theta={math.degrees(theta_rad):.1f} deg)  PASS\n")


def check_nfa_correction_rigid_mooring_limit():
    """Section 7 rigid-mooring limit: f_total -> f_hh - (f_ha)^2/f_aa as
    K_ml,net -> infinity (the cantilever-pinned-at-fairlead flexibility)."""
    print("Check: nfa_flexibility_correction, rigid-mooring limit")
    k_lat, k_rock, ei = 25.0, 4.0e4, 6.0e5
    d_sb_fl, h = 60.0, 150.0

    f_hh = pile_flexibility(h, h, k_lat, k_rock, ei)
    f_ha = pile_flexibility(d_sb_fl, h, k_lat, k_rock, ei)
    f_aa = pile_flexibility(d_sb_fl, d_sb_fl, k_lat, k_rock, ei)

    f_total_rigid = nfa_flexibility_correction(f_hh, f_ha, f_aa, k_ml_net_mn_per_m=1e12)
    pinned_at_fairlead = f_hh - (f_ha ** 2) / f_aa
    assert abs(f_total_rigid - pinned_at_fairlead) / pinned_at_fairlead < 1e-6
    assert f_total_rigid < f_hh, "mooring must stiffen (reduce flexibility), never soften"
    print(f"  f_total(k->inf)={f_total_rigid:.6e} ~= pinned-at-fairlead={pinned_at_fairlead:.6e}  PASS\n")


def check_nfa_correction_fairlead_at_mudline_limit():
    """Section 7 second exact limit: as d_sb_fl -> 0, f_aa=f_ha=1/K_L, and
    the formula must collapse to the trivial parallel-spring result
    1/(K_L + K_ml,net) -- i.e. exactly replacing K_L with K_L+K_ml,net."""
    print("Check: nfa_flexibility_correction, fairlead-at-mudline limit")
    k_lat = 25.0
    f_aa = f_ha = 1.0 / k_lat
    f_hh = f_aa  # degenerate single-spring case used only to test the algebraic limit
    k_ml_net = 9.0

    f_total = nfa_flexibility_correction(f_hh, f_ha, f_aa, k_ml_net)
    parallel_spring = 1.0 / (k_lat + k_ml_net)
    assert abs(f_total - parallel_spring) < 1e-12
    print(f"  f_total={f_total:.6f} == 1/(K_L+K_ml,net)={parallel_spring:.6f}  PASS\n")


if __name__ == "__main__":
    check_three_line_isotropy()
    check_geometry_consistency()
    check_pile_flexibility_symmetry_and_baseline_reduction()
    check_mooring_reaction_limits()
    check_net_mudline_loads_statics()
    check_vertical_force_direction_and_magnitude()
    check_nfa_correction_rigid_mooring_limit()
    check_nfa_correction_fairlead_at_mudline_limit()
    print("All bc90/mooring.py checks passed.")
