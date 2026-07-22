# MP vs. BC90 Comparison Notes

Companion to `docs/BC90_METHODOLOGY_REPORT.md`. That document derives the
methodology; this one records the numbers from actually running it
(`bc90/compare_mp_vs_bc90.py`) on one representative case, and the
interpretation of what those numbers mean. Regenerate by running:

```
python bc90/compare_mp_vs_bc90.py
```

Case: 15 MW turbine, 75 m water depth (mid of BC90's 60–90 m target range),
sand soil (phi=34 deg), Hs=5.5 m, Tp=9.5 s — a general representative case,
not tied to a specific real site. Mooring line data is literature-typical
polyester rope (see the script's own docstring for sources); not
independently verified against a real product test certificate.

## Results (as of last run)

| Case | D | t | L | Steel mass | Cost | Governing |
|---|---|---|---|---|---|---|
| MP (no mooring) | 10.00 m | 162.9 mm | 50.00 m | 1976.1 t | $4,347,346 | Buckling |
| BC90 (same geometry as MP) | 10.00 m | 162.9 mm | 50.00 m | 1976.1 t | $5,191,069 | Buckling |
| BC90 (shrunk pile) | 9.20 m | 160.9 mm | 50.00 m | 1793.5 t | $4,789,364 | Slack |

Mooring layout: N_ml=3, R_a=48.0 m, d_sb_fl=40.0 m, theta=39.8 deg,
L_ml=62.5 m. K_ml=3.24 MN/m (quasi-static) / 6.36 MN/m (dynamic), T0=0.21 MN
(1.4% MBL), MBL=15.0 MN. T_max=0.42 MN, T_min=0.01 MN, mooring ULS
utilization=0.049, slack utilization=0.973 (i.e. nearly slack — this is what
stops further shrinking; see below).

- Steel mass: 1976.1 t → 1793.5 t (**9.2% less steel**)
- Total CAPEX: $4,347,346 → $4,789,364 (**+10.2% vs. MP steel-only cost** —
  the shrunk BC90 case costs *more* overall despite less steel)

## Why less steel still costs more

The "same geometry" row isolates the pure cost of adding mooring hardware to
an already-sized pile: cost jumps from $4.35M to $5.19M (+$843,750) with
*zero* structural benefit yet, because nothing has been resized. That jump is
the mooring line + anchor cost baked into `total_capex_usd` (steel cost is
unchanged, since geometry is unchanged).

Shrinking the pile against the now-available mooring support recovers 182.6 t
of steel (~$401,720 at MP's $/t rate) — but that saving is smaller than the
mooring hardware cost that had to be paid to earn it. Net effect: BC90(shrunk)
still costs ~$442,000 more than plain MP for this case.

**Takeaway: in this representative case, BC90 does what it's supposed to do
structurally (smaller pile, same or better safety margins on every check
except the one that now governs) but does not pay for itself in pure CAPEX
terms.** The value case would have to come from something not modeled here —
e.g. installation/logistics savings from a smaller pile, or a design point
where MP's steel cost is more dominant (deeper water, harsher metocean)
so the steel savings outweigh mooring cost. That is a hypothesis for a future
sensitivity run, not something this case demonstrates.

## Why "Slack" becomes governing, and why that's expected

The shrunk case's governing constraint flips from Buckling (MP) to Slack
(BC90), with slack utilization=0.973 — right at the edge. This is the
mechanism, not a bug:

- Shrinking the pile increases its lateral displacement under load, which
  increases the mooring line's tension swing (T_max − T0).
- The line's tension can swing down as well as up; if it swings low enough
  that T_min approaches zero, the line is at risk of going slack (loses its
  taut-mooring assumption entirely — `bc90/mooring.py`'s whole stiffness
  derivation stops applying the moment a line goes slack).
- `shrink_geometry_with_mooring` (the outer shrink loop) treats slack
  utilization as a hard constraint alongside ULS/SLS/NFA/FLS/Buckling, so it
  stops shrinking right before the line would actually go slack. A
  utilization of 0.973 means it stopped one step before violating that
  limit — this is the loop working as intended, not a near-failure to worry
  about.

This is also why buckling utilization *drops* slightly in the shrunk case
(0.991 → 0.937) even though mooring adds axial compression (per
`docs/BC90_METHODOLOGY_REPORT.md` Section 5a, confirmed unconditionally by
`bc90/test_engine_bc90.py::check_buckling_axial_always_worsens`): the smaller
diameter reduces bending moment demand enough to offset the added axial load,
for this particular geometry. Both effects are real and move in the
directions the methodology predicts; they just don't move the *same* amount
for every check, which is exactly why the shrink loop must check all
constraints simultaneously rather than assuming buckling stays governing.

## Caveats (carried from the script/methodology docstrings)

- No real BC90 reference design exists yet; the checks in
  `bc90/test_engine_bc90.py` are unconditional identities (must hold for any
  valid input), not regression numbers against a known-good design.
- Mooring line EA/MBL values are literature-typical, not a specific
  manufacturer's certified product data.
- Cost/factor placeholders inherited from `engine.py` carry the same
  "unsourced, first-pass" caveat they already had for the MP-only tool.
