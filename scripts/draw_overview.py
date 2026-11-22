"""Draw the overview diagram at the top of the README (docs/architecture.png).

Top row: how the data is built. Bottom row: the three checks run on it, each with what it found.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

DOCS = Path(__file__).resolve().parents[1] / "docs"
INK, GREY, GREEN, GREEN_BG = "#1c1c1c", "#9a9a9a", "#1d7a50", "#e8f8f0"

PIPELINE = [
    ("Raw cloud bills", "AWS, Azure, Oracle, GCP\n100,000 rows"),
    ("Clean", "fix types and casing\nkeep credits apart"),
    ("Standardize tags", "82 messy tag keys\nto env, owner, app"),
    ("Daily cost table", "day x account x\nservice x tags"),
]
CHECKS = [
    ("Reconcile to the bill", "$0.00 off\n100,000 rows in and out"),
    ("Cost alerts vs a forecast", "4 alerts\nwhere fixed rules raise 30+"),
    ("Spend by owner and env", "$968 dev EC2 runs off-hours\n7% of usage has no owner"),
]


def box(ax, x, y, w, h, title, body, finding=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.15",
                                fc=GREEN_BG if finding else "#f4f4f4",
                                ec=GREEN if finding else "#c4c4c4", lw=2))
    ax.text(x + w / 2, y + h * 0.74, title, ha="center", va="center", fontsize=15,
            fontweight="bold", color=INK)
    ax.text(x + w / 2, y + h * 0.36, body, ha="center", va="center", linespacing=1.4,
            fontsize=15 if finding else 12.5, fontweight="bold" if finding else "normal",
            color=GREEN if finding else "#444444")


def arrow(ax, p0, p1):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=20, lw=2, color=GREY))


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 6.0), dpi=150)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6.0)
    ax.axis("off")

    ax.text(0.1, 5.8, "How it is built", fontsize=12, color="#777777", va="center")
    w, gap, y, h = 2.55, 0.53, 3.75, 1.75
    xs = [0.1 + i * (w + gap) for i in range(len(PIPELINE))]
    for x, (title, body) in zip(xs, PIPELINE):
        box(ax, x, y, w, h, title, body)
    for x0, x1 in zip(xs, xs[1:]):
        arrow(ax, (x0 + w + 0.05, y + h / 2), (x1 - 0.05, y + h / 2))

    ax.text(0.1, 2.75, "What it found", fontsize=12, color="#777777", va="center")
    bw, by, bh = 3.8, 0.4, 2.0
    bxs = [0.1, 4.1, 8.1]
    for x, (title, body) in zip(bxs, CHECKS):
        box(ax, x, by, bw, bh, title, body, finding=True)

    # Bus from the daily cost table down to the three checks.
    table_cx, bus_y = xs[-1] + w / 2, 3.1
    ax.plot([table_cx, table_cx], [y, bus_y], color=GREY, lw=2)
    centers = [x + bw / 2 for x in bxs]
    ax.plot([centers[0], table_cx], [bus_y, bus_y], color=GREY, lw=2)
    for cx in centers:
        arrow(ax, (cx, bus_y), (cx, by + bh + 0.05))

    fig.tight_layout(pad=0.2)
    fig.savefig(DOCS / "architecture.png", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
