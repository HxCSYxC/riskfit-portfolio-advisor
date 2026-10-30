"""Matplotlib charts shared by the Streamlit app, the PDF proposal and the README."""

import matplotlib

matplotlib.use("Agg")  # draw to files, no window needed
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from matplotlib.ticker import MultipleLocator, PercentFormatter

from riskfit.config import ASSET_LABELS
from riskfit.risk_profile.profiles import PROFILES
from riskfit.stress_test import metrics
from riskfit.stress_test.scenarios import SCENARIOS

# Colour palette. Each asset class always gets the same colour.
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#8a8984"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"
ASSET_COLOURS = {"equities": "#2a78d6", "bonds": "#eb6834", "cash": "#1baf7a", "gold": "#eda100"}
# Risk profiles are ordered, so they use one hue from light (Conservative) to dark (Aggressive).
PROFILE_COLOURS = {1: "#86b6ef", 2: "#5598e7", 3: "#2a78d6", 4: "#1c5cab", 5: "#104281"}
PROFILE_COLOURS_BY_NAME = {PROFILES[level].name: colour for level, colour in PROFILE_COLOURS.items()}
HIGHLIGHT = "#eb6834"   # used to shade the 2022 period


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



def plot_scenario_paths(asset_returns, portfolios, colours=None, figsize=(12, 4.2),
                        title="How each portfolio would have fared in past crises"):
    """One panel per crisis: value of 100 invested at the start, for each portfolio.

    portfolios: dict of name -> weights. Profile names get their profile colour;
    pass `colours` (name -> colour) for anything else.
    """
    colours = {**PROFILE_COLOURS_BY_NAME, **(colours or {})}
    fig, axes = plt.subplots(1, len(SCENARIOS), figsize=figsize, facecolor=SURFACE)
    for ax, scenario in zip(axes, SCENARIOS):
        _style_axes(ax)
        for name, weights in portfolios.items():
            port = metrics.portfolio_returns(asset_returns, weights).loc[scenario.start:scenario.end]
            wealth = metrics.wealth_index(port, start_value=100)
            ax.plot(wealth.index, wealth.values, color=colours.get(name, INK_MUTED), linewidth=2, label=name)
        ax.axhline(100, color=INK_MUTED, linewidth=1, linestyle="--")
        ax.set_title(scenario.name, loc="left", fontsize=10.5, color=INK, fontweight="bold")
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=5))
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
    axes[0].set_ylabel("Value of 100 invested", color=INK_SECONDARY, fontsize=10)
    handles, labels = axes[0].get_legend_handles_labels()
    # Leave a fixed space (in inches) at the top for the optional title and the legend,
    # so short and tall versions of the chart both lay out cleanly.
    height = figsize[1]
    title_space = 0.45 if title else 0.0
    if title:
        fig.suptitle(title, x=0.01, y=1 - 0.05 / height, va="top", ha="left", fontsize=13, color=INK,
                     fontweight="bold")
    fig.legend(handles, labels, loc="upper left", bbox_to_anchor=(0.01, 1 - title_space / height),
               ncol=len(labels), frameon=False, fontsize=9, labelcolor=INK_SECONDARY)
    fig.tight_layout()
    fig.subplots_adjust(top=1 - (title_space + 0.7) / height)
    return fig


def plot_rolling_correlation(correlation):
    """Rolling 3-year stock-bond correlation, with 2022 onwards shaded."""
    fig, ax = plt.subplots(figsize=(9, 4.2), facecolor=SURFACE)
    _style_axes(ax)
    ax.axvspan(pd.Timestamp("2022-01-01"), correlation.index[-1], color=HIGHLIGHT, alpha=0.10, linewidth=0)
    ax.axhline(0, color=INK_MUTED, linewidth=1)
    ax.plot(correlation.index, correlation.values, color=ASSET_COLOURS["equities"], linewidth=2)
    ax.annotate("2022: inflation shock.\nStocks and bonds fall together.",
                (pd.Timestamp("2022-03-01"), -0.55), fontsize=9, color=INK_SECONDARY)
    ax.text(0.01, 0.04, "Below 0: bonds tend to rise when stocks fall (good diversification)",
            transform=ax.transAxes, fontsize=9, color=INK_SECONDARY)
    ax.set_ylim(-0.8, 1.0)
    ax.set_ylabel("Correlation", color=INK_SECONDARY, fontsize=10)
    ax.set_title("Rolling 3-year correlation: US equities (SPY) vs investment-grade bonds (AGG)",
                 loc="left", fontsize=12, color=INK, fontweight="bold", pad=10)
    fig.tight_layout()
    return fig


def plot_allocation_donut(weights, centre_text=""):
    """Donut chart of the portfolio weights. Labels live in the table next to it, so none are drawn here."""
    shown = weights[weights >= 0.005]
    fig, ax = plt.subplots(figsize=(3, 3), facecolor="white")
    ax.pie(shown.values, colors=[ASSET_COLOURS[a] for a in shown.index], startangle=90, counterclock=False,
           wedgeprops={"width": 0.38, "edgecolor": "white", "linewidth": 2})
    ax.text(0, 0, centre_text, ha="center", va="center", fontsize=11, color=INK, fontweight="bold")
    ax.set_aspect("equal")
    fig.tight_layout(pad=0)
    return fig
