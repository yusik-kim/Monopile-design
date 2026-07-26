"""
Regenerates the two depth-sweep chart figures used in the Neretek BC90
engineering report (Figures 3 and 4, Section 3.2):
  - Steel weight vs. water depth (MP vs. BC90)
  - Total cost vs. water depth (MP steel-only vs. BC90 total CAPEX)

Reads bc90/water_depth_sweep_results.csv (written by sweep_water_depth_cost.py)
and writes both an SVG (hand-style, matches the existing figures/*.svg source)
and a PNG (rasterized at 2x via Pillow -- no SVG rasterizer is available in
this environment) directly into the Naretek report's docs/figures/ folder.

Run directly:  python bc90/misc/plot_depth_sweep_figures.py
"""
import csv
import math
import os

from PIL import Image, ImageDraw, ImageFont

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
BC90_DIR = os.path.dirname(THIS_DIR)
CSV_PATH = os.path.join(BC90_DIR, "water_depth_sweep_results.csv")
OUT_DIR = r"C:\Users\yusik\work\Naretek\docs\figures"

BG = "#fdfdfc"
GRID = "#d8d7cf"
AXIS = "#8c8a80"
INK = "#141413"
MUTED = "#52514e"
MP_COLOR = "#2a78d6"
BC90_COLOR = "#eb6834"
GREEN = "#006300"
RED = "#b32424"

VIEW_W, VIEW_H = 1060, 460  # wider than the 100-940 plot area to leave room for end-of-line value labels
PLOT_X0, PLOT_X1 = 100.0, 940.0
PLOT_Y0, PLOT_Y1 = 90.0, 390.0  # y0 = top (max), y1 = bottom (0)


def nice_ceil(value, unit):
    return math.ceil(value / unit) * unit


def load_rows():
    with open(CSV_PATH, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in r:
            if k != "bc90_governing":
                r[k] = float(r[k])
            r["water_depth_m"] = int(float(r["water_depth_m"]))
    return rows


def x_for_index(i, n):
    return PLOT_X0 + i * (PLOT_X1 - PLOT_X0) / (n - 1)


def y_for_value(value, axis_max):
    return PLOT_Y1 - value * (PLOT_Y1 - PLOT_Y0) / axis_max


def build_chart(rows, *, title, subtitle, legend, series_keys, axis_unit, y_fmt, end_fmt, annotations_fn):
    n = len(rows)
    depths = [r["water_depth_m"] for r in rows]
    xs = [x_for_index(i, n) for i in range(n)]

    data_max = max(max(r[k] for k in series_keys) for r in rows)
    axis_max = nice_ceil(data_max, axis_unit)
    gridline_step = axis_max / 4.0

    series_ys = {k: [y_for_value(r[k], axis_max) for r in rows] for k in series_keys}

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{VIEW_W}" height="{VIEW_H}" '
                f'viewBox="0 0 {VIEW_W} {VIEW_H}" font-family="Arial, Helvetica, sans-serif">')
    svg.append(f'<rect x="0" y="0" width="{VIEW_W}" height="{VIEW_H}" fill="{BG}"/>')
    svg.append(f'<text x="100" y="34" font-size="22" font-weight="700" fill="{INK}">{title}</text>')
    svg.append(f'<text x="100" y="58" font-size="15" fill="{MUTED}">{subtitle}</text>')
    svg.append(f'<rect x="100" y="71" width="26" height="4" fill="{MP_COLOR}"/>')
    svg.append(f'<text x="134" y="78" font-size="15" fill="{INK}">{legend[0]}</text>')
    svg.append(f'<rect x="294" y="71" width="26" height="4" fill="{BC90_COLOR}"/>')
    svg.append(f'<text x="328" y="78" font-size="15" fill="{INK}">{legend[1]}</text>')

    for g in range(5):
        gv = gridline_step * g
        gy = y_for_value(gv, axis_max)
        svg.append(f'<line x1="100" x2="940" y1="{gy:.1f}" y2="{gy:.1f}" stroke="{GRID}" stroke-width="1"/>')
        svg.append(f'<text x="86" y="{gy+5:.1f}" font-size="15" text-anchor="end" fill="{MUTED}">{y_fmt(gv)}</text>')

    svg.append(f'<line x1="100" x2="940" y1="390" y2="390" stroke="{AXIS}" stroke-width="1.5"/>')
    for i, d in enumerate(depths):
        if i % 2 == 0:
            svg.append(f'<text x="{xs[i]:.1f}" y="416" font-size="15" text-anchor="middle" fill="{MUTED}">{d}</text>')
    svg.append(f'<text x="520.0" y="446" font-size="16" text-anchor="middle" fill="{MUTED}">Water depth (m)</text>')

    for k, color in zip(series_keys, (MP_COLOR, BC90_COLOR)):
        pts = " L ".join(f"{xs[i]:.1f} {series_ys[k][i]:.1f}" for i in range(n))
        svg.append(f'<path d="M {pts}" fill="none" stroke="{color}" stroke-width="3" '
                    f'stroke-linejoin="round" stroke-linecap="round"/>')

    for i in range(n):
        for k, color in zip(series_keys, (MP_COLOR, BC90_COLOR)):
            svg.append(f'<circle cx="{xs[i]:.1f}" cy="{series_ys[k][i]:.1f}" r="5" fill="{color}" '
                        f'stroke="{BG}" stroke-width="2"/>')

    for k, color in zip(series_keys, (MP_COLOR, BC90_COLOR)):
        last_y = series_ys[k][-1]
        svg.append(f'<text x="950.0" y="{last_y+5:.1f}" font-size="15" font-weight="700" fill="{color}">'
                    f'{end_fmt(rows[-1][k])}</text>')

    for ann in annotations_fn(rows, xs, series_ys):
        svg.append(f'<line x1="{ann["x0"]:.1f}" y1="{ann["y0"]:.1f}" x2="{ann["x1"]:.1f}" y2="{ann["y1"]:.1f}" '
                    f'stroke="{AXIS}" stroke-width="1"/>')
        anchor = ann.get("anchor", "start")
        svg.append(f'<text x="{ann["x1"]:.1f}" y="{ann["y1"]+6:.1f}" font-size="15" font-weight="700" '
                    f'text-anchor="{anchor}" fill="{ann["color"]}">{ann["text"]}</text>')

    svg.append("</svg>")
    return "\n".join(svg), {
        "xs": xs, "series_ys": series_ys, "gridline_step": gridline_step, "axis_max": axis_max,
        "depths": depths, "n": n,
    }


