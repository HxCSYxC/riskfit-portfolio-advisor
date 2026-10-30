"""One-page PDF client proposal, built with reportlab.

Usage:
    from riskfit.report.pdf import build_pdf
    build_pdf(proposal, "proposal.pdf")      # or a BytesIO buffer (used by the Streamlit download button)
"""

from io import BytesIO

from reportlab.graphics.shapes import Drawing, Rect
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from riskfit.config import ASSET_LABELS, ASSET_ORDER, ASSETS
from riskfit.proposal import explain_allocation, pct
from riskfit.report.charts import ASSET_COLOURS, plot_allocation_donut, plot_scenario_paths
from riskfit.stress_test.scenarios import format_recovery

INK = colors.HexColor("#0b0b0b")
INK_2 = colors.HexColor("#52514e")
LINE = colors.HexColor("#e4e3df")
TINT = colors.HexColor("#f3f2ef")
ACCENT_HEX = "#1c5cab"
ACCENT = colors.HexColor(ACCENT_HEX)

PAGE_W, PAGE_H = A4
MARGIN = 14 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

DISCLAIMER = (
    "<b>For illustration only. Not investment advice.</b> This proposal was produced by RiskFit, a student "
    "portfolio project, for a fictional client. It is not an offer or recommendation to buy or sell any "
    "security. Figures use historical ETF data as stand-ins for each asset class and ignore fees, taxes and "
    "currency effects (USD base; HKD is pegged to USD). Expected returns are assumptions, not promises. "
    "Past performance is not a reliable indicator of future results, and the value of investments can fall "
    "as well as rise."
)


def _style(name, size, leading, bold=False, colour=INK):
    return ParagraphStyle(name, fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size,
                          leading=leading, textColor=colour, alignment=TA_LEFT)


def _styles():
    return {
        "title": _style("title", 18, 22, bold=True),
        "sub": _style("sub", 8.5, 11, colour=INK_2),
        "h": _style("h", 10.5, 15, bold=True),
        "profile": _style("profile", 16, 19, bold=True, colour=ACCENT),
        "body": _style("body", 8.5, 11.2),
        "small": _style("small", 7.5, 9.5, colour=INK_2),
        "cell": _style("cell", 8, 10),
        "cell_b": _style("cell_b", 8, 10, bold=True),
        "tile_label": _style("tile_label", 7.5, 9.5, colour=INK_2),
        "tile_value": _style("tile_value", 14, 17, bold=True),
    }


def _usd(amount, round_to=1):
    """'USD 1,500,000'. Use round_to=1000 for estimates, so they don't look falsely precise."""
    amount = round(amount / round_to) * round_to
    sign = "-" if amount < 0 else ""
    return f"{sign}USD {abs(amount):,.0f}"


def _swatch(hex_colour, size=7):
    d = Drawing(size, size)
    d.add(Rect(0, 0, size, size, fillColor=colors.HexColor(hex_colour), strokeColor=None))
    return d


def _donut_image(weights, width):
    fig = plot_allocation_donut(weights)
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=250, transparent=True)
    buf.seek(0)
    return Image(buf, width=width, height=width)


def _profile_block(proposal, s):
    p, c = proposal.profile, proposal.client
    facts = [
        ("Investment amount", _usd(c.investment_amount)),
        ("Attitude to risk score", f"{p.tolerance_score} out of 25"),
        ("Investment horizon", p.horizon),
        ("Largest loss you can accept", p.max_loss),
        ("Cash needs (next 12 months)", p.liquidity.replace(" in the next 12 months", "")),
    ]
    rows = [[Paragraph(k, s["cell"]), Paragraph(f"<b>{v}</b>", s["cell"])] for k, v in facts]
    table = Table(rows, colWidths=[33 * mm, 40 * mm])
    table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    return [
        Paragraph("Your risk profile", s["h"]),
        Paragraph(p.profile.name, s["profile"]),
        Paragraph(f"Level {p.final_level} of 5. {p.profile.description}", s["small"]),
        Spacer(1, 5),
        table,
    ]


def _allocation_block(proposal, s):
    w = proposal.portfolio.weights
    amount = proposal.client.investment_amount
    rows = [[None, Paragraph("<b>Asset class</b>", s["cell"]), Paragraph("<b>Weight</b>", s["cell"]),
             Paragraph("<b>Amount</b>", s["cell"])]]
    for asset in ASSET_ORDER:
        rows.append([
            _swatch(ASSET_COLOURS[asset]),
            Paragraph(f"{ASSET_LABELS[asset]}<br/><font size=6.5 color='#52514e'>{ASSETS[asset]} ETF</font>",
                      s["cell"]),
            Paragraph(f"{w[asset]:.0%}", s["cell_b"]),
            Paragraph(_usd(w[asset] * amount, 1000), s["cell"]),
        ])
    table = Table(rows, colWidths=[4 * mm, 30 * mm, 12 * mm, 24 * mm])
    table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 1.5), ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    donut = _donut_image(w, 30 * mm)
    inner = Table([[donut, table]], colWidths=[33 * mm, 71 * mm])
    inner.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return [Paragraph("Recommended allocation", s["h"]), inner]


