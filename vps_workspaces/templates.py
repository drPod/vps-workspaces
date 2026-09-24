from __future__ import annotations

from pathlib import Path
from string import Template


def service_template(filename: str, **values: str) -> str:
    path = Path(__file__).resolve().parent.parent / "deploy/systemd" / filename
    return Template(path.read_text()).substitute(values)
