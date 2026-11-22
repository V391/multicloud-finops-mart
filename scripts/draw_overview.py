"""Draw the one-glance overview diagram at the top of the README (docs/overview.png)."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

DOCS = Path(__file__).resolve().parents[1] / "docs"

BOXES = [
    # x, width, text, face, edge, bold
    (0.2, 3.0, "100,000 raw\ncloud bill rows", "#f3f3f3", "#bbbbbb", False),
    (4.3, 3.0, "Cleaned, tagged\ncost tables", "#f3f3f3", "#bbbbbb", False),
    (8.4, 5.4, "Match the bill: $0.00 off\n4 cost alerts, not 30\n$968 of dev EC2 runs at night",
     "#e8f8f0", "#249361", True),
]


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(14, 3.4), dpi=150)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 3.4)
    ax.axis("off")
    y, h = 0.3, 2.8
    for x, w, text, face, edge, bold in BOXES:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.25",
                                    fc=face, ec=edge, lw=2.5))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=21,
                fontweight="bold" if bold else "normal", color="#1c1c1c", linespacing=1.5)
    for (x0, w0, *_), (x1, *_rest) in zip(BOXES, BOXES[1:]):
        ax.add_patch(FancyArrowPatch((x0 + w0 + 0.1, y + h / 2), (x1 - 0.1, y + h / 2),
                                     arrowstyle="-|>", mutation_scale=32, lw=3, color="#555555"))
    fig.tight_layout(pad=0.2)
    fig.savefig(DOCS / "overview.png", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