def _tiles(proposal, s):
    low, high = proposal.typical_range
    name, worst = proposal.worst
    loss_usd = -worst.max_drawdown * proposal.client.investment_amount
    tiles = [
        ("Expected return per year", f"{proposal.portfolio.expected_return:.1%}",
         "Long-term assumption, before fees"),
        ("Typical yearly range", f"{pct(low, signed=True)} to {pct(high, signed=True)}",
         "About 2 years in 3 should fall in this range"),
        ("Worst historical fall", f"{worst.max_drawdown:.0%}",
         f"{name}: about {_usd(loss_usd, 1000)} at the lowest point; "
         f"back to its previous peak in {format_recovery(worst.recovery_days)}"),
    ]
    cells = [[Paragraph(label, s["tile_label"]), Paragraph(value, s["tile_value"]), Paragraph(note, s["small"])]
             for label, value, note in tiles]
    table = Table([cells], colWidths=[CONTENT_W / 3] * 3)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), TINT),
        ("LINEAFTER", (0, 0), (1, 0), 3, colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return [Paragraph("What to expect", s["h"]), table]


def _stress_table(proposal, s):
    amount = proposal.client.investment_amount
    header = ["Crisis", "Period", "Return over the crisis", "Largest fall", "Largest fall in USD",
              "Time to recover"]
    rows = [[Paragraph(f"<b>{h}</b>", s["cell"]) for h in header]]
    for name, r in proposal.stress.iterrows():
        rows.append([
            Paragraph(name, s["cell"]),
            Paragraph(f"{r.start:%b %Y} – {r.end:%b %Y}", s["cell"]),
            Paragraph(f"{r.total_return:+.1%}", s["cell"]),
            Paragraph(f"<b>{r.max_drawdown:.1%}</b>", s["cell"]),
            Paragraph(_usd(r.max_drawdown * amount, 1000), s["cell"]),
            Paragraph(format_recovery(r.recovery_days), s["cell"]),
        ])
    table = Table(rows, colWidths=[44 * mm, 32 * mm, 26 * mm, 22 * mm, 30 * mm, CONTENT_W - 154 * mm])
    table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    return [
        Paragraph("How this portfolio would have done in past crises", s["h"]),
        table,
        Spacer(1, 2),
        Spacer(1, 4),
        _crisis_chart(proposal),
        Paragraph("Value of 100 invested at the start of each crisis. 2022 is a warning: inflation pushed shares "
                  "and bonds down together, so bonds gave little protection that year.", s["small"]),
    ]


def _crisis_chart(proposal):
    """This client's portfolio vs 100% shares through each crisis."""
    portfolios = {"Your portfolio": proposal.portfolio.weights, "100% shares (for comparison)": {"equities": 1.0}}
    fig = plot_scenario_paths(proposal.asset_returns, portfolios, figsize=(10, 2.4), title=None,
                              colours={"Your portfolio": ACCENT_HEX, "100% shares (for comparison)": "#b9b8b2"})
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=220, bbox_inches="tight", facecolor="white")
    buf.seek(0)
    px_w, px_h = ImageReader(buf).getSize()
    buf.seek(0)
    return Image(buf, width=CONTENT_W, height=CONTENT_W * px_h / px_w)


def build_pdf(proposal, output):
    """Write the one-page proposal to a file path or a binary buffer."""
    s = _styles()
    c = proposal.client
    doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=12 * mm,
                            bottomMargin=10 * mm, title=f"RiskFit proposal - {c.name}", author="RiskFit")

    top = Table([[_profile_block(proposal, s), _allocation_block(proposal, s)]],
                colWidths=[CONTENT_W - 106 * mm, 106 * mm])
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))

    data_note = (f"<br/>Data: daily total-return prices of {', '.join(ASSETS.values())} from "
                 f"{proposal.data_start:%d %b %Y} to {proposal.data_end:%d %b %Y} (Yahoo Finance). "
                 "Portfolios are rebalanced daily in the historical tests.")
    disclaimer = Table([[Paragraph(DISCLAIMER + data_note, s["small"])]], colWidths=[CONTENT_W])
    disclaimer.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.75, INK_2), ("LEFTPADDING", (0, 0), (-1, -1), 6),
                                    ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))

    story = [
        Paragraph("Portfolio Proposal", s["title"]),
        Paragraph(f"Prepared for <b>{c.name}</b> (fictional client), age {c.age}  ·  "
                  f"{proposal.created:%d %B %Y}  ·  RiskFit Private Wealth Proposal Engine", s["sub"]),
        Spacer(1, 4),
        Table([[""]], colWidths=[CONTENT_W], rowHeights=[1.2],
              style=[("BACKGROUND", (0, 0), (-1, -1), ACCENT)]),
        Spacer(1, 6),
        top,
        Spacer(1, 8),
        *_tiles(proposal, s),
        Spacer(1, 8),
        *_stress_table(proposal, s),
        Spacer(1, 8),
        Paragraph("Why this mix suits you", s["h"]),
        *[item for text in explain_allocation(proposal) for item in (Paragraph(text, s["body"]), Spacer(1, 3))],
        Spacer(1, 8),
        disclaimer,
    ]
    doc.build(story)
    return output
