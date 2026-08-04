"""
Spectral moments, Dirlik's closed-form rainflow-equivalent stress-range
distribution, and Palmgren-Miner damage summation.

Uses engine.py's existing single-slope S-N constants (SN_LOG10_A, SN_M) --
matches its documented first segment. The DNV-RP-C203 bilinear second
segment (m2=5 above 10^7 cycles) is flagged as a follow-up refinement, not
implemented here, since its exact log10(a2) digit needs verifying against
the specific joint classification before it's hardcoded (see
docs/method_update_log.md) -- shipping an unverified second-segment constant
would be worse than being explicit about not having one yet.
"""
import math


def spectral_moments(omega_grid: list[float], s_sigma: list[float]) -> tuple[float, float, float, float]:
    """(lambda0, lambda1, lambda2, lambda4) via trapezoidal integration of
    omega^n * S_sigma(omega) over the given grid -- same numerical-
    integration style already used elsewhere in the engine (e.g.
    engine._extreme_loads's depth integral).
    """
    moments = [0.0, 0.0, 0.0, 0.0]
    orders = (0, 1, 2, 4)
    for i in range(len(omega_grid) - 1):
        w0, w1 = omega_grid[i], omega_grid[i + 1]
        s0, s1 = s_sigma[i], s_sigma[i + 1]
        dw = w1 - w0
        for idx, n in enumerate(orders):
            moments[idx] += 0.5 * (w0 ** n * s0 + w1 ** n * s1) * dw
    return tuple(moments)


def dirlik_parameters(lambda0: float, lambda1: float, lambda2: float, lambda4: float) -> dict:
    """Dirlik (1985) closed-form parameters D1, D2, D3, Q, R fitted to the
    first four spectral moments -- three densities (one exponential, two
    Rayleigh) approximating the true rainflow stress-range PDF without ever
    forming a time series.
    """
    xm = (lambda1 / lambda0) * math.sqrt(lambda2 / lambda4)
    alpha2 = lambda2 / math.sqrt(lambda0 * lambda4)
    d1 = 2 * (xm - alpha2 ** 2) / (1 + alpha2 ** 2)
    r = (alpha2 - xm - d1 ** 2) / (1 - alpha2 - d1 + d1 ** 2)
    d2 = (1 - alpha2 - d1 + d1 ** 2) / (1 - r)
    d3 = 1 - d1 - d2
    q = 1.25 * (alpha2 - d3 - d2 * r) / d1
    return {"D1": d1, "D2": d2, "D3": d3, "Q": q, "R": r}


def dirlik_expected_s_power(lambda0: float, dirlik: dict, m: float) -> float:
    """E[S^m] under the Dirlik density, closed form (exponential and Rayleigh
    moments are standard Gamma-function results):
        E[S^m] = (2*sqrt(lambda0))^m * [D1*Q^m*Gamma(m+1)
                  + (D2*R^m + D3)*2^(m/2)*Gamma(1+m/2)]
    This is what makes the method non-iterative and cheap -- no numerical
    integration over the stress-range distribution itself is needed.
    """
    d1, d2, d3, q, r = dirlik["D1"], dirlik["D2"], dirlik["D3"], dirlik["Q"], dirlik["R"]
    return (2 * math.sqrt(lambda0)) ** m * (
        d1 * q ** m * math.gamma(m + 1)
        + (d2 * r ** m + d3) * 2 ** (m / 2) * math.gamma(1 + m / 2)
    )


def bin_damage(lambda0: float, lambda1: float, lambda2: float, lambda4: float,
                s_n_log10_a: float, s_n_m: float, exposure_hours: float) -> float:
    """Damage contribution from one (DLC, wind-bin) sea state:
        D_bin = (nu0 * T_seconds / a1) * E[S^m]
    nu0 (mean up-crossing rate) comes from the response's own spectral
    moments -- replaces engine._fls_check's "one cycle per rotor revolution"
    assumption entirely.
    """
    nu0_hz = (1 / (2 * math.pi)) * math.sqrt(lambda2 / lambda0)
    dirlik = dirlik_parameters(lambda0, lambda1, lambda2, lambda4)
    e_s_m = dirlik_expected_s_power(lambda0, dirlik, s_n_m)
    a1 = 10 ** s_n_log10_a
    exposure_seconds = exposure_hours * 3600.0
    return (nu0_hz * exposure_seconds / a1) * e_s_m
