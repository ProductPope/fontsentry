"""Typer CLI entry point.

This layer stays thin: argument parsing and wiring only. All business logic lives
in the crawl / detect / risk / registry / report packages. Commands are fleshed
out in later phases.
"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="fontsentry",
    help="Audit and monitor web fonts for license-violation risk.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def main() -> None:
    """FontSentry CLI."""


if __name__ == "__main__":
    app()
