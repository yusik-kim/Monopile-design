import importlib

import pandas as pd
import streamlit as st

import engine as engine_module

# Streamlit Cloud can rerun app.py while retaining an older imported engine module.
engine_module = importlib.reload(engine_module)
TURBINE_LIBRARY = engine_module.TURBINE_LIBRARY
DesignInputs = engine_module.DesignInputs
SoilProfile = engine_module.SoilProfile
size_monopile = engine_module.size_monopile
turbine_from_capacity = engine_module.turbine_from_capacity
result_as_dict = engine_module.result_as_dict


st.set_page_config(page_title="Monopile Concept Design", layout="wide")

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; max-width: 1180px; }
      [data-testid="stMetric"] {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.75rem 0.85rem;
      }
      [data-testid="stMetric"] label,
      [data-testid="stMetric"] [data-testid="stMetricLabel"],
      [data-testid="stMetric"] [data-testid="stMetricValue"],
      [data-testid="stMetric"] [data-testid="stMetricDelta"] {
        color: #0f172a !important;
      }
      [data-testid="stMetric"] [data-testid="stMetricLabel"] p,
      [data-testid="stMetric"] [data-testid="stMetricValue"] div,
      [data-testid="stMetric"] [data-testid="stMetricDelta"] div {
        color: #0f172a !important;
      }
      div[data-testid="stVerticalBlock"] > div:has(svg) {
        overflow-x: auto;
      }
      @media (max-width: 760px) {
        .block-container { padding-left: 0.8rem; padding-right: 0.8rem; }
        [data-testid="stMetric"] { padding: 0.6rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def monopile_schematic_svg(geometry, water_depth_m: float, d_over_t: float) -> str:
    width, height = 420, 420
    cx = width / 2
    scale = min(4.0, 300.0 / max(water_depth_m + geometry.embedded_length_m, 1.0))

    stub_above_msl_m = 8.0
    msl_y = 60 + stub_above_msl_m * scale
    mudline_y = msl_y + water_depth_m * scale
    tip_y = mudline_y + geometry.embedded_length_m * scale
    top_y = msl_y - stub_above_msl_m * scale

    pile_w = max(18.0, geometry.diameter_m * scale)

    return f"""
    <svg viewBox="0 0 {width} {height}" role="img" aria-label="Monopile schematic">
      <style>
        .bg {{ fill:#ffffff; }}
        .water {{ fill:#e0f2fe; }}
        .soil {{ fill:#f3e8d8; }}
        .pile-wet {{ fill:#94a3b8; stroke:#334155; stroke-width:2; }}
        .pile-dry {{ fill:#cbd5e1; stroke:#334155; stroke-width:2; }}
        .pile-embedded {{ fill:#64748b; stroke:#334155; stroke-width:2; }}
        .waterline {{ stroke:#0284c7; stroke-width:1.5; stroke-dasharray:5 3; }}
        .mudline {{ stroke:#92400e; stroke-width:1.5; stroke-dasharray:5 3; }}
        .dim {{ stroke:#111827; stroke-width:1; marker-start:url(#arrow); marker-end:url(#arrow); }}
        .label {{ font: 13px system-ui, sans-serif; fill:#111827; }}
        .small {{ font: 12px system-ui, sans-serif; fill:#334155; }}
      </style>
      <defs>
        <marker id="arrow" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 z" fill="#111827" />
        </marker>
      </defs>
      <rect class="bg" x="0" y="0" width="{width}" height="{height}" />
      <rect class="water" x="40" y="{msl_y:.1f}" width="{width - 80}" height="{mudline_y - msl_y:.1f}" />
      <rect class="soil" x="40" y="{mudline_y:.1f}" width="{width - 80}" height="{max(0.0, height - 30 - mudline_y):.1f}" />

      <rect class="pile-dry" x="{cx - pile_w / 2:.1f}" y="{top_y:.1f}" width="{pile_w:.1f}" height="{msl_y - top_y:.1f}" />
      <rect class="pile-wet" x="{cx - pile_w / 2:.1f}" y="{msl_y:.1f}" width="{pile_w:.1f}" height="{mudline_y - msl_y:.1f}" />
      <rect class="pile-embedded" x="{cx - pile_w / 2:.1f}" y="{mudline_y:.1f}" width="{pile_w:.1f}" height="{tip_y - mudline_y:.1f}" />

      <line class="waterline" x1="40" y1="{msl_y:.1f}" x2="{width - 40}" y2="{msl_y:.1f}" />
      <text class="small" x="44" y="{msl_y - 6:.1f}">Mean sea level</text>
      <line class="mudline" x1="40" y1="{mudline_y:.1f}" x2="{width - 40}" y2="{mudline_y:.1f}" />
      <text class="small" x="44" y="{mudline_y - 6:.1f}">Mudline</text>

      <line class="dim" x1="20" y1="{msl_y:.1f}" x2="20" y2="{mudline_y:.1f}" />
      <text class="label" x="4" y="{(msl_y + mudline_y) / 2:.1f}" transform="rotate(-90 12 {(msl_y + mudline_y) / 2:.1f})" text-anchor="middle">{water_depth_m:.0f} m depth</text>

      <line class="dim" x1="{width - 20:.1f}" y1="{mudline_y:.1f}" x2="{width - 20:.1f}" y2="{tip_y:.1f}" />
      <text class="label" x="{width - 4:.1f}" y="{(mudline_y + tip_y) / 2:.1f}" transform="rotate(-90 {width - 12:.1f} {(mudline_y + tip_y) / 2:.1f})" text-anchor="middle">{geometry.embedded_length_m:.1f} m embedded</text>

      <line class="dim" x1="{cx - pile_w / 2:.1f}" y1="{top_y - 14:.1f}" x2="{cx + pile_w / 2:.1f}" y2="{top_y - 14:.1f}" />
      <text class="label" x="{cx:.1f}" y="{top_y - 20:.1f}" text-anchor="middle">D = {geometry.diameter_m:.2f} m</text>

      <text class="small" x="{cx:.1f}" y="{height - 12:.1f}" text-anchor="middle">
        t = {geometry.wall_thickness_m * 1000:.1f} mm (D/t = {d_over_t:.0f})
      </text>
    </svg>
    """


st.title("Monopile Concept Design")
st.caption(
    "Arany-et-al.-style concept-stage sizing (ULS/SLS/NFA/FLS/local buckling "
    "iteration). Concept-level screening only -- not certification or FEED design."
)

with st.sidebar:
    st.header("Turbine")
    turbine_mw = st.slider("Turbine capacity [MW]", 5.0, 25.0, 15.0, 1.0)
    turbine_props = turbine_from_capacity(turbine_mw)
    st.caption(
        f"Rotor {turbine_props['rotor_diameter_m']:.0f} m, "
        f"hub height {turbine_props['hub_height_m']:.0f} m, "
        f"thrust {turbine_props['thrust_mn']:.2f} MN."
    )

    st.header("Site")
    water_depth_m = st.number_input("Water depth [m]", min_value=5.0, max_value=80.0, value=35.0, step=1.0)
    hs_m = st.number_input("Significant wave height Hs [m]", min_value=0.5, max_value=20.0, value=5.0, step=0.5)
    tp_s = st.number_input("Peak wave period Tp [s]", min_value=3.0, max_value=25.0, value=10.0, step=0.5)
    st.caption("Hs/Tp should be the extreme (e.g. 50-year return period) design sea state, not operational/typical conditions.")
    current_m_s = st.number_input("Current [m/s]", min_value=0.0, max_value=3.0, value=0.5, step=0.1)

    st.header("Soil")
    soil_type = st.radio("Soil type", ["sand", "clay"], horizontal=True)
    submerged_unit_weight_kn_m3 = st.number_input("Submerged unit weight [kN/m3]", min_value=4.0, max_value=15.0, value=9.5, step=0.5)
    if soil_type == "sand":
        friction_angle_deg = st.number_input("Friction angle [deg]", min_value=25.0, max_value=42.0, value=35.0, step=0.5)
        undrained_shear_strength_kpa = 75.0
    else:
        undrained_shear_strength_kpa = st.number_input("Undrained shear strength [kPa]", min_value=10.0, max_value=300.0, value=75.0, step=5.0)
        friction_angle_deg = 34.0

    with st.expander("Advanced settings"):
        design_life_years = st.number_input("Design life [years]", min_value=5.0, max_value=50.0, value=27.0, step=1.0)
        duty_factor = st.number_input("Duty factor", min_value=0.1, max_value=1.0, value=0.9, step=0.05)
        allowable_sls_rotation_deg = st.number_input("Allowable SLS rotation [deg]", min_value=0.1, max_value=2.0, value=0.50, step=0.05)
        dt_ratio_min = st.number_input("Min D/t", min_value=40.0, max_value=150.0, value=80.0, step=5.0)
        dt_ratio_max = st.number_input("Max D/t", min_value=dt_ratio_min, max_value=300.0, value=160.0, step=5.0)
        st.caption("D/t bounds are advisory, not a hard limit: the converged geometry may fall outside them, flagged with a manufacturability warning below rather than being blocked from getting there.")
        l_over_d_min = st.number_input("Min L/D", min_value=1.0, max_value=6.0, value=3.0, step=0.5)
        l_over_d_max = st.number_input("Max L/D", min_value=l_over_d_min, max_value=12.0, value=8.0, step=0.5)

        override_tower = st.checkbox("Override tower geometry", value=False)
        avg_tower_diameter_m = None
        avg_tower_wall_thickness_m = None
        if override_tower:
            avg_tower_diameter_m = st.number_input("Average tower diameter [m]", min_value=2.0, max_value=15.0, value=8.25, step=0.05)
            avg_tower_wall_thickness_m = st.number_input("Average tower wall thickness [m]", min_value=0.01, max_value=0.20, value=0.05, step=0.005)

soil = SoilProfile(
    soil_type=soil_type,
    submerged_unit_weight_kn_m3=submerged_unit_weight_kn_m3,
    friction_angle_deg=friction_angle_deg,
    undrained_shear_strength_kpa=undrained_shear_strength_kpa,
)

inputs = DesignInputs(
    turbine_mw=turbine_mw,
    water_depth_m=water_depth_m,
    soil=soil,
    hs_m=hs_m,
    tp_s=tp_s,
    current_m_s=current_m_s,
    design_life_years=design_life_years,
    duty_factor=duty_factor,
    allowable_sls_rotation_deg=allowable_sls_rotation_deg,
    dt_ratio_min=dt_ratio_min,
    dt_ratio_max=dt_ratio_max,
    l_over_d_min=l_over_d_min,
    l_over_d_max=l_over_d_max,
    avg_tower_diameter_m=avg_tower_diameter_m,
    avg_tower_wall_thickness_m=avg_tower_wall_thickness_m,
)

result = size_monopile(inputs)
geometry = result.geometry
converged = not any("did not converge" in n for n in result.notes)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Diameter", f"{geometry.diameter_m:.2f} m")
c2.metric("Wall thickness", f"{geometry.wall_thickness_m * 1000:.1f} mm")
c3.metric("Embedded length", f"{geometry.embedded_length_m:.1f} m")
c4.metric("Steel mass", f"{result.steel_mass_t:,.0f} t", f"${result.steel_cost_usd / 1e6:,.1f}M")

if converged:
    st.success(f"Converged. Governing constraint: **{result.governing_constraint}**.")
else:
    st.warning(
        f"Did not converge within the configured D/t and L/D bounds. "
        f"Governing constraint: **{result.governing_constraint}**. See notes below."
    )

st.subheader("Utilization (pass if <= 1.0)")
u1, u2, u3, u4, u5 = st.columns(5)
for col, label, value in [
    (u1, "ULS", result.uls_utilization),
    (u2, "SLS", result.sls_utilization),
    (u3, "NFA", result.nfa_utilization),
    (u4, "FLS", result.fls_utilization),
    (u5, "Local Buckling", result.buckling_utilization),
]:
    with col:
        st.progress(min(1.0, value), text=f"{label}: {value:.2f}")

st.subheader("Schematic")
st.markdown(
    monopile_schematic_svg(geometry, water_depth_m, geometry.diameter_m / geometry.wall_thickness_m),
    unsafe_allow_html=True,
)

st.subheader("Geometry & Loads")
geometry_table = pd.DataFrame(
    [
        ["Diameter", geometry.diameter_m, "m"],
        ["Wall thickness", geometry.wall_thickness_m * 1000, "mm"],
        ["Embedded length", geometry.embedded_length_m, "m"],
        ["L/D", geometry.embedded_length_m / geometry.diameter_m, "-"],
        ["D/t", geometry.diameter_m / geometry.wall_thickness_m, "-"],
        ["Mudline moment (characteristic)", result.mudline_moment_mnm, "MN*m"],
        ["Mudline shear (characteristic)", result.mudline_shear_mn, "MN"],
        ["Steel mass", result.steel_mass_t, "t"],
        ["Steel cost", result.steel_cost_usd / 1e6, "USD million"],
    ],
    columns=["Quantity", "Value", "Unit"],
)
st.dataframe(geometry_table, hide_index=True, width="stretch")

st.subheader("Detailed Engineering Values")
band_low, band_high = result.soft_stiff_band_hz
details_table = pd.DataFrame(
    [
        ["Lateral stiffness K_L", result.k_lateral_mn_per_m, "MN/m"],
        ["Rocking stiffness K_R", result.k_rocking_mnm_per_rad, "MN*m/rad"],
        ["Pile stiffness parameter beta", result.beta_per_m, "1/m"],
        ["SLS mudline rotation", result.sls_rotation_deg, "deg"],
        ["Natural frequency f0", result.natural_frequency_hz, "Hz"],
        ["Soft-stiff band low", band_low, "Hz"],
        ["Soft-stiff band high", band_high, "Hz"],
        ["FLS damage (Palmgren-Miner)", result.fls_damage, "-"],
    ],
    columns=["Quantity", "Value", "Unit"],
)
st.dataframe(details_table, hide_index=True, width="stretch")

if result.notes:
    st.subheader("Notes & Caveats")
    for note in result.notes:
        st.warning(note)

with st.expander("Turbine library (reference)"):
    turbine_table = pd.DataFrame(TURBINE_LIBRARY).rename(
        columns={
            "mw": "MW",
            "rotor_diameter_m": "Rotor diameter [m]",
            "hub_height_m": "Hub height [m]",
            "mass_t": "Total mass [t]",
            "thrust_mn": "Thrust [MN]",
            "rpm_min": "Min rpm",
            "rpm_max": "Max rpm",
            "transition_piece_height_m": "Transition piece height [m]",
        }
    )
    st.dataframe(turbine_table, hide_index=True, width="stretch")
    st.caption(
        "5/15/22 MW sourced from published reference-turbine reports (OC3/NREL, IEA); "
        "10 MW from the DTU 10MW report; 25 MW is an extrapolation, not a verified turbine."
    )

csv = pd.DataFrame([result_as_dict(result)]).to_csv(index=False).encode("utf-8")
st.download_button("Download result CSV", data=csv, file_name="monopile_result.csv", mime="text/csv")
