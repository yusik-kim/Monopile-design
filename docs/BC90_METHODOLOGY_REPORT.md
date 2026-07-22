# BC90 Concept Design Methodology — Taut-Mooring-Supported Monopile (60–90 m)

**Status: methodology only. `engine.py` / `app.py` are unchanged and this document
does not describe committed code.** BC90 is a proposed extension of the MP tool
(`docs/METHODOLOGY_REPORT.md`, "baseline" below) that adds a taut-mooring
option to a bottom-founded monopile for 60–90 m water depth. Section numbers
below follow `Extend_MP_BC90.md`'s own numbering (0, 1, 2, 3, 4, 5, 5a, 6, 7,
8, 9, 9a) so the two documents can be read side by side. Where a section is
unchanged from the baseline, this says so explicitly and cites the baseline
section instead of restating it.

This report was written under an explicit brief to **critically review**, not
rubber-stamp, `Extend_MP_BC90.md`'s draft reasoning. Several of that
document's hypotheses do not survive the check — most importantly the §7
1-DOF stiffness equation (sign error: it makes mooring *soften* the system,
which is backwards) and the §5a "buckling probably doesn't change" claim
(wrong: mooring adds a previously-unmodeled vertical/axial load). These are
flagged inline, not silently corrected.

**Source of truth used, per instructions:** `Extend_MP_BC90.md` (scope/brief),
`docs/METHODOLOGY_REPORT.md` (baseline equations, symbols, structure),
`engine.py` (actual current behavior — trusted over both documents where they
disagree), `docs/method_update_log.md` (precedent/history), and
`taut moorling line model.pdf` (single-line 2D free-body diagram — the only
mooring-model source provided; reproduced and extended below to 3 lines).

---

## New symbol glossary (BC90 additions)

These add to, and do not replace, the baseline glossary in
`docs/METHODOLOGY_REPORT.md`. Units follow the same MN-based convention (§0
of the baseline).

