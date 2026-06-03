"""Stage 6: Render the HTML demo script from the DemoScript using Jinja2."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import jinja2

from demo_gen.config import DemoConfig, DemoScript

# PackageLoader so the template is loaded from the installed package, not user input.
_env = jinja2.Environment(
    loader=jinja2.PackageLoader("demo_gen", "templates"),
    autoescape=True,          # All {{ vars }} are HTML-escaped; prevents SSTI
    undefined=jinja2.StrictUndefined,
)


def render(
    script: DemoScript,
    config: DemoConfig,
    tokens: dict[str, Any],
    screenshot_rel_paths: list[str],
    output_path: Path,
) -> Path:
    """Render HTML demo script. All AI-generated content is passed as variables, never as template source."""
    tmpl = _env.get_template("demo.html.j2")
    html = tmpl.render(
        product=config.product,
        feature=config.feature,
        tagline=tokens.get("tagline", ""),
        polish=config.polish.value,
        script=script,
        tok=tokens,
        screenshots=screenshot_rel_paths,
        year=datetime.date.today().year,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
