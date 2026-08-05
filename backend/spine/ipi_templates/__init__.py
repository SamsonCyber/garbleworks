"""Document/carrier template bank for agentic IPI (v1: template strategy).

Five paste-ready shapes required for G3 acceptance:
  - tool_result envelope
  - CSV row/table
  - report/fill carrier
  - email body
  - file_content (read_file carrier)

Render functions take a CampaignObjective (or dict-like) and return document body.
"""
from __future__ import annotations

from spine.ipi_templates.registry import (
    TEMPLATE_IDS,
    get_template,
    list_templates,
    render_template,
)

__all__ = [
    "TEMPLATE_IDS",
    "get_template",
    "list_templates",
    "render_template",
]