**Mooring geometry & line properties**
| Symbol | Meaning | Units |
|---|---|---|
| `N_ml` | number of mooring lines — **fixed at 3** per the brief's scope | – |
| `d_sb_fl` | fairlead height above seabed/mudline (new design variable) | m |
| `R_a` | mooring footprint radius: horizontal distance from MP centerline to each anchor, plan view (new design variable) | m |
| `phi_i` | azimuth of line `i` in plan (`i=1..3`), assumed equally spaced 120° apart (layout assumption, see §4b) | deg |
| `theta` | mooring line angle from horizontal, `atan(d_sb_fl / R_a)` — identical for all 3 lines under the symmetric-layout assumption | deg (rad in equations) |
| `L_ml` | straight-line (taut) mooring line length, `sqrt(R_a^2 + d_sb_fl^2)` | m |
| `EA_ml` | line axial rigidity (optional underlying parameter if `K_ml` is derived rather than given directly) | MN |
| `K_ml` | single-line axial stiffness, `F = K_ml * d_ml` (new design variable, per the PDF's own notation) | MN/m |
| `d_ml` | line elongation from the pretensioned length | m |
| `F`, `Fx`, `Fz` | line tension, its horizontal component (`F cos theta`), and its **vertical component** (`F sin theta`) — `Fz` is **not** in the source PDF's FBD; see §5a for why it matters | MN |
| `T0` | single-line pretension at the undisplaced (neutral) position (new design variable) | MN |
| `Delta F_i` | incremental tension in line `i` due to fairlead displacement | MN |
| `T_i = T0 + Delta F_i` | total tension in line `i` | MN |
| `T_max` | maximum single-line tension over the design load case and heading range | MN |
| `MBL` | mooring line minimum breaking load (material/construction property — new input) | MN |
| `gamma_ml` | partial safety factor applied to line tension for the mooring ULS check (DNV-OS-E301-style; **not independently verified in this session** — see §5) | – |

**Group (net) mooring stiffness / force**
| Symbol | Meaning | Units |
|---|---|---|
| `k_ml,x` | single-line horizontal (projected) stiffness, `K_ml * cos^2(theta)` | MN/m |
| `K_ml,net` | net **isotropic** horizontal stiffness of the 3-line group at the fairlead, `1.5 * K_ml * cos^2(theta)` — derived in §4b, not assumed | MN/m |
| `F_ml` | net horizontal reaction force from the full 3-line group, acting at the fairlead, opposing the environmental load (the "redundant force" of §4c) | MN |
| `f_aa` | self-flexibility of the pile+soil system at fairlead height `a = d_sb_fl`, under a unit force applied there | m/MN |
| `f_ab` | cross-flexibility between fairlead height `a` and an applied-load height `b` | m/MN |
| `delta_fl,0` | fairlead lateral displacement from the environmental loads alone (mooring removed) | m |
| `z_wave_eq` | equivalent height of the resultant wave+current load above mudline, `M_wave / F_wave` (backed out of the *existing* §3 outputs, no new integration) | m |
| `M_char_net`, `V_char_net` | mudline design moment/shear **after** the mooring reaction is netted out — replaces `M_char`/`V_char` as the ULS/SLS/FLS input | MN·m, MN |
| `M_fl` | bending moment at the **fairlead cross-section** — a new potential critical section, see §5 | MN·m |

---

## 0. Process overview

Baseline flow (`docs/METHODOLOGY_REPORT.md` §0) is unchanged in its outer
shape (turbine lookup → initial geometry guess → evaluate → iterate). BC90
inserts new steps **between** the baseline's soil-stiffness step and its
ULS/SLS/NFA/FLS/buckling step, and adds a **new mooring-only check**:

1. Turbine lookup (§2, unchanged).
2. Initial geometry guess (§9, unchanged formulas) **and** initial mooring
   layout guess (**new §9a**: `d_sb_fl`, `R_a`, `theta`, `K_ml`, `T0`).
3. Mudline extreme loads `M_char`, `V_char` from wind+wave/current (§3,
   **unchanged equations**, just evaluated at greater water depth).
4. Soil stiffness `K_L`, `K_R` (§4, **unchanged equations**).
5. **New**: single-line and 3-line group mooring stiffness (§4a, §4b).
6. **New**: solve the redundant-force problem for the net mooring reaction
   `F_ml`, and derive `M_char_net`, `V_char_net`, and the fairlead-section
   moment `M_fl` (§4c).
7. ULS (§5, using `M_char_net`/`V_char_net`, checked at **both** mudline and
   fairlead), local shell buckling (§5a, with an added axial term), SLS (§6),
   NFA (§7, corrected stiffness-modification formula), FLS (§8) — five checks
   as before, **plus a sixth: mooring-line ULS** (line tension vs. `MBL`, §5)
   and a **slack/minimum-tension check** (§9a).
8. If any of the six utilizations fail, adjust pile geometry (§9, mostly
   unchanged priority rules) or mooring parameters (§9a) and repeat.
9. Report: diameter, thickness, embedded length, mooring line layout/specs
   (`N_ml=3`, `R_a`, `d_sb_fl`, `theta`, `L_ml`, `K_ml`, `T0`, required `MBL`),
   monopile steel mass/cost, mooring system mass/cost (**new cost items**,
   see the Note section), total CAPEX.

**Critical-review flag on process order:** steps 5–6 above make the pile
sizing loop and the mooring sizing loop coupled (mooring stiffness changes
`M_char_net`/`V_char_net`/axial load, which changes converged `D`/`t`, which
changes `K_L`/`K_R`, `EI`, and hence the flexibility terms the mooring
reaction itself depends on). This document proposes solving them as
**two nested loops** (outer: pile geometry per baseline's step-wise rule;
inner: mooring reaction/utilization for the current pile geometry) rather
than a single joint optimization — a genuine simplification, not a neutral
one, since it means the mooring layout parameters (`d_sb_fl`, `R_a`, `K_ml`,
`T0`) are **not** co-optimized with pile geometry in this phase; see §9a.

---

## 1. Constants

New constants needed, alongside the unchanged baseline constants (§1 of the
baseline):

| Constant | Proposed value | Status |
|---|---|---|
| `N_ML` | 3 | Fixed by brief's scope, not a free variable |
| `GAMMA_ML_ULS` | DNV-OS-E301-style partial factor on line tension, consequence-class dependent (roughly 1.5–2.0 for intact-line ULS, per general knowledge of the standard) | **Not independently verified this session** — a WebFetch of the source factor table returned HTTP 403; treat as an unsourced placeholder exactly like `GAMMA_F_ULS`'s documented provenance caveat in the baseline (§1), and source the real DNV-OS-E301 table before using beyond concept screening |
| `T_MIN_FRACTION` | minimum allowable line tension as a fraction of `T0` or `MBL`, to avoid slack/snap-load and (for synthetic rope) compression-fatigue damage | **Not sourced** — flagged, not invented; see §9a |
| `USD_PER_M_MOORING_LINE` | mooring line unit cost | New CAPEX placeholder, unsourced |
| `USD_PER_ANCHOR` | anchor unit cost (function of required holding capacity, not modeled) | New CAPEX placeholder, unsourced |

**Critical-review note:** the brief's "update accordingly" for §1 is correct
in spirit, but every new constant proposed above is either an unverified
external-standard value or an outright placeholder — this is consistent with,
not worse than, several baseline constants (`FATIGUE_LOAD_FACTOR`,
`USD_PER_T_STEEL`), but there is currently **zero** BC90-specific calibration
data (no sourced reference design exists, unlike the baseline's OC3/DTU/IEA
anchors — see §10).

---

## 2. Turbine library

**No change to `TURBINE_LIBRARY` itself.** The brief's "update accordingly"
is better read as a *usage* note than a *data* note: 60–90 m water depth is
outside the depth range of every sourced reference design in the baseline
library (OC3 5MW @ 20m, IEA 15MW/22MW @ 34–35m), and deep-water sites are
realistically paired with larger turbines (15–25 MW class). This means:

- The turbine **entries** (mass, thrust, rpm, hub height) need no BC90-specific
  fields.
- But the baseline's own honesty about the 25 MW row being an unverified
  extrapolation (baseline §2) becomes **more** consequential here, since BC90's
  target depth range makes the 22/25 MW entries the most likely to be
  exercised, not the least.
- `transition_piece_height_m` (already in the library) is reused unchanged as
  the height of the pile-above-mudline/tower-above-mudline split (§7).

No new turbine-library fields are needed for the mooring model itself —
`d_sb_fl`, `R_a`, `K_ml`, `T0` are **site/mooring-design inputs**, analogous to
`SoilProfile`, not turbine properties.

---

## 3. Extreme mudline loads

**Agree with the brief: no change to the governing equations.** `M_char` and
`V_char` are computed exactly as in the baseline (§3) — Morison drag-only wave
load plus point wind thrust, evaluated at the (now larger) `water_depth_m`.
`M_char`/`V_char` remain the *pre-mooring* characteristic loads; the mooring
reaction is netted out of them separately in §4c, not folded into §3 itself.

**What does change, though not the equations:** at 60–90 m depth, several of
the baseline's *already-flagged* approximations become more load-bearing than
before, simply because the water column being integrated is larger:
- `H_max = 1.9 × Hs` (unverified rule of thumb, baseline §3) now scales a
  larger `F_wave`/`M_wave`.
- Drag-only Morison (no inertia term) is a bigger source of potential
  non-conservatism the deeper/larger the structure gets, since inertia loads
  scale with pile cross-section (`~D²`) while drag scales with frontal area
  (`~D`) — a large-diameter pile in deep water is exactly the regime where
  omitting inertia is least defensible. This was already a caveat in the
  baseline; BC90 does not fix it, but should not silently inherit it either —
  flagged again here explicitly since 60–90 m is closer to the regime where it
  matters.
- Marine growth (adds effective diameter and surface roughness, hence `Cd`)
  over a taller submerged shaft is not modeled in either tool; more relevant
  at BC90 depths than at the baseline's shallower verification cases.

None of the above is a **methodology change** — they are pre-existing baseline
simplifications whose consequences simply grow with depth. No new equation is
proposed for §3.

---

## 4. Soil stiffness

**Agree with the brief's headline claim: no change to the Hetenyi
closed-form `K_L`/`K_R` equations** (baseline §4). Soil behavior is a function
of `D`, `L`, `EI`, and soil profile only — mooring lines do not touch the soil
or change the governing ODE.

**But flag an indirect coupling the brief doesn't mention:** if mooring
enables a smaller converged diameter/embedment (the whole point of adding it,
per the brief's own framing), the resulting `D`, `L` feed back into `K_L`/`K_R`
through the *same unchanged formula* — this isn't a new equation, but it does
mean the baseline's own already-documented validity caveats become live
concerns in a new way:
- The `beta × L < 2.5` validity flag (baseline §4) exists to catch piles that
  are short/stiff relative to the soil. A mooring-enabled smaller-diameter,
  shorter-embedment pile is *more* likely to trip this flag than the
  baseline's own converged designs, not less — worth actively checking, not
  assuming away.
- The baseline's own "D > 7.5 m or L/D < 4" PISA/Hetenyi-applicability warning
  (`engine.py`, `evaluate_monopile`) could plausibly stop being triggered
  (smaller D is exactly what mooring is meant to enable), which superficially
  looks like an improvement, but only means the *stiffness formula's own
  documented blind spot* (embedded length has no capacity-driven growth
  mechanism — baseline §9/§11 item 21) becomes **more** consequential, since a
  smaller-diameter, mooring-assisted pile leans even more heavily on a
  potentially under-embedded pile passing only because the model's stiffness
  checks are insensitive to `L` (verbatim baseline finding, not new to BC90,
  but sharper here).

No new equation proposed for §4; two new *notes* are.

---

## 4a. Single mooring line model (from the PDF)

Reproducing the source `taut moorling line model.pdf` (single line, 2D
vertical-plane free-body diagram) exactly:

```
F      = K_ml * d_ml              (line tension, linear stiffness)
Fx     = F * cos(theta)           (horizontal component of tension)
dx_ml  = d_ml * cos(theta)        (horizontal component of line elongation)
theta  = mooring line angle from horizontal (seabed)
d_sb_fl = fairlead height above seabed
```

**Linearization needed to close the loop (not in the PDF, added here):** for
a small horizontal fairlead displacement `dx`, the line elongation is the
projection of that displacement onto the line's own axis:
```
d_ml = dx * cos(theta)
```
Combining with the PDF's own `F = K_ml * d_ml` and `Fx = F*cos(theta)` gives
the single-line **horizontal projected stiffness**:
```
k_ml,x = Fx / dx = K_ml * cos^2(theta)
```
This is the standard taut-mooring/TLP-tendon horizontal restoring-stiffness
form (`(EA/L)·cos²θ` in the tendon-stiffness literature — see References);
it is not stated explicitly in the source PDF but follows directly from its
two given relations plus the small-displacement projection above.

**Missing from the PDF's FBD — the vertical component.** Every taut line at
angle `theta` from horizontal also has a vertical tension component:
```
Fz = F * sin(theta)
```
This is **entirely absent** from the source diagram (which only labels `Fx`)
and from the brief's discussion of ULS/SLS effects (§5, §6). It is not a
minor omission: `Fz` pulls the fairlead **down** toward the seabed anchor,
adding axial compression to the pile shell above mudline — this is exactly
the missing-physics item that answers the brief's own §5a question ("how does
mooring affect buckling?"). See §5a.

---

## 4b. Three-line group stiffness — combining N=3 lines

**Explicit layout assumption (the brief specifies neither plan-view layout
nor pretension distribution — this is a modeling choice made here, not
derived):** the 3 lines are equally spaced at 120° in plan (`phi_i = phi_0,
phi_0+120°, phi_0+240°`), each with identical `K_ml`, `theta` (hence identical
`R_a`, `d_sb_fl`), and identical pretension `T0`. This is the natural choice
for a monopile that must resist environmental loads from an arbitrary
heading (unlike a permanently-oriented vessel), and is what makes the
following isotropy result hold.

**Derivation — does the 3-line arrangement cancel net stiffness, as the task
brief warned against assuming either way?** For a fairlead lateral
displacement `u` at azimuth `phi_load`, line `i`'s elongation (projecting `u`
onto that line's 3D unit vector, horizontal part only, matching the PDF's
horizontal-plane treatment) is:
```
d_ml,i = |u| * cos(theta) * cos(phi_i - phi_load)
```
giving incremental line tension `Delta F_i = K_ml * d_ml,i`, and a horizontal
restoring-force **matrix** contribution per line of `K_ml·cos²θ · (e_i ⊗ e_i)`
where `e_i = (cos φ_i, sin φ_i)`. Summing over the 3 equally-spaced lines:
```
sum_i cos^2(phi_i - phi_load) = 3/2   (exact for N=3 equally spaced, any phi_load)
sum_i cos(phi_i-phi_load)*sin(phi_i-phi_load) = 0   (exact, same conditions)
```
(Proof: `cos²(ψ)=0.5+0.5cos(2ψ)`; summing `cos(2ψ_i)` over 3 angles spaced
120° apart is summing the real parts of the three cube roots of unity, which
is exactly zero — an exact trigonometric identity, not an approximation, and
it holds for **any** `N ≥ 3` equally-spaced lines, not just `N=3`.)

**Result: the net 3-line horizontal stiffness is isotropic** (same magnitude
in every plan-view direction) and equal to:
```
K_ml,net = 1.5 * K_ml * cos^2(theta)   =   1.5 * k_ml,x
```
**This directly answers the brief's implicit worry** ("don't assume symmetric
arrangement cancels out net horizontal restoring stiffness in an unintended
way"): it does not cancel — it is isotropic at exactly 1.5× (not 3×, and not
0×) the single-line horizontal stiffness, for any load heading, as an exact
consequence of the 120°-spacing assumption. This isotropy is a genuinely
useful simplification: it means the **group-level** stiffness used in §4c/§7
can be treated as a single scalar spring regardless of wind/wave direction,
consistent with the baseline's own single-vertical-plane (2D) treatment of
loads.