def render_png(geom, *, title, subtitle, legend, series_keys, y_fmt, end_fmt, annotations_fn, rows, out_path):
    scale = 2.0
    img = Image.new("RGB", (int(VIEW_W * scale), int(VIEW_H * scale)), BG)
    d = ImageDraw.Draw(img)
    f_title = ImageFont.truetype("arialbd.ttf", int(22 * scale))
    f_sub = ImageFont.truetype("arial.ttf", int(15 * scale))
    f_bold = ImageFont.truetype("arialbd.ttf", int(15 * scale))
    f_axis = ImageFont.truetype("arial.ttf", int(16 * scale))

    def sx(v):
        return v * scale

    d.text((sx(100), sx(34) - int(16 * scale)), title, font=f_title, fill=INK)
    d.text((sx(100), sx(58) - int(11 * scale)), subtitle, font=f_sub, fill=MUTED)
    d.rectangle([sx(100), sx(71), sx(126), sx(75)], fill=MP_COLOR)
    d.text((sx(134), sx(78) - int(11 * scale)), legend[0], font=f_sub, fill=INK)
    d.rectangle([sx(294), sx(71), sx(320), sx(75)], fill=BC90_COLOR)
    d.text((sx(328), sx(78) - int(11 * scale)), legend[1], font=f_sub, fill=INK)

    for g in range(5):
        gv = geom["gridline_step"] * g
        gy = y_for_value(gv, geom["axis_max"])
        d.line([sx(100), sx(gy), sx(940), sx(gy)], fill=GRID, width=max(1, int(scale)))
        txt = y_fmt(gv)
        w = d.textlength(txt, font=f_sub)
        d.text((sx(86) - w, sx(gy + 5) - int(11 * scale)), txt, font=f_sub, fill=MUTED)

    d.line([sx(100), sx(390), sx(940), sx(390)], fill=AXIS, width=max(1, int(1.5 * scale)))
    for i, dep in enumerate(geom["depths"]):
        if i % 2 == 0:
            txt = str(dep)
            w = d.textlength(txt, font=f_sub)
            d.text((sx(geom["xs"][i]) - w / 2, sx(416) - int(11 * scale)), txt, font=f_sub, fill=MUTED)
    xlab = "Water depth (m)"
    w = d.textlength(xlab, font=f_axis)
    d.text((sx(520) - w / 2, sx(446) - int(12 * scale)), xlab, font=f_axis, fill=MUTED)

    for k, color in zip(series_keys, (MP_COLOR, BC90_COLOR)):
        pts = [(sx(geom["xs"][i]), sx(geom["series_ys"][k][i])) for i in range(geom["n"])]
        d.line(pts, fill=color, width=int(3 * scale), joint="curve")

    for i in range(geom["n"]):
        for k, color in zip(series_keys, (MP_COLOR, BC90_COLOR)):
            cx, cy = sx(geom["xs"][i]), sx(geom["series_ys"][k][i])
            r = 5 * scale
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color, outline=BG, width=int(2 * scale))

    for k, color in zip(series_keys, (MP_COLOR, BC90_COLOR)):
        last_y = geom["series_ys"][k][-1]
        txt = end_fmt(rows[-1][k])
        d.text((sx(950), sx(last_y + 5) - int(11 * scale)), txt, font=f_bold, fill=color)

    for ann in annotations_fn(rows, geom["xs"], geom["series_ys"]):
        d.line([sx(ann["x0"]), sx(ann["y0"]), sx(ann["x1"]), sx(ann["y1"])], fill=AXIS, width=int(1 * scale))
        w = d.textlength(ann["text"], font=f_bold)
        tx = sx(ann["x1"])
        if ann.get("anchor") == "end":
            tx -= w
        d.text((tx, sx(ann["y1"] + 6) - int(11 * scale)), ann["text"], font=f_bold, fill=ann["color"])

    img.save(out_path)


