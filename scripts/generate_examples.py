"""Generate the PDF proposal for every example client in examples/*.json.

    python scripts/generate_examples.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from riskfit.data.loader import load_prices  # noqa: E402
from riskfit.proposal import Client, build_proposal  # noqa: E402
from riskfit.report.pdf import build_pdf  # noqa: E402

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

if __name__ == "__main__":
    prices = load_prices()
    for path in sorted(EXAMPLES.glob("*.json")):
        proposal = build_proposal(Client.from_json(path), prices)
        output = path.with_suffix(".pdf")
        build_pdf(proposal, str(output))
        w = proposal.portfolio.weights
        print(f"{proposal.client.name:<18} {proposal.profile.profile.name:<24} "
              f"{'  '.join(f'{a} {w[a]:.0%}' for a in w.index)}  ->  {output.name}")
