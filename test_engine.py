"""
Light, dependency-free sanity check for engine.py. Run directly:

    python test_engine.py

No pytest/GUI required -- prints each check and raises AssertionError on
failure. See docs/METHODOLOGY_REPORT.md Sections 8 and 10 for the numbers this
reproduces.
"""
from engine import DesignInputs, SoilProfile, MonopileGeometry, evaluate_monopile, size_monopile, turbine_from_capacity


def check_15mw_sand_converges():
    print("Case: 15 MW, 35 m water depth, sand (phi=35 deg)")
    soil = SoilProfile(soil_type="sand", friction_angle_deg=35.0, submerged_unit_weight_kn_m3=9.5)
    inputs = DesignInputs(turbine_mw=15.0, water_depth_m=35.0, soil=soil, hs_m=5.0, tp_s=10.0, current_m_s=0.5)
    result = size_monopile(inputs)
    g = result.geometry

    print(f"  D={g.diameter_m:.2f} m  t={g.wall_thickness_m*1000:.1f} mm  "
          f"L={g.embedded_length_m:.2f} m  L/D={g.embedded_length_m/g.diameter_m:.2f}")
    print(f"  utilizations: ULS={result.uls_utilization:.3f} SLS={result.sls_utilization:.3f} "
          f"NFA={result.nfa_utilization:.3f} FLS={result.fls_utilization:.3f}")
    print(f"  governing: {result.governing_constraint}")

    assert not any("did not converge" in n for n in result.notes), "expected this case to converge"
    assert result.uls_utilization <= 1.0
    assert result.sls_utilization <= 1.0
    assert result.nfa_utilization <= 1.0
    assert result.fls_utilization <= 1.0
    # Sanity range vs. the published IEA 15 MW reference monopile.
    assert 7.0 <= g.diameter_m <= 12.0, "diameter outside plausible IEA 15MW reference range"
    assert 30.0 <= g.embedded_length_m <= 60.0, "embedded length outside plausible range"
    print("  PASS\n")


def check_5mw_sand_converges():
    print("Case: 5 MW, 20 m water depth, sand (phi=36 deg)")
    soil = SoilProfile(soil_type="sand", friction_angle_deg=36.0, submerged_unit_weight_kn_m3=10.0)
    inputs = DesignInputs(turbine_mw=5.0, water_depth_m=20.0, soil=soil, hs_m=3.0, tp_s=7.0, current_m_s=0.3)
    result = size_monopile(inputs)
    g = result.geometry

    print(f"  D={g.diameter_m:.2f} m  t={g.wall_thickness_m*1000:.1f} mm  "
          f"L={g.embedded_length_m:.2f} m  L/D={g.embedded_length_m/g.diameter_m:.2f}")
    print(f"  utilizations: ULS={result.uls_utilization:.3f} SLS={result.sls_utilization:.3f} "
          f"NFA={result.nfa_utilization:.3f} FLS={result.fls_utilization:.3f}")
    print(f"  governing: {result.governing_constraint}")

    assert not any("did not converge" in n for n in result.notes), "expected this case to converge"
    assert result.uls_utilization <= 1.0
    assert result.sls_utilization <= 1.0
    assert result.nfa_utilization <= 1.0
    assert result.fls_utilization <= 1.0
    # Sanity range vs. the real OC3/NREL 5 MW reference monopile (D=6m).
    assert 4.0 <= g.diameter_m <= 8.0, "diameter outside plausible OC3 5MW reference range"
    assert 20.0 <= g.embedded_length_m <= 40.0, "embedded length outside plausible range"
    print("  PASS\n")


def check_22mw_sand_converges():
    print("Case: 22 MW, 34 m water depth, sand (phi=36 deg)")
    soil = SoilProfile(soil_type="sand", friction_angle_deg=36.0, submerged_unit_weight_kn_m3=10.0)
    inputs = DesignInputs(turbine_mw=22.0, water_depth_m=34.0, soil=soil, hs_m=6.0, tp_s=10.5, current_m_s=0.5)
    result = size_monopile(inputs)
    g = result.geometry

    print(f"  D={g.diameter_m:.2f} m  t={g.wall_thickness_m*1000:.1f} mm  "
          f"L={g.embedded_length_m:.2f} m  L/D={g.embedded_length_m/g.diameter_m:.2f}")
    print(f"  utilizations: ULS={result.uls_utilization:.3f} SLS={result.sls_utilization:.3f} "
          f"NFA={result.nfa_utilization:.3f} FLS={result.fls_utilization:.3f}")
    print(f"  governing: {result.governing_constraint}")

    assert not any("did not converge" in n for n in result.notes), "expected this case to converge"
    assert result.uls_utilization <= 1.0
    assert result.sls_utilization <= 1.0
    assert result.nfa_utilization <= 1.0
    assert result.fls_utilization <= 1.0
    # Sanity range vs. the real IEA 22MW reference monopile (D=10m, optimizer-capped).
    assert 8.0 <= g.diameter_m <= 14.0, "diameter outside plausible IEA 22MW reference range"
    assert 40.0 <= g.embedded_length_m <= 70.0, "embedded length outside plausible range"
    print("  PASS\n")