def weight_annotations(rows, xs, series_ys):
    i_max = max(range(len(rows)), key=lambda i: (rows[i]["mp_mass_t"] - rows[i]["bc90_mass_t"]) / rows[i]["mp_mass_t"])
    pct = 100 * (1 - rows[i_max]["bc90_mass_t"] / rows[i_max]["mp_mass_t"])
    x0, y0 = xs[i_max], series_ys["bc90_mass_t"][i_max]
    x1, y1 = x0 - 70, y0 - 46
    return [{"x0": x0, "y0": y0, "x1": x1, "y1": y1 - 6, "text": f"{pct:.1f}% lighter (max)",
             "color": GREEN, "anchor": "start"}]


def cost_annotations(rows, xs, series_ys):
    pcts = [100 * (1 - rows[i]["bc90_cost_usd"] / rows[i]["mp_cost_usd"]) for i in range(len(rows))]
    i_worst = min(range(len(rows)), key=lambda i: pcts[i])
    i_best = max(range(len(rows)), key=lambda i: pcts[i])
    out = []
    x0, y0 = xs[i_worst], series_ys["bc90_cost_usd"][i_worst]
    out.append({"x0": x0, "y0": y0, "x1": x0 + 20, "y1": y0 + 40, "text": f"{pcts[i_worst]:.1f}% (mooring costs more here)",
                "color": RED, "anchor": "start"})
    x0, y0 = xs[i_best], series_ys["bc90_cost_usd"][i_best]
    out.append({"x0": x0, "y0": y0, "x1": x0 - 30, "y1": y0 - 46, "text": f"+{pcts[i_best]:.1f}% (best)",
                "color": GREEN, "anchor": "end"})
    return out


def main():
    rows = load_rows()

    svg, geom = build_chart(
        rows,
        title="Steel weight vs. water depth",
        subtitle="15 MW turbine, sand (\u03c6=34\u00b0), Hs=5.5 m, Tp=9.5 s, current=0.4 m/s",
        legend=("MP (no mooring)", "BC90 (optimized)"),
        series_keys=["mp_mass_t", "bc90_mass_t"],
        axis_unit=400.0,
        y_fmt=lambda v: f"{v:,.0f} t",
        end_fmt=lambda v: f"{v:,.0f} t",
        annotations_fn=weight_annotations,
    )
    with open(os.path.join(OUT_DIR, "bc90_weight_vs_depth.svg"), "w", encoding="utf-8") as f:
        f.write(svg)
    render_png(geom, title="Steel weight vs. water depth",
               subtitle="15 MW turbine, sand (\u03c6=34\u00b0), Hs=5.5 m, Tp=9.5 s, current=0.4 m/s",
               legend=("MP (no mooring)", "BC90 (optimized)"), series_keys=["mp_mass_t", "bc90_mass_t"],
               y_fmt=lambda v: f"{v:,.0f} t", end_fmt=lambda v: f"{v:,.0f} t",
               annotations_fn=weight_annotations, rows=rows,
               out_path=os.path.join(OUT_DIR, "bc90_weight_vs_depth.png"))

    svg, geom = build_chart(
        rows,
        title="Total cost vs. water depth",
        subtitle="MP: steel cost only. BC90: steel + mooring line + anchors (total CAPEX).",
        legend=("MP (steel only)", "BC90 (total CAPEX)"),
        series_keys=["mp_cost_usd", "bc90_cost_usd"],
        axis_unit=0.5e6,
        y_fmt=lambda v: f"${v/1e6:.2f}M",
        end_fmt=lambda v: f"${v/1e6:.2f}M",
        annotations_fn=cost_annotations,
    )
    with open(os.path.join(OUT_DIR, "bc90_cost_vs_depth.svg"), "w", encoding="utf-8") as f:
        f.write(svg)
    render_png(geom, title="Total cost vs. water depth",
               subtitle="MP: steel cost only. BC90: steel + mooring line + anchors (total CAPEX).",
               legend=("MP (steel only)", "BC90 (total CAPEX)"), series_keys=["mp_cost_usd", "bc90_cost_usd"],
               y_fmt=lambda v: f"${v/1e6:.2f}M", end_fmt=lambda v: f"${v/1e6:.2f}M",
               annotations_fn=cost_annotations, rows=rows,
               out_path=os.path.join(OUT_DIR, "bc90_cost_vs_depth.png"))

    print(f"Wrote 2 SVG + 2 PNG figures to {OUT_DIR}")


if __name__ == "__main__":
    main()