**What is NOT isotropic — flagged for §5/§9a:** isotropy applies to the
*group stiffness*, not to *individual line tension*. For a given load
heading, tension redistributes unevenly among the 3 lines (windward line(s)
gain tension, leeward line(s) lose it), and the single most-loaded line's
tension factor ranges from `K_ml·cosθ·dx` (heading aligned with a line) down
to `0.5·K_ml·cosθ·dx` (heading bisecting two lines), depending on load heading
relative to the fixed line azimuths. This matters for the new mooring-line
ULS/slack checks (§5, §9a), which are heading-dependent even though the pile
-level stiffness is not.

---

## 4c. Net mooring reaction and its effect on mudline design loads

**This is the section that actually tests the brief's §5 hypothesis** ("M_char
reduced by Fx·d_sb_fl, V_char reduced by point force Fx"). The brief asserts
the *form* of the result without deriving `F_ml` (called `Fx` in the brief) —
treating it as if it can simply be assumed or looked up. It cannot: the
monopile-with-mooring is a **statically indeterminate** system (pile+soil
spring at the base, plus a second elastic support — the mooring group — at an
intermediate height `d_sb_fl`), and `F_ml` must be *solved for*, not assumed.

**Force/flexibility (redundant-force) method**, reusing exactly the
baseline's own toolkit (Hetenyi `K_L`/`K_R` from §4, and the virtual-work
cantilever flexibility already used for NFA in baseline §7 — no new physics
principle, only a new application of it):

