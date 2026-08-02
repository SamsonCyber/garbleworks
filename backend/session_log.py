"""Session durability for Garbleworks --auto (Wallbreaker-style polish).

Two artifacts per run:
  sessions/run-<ts>-<hex>.jsonl   one event per line (strategy, fire, leak, result)
  sessions/run-<ts>-<hex>.json    final summary (also mirrored as autosave.json)

Markdown report helper for CLI / H2H.

Secrets: never write full canary values into session files. Callers should pass
pre-scrubbed previews; finish() also redacts known secret if provided.
"""
from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _stamp() -> str:
    # Second precision alone collides under parallel H2H; append entropy.
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)


def redact_text(text: str, secret: str | None) -> str:
    if not text:
        return ""
    if secret and secret in text:
        return text.replace(secret, "[REDACTED_BY_HARNESS]")
    return text


def _redact_obj(obj: Any, secret: str | None) -> Any:
    """Deep-redact string leaves that contain the secret."""
    if not secret:
        return obj
    if isinstance(obj, str):
        return redact_text(obj, secret)
    if isinstance(obj, dict):
        return {k: _redact_obj(v, secret) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact_obj(v, secret) for v in obj]
    return obj


@dataclass
class Session:
    """Append-only JSONL + final summary JSON."""

    objective: str
    secret_fingerprint: str  # never store full secret
    session_dir: Path
    run_id: str = field(default_factory=_stamp)
    meta: dict[str, Any] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    t0: float = field(default_factory=time.time)
    _secret_for_redact: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.session_dir = Path(self.session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._jsonl = self.session_dir / f"run-{self.run_id}.jsonl"
        self._summary = self.session_dir / f"run-{self.run_id}.json"
        self._autosave = self.session_dir / "autosave.json"
        # Unique path: open exclusive create to fail loud on theoretical collision
        try:
            self._jsonl.touch(exist_ok=False)
        except FileExistsError:
            self.run_id = _stamp()
            self._jsonl = self.session_dir / f"run-{self.run_id}.jsonl"
            self._summary = self.session_dir / f"run-{self.run_id}.json"
            self._jsonl.touch(exist_ok=False)
        self.emit(
            "session_start",
            objective=self.objective,
            secret_fingerprint=self.secret_fingerprint,
            **self.meta,
        )

    @property
    def jsonl_path(self) -> Path:
        return self._jsonl

    @property
    def summary_path(self) -> Path:
        return self._summary

    def set_secret_for_redact(self, secret: str | None) -> None:
        """Optional: scrub this value from all future emit/finish payloads."""
        self._secret_for_redact = secret or None

    def emit(self, kind: str, **payload: Any) -> dict:
        payload = _redact_obj(payload, self._secret_for_redact)
        ev = {
            "ts": time.time(),
            "elapsed_s": round(time.time() - self.t0, 3),
            "kind": kind,
            **payload,
        }
        self.events.append(ev)
        with self._jsonl.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False, default=str) + "\n")
        return ev

    def finish(self, result: dict[str, Any]) -> dict:
        safe_result = _redact_obj(dict(result), self._secret_for_redact)
        summary = {
            "run_id": self.run_id,
            "objective": self.objective,
            "secret_fingerprint": self.secret_fingerprint,
            "meta": self.meta,
            "result": safe_result,
            "event_count": len(self.events),
            "wall_s": round(time.time() - self.t0, 3),
            "jsonl": str(self._jsonl),
        }
        self.emit("session_end", success=bool(result.get("success")), **{
            k: safe_result.get(k)
            for k in ("strategy", "queries", "channel", "queries_to_success")
            if k in safe_result
        })
        blob = json.dumps(summary, indent=2, ensure_ascii=False, default=str)
        self._summary.write_text(blob, encoding="utf-8")
        # Per-run autosave (no cross-run clobber) + latest pointer
        self._autosave.write_text(blob, encoding="utf-8")
        latest = self.session_dir / f"autosave-{self.run_id}.json"
        latest.write_text(blob, encoding="utf-8")
        return summary

    def markdown_report(self, result: dict[str, Any]) -> str:
        safe = _redact_obj(dict(result), self._secret_for_redact)
        ok = "WIN" if safe.get("success") else "MISS"
        lines = [
            f"# Garbleworks auto session `{self.run_id}`",
            "",
            f"- **outcome**: {ok}",
            f"- **objective**: {self.objective}",
            f"- **strategy**: {safe.get('strategy') or '-'}",
            f"- **queries**: {safe.get('queries', 0)}"
            + (
                f" (to success: {safe['queries_to_success']})"
                if safe.get("queries_to_success") is not None
                else ""
            ),
            f"- **channel**: {safe.get('channel') or '-'}",
            f"- **wall_s**: {safe.get('wall_s', round(time.time() - self.t0, 2))}",
            f"- **jsonl**: `{self._jsonl}`",
            "",
            "## Ladder",
            "",
        ]
        for step in safe.get("ladder") or []:
            mark = "Y" if step.get("success") else "."
            lines.append(
                f"- {mark} **{step.get('name')}** q={step.get('queries', 0)} "
                f"{step.get('note') or ''}".rstrip()
            )
        if safe.get("best_payload_preview"):
            lines += ["", "## Best payload (preview)", "", "```",
                      str(safe["best_payload_preview"])[:500], "```"]
        if safe.get("last_reply_preview"):
            lines += ["", "## Last reply (preview)", "", "```",
                      str(safe["last_reply_preview"])[:500], "```"]
        lines += ["", "## Event timeline", ""]
        for ev in self.events:
            if ev.get("kind") in ("session_start", "session_end"):
                continue
            lines.append(
                f"- `+{ev.get('elapsed_s')}s` **{ev.get('kind')}** "
                f"{ev.get('name') or ev.get('strategy') or ''}".rstrip()
            )
        return "\n".join(lines) + "\n"