def check_8mw_clay_converges_since_nfa_fix():
    """
    Before the 2026-07-16 NFA fix (see docs/METHODOLOGY_REPORT.md Section 10),
    this case hit the non-convergence guard. It now converges as a side
    effect of the same two-segment-cantilever fix -- still flags the
    separate, legitimate beta*L<2.5 soil-validity caveat (this case
    genuinely is at the edge of the closed-form soil assumption's range).
    """
    print("Case: 8 MW, 25 m water depth, clay (su=80 kPa) -- previously non-converging, fixed by the NFA update")
    soil = SoilProfile(soil_type="clay", undrained_shear_strength_kpa=80.0, submerged_unit_weight_kn_m3=8.0)
    inputs = DesignInputs(turbine_mw=8.0, water_depth_m=25.0, soil=soil, hs_m=3.5, tp_s=8.0, current_m_s=0.4)
    result = size_monopile(inputs)

    assert not any("did not converge" in n for n in result.notes), "expected this case to converge post-NFA-fix"
    assert any("beta*L < 2.5" in n for n in result.notes), \
        "expected the soil-validity caveat to still be flagged (separate, legitimate issue)"
    print("  now converges; soil-validity caveat still correctly flagged")
    print("  PASS\n")


def check_turbine_library_matches_sources():
    print("Case: TURBINE_LIBRARY exact values match sourced reference turbines (see docs/METHODOLOGY_REPORT.md Section 2)")
    oc3_5mw = turbine_from_capacity(5.0)
    assert oc3_5mw["rotor_diameter_m"] == 126.0
    assert oc3_5mw["hub_height_m"] == 90.0
    assert oc3_5mw["mass_t"] == 697.5

    iea_15mw = turbine_from_capacity(15.0)
    assert iea_15mw["hub_height_m"] == 150.0
    assert iea_15mw["thrust_mn"] == 2.50

    iea_22mw = turbine_from_capacity(22.0)
    assert iea_22mw["rotor_diameter_m"] == 284.0
    assert iea_22mw["hub_height_m"] == 170.0
    assert iea_22mw["rpm_min"] == 1.807

    mid = turbine_from_capacity(18.0)  # interpolated, between the 15 and 22 MW anchors
    assert 150.0 < mid["hub_height_m"] < 170.0
    print("  PASS\n")


def check_nfa_matches_real_geometries():
    """
    Fixed 2026-07-16 (see docs/METHODOLOGY_REPORT.md Section 10 and
    docs/methodology.md, kept local-only): the two-segment cantilever (pile-above-mudline +
    tower, instead of one uniform "average tower" section) and the
    soft-stiff band's degenerate-gap fallback. Verifies f0 at the *real*
    reference monopile geometries against the two source reports.
    """
    print("Case: NFA at real reference geometries (5MW/OC3, 22MW/IEA)")

    # 5 MW / OC3 real geometry (D=6m, t=60mm, L=36m, 20m water depth):
    # f0 must now sit inside the turbine's own soft-stiff band.
    soil_5mw = SoilProfile(soil_type="sand", friction_angle_deg=36.0, submerged_unit_weight_kn_m3=10.0)
    inputs_5mw = DesignInputs(turbine_mw=5.0, water_depth_m=20.0, soil=soil_5mw, hs_m=3.0, tp_s=7.0, current_m_s=0.3)
    geom_5mw = MonopileGeometry(diameter_m=6.0, wall_thickness_m=0.060, embedded_length_m=36.0)
    result_5mw = evaluate_monopile(inputs_5mw, geom_5mw)
    band_low_5mw, band_high_5mw = result_5mw.soft_stiff_band_hz
    assert band_low_5mw <= result_5mw.natural_frequency_hz <= band_high_5mw, \
        f"f0={result_5mw.natural_frequency_hz:.4f} Hz outside band [{band_low_5mw:.4f}, {band_high_5mw:.4f}]"
    print(f"  5MW: f0={result_5mw.natural_frequency_hz:.4f} Hz, band=[{band_low_5mw:.4f}, {band_high_5mw:.4f}] Hz -- inside band")

    # 22 MW / IEA real geometry (D=10m, t=100mm, L=45m, 34m water depth):
    # band must no longer be inverted, and f0 should land close to the
    # report's own stated ~0.16 Hz (achieved first fore-aft frequency).
    soil_22mw = SoilProfile(soil_type="sand", friction_angle_deg=36.0, submerged_unit_weight_kn_m3=10.0)
    inputs_22mw = DesignInputs(turbine_mw=22.0, water_depth_m=34.0, soil=soil_22mw, hs_m=6.0, tp_s=10.5, current_m_s=0.5)
    geom_22mw = MonopileGeometry(diameter_m=10.0, wall_thickness_m=0.100, embedded_length_m=45.0)
    result_22mw = evaluate_monopile(inputs_22mw, geom_22mw)
    band_low_22mw, band_high_22mw = result_22mw.soft_stiff_band_hz
    assert band_low_22mw < band_high_22mw, "soft-stiff band is inverted -- fallback logic did not engage"
    assert abs(result_22mw.natural_frequency_hz - 0.16) < 0.01, \
        f"f0={result_22mw.natural_frequency_hz:.4f} Hz too far from the IEA 22MW report's stated ~0.16 Hz"
    print(f"  22MW: f0={result_22mw.natural_frequency_hz:.4f} Hz (report states ~0.16 Hz), "
          f"band=[{band_low_22mw:.4f}, {band_high_22mw:.4f}] Hz -- valid, not inverted")
    print("  PASS\n")


if __name__ == "__main__":
    check_turbine_library_matches_sources()
    check_5mw_sand_converges()
    check_15mw_sand_converges()
    check_22mw_sand_converges()
    check_8mw_clay_converges_since_nfa_fix()
    check_nfa_matches_real_geometries()
    print("All checks passed.")
