# Monopile Concept Design

Concept-stage sizing tool for offshore wind monopile foundations: an
Arany-et-al.-style ("10-step") iteration of ULS/SLS/natural-frequency
(soft-stiff)/FLS checks that converges on a diameter, wall thickness, and
embedded length. See `docs/METHODOLOGY_REPORT.md` for every equation,
constant, and assumption used.

Concept-level screening only -- not certification or FEED design.

## Run

```bash
pip install -r requirements.txt
py -m streamlit run app.py
```

## Turbine library

`engine.py`'s `TURBINE_LIBRARY` spans 5-25 MW. The 5/15/22 MW entries are
sourced from published reference-turbine reports (OC3/NREL 5MW, IEA 15MW,
IEA 22MW); 10 MW is from the DTU 10MW report; 25 MW is an extrapolation, not
an independently verified turbine.