Define the flexibility kernel `f(a,b)` = lateral displacement at height `a`
above mudline due to a unit horizontal force at height `b` above mudline, for
a cantilever fixed at mudline with base springs `K_L`, `K_R` (baseline's
2-spring simplification, `K_LM` omitted exactly as in baseline §7):
```
f(a,b) = 1/K_L + (a*b)/K_R + integral_0^min(a,b) (a-z)(b-z)/EI(z) dz
```
This is symmetric in `a,b` (Maxwell–Betti reciprocity) and reduces exactly to
the baseline's existing `cantilever_flexibility + 1/K_L + h²/K_R` formula
when `a=b=h` (hub height) — i.e. it is a strict generalization, not a
different model. If `d_sb_fl` is below the transition piece (expected, since
the fairlead sits on the submerged monopile shaft, and `pile_above_mudline =
water_depth_m + transition_piece_height_m` is typically 70–105 m at 60–90 m
depth — almost certainly above any sensible fairlead height), the integral
uses `EI_pile` only and has closed form:
```
f(a,b) = 1/K_L + a*b/K_R + a^2*(3b-a)/(6*EI_pile)      for a <= b
f_aa := f(a,a) = 1/K_L + a^2/K_R + a^3/(3*EI_pile)
```

**Step 1 — displacement at fairlead from the environmental loads alone**
(mooring removed), using the same two-point-load decomposition the baseline
already implicitly makes (`F_thrust` at `b1 = hub_height_m+water_depth_m`,
`F_wave` at `b2 = z_wave_eq = M_wave/F_wave`, both already computed by the
unchanged §3):
```
delta_fl,0 = F_thrust * f(d_sb_fl, b1)  +  F_wave * f(d_sb_fl, b2)
```

**Step 2 — solve for the redundant mooring reaction** `F_ml` (a linear-spring
compatibility problem: the mooring group, stiffness `K_ml,net`, both causes
and resists the fairlead displacement):
```
F_ml = K_ml,net * delta_fl,0 / (1 + K_ml,net * f_aa)
```
(Derivation: `disp_fl = delta_fl,0 - f_aa*F_ml` and `F_ml = K_ml,net*disp_fl`;
solving the 2-equation system gives the above. This is the standard
force-method treatment of "a beam with an added elastic support.")

