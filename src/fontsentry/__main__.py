"""Enable `python -m fontsentry`, used by scheduled tasks for a stable invocation."""

from fontsentry.cli import app

if __name__ == "__main__":
    app()
