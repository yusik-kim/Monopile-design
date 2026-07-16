"""
Light, dependency-free sanity check for engine.py. Run directly:

    python test_engine.py

No pytest/GUI required -- prints each check and raises AssertionError on
failure. See METHODOLOGY_REPORT.md Sections 8 and 10 for the numbers this
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


def check_8mw_clay_flags_nonconvergence():
    print("Case: 8 MW, 25 m water depth, clay (su=80 kPa) -- known non-converging edge case")
    soil = SoilProfile(soil_type="clay", undrained_shear_strength_kpa=80.0, submerged_unit_weight_kn_m3=8.0)
    inputs = DesignInputs(turbine_mw=8.0, water_depth_m=25.0, soil=soil, hs_m=3.5, tp_s=8.0, current_m_s=0.4)
    result = size_monopile(inputs)

    assert any("did not converge" in n for n in result.notes), \
        "expected this case to report non-convergence (see METHODOLOGY_REPORT.md Section 10)"
    print("  correctly reported non-convergence")
    print("  PASS\n")


def check_turbine_library_matches_sources():
    print("Case: TURBINE_LIBRARY exact values match sourced reference turbines (see METHODOLOGY_REPORT.md Section 2)")
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


def check_nfa_known_broken_outside_15_20mw():
    """
    Documents (does NOT hide) two NFA issues found 2026-07-16 when evaluating
    the model at the *real* reference monopile geometries -- see
    METHODOLOGY_REPORT.md Section 10. These assertions describe the current
    (broken) behavior so a future fix is a visible, deliberate change to this
    test, not a silent regression.
    """
    print("Case: NFA known-broken behavior outside 15-20 MW (documents bugs, not correctness)")

    # 5 MW / OC3 real geometry: model underpredicts f0 below its own band.
    soil_5mw = SoilProfile(soil_type="sand", friction_angle_deg=36.0, submerged_unit_weight_kn_m3=10.0)
    inputs_5mw = DesignInputs(turbine_mw=5.0, water_depth_m=20.0, soil=soil_5mw, hs_m=3.0, tp_s=7.0, current_m_s=0.3)
    geom_5mw = MonopileGeometry(diameter_m=6.0, wall_thickness_m=0.060, embedded_length_m=36.0)
    result_5mw = evaluate_monopile(inputs_5mw, geom_5mw)
    assert result_5mw.natural_frequency_hz < result_5mw.soft_stiff_band_hz[0], \
        "expected known underprediction at the real OC3 5MW geometry (fix this assertion if NFA is corrected)"
    print(f"  5MW: f0={result_5mw.natural_frequency_hz:.3f} Hz < band_low={result_5mw.soft_stiff_band_hz[0]:.3f} Hz (known issue)")

    # 22 MW / IEA real geometry: target band itself is inverted.
    soil_22mw = SoilProfile(soil_type="sand", friction_angle_deg=36.0, submerged_unit_weight_kn_m3=10.0)
    inputs_22mw = DesignInputs(turbine_mw=22.0, water_depth_m=34.0, soil=soil_22mw, hs_m=6.0, tp_s=10.5, current_m_s=0.5)
    geom_22mw = MonopileGeometry(diameter_m=10.0, wall_thickness_m=0.100, embedded_length_m=45.0)
    result_22mw = evaluate_monopile(inputs_22mw, geom_22mw)
    band_low, band_high = result_22mw.soft_stiff_band_hz
    assert band_low > band_high, \
        "expected known band inversion at 22MW (fix this assertion if NFA is corrected)"
    print(f"  22MW: band_low={band_low:.3f} Hz > band_high={band_high:.3f} Hz (known issue, inverted band)")
    print("  PASS (bugs confirmed present, not fixed)\n")


if __name__ == "__main__":
    check_turbine_library_matches_sources()
    check_15mw_sand_converges()
    check_8mw_clay_flags_nonconvergence()
    check_nfa_known_broken_outside_15_20mw()
    print("All checks passed.")
