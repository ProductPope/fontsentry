"""Render a RunReport to a self-contained HTML dashboard via Jinja2.

Kept modular so an alternative sink (a sync plugin) could be added later without
touching this writer. Autoescaping is on — font name-table strings are untrusted.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from fontsentry.models import RunReport

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_html(report: RunReport) -> str:
    template = _environment().get_template("report.html.j2")
    return template.render(report=report)


def write_html(report: RunReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(report), encoding="utf-8")
    return path
