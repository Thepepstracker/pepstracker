import json, re, statistics, datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

H = json.load(open("pepstracker_fixed/price-history.json"))
S = H["series"]
_src = open("pepstracker_fixed/index.html", encoding="utf-8").read()
_seg = _src[_src.find("const VENDORS"):]
_seg = _seg[:_seg.find("];")]
NV = len(set(re.findall(r'id\s*:\s*"([^"]+)"', _seg)))
_pseg = _src[_src.find("const PRICES"):]
_pseg = _pseg[:_pseg.find("};") + 1]
NC = len(set(re.findall(r'"([^"]+)"\s*:', _pseg)))
GLP1 = ["Semaglutide", "Tirzepatide", "Retatrutide", "Cagrilintide"]
HEAL = ["BPC-157", "TB-500", "GHK-Cu", "Epithalon"]

dates = sorted({p["d"] for pts in S.values() for p in pts})

def series_for(names=None):
    comps = []
    for name, pts in S.items():
        if names is not None and name not in names:
            continue
        if len(pts) < 10:
            continue
        base = pts[0]["mg"]
        if not base:
            continue
        comps.append({p["d"]: p["mg"] / base * 100.0 for p in pts})
    out = []
    last = {}
    for d in dates:
        vals = []
        for i, m in enumerate(comps):
            if d in m:
                last[i] = m[d]
            if i in last:
                vals.append(last[i])
        out.append(statistics.median(vals) if vals else None)
    return out

alls = series_for()
glp = series_for(GLP1)
heal = series_for(HEAL)
xs = [datetime.datetime.strptime(d, "%Y-%m-%d") for d in dates]

BG, FG, GRID = "#0d0f14", "#e8ecf4", "#1e2430"
BLUE, GREEN, GOLD = "#3b9eff", "#4de87a", "#f5c842"

fig, ax = plt.subplots(figsize=(12, 6.3), dpi=100)
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
for s, c, lab in ((alls, BLUE, "All 83 compounds"), (heal, GREEN, "Healing peptides"), (glp, GOLD, "GLP-1 class")):
    px = [x for x, v in zip(xs, s) if v is not None]
    pv = [v for v in s if v is not None]
    ax.plot(px, pv, color=c, lw=2.6, label="%s  (%.0f)" % (lab, pv[-1]), solid_capstyle="round")
ax.axhline(100, color=GRID, lw=1, ls="--")
ax.grid(color=GRID, lw=0.6, alpha=0.6)
for sp in ax.spines.values():
    sp.set_visible(False)
ax.tick_params(colors=FG, labelsize=11)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
glp_last = [v for v in glp if v is not None][-1]
all_last = [v for v in alls if v is not None][-1]
fig.suptitle("US research peptide prices \u2014 daily best-price index (base 100)", color=FG, fontsize=19, fontweight="bold", x=0.07, y=0.965, ha="left")
ax.set_title("GLP-1 class down %.0f%%, whole market down %.0f%% since June 1 \u00b7 %d vendors \u00b7 live at pepstracker.com/price-index" % (100 - glp_last, 100 - all_last, NV), color="#9aa4b5", fontsize=12.5, loc="left", pad=14)
leg = ax.legend(loc="lower left", frameon=False, fontsize=12)
for t in leg.get_texts():
    t.set_color(FG)
ax.annotate("%.0f" % glp_last, xy=(xs[-1], glp_last), xytext=(6, 0), textcoords="offset points", color=GOLD, fontsize=12, fontweight="bold", va="center")
fig.text(0.985, 0.02, "pepstracker.com \u00b7 research use only", color="#5b6472", fontsize=10, ha="right")
plt.subplots_adjust(left=0.055, right=0.95, top=0.83, bottom=0.09)
fig.savefig("pepstracker_fixed/price-index-card.png", facecolor=BG)
print("wrote card: all=%.1f glp=%.1f days=%d" % (all_last, glp_last, len(dates)))


# ---- homepage og-image (accurate stats) ----
n_comp = len([1 for pts in S.values() if len(pts) >= 1])
fig2 = plt.figure(figsize=(12, 6.3), dpi=100)
fig2.patch.set_facecolor(BG)
fig2.text(0.5, 0.62, "PepsTracker", color=GREEN, fontsize=64, fontweight="bold", ha="center")
fig2.text(0.5, 0.47, "Compare research peptide prices across %d US vendors" % NV, color=FG, fontsize=22, ha="center")
fig2.text(0.5, 0.38, "Discount codes already applied \u00b7 Updated daily \u00b7 Free", color="#9aa4b5", fontsize=17, ha="center")
stats = [(str(NV), "vendors", BLUE), (str(NC), "compounds", GOLD), ("Daily", "updates", GREEN), ("Free", "always", BLUE)]
for i, (big, small, col) in enumerate(stats):
    x = 0.2 + i * 0.2
    fig2.text(x, 0.2, big, color=col, fontsize=30, fontweight="bold", ha="center")
    fig2.text(x, 0.12, small, color="#9aa4b5", fontsize=15, ha="center")
fig2.savefig("pepstracker_fixed/og-image.png", facecolor=BG)
print("wrote og-image")
