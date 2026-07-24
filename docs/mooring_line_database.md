# Mooring Line & Anchor Database — Sourced Reference for BC90

**Purpose:** Research-only reference database of taut-mooring line, chain, and anchor
properties/costs to support a future design-optimization pass over BC90
(`bc90/mooring.py`, `bc90/engine_bc90.py`). This document does not modify any code.

**Scope caveat (repeated from the task brief, applies throughout):** BC90 is a
bottom-founded monopile with mooring as a *supplementary stiffening/load-relief*
system, MBL requirements roughly 10–30 MN, water depth 60–90 m. Almost all
published mooring engineering data below comes from **floating** wind and
floating oil & gas (TLP/semisub/FPSO station-keeping) mooring, where lines are
longer, MBLs are often larger, and the line is the *primary* restoring system.
Every number below should be read with that context gap in mind — it is
directionally the right industry precedent, not a like-for-like match.

**Confidence labels used throughout:**
- **Primary** — directly read from a standard, datasheet, or manufacturer catalogue.
- **Secondary** — from a peer-reviewed paper, report, or reputable industry
  summary/thesis that itself cites or re-derives primary data.
- **Derived here** — a number I calculated from two or more sourced inputs
  (arithmetic shown, assumptions stated explicitly).
- **Not found** — searched for, not located; flagged as a gap, not guessed.

---

## 1. Comparison to current code placeholders

