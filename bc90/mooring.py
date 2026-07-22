"""
BC90 taut-mooring model.

Implements the single-line and 3-line group stiffness (docs/BC90_METHODOLOGY_REPORT.md
Sections 4a, 4b), the pile+mooring flexibility kernel and redundant-force solve
(Section 4c), and the corrected NFA flexibility term (Section 7) that replaces
the brief's sign-reversed 1-DOF equation.

Concept-stage, same rigor level as engine.py: linear-elastic, single scalar
K_ml per line, mooring line assumed always in tension. No slack/minimum
-tension check here -- see Section 9a of the methodology report; a caller
must verify T_min > 0 before trusting any result from this module, since the
whole isotropic-group-stiffness derivation stops applying the moment a line
goes slack.

engine.py / app.py are not modified by this module -- it is additive only,
per the BC90 brief's instruction to keep the original MP tool's code intact.
"""
import math
from dataclasses import dataclass

N_ML = 3  # fixed per BC90 scope (docs/BC90_METHODOLOGY_REPORT.md Section 1)


@dataclass
class MooringLayout:
    r_a_m: float          # mooring footprint radius: MP centerline to anchor, plan view
    d_sb_fl_m: float       # fairlead height above seabed/mudline
    k_ml_mn_per_m: float   # single-line axial stiffness, F = K_ml * d_ml
    t0_mn: float           # single-line pretension at the undisplaced (neutral) position
    mbl_mn: float | None = None  # line minimum breaking load, if a real line has been selected (Section 5)
    k_ml_dynamic_mn_per_m: float | None = None  # dynamic/storm axial stiffness, if it differs from
                                                 # k_ml_mn_per_m (quasi-static) -- Section 7. Falls
                                                 # back to k_ml_mn_per_m when not set (e.g. for chain/
                                                 # wire, where the two are close enough not to matter
                                                 # at concept stage; real synthetic rope typically has
                                                 # dynamic EA well above quasi-static EA).


def line_geometry(layout: MooringLayout) -> tuple[float, float]:
    """Returns (theta_rad, l_ml_m): line angle from horizontal and taut line
    length -- Section 4a."""
    theta_rad = math.atan2(layout.d_sb_fl_m, layout.r_a_m)
    l_ml_m = math.hypot(layout.r_a_m, layout.d_sb_fl_m)
    return theta_rad, l_ml_m


def single_line_horizontal_stiffness(layout: MooringLayout) -> float:
    """k_ml,x = K_ml * cos^2(theta) -- Section 4a. Not stated explicitly in
    the source PDF; follows from its F=K_ml*d_ml and Fx=F*cos(theta) plus the
    small-displacement projection d_ml = dx*cos(theta)."""
    theta_rad, _ = line_geometry(layout)
    return layout.k_ml_mn_per_m * math.cos(theta_rad) ** 2


def net_horizontal_stiffness(layout: MooringLayout, n_ml: int = N_ML) -> float:
    """Net horizontal stiffness of n_ml equally-spaced lines -- Section 4b.
    Isotropic (independent of load heading) and equal to (n_ml/2) times the
    single-line horizontal stiffness; exact for any n_ml >= 3 equally-spaced
    lines (cube-roots-of-unity identity), though the methodology report only
    independently checks n_ml == 3.
    """
    if n_ml < 3:
        raise ValueError("isotropy result requires n_ml >= 3 equally-spaced lines")
    return (n_ml / 2.0) * single_line_horizontal_stiffness(layout)


def net_horizontal_stiffness_dynamic(layout: MooringLayout, n_ml: int = N_ML) -> float:
    """Net horizontal stiffness using the DYNAMIC/storm line stiffness
    (falls back to the quasi-static k_ml_mn_per_m if k_ml_dynamic_mn_per_m
    isn't set) -- for NFA only (Section 7), which is inherently a dynamic
    /cyclic phenomenon. All other checks (Section 4c's static reaction,
    mooring-line ULS, the slack check) use the quasi-static
    net_horizontal_stiffness instead, per the methodology report's own
    flagged quasi-static-vs-dynamic distinction.
    """
    if n_ml < 3:
        raise ValueError("isotropy result requires n_ml >= 3 equally-spaced lines")
    theta_rad, _ = line_geometry(layout)
    k_dyn = layout.k_ml_dynamic_mn_per_m if layout.k_ml_dynamic_mn_per_m is not None else layout.k_ml_mn_per_m
    return (n_ml / 2.0) * k_dyn * math.cos(theta_rad) ** 2


