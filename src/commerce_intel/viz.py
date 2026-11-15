"""Matplotlib styling shared by every static figure (thin marks, recessive grid, fixed palette)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import ticker  # noqa: E402

from .config import FIG_DIR, GRID, PALETTE, SURFACE, TEXT_PRIMARY, TEXT_SECONDARY  # noqa: E402


def apply_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "axes.edgecolor": GRID,
            "axes.labelcolor": TEXT_SECONDARY,
            "axes.titlecolor": TEXT_PRIMARY,
            "axes.titleweight": "semibold",
            "axes.titlesize": 12,
            "axes.titlelocation": "left",
            "axes.grid": True,
            "axes.grid.axis": "y",
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.spines.left": False,
            "xtick.color": TEXT_SECONDARY,
            "ytick.color": TEXT_SECONDARY,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.frameon": False,
            "legend.fontsize": 9,
            "lines.linewidth": 2,
            "font.size": 10,
            "font.family": "DejaVu Sans",
            "axes.prop_cycle": matplotlib.cycler(color=PALETTE),
        }
    )


def new_fig(w: float = 9, h: float = 4.5):
    apply_style()
    fig, ax = plt.subplots(figsize=(w, h), dpi=150)
    ax.tick_params(length=0)
    return fig, ax


def fmt_thousands(ax, axis: str = "y", prefix: str = "", suffix: str = "") -> None:
    def _f(x, _):
        if abs(x) >= 1e6:
            return f"{prefix}{x / 1e6:.1f}M{suffix}"
        if abs(x) >= 1e3:
            return f"{prefix}{x / 1e3:.0f}K{suffix}"
        return f"{prefix}{x:.0f}{suffix}"

    getattr(ax, f"{axis}axis").set_major_formatter(ticker.FuncFormatter(_f))


def fmt_pct(ax, axis: str = "y", decimals: int = 0) -> None:
    getattr(ax, f"{axis}axis").set_major_formatter(ticker.PercentFormatter(1.0, decimals=decimals))


def save(fig, name: str) -> Path:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / f"{name}.png"
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path
