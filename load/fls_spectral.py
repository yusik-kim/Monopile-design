"""
Frequency-domain FLS check: orchestrates spectra.py + environment.py +
damping.py + dynamics.py + fatigue.py into a single (damage, utilization,
notes) result, matching the shape of engine._fls_check so it can plug into
DesignInputs.fls_method="spectral" as a side-by-side alternative -- default
remains fls_method="simple" (engine._fls_check, unchanged) until this is
benchmarked against the 5/15/22 MW reference cases in
docs/METHODOLOGY_REPORT.md Sec.10. See docs/method_update_log.md for the
rollout/validation plan.

Scope (current): DLC12 (power production) only. DLC72 (parked/idling) is an
accepted label in DesignInputs.dlcs_to_run but raises NotImplementedError --
its own sea-state/wind-range expansion is intentionally not defined yet.
ULS/extreme DLCs (13/16/61) are out of scope entirely.
"""
from engine import (
    DesignInputs, MonopileGeometry, RHO_SEAWATER_KG_M3, MORISON_CD, G,
    SN_LOG10_A, SN_M, FATIGUE_DESIGN_FACTOR, _pile_section_properties,
)
from load import spectra, environment, damping, dynamics, fatigue

OMEGA_MIN_RAD_S = 1e-3
OMEGA_MAX_RAD_S = 6.0  # covers wave + wind-turbulence + 1P energy for all TURBINE_LIBRARY entries
N_OMEGA_POINTS = 300


def _omega_grid() -> list[float]:
    n = N_OMEGA_POINTS
    step = (OMEGA_MAX_RAD_S - OMEGA_MIN_RAD_S) / (n - 1)
    return [OMEGA_MIN_RAD_S + i * step for i in range(n)]


def _stress_psd_at(omega_rad_s: float, sea_state: environment.SeaState, turbine: dict,
                    diameter_m: float, water_depth_m: float, lever_arm_m: float,
                    turbulence_intensity: float, section_modulus_m3: float,
                    f0_hz: float, damping_ratio: float) -> float:
    """S_sigma(omega) = DAF^2(omega) * [S_M,wind(omega) + S_M,wave(omega)] / Z^2."""
    s_uu = spectra.kaimal_spectrum(omega_rad_s, sea_state.wind_speed_m_s, turbulence_intensity)
    thrust_slope = dynamics.thrust_slope_mn_per_m_s(turbine["thrust_mn"], sea_state.wind_speed_m_s)
    s_m_wind = dynamics.wind_moment_psd(s_uu, thrust_slope, lever_arm_m)

    s_eta = spectra.jonswap_spectrum(omega_rad_s, sea_state.hs_m, sea_state.tp_s)
    t_wave_sq = dynamics.wave_moment_transfer_fn_sq(
        omega_rad_s, sea_state.hs_m, sea_state.tp_s, diameter_m, water_depth_m,
        RHO_SEAWATER_KG_M3, MORISON_CD, G,
    )
    s_m_wave = t_wave_sq * s_eta

    daf_sq = dynamics.dynamic_amplification_sq(omega_rad_s, f0_hz, damping_ratio)
    return daf_sq * (s_m_wind + s_m_wave) / section_modulus_m3 ** 2


def _dlc12_damage(inputs: DesignInputs, geometry: MonopileGeometry, turbine: dict,
                   f0_hz: float, hs_ref_m: float, tp_ref_s: float,
                   section_modulus_m3: float, lever_arm_m: float, omega_grid: list[float]) -> float:
    zeta = damping.total_damping_ratio(
        "DLC12", inputs.damping_struct, inputs.damping_soil, inputs.damping_aero_dlc12
    )
    wind_bins = environment.dlc12_wind_bins(
        inputs.wind_bin_start_m_s, inputs.wind_bin_step_m_s, inputs.wind_bin_stop_m_s,
        inputs.weibull_k, inputs.weibull_a_m_s,
    )
    p_dlc12 = inputs.dlc_probability["DLC12"]

    total = 0.0
    for u_i, p_norm in wind_bins:
        sea_state = environment.dlc12_sea_state(u_i, hs_ref_m, tp_ref_s, inputs.u_ref_m_s)
        s_sigma = [
            _stress_psd_at(
                w, sea_state, turbine, geometry.diameter_m, inputs.water_depth_m, lever_arm_m,
                inputs.turbulence_intensity, section_modulus_m3, f0_hz, zeta,
            )
            for w in omega_grid
        ]
        lambda0, lambda1, lambda2, lambda4 = fatigue.spectral_moments(omega_grid, s_sigma)
        exposure_hours = environment.lifetime_hours(p_norm, p_dlc12, inputs.design_life_years)
        total += fatigue.bin_damage(lambda0, lambda1, lambda2, lambda4, SN_LOG10_A, SN_M, exposure_hours)
    return total


def evaluate_fls_spectral(inputs: DesignInputs, geometry: MonopileGeometry, turbine: dict,
                           f0_hz: float) -> tuple[float, float, list[str]]:
    """Spectral FLS check -- see module docstring for scope. Returns
    (damage, utilization, notes), matching engine._fls_check's shape.
    """
    notes: list[str] = []
    if "DLC72" in inputs.dlcs_to_run:
        raise NotImplementedError(
            "DLC72 (parked/idling) sea-state/wind-range expansion is not yet defined -- "
            "see docs/method_update_log.md. Remove 'DLC72' from dlcs_to_run for now."
        )
    unknown_dlcs = set(inputs.dlcs_to_run) - {"DLC12", "DLC72"}
    if unknown_dlcs:
        raise ValueError(f"Unknown DLC(s) in dlcs_to_run: {sorted(unknown_dlcs)}")
    for dlc in inputs.dlcs_to_run:
        if dlc not in inputs.dlc_probability:
            raise ValueError(f"dlc_probability has no entry for {dlc!r} (dlcs_to_run={inputs.dlcs_to_run})")

    _, i_second_moment, _ = _pile_section_properties(geometry)
    section_modulus_m3 = i_second_moment / (geometry.diameter_m / 2)
    lever_arm_m = turbine["hub_height_m"] + inputs.water_depth_m
    hs_ref_m, tp_ref_s = environment.site_severity_reference(
        inputs.site_severity, inputs.hs_ref_m, inputs.tp_ref_s
    )
    omega_grid = _omega_grid()

    total_damage = 0.0
    if "DLC12" in inputs.dlcs_to_run:
        total_damage += _dlc12_damage(
            inputs, geometry, turbine, f0_hz, hs_ref_m, tp_ref_s, section_modulus_m3, lever_arm_m, omega_grid
        )

    utilization = total_damage * FATIGUE_DESIGN_FACTOR
    return total_damage, utilization, notes
