"""
Load transfer functions: wind-thrust moment PSD, wave-load moment transfer
function (linearized Morison), and dynamic amplification -- the pieces that
turn wind/wave excitation spectra (spectra.py) into a mudline moment
response PSD.
"""
import math

RATED_WIND_SPEED_DEFAULT_M_S = 11.0  # typical across modern multi-MW offshore turbines (~10.5-12 m/s)


def thrust_slope_mn_per_m_s(thrust_mn: float, u_bar_m_s: float,
                             rated_wind_speed_m_s: float = RATED_WIND_SPEED_DEFAULT_M_S) -> float:
    """dT/dU [MN/(m/s)] at a mean wind speed, from a generic normalized
    thrust-curve shape -- not a turbine-specific C_T(U) curve, since
    TURBINE_LIBRARY only has one rated-thrust value (see
    docs/method_update_log.md). Shape: quadratic rise to rated (T~U^2,
    roughly constant C_T below rated), then T~1/U above rated (pitch control
    holding power ~constant). A concept-stage placeholder, in the same spirit
    as engine._tower_geometry's tower-diameter regression -- refine once real
    per-turbine C_T(U) data is sourced.
    """
    u_r = rated_wind_speed_m_s
    if u_bar_m_s <= u_r:
        return thrust_mn * 2 * u_bar_m_s / u_r ** 2
    return thrust_mn * (-u_r / u_bar_m_s ** 2)


def wind_moment_psd(s_uu: float, thrust_slope_mn_per_m_s_: float, lever_arm_m: float) -> float:
    """S_M,wind(omega) = (dT/dU)^2 * lever_arm^2 * S_uu(omega) [MN^2*m^2*s].

    Quasi-steady (no dynamic-inflow attenuation |G_ind(omega)|) -- a
    concept-stage simplification, consistent with the engine's existing
    quasi-static wave treatment.
    """
    return (thrust_slope_mn_per_m_s_ * lever_arm_m) ** 2 * s_uu


def wave_moment_transfer_fn_sq(omega_rad_s: float, hs_m: float, tp_s: float,
                                diameter_m: float, water_depth_m: float,
                                rho_seawater_kg_m3: float, morison_cd: float,
                                g: float, n_slices: int = 40) -> float:
    """|T_wave(omega)|^2 [MN^2], the linearized-Morison mudline-moment
    transfer function (moment amplitude per unit wave-elevation amplitude),
    integrated over depth with the same trapezoidal pattern as
    engine._extreme_loads.

    Drag is linearized (Lorentz/stochastic linearization,
    |u|u ~ sqrt(8/pi)*sigma_u*u) about a single-pass estimate of the local
    orbital-velocity std dev, from the peak-period kinematics scaled by the
    significant-wave elevation std dev (sigma_eta = Hs/4) rather than a full
    nested spectral integral -- a documented one-pass simplification (see
    docs/method_update_log.md), adequate for a single representative sea
    state; iterating this to convergence is flagged as future refinement.
    """
    omega_p = 2 * math.pi / tp_s
    k_p = omega_p ** 2 / g  # deep-water dispersion, matches _extreme_loads
    k_omega = omega_rad_s ** 2 / g
    sigma_eta_m = hs_m / 4.0

    dz = water_depth_m / n_slices
    transfer_mn = 0.0
    for i in range(n_slices + 1):
        z = -water_depth_m + i * dz  # z=0 at MSL, z=-water_depth at mudline
        sigma_u_z_m_s = omega_p * sigma_eta_m * math.exp(k_p * z)
        c_drag_lin_mn_s_m2 = (
            0.5 * rho_seawater_kg_m3 * morison_cd * diameter_m
            * math.sqrt(8 / math.pi) * sigma_u_z_m_s / 1e6
        )
        depth_atten = math.exp(k_omega * z)
        moment_arm_m = z + water_depth_m
        weight = 0.5 if i in (0, n_slices) else 1.0
        transfer_mn += weight * c_drag_lin_mn_s_m2 * omega_rad_s * depth_atten * moment_arm_m * dz
    return transfer_mn ** 2


def dynamic_amplification_sq(omega_rad_s: float, f0_hz: float, damping_ratio: float) -> float:
    """DAF^2(omega) = 1/[(1-r^2)^2 + (2*zeta*r)^2], r = omega/omega0."""
    omega_0 = 2 * math.pi * f0_hz
    r = omega_rad_s / omega_0
    return 1.0 / ((1 - r ** 2) ** 2 + (2 * damping_ratio * r) ** 2)