def layout_from_line_data(r_a_m: float, d_sb_fl_m: float, mbl_mn: float,
                           ea_quasi_static_mn: float, ea_dynamic_mn: float | None = None,
                           pretension_fraction: float = 0.15) -> MooringLayout:
    """Build a MooringLayout from real mooring-line product data (MBL and
    axial rigidity EA) rather than guessing K_ml/T0 directly -- the approach
    Section 9a itself recommends (derive K_ml from EA/L_ml, not pick it
    freestanding). L_ml follows from the chosen (r_a_m, d_sb_fl_m) geometry.

    pretension_fraction defaults to 15% of MBL, within the commonly-cited
    15-20% MBL industry range for taut floating-wind mooring pretension --
    but note that convention comes from floating-vessel station-keeping
    design, not a fixed structure like BC90; the actual governing constraint
    for BC90 is the slack/ΔF_max criterion (Section 9a), so treat this as a
    starting point to be checked against evaluate_bc90's slack_utilization,
    not a substitute for it.
    """
    l_ml_m = math.hypot(r_a_m, d_sb_fl_m)
    k_ml_mn_per_m = ea_quasi_static_mn / l_ml_m
    k_ml_dynamic_mn_per_m = (ea_dynamic_mn / l_ml_m) if ea_dynamic_mn is not None else None
    t0_mn = pretension_fraction * mbl_mn
    return MooringLayout(
        r_a_m=r_a_m, d_sb_fl_m=d_sb_fl_m, k_ml_mn_per_m=k_ml_mn_per_m, t0_mn=t0_mn,
        mbl_mn=mbl_mn, k_ml_dynamic_mn_per_m=k_ml_dynamic_mn_per_m,
    )


def vertical_mooring_force(layout: MooringLayout, n_ml: int = N_ML) -> float:
    """Net downward force on the pile from n_ml lines' pretension, to first
    order in lateral displacement -- Section 5a. Missing from the source
    PDF's free-body diagram (which only labels Fx); this is what makes local
    shell buckling utilization rise, not fall, when mooring is added.
    """
    theta_rad, _ = line_geometry(layout)
    return n_ml * layout.t0_mn * math.sin(theta_rad)


def pile_flexibility(a_m: float, b_m: float, k_lateral_mn_per_m: float,
                      k_rocking_mnm_per_rad: float, ei_pile_mnm2: float) -> float:
    """f(a,b): lateral displacement at height a above mudline from a unit
    horizontal force at height b above mudline -- Section 4c. Cantilever
    fixed at mudline on the baseline's 2-spring (K_L, K_R) foundation,
    K_LM cross-coupling omitted exactly as in engine.py's own NFA treatment.
    Symmetric in a,b (Maxwell-Betti reciprocity); reduces exactly to
    engine.py's `cantilever_flexibility + 1/K_L + h^2/K_R` when a=b=h.

    Valid only when both a and b are within the pile's own EI (i.e. below
    the transition piece) -- the fairlead height is expected to satisfy this
    per Section 4c, but this function does not check it.
    """
    lo, hi = (a_m, b_m) if a_m <= b_m else (b_m, a_m)
    return (1.0 / k_lateral_mn_per_m
            + (a_m * b_m) / k_rocking_mnm_per_rad
            + (lo ** 2 * (3 * hi - lo)) / (6 * ei_pile_mnm2))


def solve_mooring_reaction(delta_fl0_m: float, f_aa_m_per_mn: float,
                            k_ml_net_mn_per_m: float) -> float:
    """F_ml: the redundant mooring reaction force -- Section 4c Step 2.
    delta_fl0_m is the fairlead displacement from environmental loads alone
    (mooring removed); f_aa_m_per_mn is pile_flexibility(d_sb_fl, d_sb_fl, ...).
    """
    return k_ml_net_mn_per_m * delta_fl0_m / (1.0 + k_ml_net_mn_per_m * f_aa_m_per_mn)


def net_mudline_loads(m_char_mnm: float, v_char_mn: float, f_ml_mn: float,
                       d_sb_fl_m: float) -> tuple[float, float, float]:
    """(M_char_net, V_char_net, M_fl) -- Section 4c Step 3. M_fl (the
    fairlead-section moment) is a new potential critical section the brief
    did not consider; caller must check max(|M_char_net|, |M_fl|), not
    M_char_net alone. M_fl uses the loads-above-fairlead approximation,
    valid when d_sb_fl <= z_wave_eq -- see the methodology report caveat.
    """
    m_char_net_mnm = m_char_mnm - f_ml_mn * d_sb_fl_m
    v_char_net_mn = v_char_mn - f_ml_mn
    m_fl_mnm = m_char_mnm - d_sb_fl_m * v_char_mn
    return m_char_net_mnm, v_char_net_mn, m_fl_mnm


def nfa_flexibility_correction(f_hh_m_per_mn: float, f_ha_m_per_mn: float,
                                f_aa_m_per_mn: float, k_ml_net_mn_per_m: float) -> float:
    """f_total: corrected hub-height flexibility including the taut
    mooring's stiffening contribution -- Section 7. Replaces the brief's
    sign-reversed M*x''+(k-k_ml)*x=0 equation (which implied mooring softens
    the system). f_total < f_hh always (mooring stiffens, raises f0).

    f_hh_m_per_mn: baseline's existing hub-height flexibility (unchanged).
    f_ha_m_per_mn: pile_flexibility(d_sb_fl, hub_height, ...) cross-term.
    f_aa_m_per_mn: pile_flexibility(d_sb_fl, d_sb_fl, ...).
    """
    return f_hh_m_per_mn - k_ml_net_mn_per_m * (f_ha_m_per_mn ** 2) / (1.0 + k_ml_net_mn_per_m * f_aa_m_per_mn)