**Step 3 — net mudline design loads** (this is where the brief's hypothesis
is checked):
```
M_char_net = M_char - F_ml * d_sb_fl
V_char_net = V_char - F_ml
```
**The brief's form is correct here, conditional on `F_ml` from Step 2** — not
because the brief derived it, but because it happens to match simple statics
(cutting the pile at mudline, the mooring reaction is just another applied
force above the cut, with moment arm `d_sb_fl`). **Caveat found: this
reduction is not guaranteed to be positive.** If `K_ml,net` is very large
relative to the foundation stiffness (approaching the "mooring pins the
fairlead" limit), classical propped-cantilever behavior means the *base*
reaction can reverse sign for some load distributions. The methodology must
verify the **sign and magnitude** of `M_char_net`/`V_char_net` after solving,
not assume the naive subtraction is always a benign reduction.

**New critical section — the fairlead itself.** The brief only asks about
mudline `M_char`/`V_char`. Because the mooring reaction is a point force
applied **above** mudline, the bending moment diagram between mudline and
fairlead is not guaranteed to be maximal at mudline anymore — moment is
continuous, so it is maximal at one end of the (unloaded) mudline-to-fairlead
segment. The fairlead-section moment (using loads above the fairlead only,
valid when `d_sb_fl ≤ z_wave_eq`, i.e. the wave-load resultant is above the
fairlead — flagged as an approximation, since it treats the wave load as a
single resultant, exactly as the baseline already does for `M_wave`/`F_wave`
everywhere else):
```
M_fl = M_char - d_sb_fl * V_char
```
**Required new check: ULS/buckling/SLS at the mudline must use
`max(|M_char_net|, |M_fl|)`, not `M_char_net` alone.** This is new physics the
brief's draft entirely misses — it silently assumes mudline remains governing.
In the typical case (`F_ml` a modest fraction of `V_char`, the expected
regime), `M(0) = M_char_net < M_fl`... actually the comparison needs to be
run per case; no blanket claim either way is safe, so both must be evaluated.

**Load-factor linearity caveat:** because the whole system (soil, mooring,
pile) is linear-elastic **as long as no line goes slack**, `F_ml` at
`GAMMA_F_ULS`-factored loads equals `GAMMA_F_ULS × F_ml` at characteristic
loads — i.e. the baseline's existing pattern of "factor once, reuse" still
works, **but only if line slack is verified not to occur between the
characteristic and factored load levels** (§9a). If a leeward line goes
slack under factored loads but not under characteristic loads, this linear
scaling over-predicts `F_ml` (fewer lines are actually resisting), and the
naive `GAMMA_F_ULS × F_ml,char` shortcut becomes non-conservative.

---

## 5. ULS check

**Governing equation unchanged from baseline (§5)** — `sigma_vm =
sqrt(sigma_bending² + 3·tau_shear²)`, checked against `STEEL_YIELD_MPA /
GAMMA_M_ULS`. What changes is the **input loads and the number of sections
checked**:

```
M_uls_mudline = GAMMA_F_ULS * M_char_net
V_uls_mudline = GAMMA_F_ULS * V_char_net
M_uls_fairlead = GAMMA_F_ULS * M_fl        (V at fairlead = GAMMA_F_ULS*V_char, unaffected below fairlead cut)
```
Run the existing `sigma_vm` formula at **both** sections (mudline and
fairlead — see §4c), governing = the worse of the two utilizations. Section
properties (`D`, `t`) at the fairlead location may differ from mudline if the
pile is tapered — out of scope for this concept-stage constant-`D`/`t`-per-run
model, same limitation the baseline already has.

**New sixth check — mooring line ULS (does not exist in the baseline at
all):** the pile yield check does not protect the mooring line itself. Per
DNV-OS-E301-style practice, line tension must be checked against `MBL`:
```
T_max = T0 + K_ml * cos(theta) * dx_fl,max * cos(phi_worst)
utilization_MooringULS = gamma_ml * T_max / MBL
```
where `dx_fl,max` is the fairlead displacement under factored/extreme loads
and `cos(phi_worst)` is the worst-heading single-line factor from §4b
(ranging 0.5–1.0; recommend the conservative `1.0` for concept screening
unless the mooring layout is deliberately oriented relative to a known
dominant load heading). **`gamma_ml` is not sourced in this session** (§1) —
flagged, not fabricated.

**Structural-safety-philosophy question the brief never raises, and which
this document cannot answer on its own — must be a user/owner decision, not
a silent default:** unlike a TLP (where tendon loss is potentially
catastrophic because the tendons *are* the entire station-keeping system), a
BC90 monopile is **independently** bottom-founded. Two fundamentally
different design philosophies are possible:
1. **Mooring as redundant assist**: the pile alone (mooring lines removed, or
   with one line failed) must still pass ULS/buckling — mooring only helps
   NFA/FLS/cost, is never *relied on* for ULS survival. This requires an
   **ALS "mooring-line-loss" case**: re-run ULS/buckling with `F_ml=0` (or
   with the group stiffness of only 2 remaining lines) and confirm it still
   passes.
2. **Mooring as load-bearing, non-redundant**: the pile is explicitly sized
   assuming mooring is present, in which case mooring line inspection,
   monitoring, redundancy/consequence classification, and ALS design per
   DNV-OS-E301 all become mandatory, and a corroded/damaged/fishing-gear-cut
   line is a genuine structural risk to the whole system, not just a
   serviceability issue.

This is a first-order missing-physics/scope question (see also the Note
section) — the brief's "M_char reduced by Fx·d_sb_fl" framing implicitly
assumes philosophy (2) without saying so, since it treats the mooring
reduction as unconditionally available.

---

## 5a. Local shell buckling check

**Disagree with the brief's premise.** The brief asks "how does mooring
impact buckling?" and suggests the code/formula doesn't change, only
`M_char`/`V_char` do. The DNV-RP-C202 buckling **formula** indeed does not
need new coefficients — but the brief's own two inputs (`M_char`, `V_char`)
are *not* the only inputs that change. **A required input is missing
entirely: `axial_load_estimate`.**

Recall from §4a: every taut line has a vertical tension component `Fz = F *
sin(theta)`, entirely absent from the source PDF's FBD and from the brief's
discussion. Summing over 3 lines, and noting (from the isotropy derivation in
§4b, applied to the *vertical* direction, which has no azimuthal dependence)
that the tension-redistribution terms `Delta F_i` sum to **zero** to first
order across 3 symmetric lines (their cosine-weighted sum vanishes by the
same identity as §4b), the **net downward force from mooring on the pile is,
to first order, independent of lateral load and equal to its pretensioned
value**:
```
F_ml,vertical ≈ 3 * T0 * sin(theta)
```
This **must** be added to `axial_load_estimate` (`_axial_load_estimate` in
`engine.py`, currently RNA+tower weight + pile self-weight only):
```
axial_load_estimate_BC90 = axial_load_estimate_baseline + 3*T0*sin(theta)
```
This directly increases `sigma_axial`, hence the compressive stress combined
into `sigma_vM` in the buckling check (`engine.py` §5a formula, unchanged
otherwise) — **buckling utilization goes up because of mooring, not down**,
even though bending/shear utilization (via `M_char_net`/`V_char_net`) goes
down. **This is a genuine trade-off the brief's framing misses entirely**:
stiffer/higher-pretension mooring helps NFA and reduces bending demand, but
directly worsens shell buckling. Any BC90 sizing loop must check both
directions, not assume mooring is a free win.

**Second-order note, out of scope for a formula change but worth flagging:**
the fairlead attachment itself (padeye/bracket, or a shell penetration for a
chain stopper) is a local stress concentration and potential local buckling
initiator that the "unstiffened cylinder, full exposed length" model (baseline
§5a) does not represent at all — a FEED-stage detail, not a concept-stage
methodology gap, but worth noting since it is currently unmodeled in either
direction (neither as a stiffening ring nor as a local weak point).

**`l_panel` (panel length) itself: unchanged.** The brief doesn't ask about
this directly, but for completeness: `l_panel` remains the full exposed
above-mudline shaft length (baseline's no-ring-stiffener assumption) unless
the fairlead bracket is explicitly modeled as a stiffening ring — which it
is not, at concept stage. No change proposed.

---

## 6. SLS check

**Agree with the brief: no equation change**, provided the corrected `M_char_net`,
`V_char_net` from §4c (not the brief's un-derived `Fx`) are used as the
`M_char`/`V_char` inputs to the **unchanged** baseline Hetenyi rotation formula
(baseline §6):
```
theta0 = (2*beta^2/k_line)*V_char_net + (4*beta^3/k_line)*M_char_net
utilization_SLS = |theta0_deg| / allowable_sls_rotation_deg   (unchanged)
```
**Why this is actually valid, not just convenient:** the Hetenyi flexibility
relation computes base rotation as a direct function of the *actual* applied
moment/shear at the mudline cut — and `M_char_net`/`V_char_net` are, by
construction in §4c, exactly the actual net moment/shear at that cut after
the mooring reaction is netted out. So no further correction is needed beyond
getting `F_ml` right in §4c — the brief's "no changes" conclusion for SLS
holds, but only because of the §4c derivation, not despite skipping it.

**One additional SLS-relevant question not in the brief:** should mudline
rotation still be the *sole* governing SLS criterion (baseline assumption,
§11 item 9), or does the fairlead attachment/line angle tolerance introduce a
second serviceability limit (e.g. an allowable range of `theta` before the
line geometry/anchor design is invalidated, or a minimum tension/creep
serviceability limit for synthetic rope)? Flagged as an open modeling
question, not resolved here — no rope-serviceability criterion is proposed
without a chosen line material.

---

## 7. Natural frequency / soft-stiff check (NFA)

**The brief's proposed equation has a sign error — flagged and corrected, not
adopted.**

Brief's draft: `M x'' + k x = Fx`, `Fx = K_ml * dx_ml`, rearranged to
`M x'' + (k - k_ml) x = 0`. Read literally, this makes the taut mooring line
**reduce** total stiffness (`k - k_ml`), i.e. **soften** the system and
**lower** `f0`. This is physically backwards: a taut mooring line under
tension is a restoring spring **in addition to** the structural/foundation
stiffness, exactly like the existing `K_L`/`K_R` foundation springs — it
should **stiffen** the system and **raise** `f0`. Correctly signed: if the
line elongation tracks the same DOF `x` (`dx_ml = x`), the mooring's restoring
force on the mass is `-K_ml·x` (opposing motion, same sense as `-kx`), giving
`M x'' + (k + K_ml) x = 0` — not `(k - k_ml)`.

**But the more important problem is not the sign — it's that `x` (a
single lumped DOF at hub height) and the mooring's own attachment point
(fairlead, height `d_sb_fl` ≠ hub height `h`) are not the same point.**
Simply substituting `k_ml` into the hub-height lumped-stiffness equation
(regardless of sign) ignores that the mooring spring acts at an intermediate
height and its effect on tip (hub) flexibility depends on the *lever arm*
between the two heights — exactly the same flexibility-coupling issue
resolved in §4c for the static ULS/SLS problem. **Answering the brief's
literal question — "can this relation be used to calculate the flexibility
contribution of taut mooring?" — no, not in the form given; the following
does the job correctly, reusing the same `f_ha`/`f_aa` machinery from §4c:**

Using the redundant-force method again, but now for a **unit tip (hub-height)
force** instead of the actual environmental loads (standard technique: any
elastic support's contribution to *tip flexibility* is found by asking what
the added spring does to the tip displacement under a unit tip load):
```
f_total = f_hh  -  K_ml,net * (f_ha)^2 / (1 + K_ml,net * f_aa)
```
where `f_hh` is the baseline's existing (unchanged) hub-height flexibility
(`cantilever_flexibility + 1/K_L + h²/K_R`, baseline §7), `f_aa = f(d_sb_fl,
d_sb_fl)` as in §4c, and `f_ha = f(d_sb_fl, h)` (cross-flexibility between
fairlead and hub height, same kernel).

**This formula reduces flexibility (`f_total < f_hh`), correctly stiffening
the system and raising `f0`** — the opposite direction from the brief's
draft, confirming the sign-error finding above.

**Sanity checks confirming the formula (not asserted, verified against two
known limits):**
- **Rigid-mooring limit** (`K_ml,net → ∞`): `f_total → f_hh - (f_ha)²/f_aa`,
  which is exactly the classical flexibility of a cantilever **pinned** at
  the fairlead height — the correct limiting case for an infinitely stiff
  prop.
- **Fairlead-at-mudline limit** (`d_sb_fl → 0`): `f_aa = f_ha = 1/K_L` (the
  bending/rotation terms vanish since the integration domain collapses to
  zero), giving `f_total = f_hh - K_ml,net/(K_L·(K_L+K_ml,net))`, which is
  *identical* to simply replacing `K_L → K_L + K_ml,net` in the baseline's
  own `f_hh` formula — i.e. exactly what you'd get from putting the mooring
  spring in parallel with the foundation spring at the same point. This
  confirms the general formula collapses correctly to the trivial case.

```
K_eq_BC90 = 1 / f_total
f0 = (1/2*pi) * sqrt(K_eq_BC90_in_N_per_m / m_eff)     (m_eff unchanged, §7 baseline)
```

**Additional missing physics flagged, not resolved:** (1) `K_ml` for real
mooring lines (especially synthetic rope) is not a single constant — it is
load-history/rate dependent, with **dynamic (storm) stiffness typically
higher than quasi-static stiffness** for polyester rope (a well-documented
effect in mooring engineering). NFA is inherently a dynamic/cyclic
phenomenon, so it should in principle use a *dynamic* `K_ml`, while the §4c
static moment-reduction arguably uses a slower, more quasi-static value — the
brief provides one `K_ml` with no distinction; this document flags the
distinction as a real modeling gap rather than picking a value. (2) Adding an
elastic support partway up a cantilever can, in principle, introduce
additional vibration modes beyond the classical first fore-aft bending mode
(e.g. a lower-frequency mode dominated by mooring-spring motion). This is
not derived or bounded here — flagged as a check that should be performed
(likely low frequency relative to 1P given typical mooring vs. structural
stiffness ratios, but "likely" is not a substitute for checking) before
concluding the existing single-mode soft-stiff band check is sufficient.

---

## 8. FLS check

**Mechanically, agree with the brief: reuse the unchanged Palmgren-Miner
formula (baseline §8) with `M_char_net` replacing `M_char`:**
```
sigma_char = M_char_net / Z
delta_sigma_eq = FATIGUE_LOAD_FACTOR * sigma_char      (unchanged constant, for now)
... (N_allow, n_cycles, damage, utilization_FLS all unchanged formulas)
```

**Two things the brief's "no changes" undersells:**
1. Since `M_char_net < M_char` (mooring helps), `utilization_FLS` should drop
   — but recall §5a found buckling utilization *rises* due to the new axial
   term. **The net effect on which check governs is not obvious and must be
   evaluated per case, not assumed favorable.**
2. **A completely new fatigue mode is entirely unmodeled: mooring line/fairlead
   connection fatigue.** Mooring lines see millions of tension cycles over a
   25–30 year design life (wave-frequency tension oscillation, not just 1P/3P
   rotor cycling), and chain/wire/synthetic-rope fatigue uses entirely
   different T-N (tension-range vs. cycles) curves, not the monopile shell's
   S-N curve. This is not a small omission — it is a distinct failure mode
   with its own governing standard (DNV-OS-E301 FLS provisions) that this
   document does not attempt to derive (no line material has been chosen),
   but which must exist as a **separate** check before BC90 fatigue is
   considered complete. The baseline's FLS check answers "does the monopile
   shell fatigue?"; BC90 additionally needs "does the mooring line/fairlead
   fatigue?" — a different question with a different governing curve
   entirely absent from this methodology so far. This is flagged prominently
   in the Note section below as missing physics.

---

## 9. Initial guess and iteration loop

**Pile geometry initial guess: unchanged from baseline (§9)** — `D0`, `L0`,
`t0` formulas are retained as the starting point of the pile-sizing loop.
**Step-wise priority rules: unchanged in spirit**, with two additions:
- Mooring's new axial-load contribution (§5a) is folded into the
  "ULS/FLS/Buckling failing → increase `t`" branch exactly as the existing
  axial-load term already is (no new branch needed, just a bigger axial input).
- A **new failure mode requires a new lever**: if the mooring-line ULS check
  (§5) or the slack check (§9a below) fails, neither `D`, `t`, nor `L`
  fixes it — only the **mooring parameters** (`K_ml`, `T0`, `R_a`) do. This is
  the key reason the two loops are proposed as nested (§0) rather than a
  single flat iteration: the existing baseline's 4-branch priority logic has
  no lever for a mooring-specific failure.

**Critical-review note carried over from baseline (§9/§11 item 21), sharper
here:** the baseline already documents that embedded length `L` has no
capacity-driven growth mechanism (only a passive `L/D` clamp side-effect).
Adding mooring does not fix this — if anything, a mooring-assisted design
that reduces `M_char_net`/`V_char_net` gives the loop **even less** incentive
to grow `L`, while §4's note above shows shorter/thinner mooring-assisted
piles are *more* likely to approach the `beta*L < 2.5` validity boundary. This
is not a new bug, but BC90 inherits and amplifies a known baseline gap rather
than resolving it — worth surfacing explicitly rather than letting it pass
silently under a different section number.

## 9a. Initial mooring layout (new)

No real BC90 reference design exists to anchor these the way the baseline
anchors `D0`/`L0`/`t0` to OC3/DTU/IEA turbines (§10). The following are
**physically-motivated starting points, explicitly flagged as unverified
placeholders**, not calibrated values:

- **`N_ml = 3`** (fixed, per scope).
- **Line azimuths**: `0°, 120°, 240°` — arbitrary in orientation given the
  isotropy result (§4b); site-specific interference (cables, other turbines,
  shipping lanes) may force a specific orientation, out of scope here.
- **`d_sb_fl` vs. `R_a` (and hence `theta`) — a genuine trade-off, not a
  default value.** From §4c, a **larger** `d_sb_fl` gives more moment-arm
  benefit per unit `F_ml` (`M_char_net = M_char - F_ml·d_sb_fl`); but from
  §4a, a **larger** `theta` (steeper line, which is what a large `d_sb_fl` at
  fixed `R_a` gives) **reduces** `cos²(theta)` and hence reduces `K_ml,net`
  itself, and reduces `F_ml` for the same displacement. There is an interior
  optimum, not derived here (it depends on `EA_ml` cost vs. anchor-footprint
  cost vs. seabed lease-area constraints — none of which are modeled). As a
  starting point only: pick `R_a` to give `theta` in roughly the 30–45° range
  (a commonly-cited practical range in taut-mooring literature for balancing
  restoring stiffness against footprint economy — **not independently
  verified against a specific standard in this session**, flagged rather than
  presented as sourced).
- **`K_ml`, sized to a target**: rather than guessing `K_ml` directly, size it
  to the **minimum** value that clears NFA (§7) for a pile geometry that would
  otherwise fail NFA on its own (the plausible primary use case for BC90,
  per the brief's own "deep water" framing — deeper water increases the total
  cantilever height `h`, which is exactly what drives `f0` down in the
  baseline's own formula). Use §7's corrected `f_total` formula, solve for
  the `K_ml,net` that raises `f0` to just clear `band_low`, then back out
  `K_ml` from the chosen `theta`/`R_a`.
- **`T0` (pretension)**: start at `T0 ≈ Delta F_max` (the extreme
  characteristic-load incremental tension from §4b/§5), so the leeward line's
  minimum tension is close to zero at the characteristic load level, then add
  margin (a factor of, e.g., 1.2–1.5× is a plausible starting point —
  **unverified**, not a sourced design factor) so the line does not go slack
  under factored/extreme loads. **Required check, new to BC90, not in the
  baseline at all:**
  ```
  T_min = T0 - Delta F_max,leeward   (must stay > 0, with margin, at every load level checked)
  ```
  Going slack is not merely conservative-vs-unconservative bookkeeping — a
  slack line contributes **zero** stiffness (the linear `K_ml` model in §4a
  only applies in tension; mooring lines cannot push), so the entire §4b/§4c
  isotropic-group-stiffness derivation silently stops applying to a slack
  line. This is the single most important thing to verify before trusting
  any `F_ml`-based reduction in §4c/§5/§6/§8.
- **Required MBL**: back out from the mooring ULS check (§5),
  `MBL_required = gamma_ml * T_max`.

---

## 10. Verification

**No verification cases exist for BC90 — this is a gap, not an oversight to
paper over.** The baseline's §10 verification rests entirely on three real
reference monopile designs (OC3 5MW, IEA 15MW, IEA 22MW), none of which use
mooring or operate at 60–90 m depth. There is currently no published
taut-mooring-assisted monopile reference design to check any of the above
against. Recommended before this methodology is used beyond a first internal
pass:
- Cross-check the isotropic 3-line stiffness result (§4b) and the
  redundant-force `F_ml` formula (§4c) against a simple FE model (even a
  2D/3D beam-with-springs model in any FE tool) for at least one geometry, the
  same way the baseline's buckling check was cross-checked against WISDEM
  (baseline §5a) — this is a closed-form derivation from first principles here,
  not yet independently verified against a second method.
- If any published TLP-monopile-hybrid or "taut-leg-assisted monopile"
  concept study becomes available, compare converged `D`/`t`/`K_ml`/`T0`
  against it, the same way the baseline compares to OC3/IEA.

---

## 11. Major assumptions (BC90-specific, additive to baseline §11)

1. **3 mooring lines, equally spaced 120° in plan, identical `K_ml`/`theta`/`T0`** — a modeling choice, not derived from the brief (which specifies neither plan-view layout nor pretension distribution).
2. Mooring line modeled as a single linear axial spring (`F=K_ml·d_ml`), valid **only while the line remains in tension** — no slack/compression, no nonlinear (e.g. catenary-touchdown, or synthetic-rope nonlinear) stiffness.
3. `K_ml` treated as a single constant, not distinguishing quasi-static vs. dynamic/storm stiffness (a real, documented effect for synthetic rope) — flagged in §7, not resolved.
4. Wave/current load treated as two resultant point loads (`F_thrust` at hub height, `F_wave` at `z_wave_eq = M_wave/F_wave`) for the §4c/§7 flexibility derivations — consistent with, but not more rigorous than, how the baseline already lumps `M_wave`/`F_wave` everywhere else.
5. `K_LM` foundation cross-coupling term omitted, exactly as in baseline §7 — carried through unchanged into the new `f(a,b)` kernel.
6. Single most-loaded-line tension check uses a conservative worst-heading alignment factor (`cos²=1`) unless the mooring layout is deliberately oriented relative to a known dominant load heading — not derived from a directional load model.
7. Net vertical mooring force on the pile (`3·T0·sin(theta)`) treated as first-order load-independent (tension-redistribution terms cancel exactly across 3 symmetric lines) — valid to first order/linear regime only, breaks down once any line goes slack.
8. Mooring-line and pile-sizing loops solved as nested, not jointly optimized (§0) — mooring layout parameters are not co-optimized with pile `D`/`t`/`L` in this phase.
9. `GAMMA_ML_ULS` and slack-prevention tension margins are unsourced placeholders (§1, §9a) — not verified against DNV-OS-E301's actual factor tables in this session.
10. Structural-safety philosophy (mooring as redundant assist vs. load-bearing/non-redundant, §5) is left as an explicit open decision, not defaulted silently.
11. Mooring line fatigue (T-N curve, wave-frequency tension cycling) and fairlead-connection fatigue are **not modeled at all** — a distinct missing check, not merely an unrefined one (§8).
12. Global buckling of the composite pile+mooring system (as opposed to local shell buckling) is not evaluated, consistent with the baseline's own choice not to model Euler column buckling (baseline §5a/§11 item 18) — carried through unchanged, not re-justified for the mooring case specifically.

---

## Note — answers to the brief's two open questions

**"Is there other relevant physics missing which might have impact on the
design?"**

In order of expected impact:
1. **Vertical mooring tension component (`Fz`) adding axial compression** —
   entirely absent from the source PDF's FBD and the brief's own discussion;
   directly worsens local shell buckling (§5a) even as bending/shear demand
   drops. This is the single most consequential omission found in this
   review.
2. **Line slack / tension-only nonlinearity** — the entire isotropic-stiffness
   and redundant-force derivation (§4b/§4c) is a *linear* elastic result that
   silently stops applying the moment a leeward line goes slack. No slack
   check exists in the brief at all.
3. **Mooring line and fairlead-connection fatigue** (T-N curves, wave
   -frequency cycling) — a distinct failure mode with no equivalent in the
   baseline monopile-only tool, currently entirely unmodeled (§8).
4. **New critical section at the fairlead**, not just at mudline — moment
   there (`M_fl`) can, in principle, govern instead of mudline moment; the
   brief's framing implicitly assumes mudline always governs.
5. **Structural redundancy/consequence philosophy** — whether the pile must
   independently pass ULS without mooring (fail-safe) or is explicitly
   designed to rely on mooring (requiring ALS/inspection/monitoring per
   DNV-OS-E301) is unresolved and changes what "mooring reduces M_char" is
   even allowed to mean for design purposes (§5).
6. **Dynamic vs. quasi-static mooring stiffness** for the NFA check
   specifically (§7) — real mooring lines, especially synthetic rope, do not
   have one constant `K_ml`.
7. Possible additional low-frequency vibration mode introduced by the
   intermediate elastic support, not checked here (§7).
8. Marine growth / increased Morison drag coefficient effects, more relevant
   at 60–90 m exposed shaft length than at the baseline's shallower
   verification depths (§3) — a pre-existing baseline simplification, not
   BC90-specific, but more consequential here.

**"What are the other cost factors that the current model does not
include?"**

The brief's stated output list ("total mass of MP, CAPEX") only accounts for
monopile steel, per the baseline's existing `steel_mass_t *
USD_PER_T_STEEL`. Missing for BC90 specifically:
1. **Mooring line material cost** (chain/wire/synthetic rope, cost typically
   scales with `MBL` requirement and `L_ml`, not modeled).
2. **Anchor cost** (drag-embedment, suction pile, or plate anchor — cost
   scales with required holding capacity, itself a function of `T_max` and
   soil type; no anchor-capacity model exists at all here, only the mooring
   line's own tension check).
3. **Installation cost** — mooring line/anchor installation typically requires
   a different vessel spread (anchor-handling tug, or suction-pile
   installation vessel) than monopile installation (jack-up or heavy-lift
   vessel), a cost category the baseline tool has no equivalent for at all
   (baseline doesn't model installation cost for the pile either, so this is
   a new *category* of gap, not an extension of an existing one).
4. **Fairlead/padeye hardware and local structural reinforcement** cost — not
   part of the "unstiffened cylinder, constant t" cost model.
5. **Inspection/monitoring program cost** over the design life — relevant
   specifically under the "mooring as non-redundant, load-bearing" philosophy
   (§5), and potentially a recurring OPEX item, not CAPEX, that the current
   CAPEX-only framing doesn't have a place for.
6. **Synthetic rope replacement/re-tensioning cost** during the design life
   (creep, UV degradation, marine growth on rope, periodic re-tensioning) —
   an OPEX item specific to synthetic taut mooring that chain/wire systems
   don't have to the same degree; not modeled, and not even categorized in
   the brief's output list (which only anticipates CAPEX).
7. Seabed lease-area / exclusion-zone cost implications of the mooring
   footprint (`R_a`), relevant for site layout/spacing between adjacent
   turbines in a wind farm — a site/farm-level cost the single-turbine
   concept tool has no mechanism to represent.

---

## References used for the mooring-specific derivations

- `c:\Users\yusik\work\Naretek\taut moorling line model.pdf` — source
  single-line 2D free-body diagram (§4a), reproduced exactly, extended to 3
  lines (§4b) and to the redundant-force method (§4c) in this document.
- TLP tendon / taut-mooring horizontal restoring stiffness in the
  `(EA/L)·cos²θ` form is standard in the tension-leg-platform literature
  (general-knowledge cross-check only; a literature search this session found
  general treatments of TLP tendon conventional + geometric stiffness but did
  not turn up a single canonical formula citation to quote directly — treat
  the `K_ml·cos²θ` form here as derived from the source PDF's own two given
  relations, not as a verbatim quotation from an external standard).
- DNV-OS-E301 ("Position Mooring") — referenced for the *existence* and
  general structure of ULS/FLS/ALS partial-safety-factor and minimum-tension
  practice for taut mooring systems; **specific numeric factor values were
  not independently verified in this session** (a direct fetch of the
  relevant factor table was blocked) — flagged throughout rather than
  presented as sourced.
- Baseline `docs/METHODOLOGY_REPORT.md` §4 (Hetenyi closed-form) and §7
  (virtual-work cantilever flexibility) — the entire §4c/§7 redundant-force
  derivation in this document is a direct, exact-limit-checked extension of
  those two baseline derivations, not a new physics principle.
