"""
Total system damping ratio by DLC -- three constants (structural, soil,
aerodynamic), never a function of wind speed. Aerodynamic damping is the
only component that changes with operating state, and even then it's a step
function (on for DLC12, off for DLC72), not a continuous curve -- so no
C_T(U) slope data is needed here (unlike the wind-loading spectrum itself,
see dynamics.thrust_slope_mn_per_m_s).

Defaults sourced from full-scale monopile OWT damping literature:
- structural (steel): ~0.5%, "usually <1%, 0.5% commonly applied" for a
  welded tubular tower/monopile.
- soil (foundation, hysteretic): full-scale-calibrated range ~0.15-1%
  (Carswell et al. 2015: 0.17-0.28%; Shirzadeh et al. 2013: 0.25%;
  rotor-stop-test based estimate: ~1%); radiation damping neglected (wind/
  wave excitation frequencies are well below 1 Hz).
- aerodynamic (DLC12 only): ~2-5% typical for fore-aft aerodynamic damping
  during power production; 0% for DLC72 (idling) -- matches full-scale
  parked-turbine measurements of ~1% *total* damping, consistent with
  structural+soil alone. This is the actual mechanism behind idling being a
  real fatigue driver for monopiles, not just bookkeeping.
"""
DAMPING_STRUCT_DEFAULT = 0.005
DAMPING_SOIL_DEFAULT = 0.005
DAMPING_AERO_DLC12_DEFAULT = 0.03


def total_damping_ratio(dlc: str, damping_struct: float = DAMPING_STRUCT_DEFAULT,
                         damping_soil: float = DAMPING_SOIL_DEFAULT,
                         damping_aero_dlc12: float = DAMPING_AERO_DLC12_DEFAULT) -> float:
    base = damping_struct + damping_soil
    if dlc == "DLC12":
        return base + damping_aero_dlc12
    if dlc == "DLC72":
        return base  # C_aero = 0 while idling -- see docs/method_update_log.md
    raise ValueError(f"Unknown DLC: {dlc!r}")
