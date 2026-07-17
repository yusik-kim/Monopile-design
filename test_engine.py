"""
Light, dependency-free sanity check for engine.py. Run directly:

    python test_engine.py

No pytest/GUI required -- prints each check and raises AssertionError on
failure. See docs/METHODOLOGY_REPORT.md Sections 2, 8, and 10 for the
numbers this reproduces.
"""
from engine import DesignInputs, SoilProfile, MonopileGeometry, evaluate_monopile, size_monopile, turbine_from_capacity


def check_5mw_sand_converges():
    """
    Sizes the 5 MW case with this tool, then compares against the real
    OC3/NREL 5 MW reference monopile (D=6m, t=60mm, L=36m, 20m water depth --
    see docs/METHODOLOGY_REPORT.md Section 2). f0 at the reference geometry
    is checked against the turbine's own soft-stiff band.
    """
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

    # --- Reproduce the real reference geometry directly and compare ---
    ref_geom = MonopileGeometry(diameter_m=6.0, wall_thickness_m=0.060, embedded_length_m=36.0)
    ref_result = evaluate_monopile(inputs, ref_geom)
    band_low, band_high = ref_result.soft_stiff_band_hz
    print(f"  vs. reference (OC3/NREL 5MW): D=6.00 m  t=60.0 mm  L=36.00 m")
    print(f"    at reference geometry: ULS={ref_result.uls_utilization:.3f} SLS={ref_result.sls_utilization:.3f} "
          f"NFA={ref_result.nfa_utilization:.3f} FLS={ref_result.fls_utilization:.3f} "
          f"governing={ref_result.governing_constraint}")
    print(f"    f0={ref_result.natural_frequency_hz:.4f} Hz, band=[{band_low:.4f}, {band_high:.4f}] Hz")
    assert band_low <= ref_result.natural_frequency_hz <= band_high, \
        f"f0={ref_result.natural_frequency_hz:.4f} Hz outside band [{band_low:.4f}, {band_high:.4f}]"
    print("  PASS\n")


def check_15mw_sand_converges():
    """
    Sizes the 15 MW case with this tool, then compares against the real IEA
    15 MW reference monopile (D=10m, L=45m -- see docs/METHODOLOGY_REPORT.md
    Section 2). Mudline wall thickness (~50mm) is an image-derived estimate
    from the source report's Fig. 4-2, not a table value, and water depth is
    not stated in the source (assumed 35m here to match this tool's own
    inputs) -- so unlike the 5MW/22MW cases below, utilizations at this
    "reference" geometry are informational only, not asserted against a
    validated target.
    """
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

    # --- Reproduce the real reference geometry directly and compare ---
    # t=50mm: image-derived estimate from Fig. 4-2 (mudline value), not a
    # table value; water depth not stated in source, assumed 35m.
    ref_geom = MonopileGeometry(diameter_m=10.0, wall_thickness_m=0.050, embedded_length_m=45.0)
    ref_result = evaluate_monopile(inputs, ref_geom)
    band_low, band_high = ref_result.soft_stiff_band_hz
    print(f"  vs. reference (IEA 15MW): D=10.00 m  t~50 mm (est., Fig. 4-2)  L=45.00 m")
    print(f"    at reference geometry: ULS={ref_result.uls_utilization:.3f} SLS={ref_result.sls_utilization:.3f} "
          f"NFA={ref_result.nfa_utilization:.3f} FLS={ref_result.fls_utilization:.3f} "
          f"governing={ref_result.governing_constraint}")
    print(f"    f0={ref_result.natural_frequency_hz:.4f} Hz, band=[{band_low:.4f}, {band_high:.4f}] Hz")
    print("    (informational only -- thickness/water depth are estimates, not sourced table values)")
    print("  PASS\n")


def check_22mw_sand_converges():
    """
    Sizes the 22 MW case with this tool, then compares against the real IEA
    22 MW reference monopile (D=10m, t=100mm, L=45m, 34m water depth -- see
    docs/METHODOLOGY_REPORT.md Section 2). f0 at the reference geometry is
    checked against the report's own stated ~0.16 Hz ("clamped at monopile
    base" -- see Section 2's frequency-comparison note).
    """
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

    # --- Reproduce the real reference geometry directly and compare ---
    ref_geom = MonopileGeometry(diameter_m=10.0, wall_thickness_m=0.100, embedded_length_m=45.0)
    ref_result = evaluate_monopile(inputs, ref_geom)
    band_low, band_high = ref_result.soft_stiff_band_hz
    print(f"  vs. reference (IEA 22MW): D=10.00 m  t=100.0 mm  L=45.00 m")
    print(f"    at reference geometry: ULS={ref_result.uls_utilization:.3f} SLS={ref_result.sls_utilization:.3f} "
          f"NFA={ref_result.nfa_utilization:.3f} FLS={ref_result.fls_utilization:.3f} "
          f"governing={ref_result.governing_constraint}")
    print(f"    f0={ref_result.natural_frequency_hz:.4f} Hz (report states ~0.16 Hz, clamped at monopile base), "
          f"band=[{band_low:.4f}, {band_high:.4f}] Hz")
    assert band_low < band_high, "soft-stiff band is inverted -- fallback logic did not engage"
    assert abs(ref_result.natural_frequency_hz - 0.16) < 0.01, \
        f"f0={ref_result.natural_frequency_hz:.4f} Hz too far from the IEA 22MW report's stated ~0.16 Hz"
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


if __name__ == "__main__":
    check_turbine_library_matches_sources()
    check_5mw_sand_converges()
    check_15mw_sand_converges()
    check_22mw_sand_converges()
    print("All checks passed.")
