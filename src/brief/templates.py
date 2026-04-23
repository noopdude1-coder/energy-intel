"""Jinja2 environment and the daily brief template.

The template is kept inline (not a separate .j2 file) so the brief format lives
with the rendering code — fewer moving parts for Phase 1.
"""
from __future__ import annotations

from jinja2 import Environment

BRIEF_TEMPLATE = """\
# Energy Intel — {{ date_str }}

{% if macro.values %}**Spot:** WTI {{ fmt_price(macro.values.get("wti")) }} · Brent {{ fmt_price(macro.values.get("brent")) }} · HH {{ fmt_price(macro.values.get("hh_gas"), dp=2) }} · DXY {{ fmt_num(macro.values.get("dxy")) }} · 10Y {{ fmt_pct(macro.values.get("ten_year")) }}{% else %}**Spot:** ⚠️ macro source unavailable{% endif %}

{% if movers %}## Movers (>{{ mover_threshold }}%)

{% for m in movers %}- **{{ m.ticker }}** {{ fmt_signed_pct(m.one_day_pct) }} · last {{ fmt_price(m.last) }}
{% endfor %}{% else %}## Movers

No watchlist names moved more than {{ mover_threshold }}% on the day.
{% endif %}
## Position Status

{% if positions %}| Ticker | Shares | Last | Cost | P/L | P/L % | Stop | To Stop |
|---|---:|---:|---:|---:|---:|---:|---:|
{% for p in positions %}| {{ p.ticker }}{% if p.stop_warning %} ⚠️{% endif %} | {{ "%.0f"|format(p.shares) }} | {{ fmt_price(p.last) }} | {{ fmt_price(p.cost_basis) }} | {{ fmt_money(p.unrealized_pl) }} | {{ fmt_signed_pct(p.unrealized_pct) }} | {{ fmt_price(p.trailing_stop) }} | {{ fmt_signed_pct(p.stop_distance_pct) }} |
{% endfor %}{% else %}_No positions configured. Copy `config/positions.example.yml` to `config/positions.yml` to enable._
{% endif %}
## Peer Board

{% if peer_board_rows %}| Ticker | Last | 1D | 5D | YTD | 52w Range |
|---|---:|---:|---:|---:|---:|
{% for r in peer_board_rows %}| {{ r.ticker }} | {{ fmt_price(r.last) }} | {{ fmt_signed_pct(r.one_day_pct) }} | {{ fmt_signed_pct(r.five_day_pct) }} | {{ fmt_signed_pct(r.ytd_pct) }} | {{ fmt_range(r.range_52w_pct) }} |
{% endfor %}{% else %}⚠️ equities source unavailable
{% endif %}
## Fundamental Data

{% if eia_section %}{{ eia_section }}
{% else %}_Nothing fresh today._
{% endif %}{% if rig_count %}
**Rig count ({{ rig_count.as_of }}):** US {{ rig_count.total_us }} · Permian {{ rig_count.permian }}{% if rig_count.permian_wow is not none %} ({{ fmt_signed(rig_count.permian_wow) }} WoW){% endif %}

{% endif %}
## Signals

{% if signals %}{% for s in signals %}- **{{ s.name }}** — {{ s.detail }}
{% endfor %}{% else %}_None firing._
{% endif %}
---

_Generated {{ generated_at }} UTC. Phase 1 MVP._
"""


def _fmt_price(v, dp: int = 2) -> str:
    if v is None:
        return "—"
    try:
        return f"${float(v):,.{dp}f}"
    except (TypeError, ValueError):
        return "—"


def _fmt_money(v) -> str:
    if v is None:
        return "—"
    try:
        sign = "-" if v < 0 else ""
        return f"{sign}${abs(float(v)):,.0f}"
    except (TypeError, ValueError):
        return "—"


def _fmt_num(v) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _fmt_pct(v) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.2f}%"
    except (TypeError, ValueError):
        return "—"


def _fmt_signed_pct(v) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):+.2f}%"
    except (TypeError, ValueError):
        return "—"


def _fmt_signed(v) -> str:
    if v is None:
        return "—"
    try:
        return f"{int(v):+d}"
    except (TypeError, ValueError):
        return "—"


def _fmt_range(v) -> str:
    if v is None:
        return "—"
    try:
        pct = float(v) * 100.0
        return f"{pct:.0f}% of 52w"
    except (TypeError, ValueError):
        return "—"


def make_env() -> Environment:
    env = Environment(trim_blocks=False, lstrip_blocks=False)
    env.globals.update(
        fmt_price=_fmt_price,
        fmt_money=_fmt_money,
        fmt_num=_fmt_num,
        fmt_pct=_fmt_pct,
        fmt_signed_pct=_fmt_signed_pct,
        fmt_signed=_fmt_signed,
        fmt_range=_fmt_range,
    )
    return env