def fingerprint_secret(secret: str) -> str:
    """Short non-reversible-enough label for logs (prefix/suffix only)."""
    s = secret or ""
    if len(s) <= 8:
        return f"len={len(s)}"
    # Prefer not to show long prefix of real canaries
    return f"len={len(s)} tail=…{s[-4:]}"


def default_session_dir() -> Path:
    return Path(__file__).resolve().parent / "sessions"


def load_session_summary(path: Path | str) -> dict[str, Any]:
    """Load a run-*.json summary (or autosave.json)."""
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"session summary is not an object: {p}")
    return data


def latest_session_summary(session_dir: Path | str | None = None) -> Path | None:
    """Newest run-*.json (not autosave-*) by mtime, else autosave.json."""
    d = Path(session_dir) if session_dir else default_session_dir()
    if not d.is_dir():
        return None
    runs = sorted(
        (p for p in d.glob("run-*.json") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if runs:
        return runs[0]
    auto = d / "autosave.json"
    return auto if auto.is_file() else None


def list_findings(
    session_dir: Path | str | None = None,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Recent successful sessions (Wallbreaker /findings analogue)."""
    d = Path(session_dir) if session_dir else default_session_dir()
    if not d.is_dir():
        return []
    out: list[dict[str, Any]] = []
    paths = sorted(
        (p for p in d.glob("run-*.json") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for p in paths:
        if len(out) >= max(1, limit):
            break
        try:
            data = load_session_summary(p)
        except Exception:
            continue
        res = data.get("result") or {}
        if not res.get("success"):
            continue
        out.append({
            "run_id": data.get("run_id") or p.stem,
            "objective": data.get("objective"),
            "strategy": res.get("strategy"),
            "queries": res.get("queries"),
            "queries_to_success": res.get("queries_to_success"),
            "channel": res.get("channel"),
            "wall_s": res.get("wall_s") or data.get("wall_s"),
            "path": str(p),
            "md": str(p.with_suffix(".md")) if p.with_suffix(".md").is_file() else None,
        })
    return out
