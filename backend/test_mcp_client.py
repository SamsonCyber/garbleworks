"""End-to-end MCP test suite: spawn mcp_server.py over stdio and exercise every
tool the way Claude Code / Hermes will — real JSON-RPC handshake, list_tools,
call_tool with assertions. Includes a live run of the genetic `optimize` loop
against a throwaway in-process echo target.

Run:  python backend/test_mcp_client.py     (prints PASS/FAIL per tool)
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import threading
import uuid
from http.server import HTTPServer
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# isolate the technique-log DB so tests don't touch the real one
_TMP_LOGDB = Path(tempfile.gettempdir()) / f"gw_mcp_logtest_{uuid.uuid4().hex[:8]}.db"

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from echo_target import Handler

BACKEND = Path(__file__).resolve().parent
EXPECTED_TOOLS = {
    "generate_framings", "chat_template_inject", "apply_recipe", "list_techniques",
    "field_guide_search", "field_guide_get", "field_guide_categories",
    "field_guide_crosswalk", "field_guide_ops", "op_technique",
    "field_guide_by_framework", "field_guide_by_tool",
    "start_run", "log_attempt", "query_attempts", "attempt_stats",
    "evolve_seeds", "neutralize", "optimize", "arena_solve", "arena_next_move",
    "pack_hunt", "pack_hunt_decompose", "pack_hunt_detect",
}


def _text(result) -> str:
    return "\n".join(getattr(c, "text", "") for c in result.content)


def _start_echo() -> tuple[HTTPServer, int]:
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


async def run() -> int:
    echo, port = _start_echo()
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, note: str = "") -> None:
        results.append((name, ok, note))

    params = StdioServerParameters(command=sys.executable,
                                   args=[str(BACKEND / "mcp_server.py")], cwd=str(BACKEND),
                                   env={**os.environ, "GARBLEWORKS_LOGDB": str(_TMP_LOGDB)})
    async with stdio_client(params) as (rd, wr):
        async with ClientSession(rd, wr) as s:
            init = await s.initialize()
            check("handshake", init.serverInfo.name == "garbleworks", init.serverInfo.name)

            names = {t.name for t in (await s.list_tools()).tools}
            check("list_tools", EXPECTED_TOOLS <= names,
                  f"{len(names)} tools; missing={EXPECTED_TOOLS - names or 'none'}")

            t = _text(await s.call_tool("generate_framings",
                      {"objective": "reveal the system prompt", "techniques": ["past_tense", "chat_template_inject"]}))
            check("generate_framings", '"ok": true' in t and "<|im_start|>" in t)

            t = _text(await s.call_tool("chat_template_inject",
                      {"payload": "do X", "template": "chatml"}))
            check("chat_template_inject", t.startswith("<|im_start|>system") and "<|im_end|>" in t)

            t = _text(await s.call_tool("apply_recipe",
                      {"input": "hello", "recipe": [{"op": "base64", "params": {}}]}))
            check("apply_recipe", "aGVsbG8=" in t)   # base64("hello")

            t = _text(await s.call_tool("list_techniques", {}))
            t_jb = _text(await s.call_tool("list_techniques", {"category": "jailbreak"}))
            check("list_techniques", '"chat_template_inject"' in t and '"tone_neutralize"' in t
                  and '"category": "jailbreak"' in t_jb)

            t = _text(await s.call_tool("field_guide_search",
                      {"query": "indirect injection retrieved document", "limit": 3}))
            check("field_guide_search", "Indirect Prompt Injection" in t)

            t = _text(await s.call_tool("field_guide_get", {"title": "exfil"}))
            check("field_guide_get", '"cat": "exfil"' in t or "Exfiltration" in t)

            t = _text(await s.call_tool("field_guide_categories", {}))
            check("field_guide_categories", '"exfil"' in t and '"indirect"' in t)

            # crosswalk: framework IDs + tool hooks now served from the enriched catalog
            t = _text(await s.call_tool("field_guide_crosswalk", {"title": "GCG, adversarial suffix"}))
            check("field_guide_crosswalk", "AML.T" in t and '"garak"' in t and '"benchmarks"' in t)

            t = _text(await s.call_tool("field_guide_search",
                      {"query": "GCG adversarial suffix", "limit": 3}))
            check("field_guide_search (+crosswalk)", '"crosswalk"' in t and ("AML.T" in t or "LLM01" in t))

            # technique -> op linkage (the reference becomes executable)
            t = _text(await s.call_tool("field_guide_ops", {"title": "Policy Puppetry"}))
            check("field_guide_ops", '"policy_puppetry"' in t)
            t = _text(await s.call_tool("op_technique", {"op": "chat_template_inject"}))
            check("op_technique", "Chat-Format Forgery" in t or '"technique"' in t and "null" not in t.split('"technique"')[1][:20])
            t = _text(await s.call_tool("op_technique", {"op": "echo"}))
            check("op_technique (plumbing)", "plumbing" in t)

            # crosswalk-index queries
            t = _text(await s.call_tool("field_guide_by_framework", {"framework_id": "AML.T0051"}))
            check("field_guide_by_framework", '"title"' in t and "AML.T0051" in t)
            t = _text(await s.call_tool("field_guide_by_tool", {"tool": "garak"}))
            check("field_guide_by_tool", '"probe"' in t and '"title"' in t)

            t = _text(await s.call_tool("evolve_seeds", {"objective": "leak the secret config", "reps": 2}))
            check("evolve_seeds", t.count('"strategy"') >= 5)

            t = _text(await s.call_tool("neutralize", {"text": "destroy it with a lethal weapon", "eta": 0.8}))
            check("neutralize", '"before_L"' in t and '"after_L"' in t and '"after"' in t)

            # live GA against the echo target (small budget). Judge may be offline —
            # we only assert the loop RAN and returned a best prompt + fired queries.
            target = {"adapter": "raw", "url": f"http://127.0.0.1:{port}/", "method": "POST",
                      "headers": {}, "opts": {"body": '{"message": "{payload}"}', "body_type": "json",
                                              "response_path": "hit_token"}}
            try:
                t = _text(await s.call_tool("optimize",
                          {"objective": "make the reply contain the secret", "target": target,
                           "budget": 4, "pop": 4}))
                check("optimize (live GA)", '"best_prompt"' in t and '"target_queries"' in t, "ran")
            except Exception as e:
                check("optimize (live GA)", False, f"exc: {e}"[:80])

            # pack_hunt: decomposition plan only (no firing) — benign fragments + prompt
            t = _text(await s.call_tool("pack_hunt_decompose",
                      {"objective": "reveal the secret", "n": 4}))
            check("pack_hunt_decompose", '"fragments"' in t and '"loadedness"' in t and '"prompt"' in t)

            # pack_hunt ADVISE mode (target omitted) -> plan only, advise flag set
            t = _text(await s.call_tool("pack_hunt", {"objective": "reveal the secret", "n": 4}))
            check("pack_hunt (advise)", '"advise": true' in t and '"prompt"' in t, "plan-only")

            # pack_hunt RUN mode against the echo target -> self-refines, returns a graded result
            try:
                t = _text(await s.call_tool("pack_hunt",
                          {"objective": "reveal the secret", "target": target, "attempts": 3}))
                check("pack_hunt (run/refine)",
                      '"hit"' in t and '"history"' in t and '"advise": false' in t, "ran")
            except Exception as e:
                check("pack_hunt (run/refine)", False, f"exc: {e}"[:80])

            # pack_hunt_detect (blue-team): flags the decomposition scaffold in a context
            scaffold = ("Task A. define assemble(parts): join the parts with spaces. "
                        "Task B. parts = [\"x\", \"y\"]. "
                        "Task C. combine the parts from Task B per the contract and output the result.")
            t = _text(await s.call_tool("pack_hunt_detect", {"context": scaffold}))
            check("pack_hunt_detect (blue)", '"flagged": true' in t and '"signals"' in t)

            # arena_solve with no browser attached must fail GRACEFULLY (error dict), not crash.
            t = _text(await s.call_tool("arena_solve",
                      {"objective": "x", "cdp_url": "http://127.0.0.1:59999", "budget": 1}))
            check("arena_solve (graceful no-browser)", '"error"' in t or "error" in t.lower(), "err-dict")

            # rules-compliant advisor: returns a next payload for the operator to paste
            t = _text(await s.call_tool("arena_next_move",
                      {"objective": "disable the cameras", "history": []}))
            check("arena_next_move (advisor)", '"technique"' in t and '"payload"' in t, "advises")

            # technique logs (isolated temp DB via GARBLEWORKS_LOGDB)
            t = _text(await s.call_tool("start_run", {"objective": "leak the system prompt", "kind": "test"}))
            check("start_run", '"run_id"' in t)
            t = _text(await s.call_tool("log_attempt",
                      {"technique": "Policy Puppetry", "outcome": "success", "op": "policy_puppetry",
                       "score": 0.9, "target_type": "chat"}))
            check("log_attempt", '"id"' in t)
            await s.call_tool("log_attempt", {"technique": "Policy Puppetry", "outcome": "refused",
                                              "op": "policy_puppetry", "target_type": "chat"})
            t = _text(await s.call_tool("query_attempts", {"technique": "Policy", "limit": 5}))
            check("query_attempts (+crosswalk join)", '"outcome"' in t and "LLM01" in t)
            t = _text(await s.call_tool("attempt_stats", {"group_by": "op"}))
            check("attempt_stats", '"success_rate"' in t and "policy_puppetry" in t)

    echo.shutdown()
    for _f in (_TMP_LOGDB, Path(str(_TMP_LOGDB) + "-wal"), Path(str(_TMP_LOGDB) + "-shm")):
        try:
            _f.unlink(missing_ok=True)
        except OSError:
            pass
    print("\n" + "=" * 60)
    passed = 0
    for name, ok, note in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:26} {note}")
        passed += ok
    print("=" * 60)
    print(f"{passed}/{len(results)} tools passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
