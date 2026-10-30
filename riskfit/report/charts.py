"""Matplotlib charts shared by the Streamlit app, the PDF proposal and the README."""

import matplotlib

matplotlib.use("Agg")  # draw to files, no window needed
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, PercentFormatter

from riskfit.config import ASSET_LABELS
from riskfit.risk_profile.profiles import PROFILES

# Colour palette. Each asset class always gets the same colour.
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#8a8984"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"
ASSET_COLOURS = {"equities": "#2a78d6", "bonds": "#eb6834", "cash": "#1baf7a", "gold": "#eda100"}
# Risk profiles are ordered, so they use one hue from light (Conservative) to dark (Aggressive).
PROFILE_COLOURS = {1: "#86b6ef", 2: "#5598e7", 3: "#2a78d6", 4: "#1c5cab", 5: "#104281"}


def _style_axes(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK_MUTED)
    ax.tick_params(colors=INK_SECONDARY, labelsize=9)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plot_efficient_frontier(frontier, portfolios, mu, cov):
    """Frontier line, the four single assets, and the five profile portfolios."""
    fig, ax = plt.subplots(figsize=(8, 5.2), facecolor=SURFACE)
    _style_axes(ax)

    ax.plot(frontier["volatility"], frontier["expected_return"], color=INK_SECONDARY, linewidth=2,
            label="Efficient frontier (long-only)", zorder=2)

    for asset in mu.index:
        ret, vol = mu[asset], float(cov.loc[asset, asset]) ** 0.5
        ax.scatter(vol, ret, s=60, color=INK_MUTED, edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.annotate(ASSET_LABELS[asset], (vol, ret), xytext=(7, -3), textcoords="offset points",
                    fontsize=8.5, color=INK_SECONDARY)

    for level, portfolio in portfolios.items():
        ax.scatter(portfolio.volatility, portfolio.expected_return, s=110, color=PROFILE_COLOURS[level],
                   edgecolor=SURFACE, linewidth=2, zorder=4)
        ax.annotate(PROFILES[level].name, (portfolio.volatility, portfolio.expected_return),
                    xytext=(-8, 8), textcoords="offset points", ha="right", fontsize=9, color=INK,
                    fontweight="bold")

    ax.xaxis.set_major_locator(MultipleLocator(0.02))
    ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=1))
    ax.set_xlabel("Expected volatility (annual)", color=INK_SECONDARY, fontsize=10)
    ax.set_ylabel("Expected return (annual)", color=INK_SECONDARY, fontsize=10)
    ax.set_xlim(0, max(frontier["volatility"].max(), cov.values.diagonal().max() ** 0.5) * 1.08)
    ax.set_title("Efficient frontier and the five RiskFit profiles", loc="left", fontsize=13,
                 color=INK, fontweight="bold", pad=22)
    ax.text(0, 1.02, "Each profile's weight limits (e.g. 5% minimum gold) cost under 0.1% a year "
            "versus the unconstrained frontier.", transform=ax.transAxes, fontsize=9,
            color=INK_SECONDARY)
    ax.legend(loc="lower right", frameon=False, fontsize=9, labelcolor=INK_SECONDARY)
    fig.tight_layout()
    return fig

