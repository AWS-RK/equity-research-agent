import json
from pathlib import Path

from agents.alpha_vantage import get_latest_quarterly_earnings
from agents.config import get_data_dir


def read_extracted_data(ticker: str, base_dir: str = "data") -> dict:
    extracted_path = Path(base_dir) / ticker.upper() / "extracted.json"
    if not extracted_path.exists():
        raise FileNotFoundError(
            f"No extracted.json found in {extracted_path.parent} -- run the extraction agent (M2) first."
        )
    return json.loads(extracted_path.read_text(encoding="utf-8"))


def read_eps_consensus(ticker: str, base_dir: str = "data") -> dict | None:
    data_dir = Path(base_dir) / ticker.upper()
    earnings_path = data_dir / f"{ticker.upper()}_earnings_alphavantage.json"
    if not earnings_path.exists():
        raise FileNotFoundError(
            f"No {earnings_path.name} found in {data_dir} -- run the retrieval agent (M1) first."
        )
    earnings_response = json.loads(earnings_path.read_text(encoding="utf-8"))
    return get_latest_quarterly_earnings(earnings_response)


def save_note(ticker: str, base_dir: str, markdown_text: str) -> Path:
    data_dir = get_data_dir(ticker, base_dir)
    note_path = data_dir / "note.md"
    note_path.write_text(markdown_text, encoding="utf-8")
    return note_path


def generate_trend_charts(ticker: str, base_dir: str, history: list[dict]) -> list[Path]:
    """Render trendline charts from a list of per-quarter dicts (each with
    quarter_label, revenue, non_gaap_operating_margin_pct, rpo_billions,
    rpo_yoy_growth_pct, eps_actual, eps_estimate) and save them as PNGs under
    data/{TICKER}/charts/. Returns the saved file paths.

    Revenue and margin data typically comes from SEC XBRL (agents/sec_xbrl.py,
    zero LLM cost); RPO and EPS typically come from press releases read
    directly by Claude and Alpha Vantage's saved history, respectively --
    this function only renders, it doesn't care where the numbers came from.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data_dir = get_data_dir(ticker, base_dir)
    charts_dir = data_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    labels = [q["quarter_label"] for q in history]
    paths = []

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(labels, [q["revenue"] for q in history], color="#2c5f8a")
    ax.set_title(f"{ticker.upper()} Quarterly Revenue ($M, GAAP)")
    ax.set_ylabel("Revenue ($M)")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    fig.tight_layout()
    path = charts_dir / "revenue_trend.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    paths.append(path)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(labels, [q["non_gaap_operating_margin_pct"] for q in history], marker="o", color="#2c5f8a")
    ax.set_title(f"{ticker.upper()} Non-GAAP Operating Margin")
    ax.set_ylabel("Margin (%)")
    ax.grid(True, alpha=0.3)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    fig.tight_layout()
    path = charts_dir / "margin_trend.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    paths.append(path)

    fig, ax1 = plt.subplots(figsize=(8, 4.5))
    ax1.bar(labels, [q["rpo_billions"] for q in history], color="#2c5f8a", alpha=0.85)
    ax1.set_ylabel("RPO ($B)")
    ax2 = ax1.twinx()
    ax2.plot(labels, [q["rpo_yoy_growth_pct"] for q in history], color="#c0392b", marker="o")
    ax2.set_ylabel("YoY growth (%)")
    ax1.set_title(f"{ticker.upper()} Remaining Performance Obligations")
    plt.setp(ax1.get_xticklabels(), rotation=45, ha="right")
    fig.tight_layout()
    path = charts_dir / "rpo_trend.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    paths.append(path)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = list(range(len(labels)))
    width = 0.35
    ax.bar([i - width / 2 for i in x], [q["eps_estimate"] for q in history], width, label="Street estimate", color="#999999")
    ax.bar([i + width / 2 for i in x], [q["eps_actual"] for q in history], width, label="Actual", color="#2c5f8a")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("EPS ($)")
    ax.set_title(f"{ticker.upper()} EPS: Actual vs. Street Estimate")
    ax.axhline(0, color="black", linewidth=0.6)
    ax.legend()
    fig.tight_layout()
    path = charts_dir / "eps_trend.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    paths.append(path)

    return paths
