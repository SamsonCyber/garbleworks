"""Template registry for agentic IPI carriers."""
from __future__ import annotations

from typing import Any, Callable

from spine.ipi_templates import renderers

RenderFn = Callable[[Any], str]

# Five paste-ready shapes (G3 / gap-fill P0).
_REGISTRY: dict[str, dict[str, Any]] = {
    "tool_result_envelope": {
        "id": "tool_result_envelope",
        "surfaces": ["tool_result"],
        "detectability": "high",
        "dual_objective": True,
        "description": "Tool-return JSON envelope with pending_action + ACTION_REQUIRED",
        "render": renderers.render_tool_result_envelope,
        "marker": "[GARBLEWORKS_IPI_MARKER:tool_result]",
    },
    "csv_row": {
        "id": "csv_row",
        "surfaces": ["csv"],
        "detectability": "medium",
        "dual_objective": True,
        "description": "CSV feedback table with inject cell (firmware shred shape)",
        "render": renderers.render_csv_row,
        "marker": "[GARBLEWORKS_IPI_MARKER:csv]",
    },
    "report_fill": {
        "id": "report_fill",
        "surfaces": ["report_fill"],
        "detectability": "high",
        "dual_objective": True,
        "description": "Disease report fill carrier with CIP set_ph mapping",
        "render": renderers.render_report_fill,
        "marker": "[GARBLEWORKS_IPI_MARKER:report_fill]",
    },
    "email_body": {
        "id": "email_body",
        "surfaces": ["email"],
        "detectability": "high",
        "dual_objective": True,
        "description": "Forwarded email body with ACTION_REQUIRED CIP inject",
        "render": renderers.render_email_body,
        "marker": "[GARBLEWORKS_IPI_MARKER:email]",
    },
    "file_content": {
        "id": "file_content",
        "surfaces": ["file_content"],
        "detectability": "medium",
        "dual_objective": True,
        "description": "read_file / filesystem carrier with pending_action CIP",
        "render": renderers.render_file_content,
        "marker": "[GARBLEWORKS_IPI_MARKER:file_content]",
    },
    # Aliases (same shapes; extra ids for older kits)
    "garage_door_dual": {
        "id": "garage_door_dual",
        "surfaces": ["report_fill", "tool_result"],
        "detectability": "high",
        "dual_objective": True,
        "description": "Alias of report_fill (ACTION_REQUIRED + OUTPUT_AFTER_ACTION)",
        "render": renderers.render_report_fill,
        "marker": "[GARBLEWORKS_IPI_MARKER:report_fill]",
    },
    "csv_cell_garage": {
        "id": "csv_cell_garage",
        "surfaces": ["csv"],
        "detectability": "medium",
        "dual_objective": True,
        "description": "Alias of csv_row",
        "render": renderers.render_csv_row,
        "marker": "[GARBLEWORKS_IPI_MARKER:csv]",
    },
}

# Primary five required for G3 acceptance
TEMPLATE_IDS = (
    "tool_result_envelope",
    "csv_row",
    "report_fill",
    "email_body",
    "file_content",
)


def list_templates() -> list[dict[str, Any]]:
    out = []
    for tid, meta in _REGISTRY.items():
        out.append({
            "id": tid,
            "surfaces": list(meta.get("surfaces") or []),
            "detectability": meta.get("detectability"),
            "dual_objective": bool(meta.get("dual_objective")),
            "description": meta.get("description") or "",
            "marker": meta.get("marker") or "",
        })
    return out


def get_template(template_id: str) -> dict[str, Any]:
    key = (template_id or "").strip()
    if key not in _REGISTRY:
        raise KeyError(
            f"unknown IPI template {template_id!r}; "
            f"choose one of {sorted(_REGISTRY)}"
        )
    return dict(_REGISTRY[key])


def render_template(template_id: str, objective: Any) -> str:
    """Render a paste-ready carrier body for the given objective."""
    meta = get_template(template_id)
    fn: RenderFn = meta["render"]
    body = fn(objective)
    if not (body or "").strip():
        raise ValueError(f"template {template_id!r} rendered empty body")
    return body
