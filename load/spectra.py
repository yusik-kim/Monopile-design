"""
Wind and wave excitation spectra for the frequency-domain FLS check.

Kaimal (IEC 61400-1) and JONSWAP (DNV-RP-C205) power spectral densities, both
expressed in angular frequency omega [rad/s] so they combine directly with
the structural transfer functions in dynamics.py.
"""
import math

IEC_LAMBDA_1_M = 42.0  # IEC 61400-1 turbulence length-scale parameter, hub height > 60 m


def kaimal_spectrum(omega_rad_s: float, u_bar_m_s: float, turbulence_intensity: float) -> float:
    """One-sided Kaimal PSD of longitudinal wind speed, S_uu(omega) [(m/s)^2*s].

    IEC 61400-1 defines the Kaimal model in terms of frequency f [Hz]:
        S_uu(f) = sigma_u^2 * (4*L_k/Ubar) / (1 + 6*f*L_k/Ubar)^(5/3)
    Converted to angular frequency via S(omega) = S(f)/(2*pi), f = omega/(2*pi),
    so it integrates consistently (d(omega) = 2*pi*df) against the
    omega-domain transfer functions and JONSWAP spectrum below.
    """
    if omega_rad_s <= 0.0:
        return 0.0
    sigma_u_m_s = turbulence_intensity * u_bar_m_s
    l_k_m = 8.1 * IEC_LAMBDA_1_M
    f_hz = omega_rad_s / (2 * math.pi)
    s_f = sigma_u_m_s ** 2 * (4 * l_k_m / u_bar_m_s) / (1 + 6 * f_hz * l_k_m / u_bar_m_s) ** (5 / 3)
    return s_f / (2 * math.pi)


def jonswap_spectrum(omega_rad_s: float, hs_m: float, tp_s: float, gamma: float = 3.3) -> float:
    """One-sided JONSWAP PSD of sea-surface elevation, S_eta(omega) [m^2*s].

    DNV-RP-C205 Hs-parameterized form (avoids a separate Phillips constant);
    the A_gamma normalizing factor keeps the total variance at Hs^2/16.
    """
    if omega_rad_s <= 0.0:
        return 0.0
    omega_p = 2 * math.pi / tp_s
    sigma = 0.07 if omega_rad_s <= omega_p else 0.09
    a_gamma = 1.0 - 0.287 * math.log(gamma)
    peak_shape = math.exp(-1.25 * (omega_p / omega_rad_s) ** 4)
    peak_enhancement = gamma ** math.exp(-0.5 * ((omega_rad_s - omega_p) / (sigma * omega_p)) ** 2)
    return a_gamma * (5.0 / 16.0) * hs_m ** 2 * omega_p ** 4 * omega_rad_s ** -5 * peak_shape * peak_enhancement
