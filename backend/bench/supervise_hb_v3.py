"""Never-die supervisor for MiniMax full-v3 HarmBench.

Hard rules:
1. One supervisor only (exclusive lock held for process life).
2. One runner only (tracked via PID file + live process check).
3. Never kill a healthy runner. Restart only if process is dead or heartbeat
   is older than STALE_HEARTBEAT_S (default 30m). Checkpoint age alone is not
   enough: long ladders can go 10+ minutes between checkpoint writes.
4. After starting a runner, grace period before any kill/dedup.
5. Poll slowly so we never thrash mid-ladder.

  python bench/supervise_hb_v3.py --poll 90
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
_RESULTS = _BACKEND / "bench" / "results"
CKPT = _RESULTS / "harmbench-minimax-full-v3-checkpoint.json"
OUT = _RESULTS / "harmbench-minimax-full-v3.json"
RUNNER = _BACKEND / "harmbench_minimax_run.py"
LOCK = _RESULTS / "hb_v3_supervisor.lock"
RUNNER_PID = _RESULTS / "hb_v3_runner.pid"
HEARTBEAT = _RESULTS / "hb_v3_heartbeat"
LOG = _RESULTS / "hb_v3_supervisor.log"
RLOG = _RESULTS / "hb_v3_runner.log"

# Heartbeat must go stale this long before we declare hung and restart.
# Full ladder can be 10-16 fires x ~20-60s = up to ~15 min per behavior.
STALE_HEARTBEAT_S = 1800
# After we spawn, do not kill anything for this long.
START_GRACE_S = 120
POLL_S = 90

_lock_fp = None  # held open for exclusive lock
_last_start_mono = 0.0


def log(msg: str) -> None:
    line = time.strftime("%Y-%m-%dT%H:%M:%SZ ", time.gmtime()) + msg
    print(line, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_key() -> None:
    if not os.environ.get("MINIMAX_API_KEY"):
        p = Path.home() / ".secrets" / "minimax_api_key.txt"
        if p.is_file():
            os.environ["MINIMAX_API_KEY"] = p.read_text(encoding="utf-8").strip()
    os.environ.setdefault("GARBLEWORKS_TARGET_MAX_TOKENS", "2048")
    # Live sharpen + never skip plain baseline
    os.environ.setdefault("GARBLEWORKS_LIVE_SHARPEN", "1")
    os.environ.setdefault("GARBLEWORKS_SKIP_DEAD_RUNGS", "1")


def pid_alive(pid: int) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        r = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        o = (r.stdout or "").strip()
        return str(pid) in o and "No tasks" not in o
    except Exception:
        return False


def read_int_file(path: Path) -> int:
    try:
        if path.is_file():
            return int(path.read_text(encoding="utf-8").strip().split()[0])
    except Exception:
        pass
    return 0


def file_age_s(path: Path) -> float:
    if not path.is_file():
        return 1e9
    try:
        return time.time() - path.stat().st_mtime
    except Exception:
        return 1e9


def ckpt_n() -> int:
    if not CKPT.is_file():
        return 0
    try:
        import json

        d = json.loads(CKPT.read_text(encoding="utf-8"))
        return int(d.get("n_done") or len(d.get("results_by_id") or {}))
    except Exception:
        return 0


def list_full_v3_runners() -> list[int]:
    """All python PIDs whose cmdline is the full-v3 minimax battery (not category slice)."""
    ps = r"""
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ForEach-Object {
  $c = $_.CommandLine
  if ($c -and ($c -match 'harmbench_minimax_run') -and ($c -match 'full-v3') -and ($c -notmatch 'supervise_hb_v3') -and ($c -notmatch '--category')) {
    $_.ProcessId
  }
}
"""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=60,
        )
        out = []
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if line.isdigit():
                out.append(int(line))
        return sorted(set(out))
    except Exception as e:
        log(f"list_fail {e}")
        return []


def kill(pid: int, reason: str = "") -> None:
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/F"],
        capture_output=True,
        timeout=20,
    )
    log(f"killed {pid}" + (f" ({reason})" if reason else ""))


def tracked_runner() -> tuple[int | None, str]:
    """Return (alive_pid, status). Prefer PID file; fall back to process scan."""
    pid = read_int_file(RUNNER_PID)
    if pid and pid_alive(pid):
        return pid, "pidfile"
    pids = list_full_v3_runners()
    if len(pids) == 1:
        # Adopt orphan sole runner
        try:
            RUNNER_PID.write_text(str(pids[0]), encoding="utf-8")
        except Exception:
            pass
        return pids[0], "adopted"
    if len(pids) > 1:
        return None, f"multi:{pids}"
    return None, "none"


def heartbeat_fresh(max_age: float = STALE_HEARTBEAT_S) -> bool:
    # Heartbeat or runner log activity counts as life.
    ages = [file_age_s(HEARTBEAT), file_age_s(RLOG), file_age_s(CKPT)]
    return min(ages) < max_age


def start_runner() -> int | None:
    global _last_start_mono
    load_key()
    env = os.environ.copy()
    env.setdefault("GARBLEWORKS_TARGET_MAX_TOKENS", "2048")
    env.setdefault("GARBLEWORKS_LIVE_SHARPEN", "1")
    env.setdefault("GARBLEWORKS_SKIP_DEAD_RUNGS", "1")
    # Point runner at known paths for heartbeat/pid
    env["GARBLEWORKS_HB_RUNNER_PID"] = str(RUNNER_PID)
    env["GARBLEWORKS_HB_HEARTBEAT"] = str(HEARTBEAT)

    cmd = [
        sys.executable,
        "-u",
        str(RUNNER),
        "--full",
        "--timeout",
        "100",
        "--out",
        str(OUT),
        "--checkpoint",
        str(CKPT),
    ]
    RLOG.parent.mkdir(parents=True, exist_ok=True)
    # Windows agent shells often run inside a Job Object: if the parent shell dies
    # or is killed, *all* children die unless we break away from the job.
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    DETACHED_PROCESS = 0x00000008
    CREATE_NO_WINDOW = 0x08000000
    flags = 0
    if sys.platform == "win32":
        # BREAKAWAY_FROM_JOB needs SeTcbPrivilege (Access Denied on this host).
        flags = CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS | CREATE_NO_WINDOW

    log("start " + " ".join(cmd))
    # Prefer WMI Create so the runner is not a job descendant of the agent shell.
    if sys.platform == "win32":
        try:
            import subprocess as _sp

            # Build a cmd.exe one-liner that appends stdout/stderr to RLOG and
            # is launched via WMI (outside current Job Object).
            py = cmd[0]
            args = " ".join(f'"{c}"' if " " in c else c for c in cmd[1:])
            # Environment for child: write a tiny env-bootstrap .cmd
            env_cmd = _RESULTS / "hb_v3_runner_env.cmd"
            key = env.get("MINIMAX_API_KEY", "")
            env_cmd.write_text(
                "\r\n".join(
                    [
                        "@echo off",
                        f'set "MINIMAX_API_KEY={key}"',
                        'set "GARBLEWORKS_LIVE_SHARPEN=1"',
                        'set "GARBLEWORKS_SKIP_DEAD_RUNGS=1"',
                        'set "GARBLEWORKS_REQUEUE_HELD=1"',
                        'set "GARBLEWORKS_TARGET_MAX_TOKENS=2048"',
                        'set "PYTHONUNBUFFERED=1"',
                        'set "PYTHONIOENCODING=utf-8"',
                        f'set "GARBLEWORKS_HB_RUNNER_PID={RUNNER_PID}"',
                        f'set "GARBLEWORKS_HB_HEARTBEAT={HEARTBEAT}"',
                        f'cd /d "{_BACKEND}"',
                        f'echo.>> "{RLOG}"',
                        f'echo --- wmi spawn %DATE% %TIME% --->> "{RLOG}"',
                        f'"{py}" -u {args} >> "{RLOG}" 2>&1',
                        f'echo exit=%ERRORLEVEL% %DATE% %TIME%>> "{RLOG}"',
                    ]
                )
                + "\r\n",
                encoding="utf-8",
            )
            # Win32_Process.Create via PowerShell (reliable outside job)
            ps = (
                f"$p = Start-Process -FilePath 'cmd.exe' "
                f"-ArgumentList '/c \"\"{env_cmd}\"\"' "
                f"-WorkingDirectory '{_BACKEND}' "
                f"-WindowStyle Hidden -PassThru; "
                f"Write-Output $p.Id"
            )
            # Try breakaway via .NET ProcessStartInfo if available
            ps2 = r"""
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = 'cmd.exe'
$psi.Arguments = '/c ""{env}""'
$psi.WorkingDirectory = '{cwd}'
$psi.UseShellExecute = $true
$psi.CreateNoWindow = $true
$psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$p = [System.Diagnostics.Process]::Start($psi)
Write-Output $p.Id
""".replace("{env}", str(env_cmd)).replace("{cwd}", str(_BACKEND))
            r = _sp.run(
                ["powershell", "-NoProfile", "-Command", ps2],
                capture_output=True,
                text=True,
                timeout=30,
            )
            pid_s = (r.stdout or "").strip().splitlines()
            pid = int(pid_s[-1]) if pid_s and pid_s[-1].isdigit() else 0
            if not pid:
                # Fallback: plain Start-Process
                r = _sp.run(
                    ["powershell", "-NoProfile", "-Command", ps],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                pid_s = (r.stdout or "").strip().splitlines()
                pid = int(pid_s[-1]) if pid_s and pid_s[-1].isdigit() else 0
            if pid:
                _last_start_mono = time.monotonic()
                try:
                    RUNNER_PID.write_text(str(pid), encoding="utf-8")
                    HEARTBEAT.write_text(
                        f"{time.strftime('%Y-%m-%dT%H:%M:%SZ')} spawn pid={pid}\n",
                        encoding="utf-8",
                    )
                except Exception as e:
                    log(f"pidfile_write_fail {e}")
                log(f"started pid={pid} via=process_start")
                return pid
            log(f"spawn_ps_fail stdout={r.stdout!r} stderr={r.stderr!r}")
        except Exception as e:
            log(f"spawn_breakaway_fail {type(e).__name__}: {e}")

    # Fallback: subprocess (may still die with agent job object)
    logf = open(RLOG, "a", encoding="utf-8")
    logf.write(f"\n--- supervisor spawn {time.strftime('%Y-%m-%dT%H:%M:%SZ')} ---\n")
    logf.flush()
    try:
        p = subprocess.Popen(
            cmd,
            cwd=str(_BACKEND),
            env=env,
            stdout=logf,
            stderr=subprocess.STDOUT,
            creationflags=flags if sys.platform == "win32" else 0,
            close_fds=False,
        )
    except Exception as e:
        log(f"spawn_fail {e}")
        try:
            logf.close()
        except Exception:
            pass
        return None

    _last_start_mono = time.monotonic()
    try:
        RUNNER_PID.write_text(str(p.pid), encoding="utf-8")
        HEARTBEAT.write_text(
            f"{time.strftime('%Y-%m-%dT%H:%M:%SZ')} spawn pid={p.pid}\n",
            encoding="utf-8",
        )
    except Exception as e:
        log(f"pidfile_write_fail {e}")
    log(f"started pid={p.pid} via=popen")
    return p.pid


def acquire_lock() -> bool:
    """Exclusive supervisor lock. Hold file handle open for process life."""
    global _lock_fp
    me = os.getpid()
    LOCK.parent.mkdir(parents=True, exist_ok=True)

    # Stale lock takeover if owner dead
    if LOCK.is_file():
        try:
            old = int(LOCK.read_text(encoding="utf-8").strip().split()[0])
        except Exception:
            old = 0
        if old and old != me and pid_alive(old):
            log(f"other supervisor alive pid={old} — exit")
            return False

    try:
        # Open RW create; exclusive byte lock on Windows
        _lock_fp = open(LOCK, "a+", encoding="utf-8")
        if sys.platform == "win32":
            import msvcrt

            try:
                _lock_fp.seek(0)
                msvcrt.locking(_lock_fp.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                log("lock busy (msvcrt) — exit")
                _lock_fp.close()
                _lock_fp = None
                return False
        _lock_fp.seek(0)
        _lock_fp.truncate()
        _lock_fp.write(str(me))
        _lock_fp.flush()
    except Exception as e:
        log(f"lock_fail {e}")
        return False

    # Double-check: re-read after short pause (race with twin)
    time.sleep(0.5)
    try:
        if LOCK.read_text(encoding="utf-8").strip().split()[0] != str(me):
            log("lost lock race — exit")
            return False
    except Exception:
        pass
    return True


def release_lock() -> None:
    global _lock_fp
    try:
        if _lock_fp is not None:
            if sys.platform == "win32":
                try:
                    import msvcrt

                    _lock_fp.seek(0)
                    msvcrt.locking(_lock_fp.fileno(), msvcrt.LK_UNLCK, 1)
                except Exception:
                    pass
            _lock_fp.close()
            _lock_fp = None
        if LOCK.is_file() and LOCK.read_text(encoding="utf-8").strip().split()[0] == str(
            os.getpid()
        ):
            LOCK.unlink(missing_ok=True)  # type: ignore[call-arg]
    except Exception:
        pass


def in_grace() -> bool:
    return (time.monotonic() - _last_start_mono) < START_GRACE_S


def tick() -> str:
    n = ckpt_n()
    if n >= 300 and OUT.is_file():
        return f"COMPLETE {n}"

    pid, how = tracked_runner()
    pids = list_full_v3_runners()

    # Multiple runners: keep the tracked one (or newest), kill rest — never during grace
    if len(pids) > 1:
        if in_grace():
            return f"GRACE multi={pids} n={n} keep_hands_off"
        keep = pid if (pid and pid in pids) else max(pids)
        for p in pids:
            if p != keep:
                kill(p, "dedup")
        try:
            RUNNER_PID.write_text(str(keep), encoding="utf-8")
        except Exception:
            pass
        return f"DEDUP keep={keep} n={n}"

    if pid and pid_alive(pid):
        # Healthy process. Only restart if heartbeat truly dead.
        if heartbeat_fresh():
            hb_age = min(file_age_s(HEARTBEAT), file_age_s(RLOG), file_age_s(CKPT))
            return f"OK n={n}/300 pid={pid} via={how} life={hb_age:.0f}s"
        if in_grace():
            return f"GRACE no_hb yet pid={pid} n={n}"
        # Hung: process alive but silent for STALE_HEARTBEAT_S
        kill(pid, "stale_heartbeat")
        time.sleep(2)
        # Clear pid file so we do not re-adopt a zombie
        try:
            if RUNNER_PID.is_file():
                RUNNER_PID.unlink()
        except Exception:
            pass
        new = start_runner()
        return f"UNHUNG was={pid} n={n} new={new}"

    # No live runner
    expect = read_int_file(RUNNER_PID)
    if in_grace() and expect and pid_alive(expect):
        # Just started; process scan lag only while the PID is actually alive
        return f"GRACE wait_spawn n={n} expect={expect}"
    if expect and not pid_alive(expect):
        # Corpse PID file: clear so we do not sit in grace forever after a crash
        try:
            RUNNER_PID.unlink(missing_ok=True)  # type: ignore[call-arg]
        except Exception:
            try:
                RUNNER_PID.unlink()
            except Exception:
                pass
        log(f"cleared_dead_pidfile was={expect}")

    # Kill any stray full-v3 that is not ours (should be none)
    for p in pids:
        kill(p, "stray_before_start")
    new = start_runner()
    time.sleep(5)
    pids2 = list_full_v3_runners()
    return f"START n={n} new={new} seen={pids2}"


def main() -> int:
    global STALE_HEARTBEAT_S
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--poll", type=float, default=POLL_S)
    ap.add_argument(
        "--stale",
        type=float,
        default=STALE_HEARTBEAT_S,
        help="seconds without heartbeat before restart",
    )
    args = ap.parse_args()
    STALE_HEARTBEAT_S = float(args.stale)

    if not acquire_lock():
        return 0
    log(
        f"supervisor_start pid={os.getpid()} poll={args.poll} "
        f"stale_hb={STALE_HEARTBEAT_S}s grace={START_GRACE_S}s"
    )
    try:
        while True:
            try:
                log(tick())
            except Exception as e:
                log(f"err {type(e).__name__}: {e}")
            if args.once:
                return 0
            time.sleep(max(45.0, float(args.poll)))
    except KeyboardInterrupt:
        return 130
    finally:
        release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
