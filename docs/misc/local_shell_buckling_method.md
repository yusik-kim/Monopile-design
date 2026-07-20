# Local shell buckling — method (DNV-RP-C202)

Reference note, captured 2026-07-17. Answers: "how to calculate local shell
buckling?" and "how likely is it to govern the design?" for this project's
monopile concept-design engine. Cross-checked against WISDEM's open-source
DNV-RP-C202 implementation (`wisdem/commonse/utilization_dnvgl.py`,
`CylinderBuckling` class) to keep the coefficients right. See
`METHODOLOGY_REPORT.md` §5a/§11 item 18 for how this informed the decision
**not** to implement a buckling check in `engine.py` at concept stage.

Local shell buckling is different from both ULS yield (pure stress vs.
yield) and global Euler buckling (whole-column instability) — it's the thin
shell **wall itself** rippling into a wave pattern under compressive stress,
well before the material yields. It's highly imperfection-sensitive (real
fabricated shells buckle far below the "perfect cylinder" theoretical load),
which is why the code applies large, stress-level-dependent knockdown
factors rather than a simple safety margin.

## Method

### 1. Characterize the shell's geometry — the curvature (Batdorf) parameter

```
Z = (l^2 / (r * t)) * sqrt(1 - nu^2)
```
`r` = shell radius, `t` = wall thickness, `l` = unsupported panel length
(distance between ring stiffeners, or the full unstiffened length if there
are none), `nu` = Poisson's ratio (0.3 for steel). `Z` tells you whether the
shell behaves like a "short" or "long" cylinder for buckling purposes.

### 2. Elastic (characteristic) buckling strength for each stress type

Each stress component — axial+bending, torsion/shear, and hoop
(circumferential, from external hydrostatic pressure) — gets its **own**
elastic buckling capacity, via a curve-fit coefficient `C` (empirical,
calibrated to shell buckling test data) and the classical shell buckling
formula:
```
fE = (C * pi^2 * E) / (12 * (1 - nu^2)) * (t / l)^2
```
`C` itself is built from three sub-parameters (`psi`, `xi`, `rho` —
different for each stress type, e.g. for axial/bending on an unstiffened
shell: `psi=1`, `xi=0.702*Z`, `rho=0.5*(1+r/(150t))^-0.5`, giving
`C = psi*sqrt(1+(rho*xi/psi)^2)`). This gives three separate elastic
capacities: `fea` (axial/bending), `fet` (shear), `feh` (hoop).

### 3. Combine the actual applied stresses (compression only)

Per DNV convention, only the **compressive** part of each stress counts
(tension doesn't buckle), combined via a von Mises-style formula:
```
sigma_vM = sqrt( ((axial+hoop)/2)^2 + 3*((axial-hoop)/2)^2 + 3*shear^2 )
```

### 4. Reduced slenderness and material factor

```
lambda_s = sqrt( (fy / sigma_vM) * (axial/fea + shear/fet + hoop/feh) )
```
This single number captures how close the shell is to its *elastic*
buckling limit relative to its *material* (yield) limit — low `lambda_s`
means yield governs (thick shell), high `lambda_s` means elastic buckling
governs (thin shell). DNV then assigns a material factor that gets more
conservative as slenderness increases:
```
gamma_m = 1.15                  if lambda_s < 0.5
        = 0.85 + 0.6*lambda_s   if 0.5 <= lambda_s < 1.0
        = 1.45                 if lambda_s >= 1.0
```

### 5. Characteristic and design buckling strength

```
fks  = fy / sqrt(1 + lambda_s^4)        (smooth Ayrton-Perry-style transition
                                         between yield- and buckling-governed failure)
fksd = fks / gamma_m

utilization_shell = sigma_vM / fksd     (pass if <= 1.0)
```

## How likely is it to govern — worked example

Plugging in this model's converged 15 MW geometry (D=9.33 m, t=60.8 mm),
using its own `M_char`/`V_char`, plus rough estimates for the two stress
components this model doesn't currently compute at all (axial self-weight,
hoop pressure from a 35 m water depth):

| Quantity | Value |
|---|---|
| sigma_bending (from `M_uls`) | 157.0 MPa |
| sigma_axial (self-weight, rough estimate) | 13.1 MPa |
| sigma_hoop (35 m hydrostatic pressure) | 27.0 MPa |
| tau_shear | 4.6 MPa |
| `fea` (axial/bending elastic buckling capacity) | 674 MPa |
| `fet` (shear) | 151 MPa |
| `feh` (hoop) | **23.1 MPa** |
| sigma_vM (combined) | 158.5 MPa |
| `lambda_s` | 1.80 |
| `fks` / `fksd` | 104.3 / 72.0 MPa |
| **utilization_shell** | **2.20** |

**This design fails local shell buckling by more than 2x** — worse than
every currently-implemented check combined (FLS, the governing check at the
time, sat at 0.95). Notably, `feh` (23.1 MPa) is already *below* the hoop
stress alone (27.0 MPa) — meaning circumferential buckling from hydrostatic
pressure alone nearly exceeds capacity, before even combining with bending.

**Robustness check:** whether this hinges on the assumed unstiffened panel
length (`l` — the model has no ring stiffeners at all, so 35 m, the full
water depth, was used) was tested directly: it doesn't, for the axial mode.
`fea` comes out to exactly **674.1 MPa whether `l`=10 m or 70 m** — this
shell is deep enough into the "long cylinder" asymptotic regime that the
axial/bending buckling capacity is governed by `r/t` alone, not panel
length. (The **hoop** mode is a different story — it scales roughly as
`1/l` across the whole practical range, which is why panel-length
sensitivity later became the more useful lever to explore; see the
follow-up sensitivity analysis referenced in `METHODOLOGY_REPORT.md`.)

**Bottom line:** if this check were implemented, it would almost certainly
become the new governing constraint, superseding FLS by a wide margin —
meaning this design (and likely the other converged cases) would need
substantially thicker walls, or — as real monopiles do — **ring stiffeners**
near the mudline/high-stress region to make a thin-wall design viable at
all. This is exactly why real offshore monopiles are rarely fully
unstiffened over their full length, and it's the concrete evidence behind
the decision to flag buckling as a real, non-trivial gap (`METHODOLOGY_REPORT.md`
§11 item 18) even though it isn't implemented at concept stage.
