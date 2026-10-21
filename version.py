"""Single source of truth for the project version."""

from pathlib import Path

__version__ = Path(__file__).with_name('VERSION').read_text(encoding='utf-8').strip()
