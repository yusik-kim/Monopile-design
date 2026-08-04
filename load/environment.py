"""
Environmental input model for the frequency-domain FLS check: expands a
compact site-severity anchor into per-wind-speed DLC12 sea states and their
Weibull occurrence weighting, plus the DLC12/DLC72 top-level probability
split.

Ported from FloatingWind/Simulation_database/openfast_campaign/docs/
METOCEAN_PROBABILITY_METHOD.md (same equations/convention, not a code
import -- keeps the two projects' workspaces independent).

Only DLC12 (power production) is implemented here. DLC72 (parked/idling) is
an accepted label in DesignInputs.dlcs_to_run, but its own sea-state/
wind-range expansion is intentionally not defined yet -- see fls_spectral.py.
ULS/extreme DLCs (13/16/61) are out of scope entirely, not just deferred.
"""
import math
from dataclasses import dataclass

SITE_SEVERITY_PRESETS = {
    "Mild": (2.0, 8.0),
    "Medium": (4.0, 10.0),
    "Harsh": (6.0, 12.0),
    "Very harsh": (8.0, 14.0),
}

HS_OPERATIONAL_MAX_FACTOR = 1.5
TP_OPERATIONAL_MAX_FACTOR = 1.25
HS_MIN_M = 0.5
TP_MIN_S = 5.0


def site_severity_reference(site_severity: str, hs_ref_m: float | None, tp_ref_s: float | None) -> tuple[float, float]:
    """Returns (Hs_ref, Tp_ref) for a preset name, or the custom pair as given."""
    if site_severity in SITE_SEVERITY_PRESETS:
        return SITE_SEVERITY_PRESETS[site_severity]
    if hs_ref_m is None or tp_ref_s is None:
        raise ValueError(
            f"site_severity={site_severity!r} is not a preset "
            f"({list(SITE_SEVERITY_PRESETS)}) -- provide hs_ref_m and tp_ref_s explicitly."
        )
    return hs_ref_m, tp_ref_s


@dataclass
class SeaState:
    wind_speed_m_s: float
    hs_m: float
    tp_s: float


def dlc12_sea_state(wind_speed_m_s: float, hs_ref_m: float, tp_ref_s: float, u_ref_m_s: float) -> SeaState:
    """DLC12 (normal operation) sea state at one wind-speed bin centre.

    Base scaling Hs(U)=Hs_ref*(U/Uref)^2, Tp(U)=Tp_ref*(U/Uref)^0.5, clipped
    to an operational range. DLC12's own multiplier on the base scaling is
    1.0 (it *is* the base scaling) -- other DLCs would apply their own
    multiplier here, but none besides DLC12 are implemented.
    """
    hs_base_m = hs_ref_m * (wind_speed_m_s / u_ref_m_s) ** 2
    tp_base_s = tp_ref_s * (wind_speed_m_s / u_ref_m_s) ** 0.5
    hs_m = min(max(hs_base_m, HS_MIN_M), HS_OPERATIONAL_MAX_FACTOR * hs_ref_m)
    tp_s = min(max(tp_base_s, TP_MIN_S), TP_OPERATIONAL_MAX_FACTOR * tp_ref_s)
    return SeaState(wind_speed_m_s=wind_speed_m_s, hs_m=hs_m, tp_s=tp_s)


def weibull_cdf(u_m_s: float, k: float, a_m_s: float) -> float:
    if u_m_s <= 0.0:
        return 0.0
    return 1.0 - math.exp(-((u_m_s / a_m_s) ** k))


def dlc12_wind_bins(start_m_s: float, step_m_s: float, stop_m_s: float,
                     weibull_k: float, weibull_a_m_s: float) -> list[tuple[float, float]]:
    """Returns [(U_i, p_norm_i), ...]: DLC12 wind-speed bin centres and their
    Weibull occurrence probability, normalized to sum to 1 over the modeled
    bins (matches the source method -- bins outside [start,stop] carry no
    probability rather than the Weibull tail being silently lost).
    """
    centers = []
    u = start_m_s
    while u <= stop_m_s + 1e-9:
        centers.append(u)
        u += step_m_s
    raw = []
    for u_i in centers:
        u_lo = max(0.0, u_i - step_m_s / 2)
        u_hi = u_i + step_m_s / 2
        raw.append(weibull_cdf(u_hi, weibull_k, weibull_a_m_s) - weibull_cdf(u_lo, weibull_k, weibull_a_m_s))
    total = sum(raw)
    return [(u_i, p / total) for u_i, p in zip(centers, raw)]


def lifetime_hours(p_norm: float, dlc_probability: float, design_life_years: float) -> float:
    """H_life,i,DLC = p_norm,i,DLC * P(DLC) * Y*365.25*24."""
    return p_norm * dlc_probability * design_life_years * 365.25 * 24.0