| Constant (file) | Current value | Research finding | Verdict |
|---|---|---|---|
| Polyester quasi-static EA (`mooring.py` docstring / brief) | ≈13.5×MBL (range 12–15×) | Secondary literature (see §2) gives quasi-static EA in roughly the same **10–15×MBL** band; one source states "typical static stiffness ≈13×MBL" almost verbatim. | **Roughly confirmed**, no primary-standard number found to replace it; treat as reasonable order-of-magnitude, not verified to the decimal. |
| Polyester dynamic/storm EA (≈26.5×MBL, 25.8× at 25%MBL / 27.5× at 40%MBL) | ≈26.5×MBL | Same secondary literature also gives "typical dynamic stiffness ≈30×MBL", and the two ResearchGate papers already cited in the code are the actual origin of the 25.8×/27.5× figures — confirmed as an accurate paraphrase of those two papers (see §2), not independently re-derived from raw test data. | **Confirmed as accurately citing its stated sources**; the 25–28× working range is consistent with the broader literature's ~30× figure, on the low side but not contradicted. |
| Pretension 15–20% MBL (`layout_from_line_data` docstring) | 0.15 default | **Now has a real citable convention**: DNV-OS-E301 itself does not mandate a numeric pretension fraction (it just requires "the relevant pretension shall be applied for the operating state," §B406) — the 10–20% MBL figure is an *industry rule-of-thumb* repeated across multiple floating-wind mooring papers/theses (see §9), not a DNV requirement. | **Partially confirmed**: the range is real and widely used, but its authority is "common practice cited across many secondary sources," not a numbered clause in a standard — code's phrasing (informal convention) is more accurate than calling it a standard. |
| `GAMMA_ML_ULS = 1.75` | 1.75, "DNV-OS-E301-style, 1.5–2.0" | **Found the actual DNV-OS-E301 (Oct 2008) Table D1** (§8 below): for a **quasi-static** analysis (the structural equivalent of BC90's single-scalar model) the factor is **1.70 for Consequence Class 1** or **2.50 for Consequence Class 2** — applied as one factor on total characteristic tension, matching BC90's `γ×T_max` structure. For a **dynamic** analysis DNV instead splits tension into mean+dynamic components with *separate* factors (1.10/1.50 CC1, 1.40/2.10 CC2) — a structurally different equation BC90 does not implement. | **Contradicted/refined**: 1.75 sits just above the CC1 quasi-static value (1.70) but far below CC2 (2.50) — reasonable *if* BC90's mooring assist is judged Consequence Class 1 (failure "unlikely to lead to unacceptable consequences," §D101) and analyzed quasi-statically. If CC2, or if BC90 is judged a non-redundant single-point system (§D203, ×1.2 uplift on the whole table), the required factor is 2.04–3.0, materially higher than 1.75. **This determination (CC1 vs CC2) is a judgment call the methodology report has not yet made — flagged as the actual open item**, not the numeric value itself. |
| `T_MIN_FRACTION = 0.05` | 0.05 | **Not found.** DNV-OS-E301 requires anchors not designed for uplift to keep lines from going slack at all (§D801) and separately requires the anchor line to have "enough length to avoid uplift... for all relevant design conditions in the ULS" — it does not define a numeric minimum-tension fraction of T0/MBL comparable to `T_MIN_FRACTION`. No other source searched gave one either. | **Gap confirmed** — remains an unsourced, arbitrary placeholder; nothing found to replace it with. |
| `USD_PER_M_MOORING_LINE = $500/m` | $500/m | **Now sourced for polyester specifically**: Striani et al. 2025 (J. Mar. Sci. Eng. 13(12), 2341), Eq. (2): `C_polyester = (0.0138·MBL + 11.281)·L_m` [EUR], MBL in kN, L_m in m — a per-meter cost linear in MBL, not the flat $500/m the code currently uses regardless of line size (see §10 for the computed table). | **Contradicted (for polyester)**: at the tool's current default MBL=15 MN, Eq.(2) gives ≈€218/m (≈$236/m at an indicative FX rate) — well under $500/m, and the relationship is MBL-dependent where the code's constant is not. Chain/wire/HMPE $/m remain unsourced gaps (see §10). |
| `USD_PER_ANCHOR = $250,000` | $250,000 | BVG Associates: drag-embedment anchor cost ≈£35M for a 1 GW floating wind farm (§7, §10). **Derived here**: assuming 15 MW turbines (~67 turbines/GW) × 3 lines/anchors each = 201 anchors, £35M / 201 ≈ £174,000/anchor ≈ **$221,000/anchor** at an indicative ~1.27 USD/GBP rate. | **Roughly confirmed in floating-wind drag-anchor terms** — same order of magnitude as $250,000 — but this is a *derived* estimate built on assumptions the source doesn't state (turbine size, anchors/turbine), and it prices a floating-wind drag anchor sized for full station-keeping, not a BC90 anchor sized for a much smaller assist load in 60–90 m water. Treat the closeness as coincidental, not validation, and note it does not model holding-capacity dependence, exactly as the code's own comment already flags. |

---

## 2. Polyester rope

| Property | Value / range | Source | Confidence |
|---|---|---|---|
| Quasi-static axial stiffness | ~13×MBL typical (12–15× commonly cited band) | Secondary summary drawing on: Del Vecchio (1992) type deepwater mooring rope literature, as reflected in ResearchGate figure "Non-linear Polyester Axial Stiffness" (tbl2_254518183) and "Factors Affecting the Measurement of Axial Stiffness of Polyester Deepwater Mooring Rope Under Sinusoidal Loading" (Flory/Banfield et al., OMAE, via ResearchGate pub 254518760) | Secondary (full papers paywalled; numbers taken from indexed abstract/table text) |
| Dynamic (storm) axial stiffness | ~30×MBL typical; 25.8×MBL at 25%MBL mean load, 27.5×MBL at 40%MBL mean load | Same two papers as above | Secondary |
| Permanent creep | ~4% over service life (order of magnitude) | Same literature summary (creep of polyester ropes averages ~4%) | Secondary |
| Fatigue (T-N curve) | `log(n_c(R)) = log(a_D) − m·log(R)`, with **a_D = 0.259, m = 13.46**, R = tension range ÷ characteristic strength; design fatigue safety factor **γ_F = 60** (deliberately far larger than steel's 3–8 because of test scatter in the polyester R-N curve — DNV states 60 combined with m=13.46 corresponds to an equivalent safety factor of only ~1.36 on line tension, same as steel's γ_F=2.5 at m=3) | **DNV-OS-E301 (Oct 2008), Ch.2 Sec.2, Table F3 and §F602–F702**, primary standard text, read directly from the PDF | **Primary** |
| Long-term mooring (LTM) fatigue-life check | replacement-based fibre segments require calculated/design fatigue life ratio of 5–8 (5 if no replacement planned, 3 if replacement is planned) | DNV-OS-E301 §F703 | Primary |
| Stiffness models required by DNV | Full non-linear force-elongation curve preferred; if unavailable, static stiffness for mean/LF tension + dynamic stiffness for WF tension; stiffness of synthetic rope "has to be verified by testing" per certification (DNV-OS-E303) | DNV-OS-E301 §B107–B108 | Primary (existence of the requirement); the underlying test curve itself is rope-specific and not reproduced here |
| MBL vs diameter table | **Not found** — manufacturer datasheets (Bexco/Bekaert "Bridon MoorLine", Lankhorst "Ecoline"/"Gama 98") are referenced across multiple sources as the standard commercial source but full public tables were not retrievable (available "on request" per manufacturer sites) | Bexco (bexco.be), Lankhorst Ropes (lankhorstropes.com) — existence confirmed, table contents not accessed | Gap (source identified, data not obtained) |
| Cost per meter | **`C_polyester = (0.0138·MBL_kN + 11.281)·L_m` [EUR]** → cost/m = `0.0138·MBL_kN + 11.281` EUR/m (L_m cancels out of the per-meter figure) — see §10 for the computed table across MBL=5–30 MN | **Striani, Jiang, Biroli, Shao & Wang (2025), "Review of Floating Offshore Wind Turbines with Shared Mooring Systems," J. Mar. Sci. Eng. 13(12), 2341, Eq. (2), p.17** — read directly from the PDF; the paper's own text attributes the correlation to a DTOcean+-style cost-estimation model (§5, citing Chemineau et al. 2023) rather than deriving it themselves | **Primary** (read directly), though the underlying correlation's ultimate origin (DTOcean+ deliverable D4.6, ref [72] in that paper) was not independently re-verified this session |
| Cost per meter (relative, not absolute) | Nylon-vs-polyester comparison implies polyester is *more* expensive per unit of compliance than nylon (40–45% total mooring-system cost saving reported for nylon vs polyester in a 100-turbine farm study) | Acteon blog "Is nylon rope a better mooring systems option for FOW?", citing Ruiz-Minguela et al., "Assessment of nylon versus polyester ropes for mooring of floating wind turbines," Ocean Engineering (ScienceDirect, 2023) | Secondary (relative comparison only, no absolute $/m) |
| Why polyester is the current default choice | "Proven for permanent moorings for decades"; predictable axial stiffness (bounded, largely load-history-insensitive) vs. nylon's strongly rate/amplitude-dependent behavior; superior UV and wear resistance vs. nylon in wet conditions | Acteon blog (as above); PLOS ONE 2025 "Mechanical behavior of synthetic fiber ropes for mooring floating offshore wind turbines" (Guo et al.) — found polyester's static stiffness (~1,637–1,847 kN at 30–60% MBS) more stable than nylon's (~1,193–1,340 kN) across load levels, and superior wet wear resistance | Secondary |

**Net assessment for §1's placeholders:** the 13.5×/26.5× EA figures in the code are an accurate paraphrase of real (if paywalled) papers, and the broader literature's ~13×/~30× figures don't contradict them — no primary-standard number was found to replace them, so they remain the best available approximation, just still "secondary, not independently re-derived" exactly as the code already says.

---

## 3. HMPE / Dyneema rope

| Property | Value / range | Source | Confidence |
|---|---|---|---|
| Elongation at break | ~3–4%, similar order to steel wire — implies much higher axial stiffness than polyester for the same MBL | General HMPE mooring-rope literature (Offshore Magazine "New polyethylene fiber suitable for deepwater mooring ropes"; connect-knkt.com, duracordix.com buyer's guides) | Secondary |
| EA as multiple of MBL | **Not found** as a specific number (unlike polyester, no paper surfaced giving an explicit ×MBL figure for HMPE) | — | Gap |
| Creep — SK78 grade (older/common HMPE) | ~0.5%/year | Dynamica Ropes / DSM Dyneema product literature (dynamica-ropes.com/products/dm20) | Secondary (manufacturer marketing page, but a specific quantitative claim) |
| Creep — DM20 grade (Dyneema Max Technology, purpose-built for deepwater permanent mooring) | ~0.02%/year, <0.5% cumulative elongation over 25 years in a Lankhorst Gama 98 DM20 rope | Dynamica Ropes (dynamica-ropes.com/products/dm20); DSM/Offshore-Technology press release on "Dyneema Max Technology" | Secondary (manufacturer-sourced, but the only source found with a specific creep figure) |
| MBL vs diameter | **Not found** in public form | — | Gap |
| Cost vs polyester | Generic HMPE/Dyneema carries a 15–30% price premium over generic HMPE or polyester in commercial (non-offshore-certified) rope retail; separately, one study claims HMPE can lower **total mooring system cost 15–20% over a 20-year field life** vs. steel chain due to lower replacement frequency and easier handling, while another explicitly concludes HMPE's "poor economics" mean it does *not* hold a cost advantage for FOWT mooring overall | Retail rope comparison sites (cheaprope.co.uk, premiumropes.com) for the 15–30% figure — **low confidence, consumer market, not offshore-certified product pricing**; PLOS ONE 2025 (Guo et al.) for the "poor economics" conclusion — secondary, peer-reviewed | Mixed: retail premium figure is low-confidence; the "poor economics" conclusion is secondary but from a peer-reviewed source. **These two findings are in tension with each other and are not reconciled here** — flagged, not resolved. |
| Suitability for taut mooring | Explicitly cited as suited to taut designs due to high stiffness; used in ultra-deepwater (>2,000 m) beyond where synthetic rope elongation would be excessive | Offshore Magazine; duracordix.com | Secondary |

---

## 4. Nylon rope

| Property | Value / range | Source | Confidence |
|---|---|---|---|
| Suitability for taut mooring | Yes — "polyester and nylon are more suitable for taut mooring configurations due to their relatively higher flexibility" than chain/wire; nylon is the *most* compliant of the common fiber ropes | Acteon blog; PLOS ONE 2025 (Guo et al.) | Secondary |
| Why not more widely used (despite lower cost) | Axial stiffness strongly dependent on load amplitude and loading frequency (unlike polyester, where this dependence is "usually negligible") — harder to design/model predictably; less UV-durable; qualification testing still incomplete relative to polyester's decades of proven service | Ruiz-Minguela et al. 2023 (Ocean Engineering, via Acteon summary); PLOS ONE 2025 | Secondary |
| Static stiffness (initially installed, 1×12 braided) | ~1,340 kN at 30% MBS, ~1,285 kN at 45% MBS, ~1,193 kN at 60% MBS (coefficient, not a ×MBL ratio — rope-specific test result) | PLOS ONE 2025 (Guo et al.), "Mechanical behavior of synthetic fiber ropes for mooring floating offshore wind turbines" | Secondary, direct experimental data from a named study, but not normalized to EA/MBL form |
| Cost vs polyester | ~40–45% total mooring-system cost reduction reported using nylon instead of polyester for a representative 100-turbine floating wind farm, achieving equivalent compliance with roughly ⅓ the rope length of polyester | Acteon blog, citing Ruiz-Minguela et al. 2023 | Secondary |
| Wear/durability concern | Wet conditions cause faster wear via hydrogen-bonding of water with nylon's polar groups — a documented mechanism, unlike polyester | PLOS ONE 2025 (Guo et al.) | Secondary |
| MBL vs diameter, EA/MBL ratio, T-N fatigue curve | **Not found** in standard/datasheet form (no DNV T-N table for nylon; DNV-OS-E301 explicitly only tabulates polyester, §F604: "developed for polyester ropes... may be used for other types of fibres due to lack of information") | DNV-OS-E301 §F604 (explicitly flags the absence) | Primary confirmation of the gap itself |

**Conclusion for BC90 relevance:** nylon is a real, occasionally-used taut-mooring material with a genuine cost advantage, but its stiffness/fatigue behavior is materially less standardized than polyester's — reasonable to exclude from a first-pass BC90 database expansion beyond this flag.

---

## 5. Wire rope (spiral strand / six-strand)

| Property | Value / range | Source | Confidence |
|---|---|---|---|
| Young's modulus, stranded (six-strand) rope | **E = 7.0×10¹⁰ N/m²**, corresponding to nominal wire rope diameter (i.e., area = π/4·d²_nominal, not summed wire cross-sections) | **DNV-OS-E301 (Oct 2008), Ch.2 Sec.2, §B106 guidance note** — primary standard text | **Primary** |
| Young's modulus, spiral strand rope | **E = 1.13×10¹¹ N/m²**, same nominal-diameter convention | DNV-OS-E301 §B106 | **Primary** |
| Seabed friction coefficient | 0.5 for steel wire rope (vs. 1.0 for chain) | DNV-OS-E301 Ch.2 Sec.2 §A104 | **Primary** |
| Fatigue (S-N curve) | `log(n_c(s)) = log(a_D) − m·log(s)`; **six-strand/"stranded rope": a_D = 3.4×10¹⁴, m = 4.0**; **spiral strand: a_D = 1.7×10¹⁷, m = 4.8** (stress range s in MPa on nominal area π/4·d²); curves assume the rope is protected from seawater corrosion | **DNV-OS-E301 Table F1 and Fig. 7**, primary standard text | **Primary** |
| Qualitative fatigue comparison | Spiral strand is more fatigue-resistant than six/multi-strand rope, consistent with the higher a_D/m in its S-N curve; six-strand is more flexible/easier to handle but generates torque under tension | Acteon "Wire rope for offshore moorings" blog; DNV-OS-E301 Fig. 7 (spiral strand plots above six-strand/stud-link/open-link on the same S-N chart) | Secondary (qualitative) + Primary (the chart itself) |
| Choice-of-construction guidance vs. field design life | DNV Table E2: for field design life <8 yr, replaceable half-locked/full-locked/spiral (with or without sheathing) or stranded rope are all acceptable; 8–15 yr, same three minus unsheathed variants depending on replaceability; >15 yr, sheathed spiral/locked-coil only if non-replaceable | DNV-OS-E301 Ch.2 Sec.2 Table E2 | **Primary** |
| Construction/diameter range | 45–145 mm typical for spiral strand mooring wire | Bekaert.com product page "Spiral strands for anchorage of offshore oil production platforms" | Secondary/manufacturer |
| Water depth suitability | Static/taut applications up to ~1,500 m; excellent fatigue resistance under cyclic tension | Acteon blog | Secondary |
| MBL vs diameter formula | `MBF = d²·K·R` where d = nominal diameter (mm), K = construction-specific fill/spin-loss factor, R = wire tensile grade (N/mm²); K typically implies a 0.80–0.97 "spin loss" efficiency vs. the sum of individual wire areas | General wire-rope engineering summary (qianjun-wire-rope.com); exact K/R values for offshore spiral-strand grades **not found** | Secondary, formula structure only — no ready-to-use coefficient table found |
| Cost per meter | **Not found** | — | Gap |

---

## 6. Chain (studless/studlink, grades R3/R4/R5)

| Property | Value / range | Source | Confidence |
|---|---|---|---|
| Young's modulus, stud chain R3 | **E = (12.028 − 0.053·d)×10¹⁰ N/m²**, d = chain bar diameter in mm | **DNV-OS-E301 §B106 guidance note, attributed by DNV to chain manufacturer Vicinay** | **Primary** |
| Young's modulus, stud chain R4/R5 | **E = (8.208 − 0.029·d)×10¹⁰ N/m²** | DNV-OS-E301 §B106 (Vicinay) | **Primary** |
| Young's modulus, studless chain R3 | **E = (8.37 − 0.0305·d)×10¹⁰ N/m²** | DNV-OS-E301 §B106 (Vicinay) | **Primary** |
| Young's modulus, studless chain R4/R5 | **E = (7.776 − 0.01549·d)×10¹⁰ N/m²** | DNV-OS-E301 §B106 (Vicinay) | **Primary** |
| Converting E to EA for chain | Nominal chain-link stress area for fatigue purposes is **2×(π/4)·d²** (two bars per link cross-section) — DNV uses this same area convention for computing nominal stress ranges, and it is the natural convention for EA = E × Area from the moduli above | DNV-OS-E301 Ch.2 Sec.2 §F102 (`2πd²/4` given explicitly for chain) | **Primary** (area convention); EA value itself not computed here — left for a future pass with an actual chain diameter |
| Seabed friction coefficient | 1.0 for chain (unless documented otherwise) | DNV-OS-E301 §A104 | **Primary** |
| Corrosion allowance | Splash zone 0.4 mm/yr (no inspection) / 0.2 mm/yr (regular inspection) / 0.8 mm/yr (Norwegian continental shelf); catenary 0.3/0.2 mm/yr; bottom 0.4/0.3/0.2 mm/yr | DNV-OS-E301 Table E1 | **Primary** |
| Fatigue (S-N curve) | Stud chain: **a_D = 1.2×10¹¹, m = 3.0**; studless (open link) chain: **a_D = 6.0×10¹⁰, m = 3.0** (in-air test data; in-seawater fatigue life reduced by factor 2 for stud-link, factor 5 for studless, already reflected in the given curve for use "in sea water") | **DNV-OS-E301 Table F1 and Fig. 7** | **Primary** |
| Fatigue safety factor | γ_F = 5 (regularly-inspected-ashore mobile units: γ_F = 3) when adjacent-line damage ratio d_F ≤ 0.8; γ_F = 5 + 3·(d_F−0.8)/0.2 for d_F > 0.8 (up to γ_F = 8 at d_F = 1) | DNV-OS-E301 §F402–F404 | **Primary** |
| Out-of-plane bending (OPB) fatigue | Additional stress concentration factor of 1.15 for chain links at fairleads with 7-pocket wheels; a separate, non-tension-fatigue failure mode DNV requires be checked independently | DNV-OS-E301 §F206–F207 | **Primary** |
| MBL formula (approximate, generic — not confirmed as current R3/R4/R5) | `MBL = c·d²·(44 − 80d) kN`, d in the source's implied units (consistent with historical "Grade 2/3/ORQ/R4" designations, not confirmed identical to current ISO 20438 R3/R4/R5 grade naming); c = 1.37×10⁴ (Grade 2), 1.96×10⁴ (Grade 3), 2.11×10⁴ (ORQ), 2.74×10⁴ (R4) | Orcina OrcaFlex documentation ("Chain: Mechanical properties"), citing "catalogue data from chain manufacturer Scana Ramnas (1990 & 1995)" | Secondary — formula is from a real manufacturer catalogue via a widely-used engineering-software vendor's documentation, but it predates and does not confirm alignment with modern ISO 20438 R3/R3S/R4/R4S/R5 grade definitions |
| Mass per unit length | Studless: **19.9·d² tonnes/m**; studlink: **21.9·d² tonnes/m** (d in the same units as the MBL formula) | Same Orcina/Scana Ramnas source | Secondary |
| Chain diameter range in current commercial/offshore use | 34–162 mm generally quoted; 185–220 mm specifically noted for floating-wind chain (larger than typical oil & gas due to larger loads); a single 220 mm link weighs ~700 kg and exceeds 1 m in length; chain mass restricts deployment to shallower sites, "typically under 200 m" | Dawson Group product pages (existing code source); guidetofloatingoffshorewind.com "B.3.2 Mooring lines" | Primary (diameter range, manufacturer) + Secondary (floating-wind-specific figures) |
| Studless vs. stud-link preference | Studless preferred for most permanent moorings: ~10% lighter than stud-link at equal breaking strength, no loose studs, no stud-weld cracking, easier manufacture/inspection; stud-link resists knot formation better | ScienceDirect Topics "Mooring Chain" overview; guidetofloatingoffshorewind.com | Secondary |
| MBL vs diameter, R3/R4/R5-specific table | **Not independently obtained beyond the existing Dawson Group reference already in the code** — ISO 20438 Table 2 is repeatedly cited as the authoritative source but its numeric content was not retrievable in this session (sample PDF from iTeh Standards did not yield readable table text) | ISO 20438:2017 (existence and location of the table confirmed; values not extracted) | Gap (source identified, data not obtained — same limitation the code's own comment already flags for the "single Dawson data point") |
| Cost per meter / per tonne | **Not found** as a directly quotable $/m or $/tonne figure; only a market-size figure was found (global offshore mooring chain for floating wind market ≈$114M in 2023, forecast ≈$1,020M by 2030 — a market total, not a unit price) | Valuates Reports market-sizing summary | Gap (market total ≠ unit cost; not usable for BC90 costing) |

---

## 7. Anchors

| Anchor type | Holding capacity / cost data | Source | Confidence |
|---|---|---|---|
| **Drag embedment anchor (DEA)** | Under good conditions, holding capacity 33× to >50× anchor weight. Vryhof full-scale test data: 2 t Stevpris → 107 t ultimate holding capacity (~53×); 7 t Stevpris → >338 t (~48×+); 3 t Stevpris → 150 t in sand, 102 t in soft clay, 150 t in an 8 m-mud-over-rock profile (~50×, ~34×, ~50× respectively); a 1984 Gullfaks A mooring design used 40 t (sand), 65 t (mud), 60 t (mud-on-rock) Stevpris/Stevshark anchors against a 1,500 t survival-load requirement | Vryhof Anchor Manual 2005, §"Anchor tests" (full-scale field/model test data, primary manufacturer manual); Wikipedia "Offshore embedded anchors" for the general 33–50× figure | **Primary** (Vryhof manual is a directly-read primary industry reference, albeit from a single manufacturer) |
| DEA — cyclic/set-up effects | Cyclic (storm) loading followed by static hold shows 25–50% *increase* in anchor resistance vs. initial installation load (further penetration during cycling); clay set-up/consolidation effect ≈1.5× over 3–4 weeks; rate effect (dynamic vs static loading) 1.1–1.3× | Vryhof Anchor Manual 2005, §"Anchor behaviour in the soil," §"Cyclic effect factor" | **Primary** |
| DEA — soil suitability | Best suited to cohesive sediments not too stiff to resist embedment; uni-directional horizontal loading only (small uplift capacity unless a Vertical Load Anchor / VLA design); requires high pretension to embed correctly, difficult in deep water without a tensioning device | guidetofloatingoffshorewind.com "B.3.1 Anchors"; Vryhof Anchor Manual 2005 | Secondary + Primary |
| **Vertical Load Anchor (VLA)** | Once triggered to normal (perpendicular) loading, holding capacity increases 2.5–3× relative to installation load; required installation load ≈33–40% of required ultimate pull-out capacity (UPC); ideal for taut-leg systems (line-seabed angle 25–45°) since load can be applied in any direction once deeply embedded | Vryhof Anchor Manual 2005, §"Vertical Load Anchors" | **Primary** |
| **Suction pile** | Multi-directional (horizontal + vertical) loading capable; requires seabed firm enough to hold suction but soft enough to allow penetration; installation is self-weight + applied suction, reversible; anchor positioning tolerance ±5 m per DNV-OS-E301 §D111 | guidetofloatingoffshorewind.com; DNV-OS-E301 §D111 | Secondary + Primary (positioning tolerance) |
| **Driven pile** | Multi-directional loading; works in varied ground incl. boulders/hard ground where suction/drag anchors don't; installation noise from impact/vibro-hammer; difficult to remove | guidetofloatingoffshorewind.com | Secondary |
| Pile vs. drag-anchor cost (qualitative) | "The required pile weight for a system is equal to the required weight of a [drag] anchor. Piles cost about 40% of equivalent capability anchors. However, the installation costs for piles are much higher" — net effect on total installed cost not resolved in the source | Vryhof Anchor Manual 2005, §"Pile or anchor," Table L | **Primary** (though a single manufacturer's framing, and dated 2005) |
| **Plate anchor / SEPLA** | High pull-out capacity relative to weight, enabling smaller/cheaper anchors than driven or suction piles for equivalent capacity; SEPLA (Suction-Embedded Plate Anchor) uses "as little as one-third the material" of a suction pile for equivalent performance; holding capacity in clay dominated by undrained shear strength Su, response can be effectively drained over the design life as excess pore pressure dissipates (increasing capacity with time); sand behavior less proven, "problematic," alternative concepts (e.g., Umbrella anchor) proposed but not established practice | ScienceDirect "Anchor geotechnics for floating offshore wind" review (2023); Acteon "Anchor types for floating energy facilities" blog | Secondary |
| Drag-anchor total cost, 1 GW floating wind farm | ≈**£35 million** | guidetofloatingoffshorewind.com "B.3.1 Anchors" (BVG Associates methodology) | Secondary (aggregate project-level figure, not manufacturer unit pricing) |
| Suction/driven-pile cost premium | "Difficult ground conditions require the use of piled or suction anchors which could result in anchor costs that are several times higher [than drag anchors]" — qualitative multiplier only, no numeric factor given | Same source | Secondary, qualitative only |
| Cost vs. holding-capacity formula | **Not found** as an explicit function (no $ = f(capacity) curve located for any anchor type) | — | Gap |

---

## 8. DNV mooring safety factors — full table recovered

The prior WebFetch attempt (per the task brief) returned HTTP 403 against DNV's
rules portal. **This session successfully retrieved DNV-OS-E301 (October 2008
edition) as a PDF and read the actual clauses/tables directly** (not a
secondary paraphrase) using a local PDF reader rather than a live web fetch.
This is the single most load-bearing finding in this whole document for BC90's
`GAMMA_ML_ULS` constant.

### Consequence classes (DNV-OS-E301 Ch.2 Sec.2 §D101)
- **Class 1**: mooring system failure unlikely to lead to unacceptable
  consequences (loss of life, collision, uncontrolled hydrocarbon release,
  capsize/sinking).
- **Class 2**: failure may well lead to unacceptable consequences of these types.

### Table D1 — Partial safety factors for ULS (§D200)
Design equation: `S_C − T_C,mean·γ_mean − T_C,dyn·γ_dyn ≥ 0`

| Consequence Class | Type of analysis | γ_mean | γ_dyn |
|---|---|---|---|
| 1 | Dynamic | 1.10 | 1.50 |
| 2 | Dynamic | 1.40 | 2.10 |
| 1 | Quasi-static | 1.70 (single factor on total tension) | — |
| 2 | Quasi-static | 2.50 (single factor on total tension) | — |

Notes directly from the standard:
- §D202: if characteristic mean tension exceeds ⅔ of characteristic dynamic
  tension in a CC1 dynamic analysis, use a common factor of **1.3** on total
  tension instead of the separate 1.10/1.50 pair.
- §D203: single-point mooring systems designed **without redundancy** (where
  ALS is therefore not applicable) must have **all Table D1 factors increased
  by ×1.2**, provided loss of the unit won't cause major pollution/damage and
  emergency disconnection/backup propulsion exists.

### Table D2 — Partial safety factors for ALS (§D300)

| Consequence Class | Type of analysis | γ_mean | γ_dyn |
|---|---|---|---|
| 1 | Dynamic | 1.00 | 1.10 |
| 2 | Dynamic | 1.00 | 1.25 |
| 1 | Quasi-static | 1.10 | — |
| 2 | Quasi-static | 1.35 | — |

### Table H1 — Target annual probability of failure (§G103)

| Limit state | Consequence class | Target annual P(failure) |
|---|---|---|
| ULS | 1 | 10⁻⁴ |
| ULS | 2 | 10⁻⁵ |
| ALS | 1 | 10⁻⁴ |
| ALS | 2 | 10⁻⁵ |
| FLS | single line | 10⁻³ |
| FLS | multiple lines | 10⁻⁵ |

### Direct implication for BC90's `GAMMA_ML_ULS = 1.75`
BC90's model computes one factored line tension (`γ × T_max`) with no
mean/dynamic split — structurally a **quasi-static** analysis in DNV's terms.
The matching DNV factor is **1.70 (CC1) or 2.50 (CC2)**, times **1.2 if the
system is judged non-redundant** (§D203). 1.75 is defensible only under the
specific combination "CC1 + redundant (3-line) system" — and even then it's
essentially the CC1 value rounded up slightly, not really justified by CC2 or
non-redundancy considerations. **This is a modeling decision (which
consequence class applies to a mooring-assisted monopile, and whether §D203's
non-redundancy uplift applies) that the methodology report has not made — the
real gap is that decision, not a missing number.**

---

## 9. Pretension conventions (10–20% MBL)

| Finding | Source | Confidence |
|---|---|---|
| DNV-OS-E301 itself does not specify a numeric pretension fraction — it requires "the relevant pretension shall be applied for the operating state that is considered," full stop | DNV-OS-E301 §B406 (read directly) | **Primary** (confirms the *absence* of a DNV-specified number) |
| "Pretensions of the lines are checked to ensure they stay roughly between 10% and 20% of minimum breaking load (MBL)" — recurring statement across floating-wind mooring design papers/theses | Multiple: ResearchGate "Mooring System Design and Analysis for a Floating Offshore Wind Turbine in Pantelleria"; UMass Amherst thesis "Mooring Systems for Floating Offshore Wind"; general design-practice summaries indexed under this search | Secondary — repeated across several independent design studies, so likely a genuine industry rule-of-thumb, but no single standard clause found mandating it |
| A **constant pretension ratio of 0.15** (i.e., the same 15% used as BC90's default) combined with 40 t clump weights reduced mooring line length, footprint, and peak tension by 14%, 15%, and 9% respectively in one design study | Indexed floating-wind mooring optimization paper (via search summary; specific paper not independently re-verified in full text) | Secondary |
| "Values of 10% and 30% of MBL have traditionally been used" — a wider historical range than the commonly-quoted 15–20% | Same search-indexed literature | Secondary, and notably wider than the code's 15–20% framing — flagged as a minor inconsistency in the literature itself, not resolved here |

**Conclusion:** the 15–20% MBL convention is real and traceable to widespread
floating-wind and oil & gas mooring design practice, but it is a convention
repeated across many secondary sources, not a clause in DNV-OS-E301 or any
other primary standard located in this session. BC90's own documentation
already correctly describes it as a floating-vessel convention used only as a
sanity check, not a governing constraint — that framing holds up.

---

## 10. Costs — overall findings and gaps

| Cost item | Finding | Source | Confidence |
|---|---|---|---|
| Mooring lines, 1 GW floating wind farm (aggregate) | ≈**£175 million** | guidetofloatingoffshorewind.com "B.3.2 Mooring lines" (BVG Associates) | Secondary, aggregate only |
| Anchors, 1 GW floating wind farm (aggregate, drag-embedment) | ≈**£35 million** | Same source, "B.3.1 Anchors" | Secondary, aggregate only |
| "Jewellery" (connectors/fittings), 1 GW | ≈£98 million | Same source, "B.3.3 Jewellery" | Secondary, aggregate only |
| Anchor/mooring pre-installation (vessel time etc.), 1 GW | ≈£153 million | Same source, "I.4 Anchor and mooring pre-installation" | Secondary, aggregate only |
| Derived anchor unit cost | ≈**$221,000/anchor** — **derived here**: £35M ÷ (assumed 67×15MW turbines × 3 anchors/turbine = 201 anchors) × ~1.27 USD/GBP. Assumptions (turbine size, anchors/turbine) are not stated in the source and are mine, made explicit here rather than left implicit. | Derived from the above | **Derived here** — order-of-magnitude only |
| Mooring line unit cost ($/m), polyester | **Found**: Striani et al. 2025, Eq. (2) — see table and citation immediately below. Chain (Eq. 1), single anchor (Eq. 3), and shared-anchor (Eq. 4) correlations are given in the same source but not computed here since only the polyester relation was requested. | Striani et al. 2025, Eqs. (1)–(4), p.17 | **Primary** for polyester (Eq. 2); chain/anchor equations available for a future pass |
| Mooring line unit cost ($/m), BVG Associates aggregate route | **Not derived** — the source gives no total line-length figure, so £175M cannot be converted to $/m without an additional unstated assumption (e.g. average line length per turbine) that would be pure guesswork; abandoned rather than fabricated | — | Gap (superseded for polyester by the row above) |
| Cost-modeling functional form referenced in literature | NREL wave-energy-converter mooring-cost methodology reportedly prices chain and polyester rope in $/m scaling with (line diameter)² — i.e. cost ∝ d² — consistent with how MBL itself scales with d² for both chain and rope | Search-indexed summary of NREL WEC mooring cost methodology; **coefficient values not recovered**, functional form only | Secondary, structure only — **not usable to produce an actual $/m number** |
| HMPE cost vs. polyester | Conflicting: 15–30% retail premium (low-confidence, non-offshore market) vs. a peer-reviewed claim that HMPE's "poor economics" mean no net FOWT mooring cost advantage; separately, a different claim that HMPE cuts total system cost 15–20% over 20 years via reduced replacement | See §3 | Mixed / contradictory, flagged not resolved |
| Nylon cost vs. polyester | ≈40–45% total system cost reduction reported for a 100-turbine farm | Acteon / Ruiz-Minguela et al. 2023 | Secondary |
| Global offshore mooring chain (floating wind) market size | ≈$114M (2023) → ≈$1,020M (2030F), CAGR 37.9% | Valuates Reports market-sizing summary | Secondary, market total — **not a unit cost, not usable for per-line/per-tonne costing** |
| Direct manufacturer $/m or $/tonne for chain, polyester, wire, HMPE | **Not found** for any material | Multiple manufacturer sites checked (Bexco, Lankhorst, Dawson Group, Bekaert) — datasheets exist but pricing is "on request," not published | Gap across the board |

### 10a. Polyester cost vs. MBL (Striani et al. 2025, Eq. 2)

`C_polyester = (0.0138 · MBL + 11.281) · L_m` [EUR], where `MBL` is in **kN**
(not MN — the tool's convention) and `L_m` is line length in m. Dividing by
`L_m` gives a per-meter cost that depends only on MBL:

```
cost_per_m [EUR/m] = 0.0138 * MBL_kN + 11.281 = 13.8 * MBL_MN + 11.281
```

| MBL (MN) | Cost (EUR/m) | Cost (USD/m, indicative FX 1 EUR≈1.08 USD) |
|---|---|---|
| 5 | 80.3 | 86.7 |
| 10 | 149.3 | 161.2 |
| 15 | 218.3 | 235.7 |
| 20 | 287.3 | 310.3 |
| 25 | 356.3 | 384.8 |
| 30 | 425.3 | 459.3 |
| 40 | 563.3 | 608.3 |
| 50 | 701.3 | 757.4 |
| 60 | 839.3 | 906.4 |
| 75 | 1,046.3 | 1,130.0 |
| 100 | 1,391.3 | 1,502.6 |
| 125 | 1,736.3 | 1,875.2 |
| 150 | 2,081.3 | 2,247.8 |

The USD column applies an indicative, unsourced FX conversion for
order-of-magnitude comparison against the code's USD-denominated constant —
not a sourced number in its own right. Context caveat: this correlation, like
most of this database, comes from **floating**-wind shared-mooring cost
analysis (via a DTOcean+-style model), not a BC90-type bottom-founded
supplementary-mooring application specifically.

**Extrapolation caveat (rows above MBL=30 MN):** Striani et al. 2025's own
paper concerns floating-wind shared-mooring systems, whose individual line
MBLs are not stated in the excerpt read this session but are generally
consistent with the 5-30 MN range already in the table — this document's own
§1/scope note puts BC90's own target range at roughly 10-30 MN. The 40-150 MN
rows are a **linear extrapolation of Eq. (2) far outside any MBL range the
source paper is known to have validated**, added here only because the tool
is now being used to explore higher-MBL polyester lines; the formula's
intercept-plus-slope form has no physical reason to stay linear at this
scale (e.g. it ignores manufacturing/handling step-changes for
very-large-diameter rope), so treat the 40+ rows as an order-of-magnitude
placeholder, weaker in confidence than the already-Primary 5-30 MN rows, not
as sourced data in their own right.

Companion equations in the same source (not computed into a table here, since
only the polyester relation was requested — available for a future pass):
`C_chain = (0.055·MBL − 83.41)·L_m` [EUR] (Eq. 1), `C_anchor,single =
9.484·MBL` [EUR] (Eq. 3, MBL in kN), `C_anchor,shared = M·C_material·(1+CF)`
[EUR] (Eq. 4, M = anchor mass in kg, C_material in EUR/kg).

**Unverified supplementary commentary (excluded from the sourced rows above,
noted for transparency only):** a ChatGPT conversation referenced alongside
this request initially presented a diameter-indexed MBL/weight/cost table
attributed to a Bekaert catalogue, then retracted it in the same conversation
("those cost figures did not come from the Bekaert catalogue... I should have
explicitly labelled them as such"). That table, and an accompanying "typical
design properties" table (axial stiffness, elongation, density, safety
factor) from the same unverified turn, are deliberately **not** included here.
Two ideas from that conversation may be worth independent verification later,
but are not treated as sourced: (1) a supplier-adjustment factor `f_sup`
(0.8 optimistic / 1.0 literature / 1.2 conservative) multiplying Eq. (2) to
bracket quotation uncertainty; (2) a mention of a separate paper, "Cost
Optimisation of Mooring Systems for Offshore Floating Platforms in Deep
Water" (European Journal of Mechanical Engineering Research, via
eajournals.org), reportedly reporting cost per mooring line for chain-wire
-chain vs. chain-polyester-chain systems — not fetched or read this session.

---

**Bottom line for §1:** `USD_PER_ANCHOR` and the polyester `$/m` figure both
now have a citable basis (§7/§10 and 10a respectively), though neither is a
clean drop-in replacement — the anchor figure is a derived estimate built on
unstated assumptions from the source, and the polyester relation is sourced
from floating-wind shared-mooring cost modeling, not a BC90-specific context.
`T_MIN_FRACTION` and chain/wire/HMPE per-meter costs remain genuine,
unresolved gaps.

---

## 11. Full source list

**Primary (standards, manuals, directly read):**
- DNV-OS-E301, "Position Mooring," Det Norske Veritas, October 2008 edition —
  read directly (Ch.2 Sec.1 D200/D300/D400, Ch.2 Sec.2 A–H in full, Ch.2 Sec.3
  A–D). URL: `https://rules.dnv.com/docs/pdf/dnvpm/codes/docs/2008-10/OS-E301.pdf`
- Vryhof Anchor Manual 2005, Vryhof Anchors b.v. — read directly (General,
  Anchor behaviour in the soil, Proof loads, Anchor tests, Pile or anchor
  sections). URL: `https://ocw.tudelft.nl/wp-content/uploads/AM2000.pdf`
- Dawson Group R3/R4/R5 studless mooring chain product pages
  (dawson-group.com) — same source already used in the existing code; diameter
  range and certification list confirmed, MBL table not retrieved.
- Striani, R.; Jiang, H.; Biroli, M.V.; Shao, Y.; Wang, S. "Review of Floating
  Offshore Wind Turbines with Shared Mooring Systems." Journal of Marine
  Science and Engineering 2025, 13(12), 2341.
  https://doi.org/10.3390/jmse13122341 — read directly (PDF via DTU Orbit,
  backend.orbit.dtu.dk); Section 5 "Mooring Costs Estimation," Eqs. (1)-(4),
  p.17, used for §10a's polyester cost-vs-MBL relation.

**Secondary (papers, reports, industry summaries):**
- Guo et al., "Mechanical behavior of synthetic fiber ropes for mooring
  floating offshore wind turbines," PLOS ONE, 2025 (open access,
  journals.plos.org/plosone/article?id=10.1371/journal.pone.0318190).
- Ruiz-Minguela et al., "Assessment of nylon versus polyester ropes for
  mooring of floating wind turbines," Ocean Engineering, 2023 (ScienceDirect,
  as summarized by Acteon's blog "Is nylon rope a better mooring systems
  option for FOW?").
- "Non-linear Polyester Axial Stiffness" (ResearchGate figure,
  tbl2_254518183) and "Factors Affecting the Measurement of Axial Stiffness of
  Polyester Deepwater Mooring Rope Under Sinusoidal Loading" (ResearchGate
  pub 254518760) — the same two papers already cited in the existing BC90 code.
- "Anchor geotechnics for floating offshore wind: Current technologies and
  future innovations," Ocean Engineering, 2023 (ScienceDirect).
- guidetofloatingoffshorewind.com, "Guide to a Floating Offshore Wind Farm"
  (BVG Associates methodology), sections B.3.1 (Anchors), B.3.2 (Mooring
  lines), B.3.3 (Jewellery), I.4 (Anchor and mooring pre-installation).
- Orcina, "OrcaFlex Documentation" — Chain and Rope/Wire mechanical-property
  derivation pages, citing Scana Ramnas (1990/1995) and Marlow Ropes Ltd
  (1995) manufacturer catalogues.
- Acteon blog posts: "Wire rope for offshore moorings," "Anchor types for
  floating energy facilities," "Is nylon rope a better mooring systems option
  for FOW?"
- Dynamica Ropes / DSM Dyneema, "DM20 rope with Dyneema — Lowest creep
  obtainable" product page, and associated Offshore-Technology press release
  on "Dyneema Max Technology."
- ScienceDirect Topics overview articles: "Mooring Chain," "Spiral Strand,"
  "Strand Rope" (tertiary encyclopedic summaries, used only for orientation,
  not as primary numeric sources).
- Valuates Reports, "Global Offshore Mooring Chain for Floating Offshore Wind
  Market" sizing summary (market total only, not unit costs).

**Searched but not successfully retrieved / not found:**
- ISO 20438:2017 Table 2 (R3/R4/R5 chain MBL table) — location confirmed, text
  not extracted from the sample PDF available.
- Bexco/Bekaert and Lankhorst Ropes full polyester/HMPE product datasheets
  (MBL-vs-diameter tables) — described as "available on request," not public.
- NREL/DOE floating wind reference-design and cost reports
  (`docs.nrel.gov/docs/fy24osti/89121.pdf`, `.../fy25osti/91416.pdf`) — DNS/
  network resolution failed for this domain in this environment; not accessed.
- Direct manufacturer $/m or $/tonne pricing for any mooring line material.
- A cost-vs-holding-capacity formula/curve for any anchor type.
- A DNV or other standard's numeric minimum-tension/slack fraction comparable
  to `T_MIN_FRACTION`.
